"""Node-based plate contact surface: thickness sweep decks.
Usage: python make_thickness_sweep.py BASE_OUTPUT_INP OUTDIR T1_mm [T2_mm ...]
Each deck = the mesher output plus a *Surface, type=NODE over the plate node set, its contact inclusion
against the ball surface, and (when thickness > 0) a THICKNESS surface property. Directory name: thk<mm*10, 3 digits>.
"""
import os
import sys

base, outdir = sys.argv[1], sys.argv[2]
mms = [float(a) for a in sys.argv[3:]]
LINES = open(base, encoding="utf-8").read().split("\n")
NODESURF = ["*Surface, type=NODE, name=Surf-Plate-Nodes", "plate,"]
BALL_STATUS = ["*Output, field, number interval=1000", "*Element Output, elset=ball", "STATUS"]

for mm in mms:
    name = "thk%03d" % round(mm * 10)
    L = list(LINES)
    i = L.index("*Surface, type=ELEMENT, name=Surf-2")
    L = L[:i] + NODESURF + L[i:]
    i = L.index("*Contact Property Assignment")
    j = L.index("Surf-2 , ", L.index("*Contact Inclusions"))
    L.insert(j + 1, "Surf-Plate-Nodes , Surf-2")
    i += 1
    extra = []
    if mm > 0:
        extra = ["*Surface Property Assignment, property=THICKNESS", " Surf-Plate-Nodes, %g" % (mm * 1e-3)]
    L = L[:i + 2] + extra + L[i + 2:]
    k = L.index("*End Step")
    L = L[:k] + BALL_STATUS + L[k:]
    path = os.path.join(outdir, name)
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, "output.inp"), "w", encoding="utf-8").write("\n".join(L))
    print(name, mm, "mm", len(L))
