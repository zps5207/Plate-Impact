"""Per-frame comparison statistics for v500 (no fiber contact) vs v500* (fiber contact) from the viewer .npz files.

Writes verification/roar/t_nc/compare_fc.json. Ball interior test: convex hull of the deformed ball nodes
(the ball is nearly convex; a surface dent would make this slightly overstate depth, host nodes are the control).
"""
import json
import os
import sys
import numpy as np
from scipy.spatial import ConvexHull

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t_nc")
CASES = [("v500_100", "v500 (no fiber contact)"), ("v500star_100", "v500* (fiber contact)")]


def depth_inside(eq, pts):
    s = pts @ eq[:, :3].T + eq[:, 3]          # negative inside each half-space
    m = s.max(axis=1)
    return np.where(m < 0, -m, 0.0)           # penetration depth (m), 0 outside


out = {}
for name, label in CASES:
    d = np.load(os.path.join(ROOT, name, name + "_viewer.npz"))
    t = d["times"]
    bp, fp, hp, st = d["ball_pos"], d["fiber_pos"], d["host_pos"], d["host_status"]
    n = len(t)
    rec = {"label": label, "t_us": (t * 1e6).tolist(), "n_frames": n}
    rec["host_deleted"] = (st.shape[1] - st.sum(axis=1)).astype(int).tolist()
    vz = np.gradient(bp[:, :, 2].mean(axis=1), t)
    rec["ball_vz"] = (-vz).tolist()                     # speed toward -z, m/s
    rec["ball_zmin_mm"] = (bp[:, :, 2].min(axis=1) * 1e3).tolist()
    fi, fd, hi, hd = [], [], [], []
    fcount95 = []
    for i in range(n):
        hull = ConvexHull(bp[i].astype(np.float64))
        eq = hull.equations
        f = depth_inside(eq, fp[i].astype(np.float64))
        h = depth_inside(eq, hp[i].astype(np.float64))
        fi.append(int((f > 0).sum())); fd.append(float(f.max() * 1e3))
        hi.append(int((h > 0).sum())); hd.append(float(h.max() * 1e3))
    rec.update(fiber_in_ball=fi, fiber_max_depth_mm=fd, host_in_ball=hi, host_max_depth_mm=hd)
    # fiber motion
    disp = np.linalg.norm(fp - fp[0], axis=2)
    rec["fiber_max_disp_mm"] = (disp.max(axis=1) * 1e3).tolist()
    rec["fiber_mean_disp_mm"] = (disp.mean(axis=1) * 1e3).tolist()
    # fibers dragged out: fiber nodes whose z is below the plate lower face at frame 0 (host min z at 0)
    zlow = float(hp[0, :, 2].min())
    rec["plate_zmin_mm"] = zlow * 1e3
    rec["fiber_below_plate"] = (fp[:, :, 2] < zlow - 1e-4).sum(axis=1).astype(int).tolist()
    # fiber elements stretched: segment strain from connectivity
    conn = d["fiber_conn_T3D2"]
    L0 = np.linalg.norm(fp[0, conn[:, 0]] - fp[0, conn[:, 1]], axis=1)
    L = np.linalg.norm(fp[:, conn[:, 0]] - fp[:, conn[:, 1]], axis=2)
    eng = (L - L0) / L0
    rec["fiber_strain_max"] = eng.max(axis=1).tolist()
    rec["fiber_strain_p99"] = np.percentile(eng, 99, axis=1).tolist()
    rec["fiber_over_10pct"] = (eng > 0.1).sum(axis=1).astype(int).tolist()
    out[name] = rec
    print(name, "deleted end", rec["host_deleted"][-1], "fiber in ball peak", max(fi), "max depth %.2f mm" % max(fd),
          "host in ball peak", max(hi), "depth %.2f" % max(hd), "ball v end %.1f" % rec["ball_vz"][-1])
json.dump(out, open(os.path.join(ROOT, "compare_fc.json"), "w"))
