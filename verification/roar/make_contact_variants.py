"""Build contact-workaround deck variants of the flat_v2 mesher output (T-010 experiments).
Usage: python make_contact_variants.py BASE_OUTPUT_INP OUTDIR
Each variant is a text edit of the mesher output deck; ghost-scale variants need a re-mesh instead.
"""
import os
import sys

base, outdir = sys.argv[1], sys.argv[2]
LINES = open(base, encoding="utf-8").read().split("\n")

SURF1_OLD = ["*Surface, type=ELEMENT, name=Surf-1", "_Surf-1_S2, S2", "_Surf-1_S3, S3", "_Surf-1_S4, S4"]
WHOLE = ["*Elset, elset=EMBMESH_GHOST_ALL, instance=Plate-1, generate", " 24001, 48000, 1",
         "*Surface, type=ELEMENT, name=Surf-1", "EMBMESH_GHOST_ALL,"]
NODESURF = ["*Surface, type=NODE, name=Surf-Plate-Nodes", "plate,"]
BALL_STATUS = ["*Output, field, number interval=1000", "*Element Output, elset=ball", "STATUS"]


def replace_block(lines, old, new):
    for i in range(len(lines) - len(old) + 1):
        if lines[i:i + len(old)] == old:
            return lines[:i] + new + lines[i + len(old):]
    raise SystemExit("block not found: %r" % old[0])


def build(name, whole=False, linear=None, nodesurf=False, thickness=None, penalty=None):
    L = list(LINES)
    if whole:
        L = replace_block(L, SURF1_OLD, WHOLE)
    if nodesurf:
        i = L.index("*Surface, type=ELEMENT, name=Surf-2")
        L = L[:i] + NODESURF + L[i:]
    if linear is not None:
        i = L.index("*Surface Behavior, pressure-overclosure=HARD")
        L[i] = "*Surface Behavior, pressure-overclosure=LINEAR"
        L.insert(i + 1, " %g, , " % linear)
    i = L.index("*Contact Property Assignment")
    extra = []
    if nodesurf:
        j = L.index("Surf-2 , ", L.index("*Contact Inclusions"))
        L.insert(j + 1, "Surf-Plate-Nodes , Surf-2")
        i += 1
    if penalty is not None:
        extra += ["*Contact Controls Assignment, type=SCALE PENALTY", " , , %g" % penalty]
    if thickness is not None:
        extra += ["*Surface Property Assignment, property=THICKNESS", " Surf-Plate-Nodes, %g" % thickness]
    L = L[:i + 2] + extra + L[i + 2:]          # after the property-assignment data line
    k = L.index("*End Step")
    L = L[:k] + BALL_STATUS + L[k:]
    path = os.path.join(outdir, name)
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, "output.inp"), "w", encoding="utf-8").write("\n".join(L))
    print(name, len(L))


build("v2_whole", whole=True)
build("v2_whole_lin1e10", whole=True, linear=1e10)
build("v2_whole_lin1e12", whole=True, linear=1e12)
build("v2_whole_pen1e4", whole=True, penalty=1e4)
build("v2_nodes", nodesurf=True, thickness=0.0005)
build("v2_whole_nodes", whole=True, nodesurf=True, thickness=0.0005)
