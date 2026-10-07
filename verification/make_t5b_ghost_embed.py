"""Generate T5b (native *Embedded Element onto a C3D8R "ghost" element that
is node-for-node superimposed on the VUEL host) into verification/roar/t5/.

Follow-up to make_t5_uel_embed.py / BUG-020: *Embedded Element's host
point-location search does not work against a *User Element host at all
(100% of embedded nodes rejected, uniformly). This test asks whether a
workaround is viable: keep the real mechanics on the VU1 user element, but
also define a second, structurally near-inert C3D8R element sharing the
exact same 8 corner nodes as each VU1 host element ("ghost" elements, new
labels, elset=GHOST), and point *Embedded Element's host elset at GHOST
instead of the VU1 HOST elset. If Abaqus's host search succeeds against the
ghost C3D8R (since it IS a native continuum element), the embedded fiber
nodes get positioned/interpolated against the ghost geometry -- which is
node-identical to the real VU1 host, so (if Abaqus internally uses the
*current* host node positions each increment, not just the reference
configuration) the fibers would still track the VUEL host's deformation
correctly.

Ghost elements use a *Material with deliberately tiny density/stiffness
(rho=1e-6, E=1.0 Pa) so they are geometrically real (satisfying whatever
Abaqus checks at input-file-processing) but mechanically negligible next to
the real VUEL host's actual properties -- isolating "does the host search
succeed" from "does the ghost stiffness/mass corrupt the mechanics".

byte-identical to vuel_host.inp except for: (a) the added GHOST element/
section/material block in the PLATE part, (b) EMBMESH_HOST's element list
now pointing at the GHOST labels instead of the VU1 HOST labels.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.deckgen import materials, step_block
from verification.make_t5_uel_embed import (
    HOST, T, OUT, build_source, run_mesher, to_vuel_host, build_user_subroutine,
)

GHOST_LABEL_OFFSET = 1000
GHOST = dict(E=1.0, nu=0.3, rho=1.0e-6)  # deliberately near-inert: real geometry, negligible mechanics


def to_ghost_embed_host(vuel_text):
    """Starting from the already-VUEL-ized mesher output (to_vuel_host's
    result), add a node-superimposed C3D8R GHOST element per VU1 HOST
    element and repoint EMBMESH_HOST's embedded-element host elset at GHOST
    instead of HOST."""
    lines = vuel_text.splitlines()

    # 1) grab the VU1 *Element data lines (elset=HOST) to clone as GHOST with offset labels
    i_elem = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*element, type=vu1"))
    j = i_elem + 1
    while j < len(lines) and not lines[j].lstrip().startswith("*"):
        j += 1
    elem_data = lines[i_elem + 1:j]

    ghost_elem_data = []
    for l in elem_data:
        fields = [f.strip() for f in l.split(",")]
        label = int(fields[0])
        nodes = fields[1:]
        ghost_elem_data.append(f"{label + GHOST_LABEL_OFFSET}, " + ", ".join(nodes))

    # 2) insert GHOST element + section block right after *UEL Property's data line,
    #    before *End Part
    i_endpart = next(i for i, l in enumerate(lines) if l.strip().lower() == "*end part")
    ghost_block = (
        ["*Element, type=C3D8R, elset=GHOST"] + ghost_elem_data +
        [f"*Solid Section, elset=GHOST, material=GHOST", ","]
    )
    new_lines = lines[:i_endpart] + ghost_block + lines[i_endpart:]
    text = "\n".join(new_lines)

    # 3) repoint EMBMESH_HOST's element list (currently the VU1 HOST labels) at the GHOST labels
    def repoint(m):
        return m.group(0).replace(
            m.group(1), ", ".join(str(int(x) + GHOST_LABEL_OFFSET) for x in m.group(1).split(","))
        )
    text = re.sub(
        r"\*Elset, elset=EMBMESH_HOST, instance=PLATE-1\n([0-9, ]+)",
        repoint, text,
    )
    return text


def main():
    src = build_source()
    mesher_out = run_mesher(src)
    vuel_text = to_vuel_host(mesher_out)
    ghost_text = to_ghost_embed_host(vuel_text)

    tail_mat = "\n".join(materials("FIBER", True, vumat=False))
    ghost_mat = "\n".join([
        "*Material, name=GHOST",
        "*Density",
        f"{GHOST['rho']:.6g},",
        "*Elastic",
        f"{GHOST['E']:.6g}, {GHOST['nu']:.6g}",
    ])
    bcs = ["*Boundary", "LEFT, 1, 1", "ORIGIN, 2, 3", "*Boundary, amplitude=RAMP", "RIGHT, 1, 1, 0.01"]
    tail_step = "\n".join(step_block(bcs, T=T, print_nset="RIGHT"))

    deck = ghost_text + "\n" + tail_mat + "\n" + ghost_mat + "\n" + tail_step + "\n"
    out_path = OUT / "ghost_embed.inp"
    out_path.write_text(deck)
    print("wrote", out_path)

    user_path = OUT / "ghost_embed_user.for"
    user_path.write_text(build_user_subroutine())
    print("wrote", user_path)

    print("\nghost_embed.inp: VU1 host (real mechanics) + superimposed C3D8R GHOST")
    print("elements sharing the same 8 nodes per host element; *Embedded Element's")
    print("host elset now points at GHOST instead of the VU1 HOST elset.")
    print("Submit to Abaqus 2024 on ROAR; compare against c3d8_host.inp / vuel_host.inp.")


if __name__ == "__main__":
    main()
