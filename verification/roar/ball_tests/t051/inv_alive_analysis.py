"""Combine per-element STATUS (extract_inversion_odb.py npz) with viewer node positions: are inverted hexes alive or already deleted?

Usage: python inv_alive_analysis.py <inversion.npz> <viewer.npz> <out.json>
Viewer node order differs from the ODB's, so nodes are matched by initial coordinates.
"""
import json, sys
import numpy as np
from scipy.spatial import cKDTree

NBR = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}


def min_sj(P):
    sj = np.full(len(P), 9.0)
    for v, (a, b, c) in NBR.items():
        e1, e2, e3 = P[:, a] - P[:, v], P[:, b] - P[:, v], P[:, c] - P[:, v]
        t = np.einsum("ij,ij->i", np.cross(e1, e2), e3)
        n = np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1) * np.linalg.norm(e3, axis=1)
        sj = np.minimum(sj, t / np.maximum(n, 1e-30))
    return sj


I = np.load(sys.argv[1], allow_pickle=True)
V = np.load(sys.argv[2])
d, v2i = cKDTree(I["ball_coords0"]).query(V["ball_coords0"])
assert d.max() < 1e-7, "node coordinate match failed (%g)" % d.max()
# viewer hex -> ODB element index via the ODB node-index sets
ty = I["ball_elem_types"]
key = {tuple(sorted(r)): i for i, r in enumerate(I["ball_conn"][ty == "C3D8R"])}
hex_idx = np.where(ty == "C3D8R")[0]
vconn = V["ball_conn_C3D8R"]
emap = np.array([hex_idx[key[tuple(sorted(v2i[r]))]] for r in vconn])
tI = I["times"]
status = I["STATUS"]
out = {"t": [], "alive_inv": [], "dead_inv": [], "alive_total": [], "dead_total": []}
first_inv = np.full(len(vconn), np.nan)
first_dead = np.full(len(vconn), np.nan)
tV = V["times"]
for k in range(len(tV)):
    j = int(np.argmin(abs(tI - tV[k])))
    pos = V["ball_pos"][k].astype(np.float64)
    inv = min_sj(pos[vconn]) <= 0
    dead = status[j][emap] < 0.5
    out["t"].append(tV[k] * 1e6)
    out["alive_inv"].append(int((inv & ~dead).sum()))
    out["dead_inv"].append(int((inv & dead).sum()))
    out["alive_total"].append(int((~dead).sum()))
    out["dead_total"].append(int(dead.sum()))
    new_i = inv & np.isnan(first_inv)
    first_inv[new_i] = tV[k] * 1e6
    new_d = dead & np.isnan(first_dead)
    first_dead[new_d] = tI[j] * 1e6
# per-element order for elements that ever invert
ever = ~np.isnan(first_inv)
dead_before = ever & ~np.isnan(first_dead) & (first_dead <= first_inv)
dead_after = ever & ~np.isnan(first_dead) & (first_dead > first_inv)
never_dead = ever & np.isnan(first_dead)
out["summary"] = {"ever_inverted": int(ever.sum()), "dead_at_or_before_first_inversion": int(dead_before.sum()),
                  "dead_only_after_first_inversion": int(dead_after.sum()), "inverted_never_deleted": int(never_dead.sum())}
# status-only check at the end: inverted elements still alive
json.dump(out, open(sys.argv[3], "w"))
print(json.dumps(out["summary"]), "last frame: alive-inv", out["alive_inv"][-1], "dead-inv", out["dead_inv"][-1], "t", round(out["t"][-1], 2))
