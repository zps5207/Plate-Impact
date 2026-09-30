"""Generate T5 (native *Embedded Element onto a *User Element host) into
verification/roar/t5/.

This directly tests the open question flagged before any VUEL host toggle is
built into the mesher/GUI: is Abaqus's native `*Embedded Element` constraint
-- which is what embmesh.writers always uses -- actually honored when the
host is a `*User Element` (uel/VUEL.for) instead of a native continuum
element? This has never been tried in this project: make_t4.py's
vuel_fiber_smoke deliberately avoided `*Embedded Element` for its VUEL host
(coupling fiber nodes to host nodes via literally shared corner DOFs
instead), specifically because the embedding algorithm is documented for
standard continuum/shell/etc. hosts, not user elements -- so that test does
not exercise Abaqus's host point-location search at all.

This one does. Unlike make_t4's 1-element/4-fiber case (whose fiber nodes
sit exactly on host corner nodes -- a degenerate case with no geometric
search needed), this uses the mesher's *own*, now-fixed CLI output on a
genuine multi-element (2x2x2) host, so fiber node coordinates are real
floating-point interior points, several of them at mid-depth, non-corner,
non-boundary-skin host elements -- the actual case Abaqus's host search has
to resolve. `c3d8_host` is the (already-validated) native-host control;
`vuel_host` is byte-identical except the host element block is swapped for
the *User Element/*UEL Property equivalent, so exactly one variable changes.

The answer to "does *Embedded Element work on a VUEL host" decides how (or
whether) a VUEL toggle can be added to the mesher: if this fails the same
way make_t4 anticipated, the toggle needs the node-snapped coupling
alternative instead; if it succeeds, the toggle can reuse the mesher's
existing embedding path unchanged.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import run_cli, hex_plate_deck
from verification.deckgen import materials, step_block

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t5"
OUT.mkdir(parents=True, exist_ok=True)
MESH = OUT / "_mesher_out"
MESH.mkdir(exist_ok=True)

HOST = dict(E=200.0e9, nu=0.3, rho=7800.0, beta_rayleigh=0.0, b1=0.06, b2=1.2)  # SI: Pa, kg/m^3, m
FIBER_E, FIBER_nu, FIBER_RHO = 100.0e9, 0.2, 1800.0
T = 1.0e-3  # step time, s -- short; this test's point is the pre-processing host-search check, not mechanics


def build_source():
    """2x2x2 unit-metre cube host, native C3D8R, elset=HOST -- gives the
    mesher a genuinely multi-element host to embed fibers into (not the
    single-element degenerate case make_t4 used)."""
    p = OUT / "host_src.inp"
    n0, e0 = hex_plate_deck(
        p, 2, 2, 2, 1.0, 1.0, 1.0, etype="C3D8R", elset="HOST",
        extra_part=f"*Solid Section, elset=HOST, material=MATRIX\n,",
    )
    left = sorted(k for k, c in n0.items() if abs(c[0]) < 1e-9)
    right = sorted(k for k, c in n0.items() if abs(c[0] - 1) < 1e-9)
    origin = min(n0, key=lambda k: sum(n0[k]))
    alln = sorted(n0)
    asm = (f"*Nset, nset=LEFT, instance=PLATE-1\n{', '.join(map(str, left))}\n"
           f"*Nset, nset=RIGHT, instance=PLATE-1\n{', '.join(map(str, right))}\n"
           f"*Nset, nset=ORIGIN, instance=PLATE-1\n{origin}\n"
           f"*Nset, nset=ALLN, instance=PLATE-1\n{', '.join(map(str, alln))}")
    hex_plate_deck(
        p, 2, 2, 2, 1.0, 1.0, 1.0, etype="C3D8R", elset="HOST",
        extra_part=f"*Solid Section, elset=HOST, material=MATRIX\n,", extra_asm=asm,
    )
    return p


def run_mesher(src):
    """Mesh through the real CLI -- exercises the mesher's own (now-fixed)
    EMBMESH_HOST elset + *Embedded Element writing unchanged, on a
    deliberately coarse diameter so only a handful of fibers are produced
    (keeps the deck small; this test needs a few genuinely multi-element,
    non-corner embedded nodes, not a dense layup)."""
    rc, o, e = run_cli(["visualize", str(src), "--instance", "PLATE-1", "--diameter", "0.2",
                         "--gap", "0.05", "--fiber-type", "truss", "--output", str(MESH),
                         "--fiber-material", "FIBER"])
    if rc != 0:
        raise RuntimeError(f"mesher failed rc={rc}: {(e.strip().splitlines() or [''])[-1]}")
    return (MESH / "output.inp").read_text()


def to_vuel_host(text):
    """Swap the native host element block (*Element type=C3D8R + its
    *Solid Section + its *Material) for the *User Element/*UEL Property
    equivalent (uel/VUEL.for), keeping every fiber/embedding line --
    including EMBMESH_HOST's element-label list and *Embedded Element
    itself -- byte-identical. Isolates host formulation as the only
    variable between the two decks."""
    lines = text.splitlines()

    # 1) *Element, type=C3D8R, elset=HOST ... up to (not including) the next '*'
    i_elem = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*element, type=c3d8r"))
    j = i_elem + 1
    while j < len(lines) and not lines[j].lstrip().startswith("*"):
        j += 1
    elem_data = lines[i_elem + 1:j]  # "<label>, n1, n2, ..., n8" lines, unchanged

    # 2) *Solid Section, elset=HOST, material=MATRIX + its data line
    i_sec = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*solid section") and "elset=host" in l.lower())
    k = i_sec + 1
    while k < len(lines) and not lines[k].lstrip().startswith("*"):
        k += 1

    uel_block = [
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=6, variables=48",
        "1, 2, 3",
        "*Element, type=VU1, elset=HOST",
    ] + elem_data + [
        "*UEL Property, elset=HOST",
        f"{HOST['E']:.6g}, {HOST['nu']:.6g}, {HOST['rho']:.6g}, {HOST['beta_rayleigh']:.6g}, {HOST['b1']:.6g}, {HOST['b2']:.6g}",
    ]
    new_lines = lines[:i_elem] + uel_block + lines[k:]

    # 3) drop the now-unused MATRIX *Material block (VUEL takes props via *UEL Property, not *Material)
    text2 = "\n".join(new_lines)
    text2 = re.sub(r"\*Material, name=MATRIX\n(?:(?!\*Material|\*Step|\*End).*\n)*", "", text2)
    return text2


def build_user_subroutine():
    vuel = (ROOT / "uel" / "VUEL.for").read_text()
    header = ("C     Job-specific copy of uel/VUEL.for for the T5 embedding smoke test\n"
              "C     (verification/make_t5_uel_embed.py). No VUMAT needed here -- fibers\n"
              "C     use a plain *Elastic material; this test isolates the host-formulation\n"
              "C     / embedded-element question only.\n")
    return header + vuel


def main():
    src = build_source()
    mesher_out = run_mesher(src)

    tail_mat = "\n".join(materials("FIBER", True, vumat=False))
    bcs = ["*Boundary", "LEFT, 1, 1", "ORIGIN, 2, 3", "*Boundary, amplitude=RAMP", "RIGHT, 1, 1, 0.01"]
    tail_step = "\n".join(step_block(bcs, T=T, print_nset="RIGHT"))

    c3d8_deck = mesher_out + "\n" + tail_mat + "\n" + tail_step + "\n"
    (OUT / "c3d8_host.inp").write_text(c3d8_deck)
    print("wrote", OUT / "c3d8_host.inp")

    vuel_mesher_out = to_vuel_host(mesher_out)
    vuel_deck = vuel_mesher_out + "\n" + tail_mat + "\n" + tail_step + "\n"
    (OUT / "vuel_host.inp").write_text(vuel_deck)
    print("wrote", OUT / "vuel_host.inp")

    user_path = OUT / "vuel_host_user.for"
    user_path.write_text(build_user_subroutine())
    print("wrote", user_path)

    print("\nc3d8_host.inp is the control (native host, same fibers/embedding).")
    print("vuel_host.inp is the test (VUEL host, byte-identical fibers/embedding).")
    print("Submit both to Abaqus 2024 on ROAR; compare datacheck/run results.")


if __name__ == "__main__":
    main()
