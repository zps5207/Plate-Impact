"""Do fibers outlive their host? For each viewer .npz: map every fiber node to the host element that contains it at
frame 0, then track (a) the fraction of fiber nodes whose host element has been deleted (orphaned: the embedded
constraint is gone and the node moves on its own momentum), (b) how fast orphaned vs attached nodes move,
(c) fiber segment strain.

Usage: python fiber_orphan_analysis.py <label>=<npz> [...]   -> prints a table, writes fiber_orphan_<label>.json next to the npz
"""
import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from embmesh.geometry import inverse_hex  # noqa: E402


def analyse(path, k_candidates=10):
    d = np.load(path)
    t = d["times"]
    hp, fp, st = d["host_pos"], d["fiber_pos"], d["host_status"]
    conn = d["host_conn_C3D8R"]
    fconn = d["fiber_conn_T3D2"]
    n_f = len(fp[0])
    hexes0 = hp[0][conn].astype(np.float64)                    # (n_el, 8, 3) at frame 0
    cen = hexes0.mean(axis=1)
    tree = cKDTree(cen)
    p0 = fp[0].astype(np.float64)
    _, cand = tree.query(p0, k=k_candidates)
    host = np.full(n_f, -1, dtype=np.int64)
    for i in range(n_f):
        for e in cand[i]:
            if inverse_hex(p0[i], hexes0[e]) is not None:
                host[i] = e
                break
    found = host >= 0
    print("%s: fiber nodes %d, host found for %d (%.2f%%)" % (os.path.basename(path), n_f, found.sum(), 100 * found.mean()))
    alive = st[:, host[found]] > 0                              # (frames, n_found)
    orphan_frac = 1.0 - alive.mean(axis=1)
    vel = np.gradient(fp.astype(np.float64), t, axis=0)         # (frames, n_f, 3)
    speed = np.linalg.norm(vel, axis=2)[:, found]
    res = {"t_us": (t * 1e6).tolist(), "n_fiber_nodes": int(n_f), "n_found": int(found.sum()),
           "orphan_frac": orphan_frac.tolist()}
    sp_o, sp_a = [], []
    for i in range(len(t)):
        o = ~alive[i]
        sp_o.append(float(speed[i][o].mean()) if o.any() else 0.0)
        sp_a.append(float(speed[i][~o].mean()) if (~o).any() else 0.0)
    res["speed_orphaned_mean"], res["speed_attached_mean"] = sp_o, sp_a
    L0 = np.linalg.norm(fp[0][fconn[:, 0]] - fp[0][fconn[:, 1]], axis=1).astype(np.float64)
    L = np.linalg.norm(fp[:, fconn[:, 0]].astype(np.float64) - fp[:, fconn[:, 1]], axis=2)
    eng = (L - L0) / L0
    res["seg_strain_max"] = eng.max(axis=1).tolist()
    res["seg_over_10pct"] = (eng > 0.10).sum(axis=1).astype(int).tolist()
    # displacement of orphaned nodes from where their host's last surviving neighbour would have taken them is not
    # available; report orphaned-node displacement from frame 0 instead
    disp = np.linalg.norm(fp.astype(np.float64) - fp[0], axis=2)[:, found]
    res["disp_orphaned_mean_mm"] = [float(disp[i][~alive[i]].mean() * 1e3) if (~alive[i]).any() else 0.0 for i in range(len(t))]
    res["disp_attached_mean_mm"] = [float(disp[i][alive[i]].mean() * 1e3) if alive[i].any() else 0.0 for i in range(len(t))]
    return res


def main(args):
    out = {}
    for a in args:
        label, path = a.split("=", 1)
        r = analyse(path)
        out[label] = r
        json.dump(r, open(os.path.splitext(path)[0] + "_orphans.json", "w"))
    print("\n%-16s %10s %10s %12s %12s %12s %12s" % ("run", "orph@25us", "orph@50us", "orph@100us", "spd orph", "spd attach", "seg>10%"))
    for label, r in out.items():
        t = np.array(r["t_us"])
        at = lambda x: int(np.argmin(abs(t - x)))
        print("%-16s %9.1f%% %9.1f%% %11.1f%% %10.1f m/s %9.1f m/s %12d" % (
            label, 100 * r["orphan_frac"][at(25)], 100 * r["orphan_frac"][at(50)], 100 * r["orphan_frac"][-1],
            r["speed_orphaned_mean"][-1], r["speed_attached_mean"][-1], r["seg_over_10pct"][-1]))


if __name__ == "__main__":
    main(sys.argv[1:])
