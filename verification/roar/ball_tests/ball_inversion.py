"""Per-frame fraction of ball C3D8R elements with a non-positive corner Jacobian, from viewer npz files.

Usage: python ball_inversion.py out.json name=npz [name=npz ...]
"""
import json
import sys
import numpy as np

NBR = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}


def min_sj(P):
    sj = np.full(len(P), 9.0)
    for v, (a, b, c) in NBR.items():
        e1, e2, e3 = P[:, a] - P[:, v], P[:, b] - P[:, v], P[:, c] - P[:, v]
        t = np.einsum("ij,ij->i", np.cross(e1, e2), e3)
        n = np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1) * np.linalg.norm(e3, axis=1)
        sj = np.minimum(sj, t / np.maximum(n, 1e-30))
    return sj


out = {}
for arg in sys.argv[2:]:
    name, fn = arg.split("=", 1)
    d = np.load(fn)
    conn = d["ball_conn_C3D8R"]
    pos = d["ball_pos"]
    frac = []
    for i in range(len(d["times"])):
        frac.append(float((min_sj(pos[i].astype(np.float64)[conn]) <= 0).mean()))
    out[name] = {"t": (d["times"] * 1e6).tolist(), "inv": frac}
    print(name, "inverted at end %.2f%%" % (100 * frac[-1]), flush=True)
json.dump(out, open(sys.argv[1], "w"))
