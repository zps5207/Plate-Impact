"""Compare VUEL failure events (job stdout) with native ghost deletions (viewer .npz host_status).

Inputs: vuel_failures.txt  (lines "<run> *** VUEL_FAILURE (ENG STRAIN|JACOBIAN): elem = N time = T ...")
        viewer npz per run (host_status[frame, element], times)
Per run: cumulative VUEL failures N_v(t) against cumulative ghost deletions N_g(t); failure type counts; and a per-element
match (VUEL element number n <-> host_status column n-1, validated by the offset distribution) giving
dt = t_ghost_deleted - t_vuel_failed for every element that has both.
"""
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RES = os.path.join(ROOT, "Meshing", "plywise-500", "results")
NPZ = {
    "flat_solid": os.path.join(ROOT, "verification", "roar", "t_nc", "v500star_100", "v500star_100_viewer.npz"),
    "flat_ply_v3": os.path.join(RES, "pw_flat500_v3", "pw_flat500_v3_viewer.npz"),
    "cc_solid": os.path.join(ROOT, "reports", "cc_run", "dl", "cc500_100", "cc500_100_viewer.npz"),
    "cc_ply_v3": os.path.join(RES, "pw_cc500_v3", "pw_cc500_v3_viewer.npz"),
}
pat = re.compile(r"^(\S+)\s+\*\*\* VUEL_FAILURE \((ENG STRAIN|JACOBIAN)\): elem =\s*(\d+)\s+time =\s*([0-9.eE+\-]+)")
events = {}
for line in open(os.path.join(RES, "vuel_failures.txt")):
    m = pat.match(line)
    if m:
        events.setdefault(m.group(1), []).append((m.group(2), int(m.group(3)), float(m.group(4))))

out = {}
for run, ev in events.items():
    typ = np.array([e[0] for e in ev]); el = np.array([e[1] for e in ev]); tv = np.array([e[2] for e in ev])
    r = {"n_events": len(ev), "n_unique_elements": int(len(set(el))), "eng_strain": int((typ == "ENG STRAIN").sum()),
         "jacobian": int((typ == "JACOBIAN").sum()), "first_us": float(tv.min() * 1e6), "median_us": float(np.median(tv) * 1e6),
         "last_us": float(tv.max() * 1e6)}
    if run in NPZ and os.path.exists(NPZ[run]):
        d = np.load(NPZ[run])
        t, st = d["times"], d["host_status"]
        n_el = st.shape[1]
        dead = st == 0
        ever = dead.any(axis=0)
        first_dead = np.where(ever, dead.argmax(axis=0), -1)       # first frame where STATUS = 0
        tg = np.where(ever, t[np.maximum(first_dead, 0)], np.nan)
        r["n_ghost_deleted"] = int(ever.sum()); r["n_ghost_frames"] = len(t)
        r["first_ghost_us"] = float(np.nanmin(tg) * 1e6)
        # cumulative curves on the frame grid
        ng = dead.sum(axis=1)
        nv = np.array([(tv <= ti).sum() for ti in t])
        r["cum"] = {"t_us": (t * 1e6).tolist(), "ghost": ng.tolist(), "vuel": nv.tolist()}
        # per-element match
        idx = el - 1
        ok = (idx >= 0) & (idx < n_el)
        first_v = {}
        for i, tt in zip(idx[ok], tv[ok]):
            first_v[int(i)] = min(first_v.get(int(i), 1e9), tt)
        both = [i for i in first_v if ever[i]]
        dts = np.array([tg[i] - first_v[i] for i in both]) * 1e6
        only_v = [i for i in first_v if not ever[i]]
        only_g = [i for i in np.flatnonzero(ever) if i not in first_v]
        r["match"] = {"both": len(both), "vuel_only": len(only_v), "ghost_only": len(only_g),
                      "dt_us_median": float(np.median(dts)) if len(dts) else None,
                      "dt_us_p05": float(np.percentile(dts, 5)) if len(dts) else None,
                      "dt_us_p95": float(np.percentile(dts, 95)) if len(dts) else None,
                      "ghost_before_vuel": int((dts < -0.5).sum()), "within_1_frame": int((abs(dts) <= 0.5).sum()),
                      "ghost_after_vuel": int((dts > 0.5).sum()), "frame_us": float(np.median(np.diff(t)) * 1e6)}
        r["match"]["dt_hist_us"] = np.histogram(dts, bins=np.arange(-5, 5.01, 0.5))[0].tolist() if len(dts) else []
    out[run] = r
json.dump(out, open(os.path.join(RES, "vuel_vs_ghost_timing.json"), "w"), indent=1)
for run, r in out.items():
    print(run, {k: v for k, v in r.items() if k not in ("cum",)})
