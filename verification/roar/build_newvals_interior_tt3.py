r"""Interior-face eroding contact check deck (short run) from the nv3_elem deck.

Takes Meshing/newvals-elemcontact-tt3/vuel/nv_vuel_elem.inp and rewrites the general contact:
  * PLATE_ERODE = exterior AND interior faces of every ply's ghost C3D8R hosts (VUEL elements cannot carry surfaces)
  * self contact of PLATE_ERODE (penalty, general contact default) -> ply-ply, sublayer-sublayer as elements erode
  * PLATE_ERODE with the ball, fiber nodes with the ball (fibers stay node-based, embedded in the hosts so they are
    kept out of plate contact)
  * cohesive property assignments on the Ply-k_top / Ply-(k+1)_bottom pairs unchanged, General everywhere else
  * *Contact Controls Assignment, nodal erosion=YES (nodes whose elements have all failed leave the contact)
  * no plate contact thickness (solid faces default to zero)
Step shortened to 2 us (ball touches at ~0.97 us) and field output every 0.1 us, to check for spurious contact or
host deletion before impact and early contact with the ball.
Usage: python verification/roar/build_newvals_interior_tt3.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Meshing" / "newvals-elemcontact-tt3" / "vuel" / "nv_vuel_elem.inp"
OUT = ROOT / "Meshing" / "newvals-interior-tt3" / "nv3_int.inp"
PLIES = 20
STEP = 2e-6
FRAMES = 20


def main():
    lines = SRC.read_text().splitlines()
    # 1) eroding surface with interior faces, next to the existing EMBMESH_PLATE_ELEMS definition
    i = lines.index("*Surface, type=ELEMENT, name=EMBMESH_PLATE_ELEMS")
    surf = ["** interior-face eroding plate surface (ghost hosts); faces become active as elements are deleted",
            "*Surface, type=ELEMENT, name=PLATE_ERODE"]
    for k in range(1, PLIES + 1):
        surf += [f"Ply-{k}.EMBMESH_GHOST_HOST,", f"Ply-{k}.EMBMESH_GHOST_HOST, INTERIOR"]
    lines[i:i] = surf
    # 2) contact inclusions
    a = lines.index("*Contact Inclusions")
    b = lines.index("*Contact Property Assignment")
    assert lines[a + 1].startswith("EMBMESH_PLATE_ELEMS")
    lines[a:b] = ["*Contact Inclusions",
                  "PLATE_ERODE ,",
                  "PLATE_ERODE , EMBMESH_BALL_SURF",
                  "EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF"]
    # 3) nodal erosion, inside *Contact after the property assignments
    t = lines.index("*Surface Property Assignment, property=THICKNESS")
    lines[t:t] = ["*Contact Controls Assignment, nodal erosion=YES"]  # takes no data lines
    # 4) short step and 0.1 us field frames
    d = lines.index("*Dynamic, Explicit")
    assert lines[d + 1].strip() == ", 1e-04"
    lines[d + 1] = f", {STEP:g}"
    n = 0
    for j, s in enumerate(lines):
        if s.startswith("*Output, field") and "number interval=1000" in s:
            lines[j] = s.replace("number interval=1000", f"number interval={FRAMES}")
            n += 1
    assert n == 3, n
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
