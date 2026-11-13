"""Plywise decks (3 hex layers per ply, native + VUEL) from the user's own re-meshed Meshing/NewVals.inp.

Same pipeline as build_vals_ballfix_tt3.py but the ball is NOT replaced: NewVals.inp's quarter ball
(C3D8R + C3D6, rotated instance, centre z = 5.762 mm) is kept. Applied on top (as in the ball-fix decks):
speed 1000 -> 1028 m/s and an element-based rigid ball whose density is scaled so the rigid quarter has the
mass of a true 3/8 in steel sphere (volume of hexes and wedges taken from the mesh).
Usage: python verification/roar/build_newvals_tt3.py [out_dir]   (default Meshing/newvals-plywise-tt3)
"""
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent.parent
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "Meshing" / "newvals-plywise-tt3")]

import build_vals_plywise as bvp  # noqa: E402
_orig = bvp.run_cli
bvp.run_cli = lambda deck, out, extra: _orig(deck, out, [*extra, "--through-thickness", "3"])
import build_vals_ballfix as bvf  # noqa: E402

SRC = ROOT / "Meshing" / "NewVals.inp"
R = 0.0047625


def ball_info():
    L = SRC.read_text().replace("\r", "").split("\n")
    nodes, hexes, wedges, cur, mode = {}, [], [], None, None
    for ln in L:
        s = ln.strip()
        if s.startswith("*Part"):
            cur = s.split("name=")[1].strip(); mode = None
        elif s.startswith("*End Part"):
            cur = None; mode = None
        elif cur == "Ball" and s.startswith("*Node"):
            mode = "n"
        elif cur == "Ball" and s.startswith("*Element"):
            mode = re.search(r"type=(\w+)", s).group(1)
        elif s.startswith("*"):
            mode = None
        elif cur == "Ball" and mode == "n":
            v = s.split(","); nodes[int(v[0])] = [float(x) for x in v[1:4]]
        elif cur == "Ball" and mode == "C3D8R":
            hexes.append([int(x) for x in s.strip(",").split(",")][1:])
        elif cur == "Ball" and mode == "C3D6":
            wedges.append([int(x) for x in s.strip(",").split(",")][1:])
    ids = sorted(nodes); ix = {n: i for i, n in enumerate(ids)}
    pts = np.array([nodes[n] for n in ids])
    vh = bvf.gauss_volume(pts, np.array([[ix[n] for n in e] for e in hexes]))
    vw = 0.0
    for e in wedges:  # straight-sided prism = 3 tets (accurate for near-planar wedge faces)
        p = pts[[ix[n] for n in e]]
        for t in ((0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5)):
            vw += abs(np.linalg.det(p[list(t[1:])] - p[t[0]])) / 6.0
    exact = np.pi * R ** 3 / 3.0
    return dict(nodes=len(pts), hexes=len(hexes), wedges=len(wedges), volume_hex=vh, volume_wedge=vw,
                volume_quarter_exact=exact, density=7850.0 * exact / (vh + vw), radius=float(np.linalg.norm(pts, axis=1).max()))


INFO = ball_info()
bvf.VALS = SRC
bvf.CENTRE_Z = 0.005762
bvf.make_ball = lambda: (None, None, INFO)
bvf.swap_ball = lambda lines, pts, hexes: lines
bvf.GAP = 0.005762 - R   # actual gap between ball and plate top (z = 0)
sys.argv = sys.argv[:2]

if __name__ == "__main__":
    bvf.main()
