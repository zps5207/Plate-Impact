"""Build the plywise plate-impact decks from Valerie's Meshing/Vals.inp (Stage 8 comparison).

Plate: 20 plies (one hex thick each) from the 9-layer plate, one fiber layer per ply (d = 0.632 mm,
cross-ply 0/90), Hazzard-style cohesive interfaces with the numbers supplied for this study,
node-based ball contact. Two decks:
  native   Matrix as native C3D8R (Valerie's material) with embedded fibers
  vuel     VU1 + ghost host, --matrix-model ductile-damage (VUEL_material.for, MAT_MODEL = 1)
Everything else (ball -1000 m/s, symmetry BCs, 7e-5 s step, outputs) is taken from Vals.inp unchanged.

Usage: python verification/roar/build_vals_plywise.py [out_dir]
       python verification/roar/build_vals_plywise.py --element-deletion <built_dir> <out_dir>
The second form copies the already built native/ and vuel/ decks into out_dir with element deletion on for every
element type (fiber T3D2, steel ball, native matrix); it does not re-run the mesher.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALS = ROOT / "Meshing" / "Vals.inp"
DELETE_MODE = len(sys.argv) > 1 and sys.argv[1] == "--element-deletion"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 and not DELETE_MODE else ROOT / "Meshing" / "vals-plywise"

PLIES = 20
FIBER_D = 0.632e-3
FIBER_GAP = 0.0
LAYUP = ",".join(["0", "90"] * (PLIES // 2))

# cohesive numbers as supplied (SI): N/mm^3 -> Pa/m x1e9, MPa -> Pa, N/mm -> J/m^2 x1e3
COHESIVE = ["** cohesive interface: Mode I / II strength 1.2 / 1.8 MPa, stiffness 60 / 36 N/mm^3, Gc 0.544 / 1.088 N/mm",
            "*Cohesive Behavior", " 6e+10, 3.6e+10, 3.6e+10",
            "*Damage Initiation, criterion=MAXS", " 1.2e+06, 1.8e+06, 1.8e+06",
            "*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1",
            " 544, 1088, 1088"]

EPSF = 0.1              # matrix damage-onset strain per the brief (Vals.inp has 0.01)


def with_static_fiber_curve(text):
    """Abaqus wants the static (rate-less) yield curve first; Vals.inp starts the fiber table at rate=0.01.
    The 0.01 /s curve becomes the static one, the 1 and 1000 /s curves are unchanged."""
    old = "*Plastic, rate=0.01\n 3.5e+09,0."
    assert old in text
    return text.replace(old, "** Vals.inp had rate=0.01 here; Abaqus needs the static curve first\n*Plastic\n 3.5e+09,0.", 1)


def with_cohesive(text):
    marker = "*Surface Behavior, pressure-overclosure=HARD\n"
    assert marker in text
    block = "*Surface Interaction, name=Cohesion\n" + "\n".join(COHESIVE) + "\n"
    return text.replace(marker, marker + "** \n" + block, 1)


def with_element_deletion(text):
    """Turn element deletion on for every element type of a built deck.

    The fiber (T3D2) and ball (Johnson-Cook) materials only had a damage-initiation card, which never deletes in
    Abaqus/Explicit; add an instantaneous displacement-type evolution (as the VUEL ghost material uses) and attach
    a deletion Section Controls to each Solid Section that has none (ghost hosts keep EMBMESH_GHOST_CONTROLS)."""
    fiber = re.compile(r"(\*Material, name=Fiber\n\*Damage Initiation, criterion=DUCTILE\n(?: [^\n]*\n)+)")
    steel = re.compile(r'(\*Material, name="Mild Steel"\n\*Damage Initiation, criterion=JOHNSON COOK\n[^\n]*\n)')
    evolution = "*Damage Evolution, type=DISPLACEMENT\n0.\n"
    for pattern in (fiber, steel):
        assert len(pattern.findall(text)) == 1, pattern.pattern
        text = pattern.sub(lambda m: m.group(1) + evolution, text, count=1)
    marker = "*Material, name=Fiber\n"
    assert text.count(marker) == 1
    text = text.replace(marker, "*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES\n" + marker, 1)
    section = re.compile(r"^(\*Solid Section, elset=[^\n]*)$", re.M)
    return section.sub(lambda m: m.group(1) if "controls=" in m.group(1)
                       else m.group(1) + ", controls=EMBMESH_DELETE_ALL", text)


def run_cli(deck, out, extra):
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "embmesh.cli", "plywise", str(deck), "--instance", "Plate-1",
           "--collapse-layers", "--plies", str(PLIES), "--layup", LAYUP,
           "--fiber-diameter", str(FIBER_D), "--fiber-gap", str(FIBER_GAP),
           "--cohesion", "Cohesion", "--plate-node-contact", "--fiber-node-contact",
           "--ball-instance", "Ball-1", "--ball-interaction", "General",
           "--output", str(out / "output.inp"), *extra]
    with (out / "console.json").open("w") as f:
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=f)
    return json.loads((out / "console.json").read_text())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "Vals_cohesive.inp"
    src.write_text(with_static_fiber_curve(with_cohesive(VALS.read_text())))
    rep = run_cli(src, OUT / "native", ["--host-mode", "native"])
    print("native ok")
    # Stage 8 matrix property type; brief's onset strain 0.1 overrides the deck's 0.01; Gf, yield and
    # rates come from the Matrix card; the ghost deletion strain defaults to the VUEL death strain
    rep2 = run_cli(src, OUT / "vuel", ["--host-mode", "vuel-ghost", "--matrix-model", "ductile-damage",
                                       "--vuel-eps-fail", str(EPSF)])
    print("vuel ok:", {k: rep2["vuel_ghost"][k] for k in ("matrix_model", "user_subroutine", "vuel_nsvars",
                                                          "ghost_ductile_failure_strain")})


def main_delete():
    src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    for case in ("native", "vuel"):
        out = dst / case
        out.mkdir(parents=True, exist_ok=True)
        patched = with_element_deletion((src / case / "output.inp").read_text())
        (out / "output.inp").write_text(patched)
        print(case, "controls on", patched.count("controls=EMBMESH_DELETE_ALL"), "solid sections")


if __name__ == "__main__":
    main_delete() if DELETE_MODE else main()
