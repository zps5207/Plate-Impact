"""Analysis of NewVals 3-layer native impact run from local viewer data.
Computes spatial and temporal distributions of host deletion, radial zones,
per-ply and per-layer metrics, fiber axial strains, and kinematic plug formation.
"""
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

VIEWER_DIR = Path("../../Meshing/newvals-paper-tt3/results/viewer_nv3_native")
OUT_DIR = Path("C:/Users/salas/OneDrive - The Pennsylvania State University/Plate Impact/agents/drafter/outbox/T-054")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with open(VIEWER_DIR / "manifest.json") as f:
    manifest = json.load(f)

times_us = np.array(manifest["times_us"])
n_frames = len(times_us)
n_hosts = manifest["counts"]["host_elements"] # 217500
n_fibers = manifest["counts"]["fiber_segments"] # 524180

hp0 = np.memmap(VIEWER_DIR / "host_pos.f32", dtype=np.float32, mode="r",
                shape=tuple(manifest["files"]["host_pos"]["shape"]))[0]
e1 = np.memmap(VIEWER_DIR / "host_faces_e1.u32", dtype=np.uint32, mode="r",
               shape=tuple(manifest["files"]["host_faces_e1"]["shape"]))
tris = np.memmap(VIEWER_DIR / "host_faces_tris.u32", dtype=np.uint32, mode="r",
                 shape=tuple(manifest["files"]["host_faces_tris"]["shape"]))
hs = np.memmap(VIEWER_DIR / "host_status.u8", dtype=np.uint8, mode="r",
               shape=tuple(manifest["files"]["host_status"]["shape"]))

# 1. Compute initial host element centroids
elem_pts_sum = np.zeros((n_hosts, 3), dtype=np.float64)
elem_pts_cnt = np.zeros(n_hosts, dtype=np.int32)
for k in range(6):
    np.add.at(elem_pts_sum, e1, hp0[tris[:, k]])
    np.add.at(elem_pts_cnt, e1, 1)
elem_centers = elem_pts_sum / elem_pts_cnt[:, None]

xc = elem_centers[:, 0]
yc = elem_centers[:, 1]
zc = elem_centers[:, 2]
r = np.sqrt(xc**2 + yc**2)
depth = -zc  # top surface is z=0, bottom is z=-0.0254

# Ply index (1 at bottom z=-25.4mm, 20 at top z=0)
# Height = 25.4 mm = 20 plies * 1.27 mm
ply_idx = np.clip(np.floor((zc + 0.0254) / 0.00127).astype(int) + 1, 1, 20)
z_rel = (zc + 0.0254) - (ply_idx - 1) * 0.00127
sublayer = np.clip(np.floor(z_rel / (0.00127 / 3.0)).astype(int), 0, 2)
# sublayer 0: bottom 1/3, 1: middle 1/3 (fiber bearing), 2: top 1/3

# Deletion time per element
dead_mask = (hs == 0)
has_deleted = dead_mask.any(axis=0)
first_dead_frame = np.where(has_deleted, np.argmax(dead_mask, axis=0), -1)
del_times = np.where(has_deleted, times_us[first_dead_frame], np.inf)

R_BALL = 0.0047625  # 4.7625 mm

# --- Question 1 Analysis ---
q1_res = {}
q1_res["total_elements"] = int(n_hosts)
q1_res["deleted_70us"] = int((del_times <= 70.0).sum())
q1_res["deleted_100us"] = int(has_deleted.sum())

# Radial breakdown at 100 us
is_del100 = has_deleted
in_ball = is_del100 & (r <= R_BALL)
in_annulus = is_del100 & (r > R_BALL) & (r <= 1.2 * R_BALL)
in_outer = is_del100 & (r > 1.2 * R_BALL)

q1_res["radial_breakdown_100us"] = {
    "footprint_r_le_4p76mm": {
        "count": int(in_ball.sum()),
        "pct_of_deleted": float(100 * in_ball.sum() / has_deleted.sum()),
        "total_in_zone": int((r <= R_BALL).sum()),
        "zone_deletion_rate_pct": float(100 * in_ball.sum() / (r <= R_BALL).sum())
    },
    "annulus_4p76_to_5p72mm": {
        "count": int(in_annulus.sum()),
        "pct_of_deleted": float(100 * in_annulus.sum() / has_deleted.sum()),
        "total_in_zone": int(((r > R_BALL) & (r <= 1.2 * R_BALL)).sum()),
        "zone_deletion_rate_pct": float(100 * in_annulus.sum() / ((r > R_BALL) & (r <= 1.2 * R_BALL)).sum())
    },
    "outer_r_gt_5p72mm": {
        "count": int(in_outer.sum()),
        "pct_of_deleted": float(100 * in_outer.sum() / has_deleted.sum()),
        "total_in_zone": int((r > 1.2 * R_BALL).sum()),
        "zone_deletion_rate_pct": float(100 * in_outer.sum() / (r > 1.2 * R_BALL).sum())
    },
    "max_radius_deleted_mm": float(r[is_del100].max() * 1e3)
}

# Sublayer breakdown
q1_res["sublayer_breakdown_100us"] = {}
for sl, name in [(0, "Layer 0 (Bottom)"), (1, "Layer 1 (Middle / Fiber-bearing)"), (2, "Layer 2 (Top)")]:
    cnt = int(((sublayer == sl) & is_del100).sum())
    tot = int((sublayer == sl).sum())
    q1_res["sublayer_breakdown_100us"][name] = {
        "deleted": cnt,
        "total": tot,
        "rate_pct": float(100 * cnt / tot)
    }

# Per-ply breakdown
q1_res["per_ply_breakdown_100us"] = {}
for p in range(20, 0, -1):
    cnt = int(((ply_idx == p) & is_del100).sum())
    tot = int((ply_idx == p).sum())
    sl_cnts = [int(((ply_idx == p) & (sublayer == s) & is_del100).sum()) for s in range(3)]
    q1_res["per_ply_breakdown_100us"][f"Ply_{p}"] = {
        "depth_range_mm": [float((20 - p) * 1.27), float((21 - p) * 1.27)],
        "deleted": cnt,
        "total": tot,
        "rate_pct": float(100 * cnt / tot),
        "by_sublayer_0_1_2": sl_cnts
    }

# Temporal evolution
timeline = []
eval_times = [1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
for t_target in eval_times:
    f_idx = int(np.argmin(np.abs(times_us - t_target)))
    t_val = float(times_us[f_idx])
    del_t = (del_times <= t_val)
    tot_d = int(del_t.sum())
    if tot_d > 0:
        row = {
            "t_us": t_val,
            "total_deleted": tot_d,
            "under_ball": int((del_t & (r <= R_BALL)).sum()),
            "annulus": int((del_t & (r > R_BALL) & (r <= 1.2 * R_BALL)).sum()),
            "outer": int((del_t & (r > 1.2 * R_BALL)).sum()),
            "max_r_mm": float(r[del_t].max() * 1e3),
            "max_depth_mm": float(depth[del_t].max() * 1e3)
        }
    else:
        row = {
            "t_us": t_val,
            "total_deleted": 0,
            "under_ball": 0,
            "annulus": 0,
            "outer": 0,
            "max_r_mm": 0.0,
            "max_depth_mm": 0.0
        }
    timeline.append(row)
q1_res["timeline"] = timeline

# --- Question 3 Analysis: Fiber Axial Strain ---
lines = np.memmap(VIEWER_DIR / "fiber_lines.u32", dtype=np.uint32, mode="r").reshape(-1, 2)
fp = np.memmap(VIEWER_DIR / "fiber_pos.f32", dtype=np.float32, mode="r",
               shape=tuple(manifest["files"]["fiber_pos"]["shape"]))
fs = np.memmap(VIEWER_DIR / "fiber_status.u8", dtype=np.uint8, mode="r",
               shape=tuple(manifest["files"]["fiber_status"]["shape"]))

p0_0 = fp[0, lines[:, 0]]
p0_1 = fp[0, lines[:, 1]]
L0 = np.linalg.norm(p0_1 - p0_0, axis=1)

q3_fiber = {}
for f_idx, t_name in [(20, "10us"), (40, "20us"), (140, "70us"), (199, "100us")]:
    pt_0 = fp[f_idx, lines[:, 0]]
    pt_1 = fp[f_idx, lines[:, 1]]
    Lt = np.linalg.norm(pt_1 - pt_0, axis=1)
    eps = (Lt - L0) / L0
    alive = (fs[f_idx] == 1)
    eps_al = eps[alive]
    q3_fiber[t_name] = {
        "t_us": float(times_us[f_idx]),
        "alive_count": int(alive.sum()),
        "deleted_count": int((~alive).sum()),
        "strain_min": float(eps_al.min()),
        "strain_median": float(np.median(eps_al)),
        "strain_max": float(eps_al.max()),
        "tensile_count_gt_0p001": int((eps_al > 0.001).sum()),
        "high_tension_gt_0p01": int((eps_al > 0.01).sum()),
        "yielded_gt_0p026": int((eps_al > 0.026).sum()),
        "compressive_count_lt_m0p001": int((eps_al < -0.001).sum())
    }

# Save findings JSON
out_data = {
    "question_1_spatial_temporal": q1_res,
    "question_3_fiber_mechanics": q3_fiber
}
with open(OUT_DIR / "native_viewer_analysis.json", "w") as f:
    json.dump(out_data, f, indent=2)

print("Saved native_viewer_analysis.json successfully.")

# --- Generate Figures ---

# Figure 1: Deletion map vs radius and depth
plt.figure(figsize=(9, 6), dpi=200)
del_mask_plot = (has_deleted)
sc = plt.scatter(r[del_mask_plot] * 1e3, depth[del_mask_plot] * 1e3,
                 c=del_times[del_mask_plot], cmap="plasma_r", s=4, alpha=0.8,
                 vmin=0, vmax=100)
plt.axvline(R_BALL * 1e3, color="black", linestyle="--", linewidth=1.5, label=f"Ball Radius ({R_BALL*1e3:.2f} mm)")
plt.axvline(1.2 * R_BALL * 1e3, color="gray", linestyle=":", linewidth=1.2, label=f"Annulus Boundary ({1.2*R_BALL*1e3:.2f} mm)")
plt.gca().invert_yaxis()
plt.xlabel("Radial Distance from Impact Axis $r$ (mm)", fontsize=11)
plt.ylabel("Depth below Top Surface (mm)", fontsize=11)
plt.title("Spatial Distribution & Timing of Matrix Host Deletion (Native Deck)", fontsize=12, pad=10)
cbar = plt.colorbar(sc)
cbar.set_label(r"Deletion Time ($\mu$s)", fontsize=10)
plt.legend(loc="lower right")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
plt.savefig(OUT_DIR / "deletion_map_radius_depth.png")
plt.close()

# Figure 2: Deleted count vs time (Under ball vs Annulus vs Outer plate)
plt.figure(figsize=(8, 5), dpi=200)
t_eval = [r["t_us"] for r in timeline]
cnt_tot = [r["total_deleted"] for r in timeline]
cnt_ball = [r["under_ball"] for r in timeline]
cnt_ann = [r["annulus"] for r in timeline]
cnt_out = [r["outer"] for r in timeline]

plt.plot(t_eval, cnt_tot, "k-o", label="Total Deleted Hosts", linewidth=2)
plt.plot(t_eval, cnt_ball, "r-s", label=f"Under Ball (r <= {R_BALL*1e3:.2f} mm)", linewidth=1.8)
plt.plot(t_eval, cnt_ann, "g-^", label=f"Annulus ({R_BALL*1e3:.2f} < r <= {1.2*R_BALL*1e3:.2f} mm)", linewidth=1.5)
plt.plot(t_eval, cnt_out, "b-d", label=f"Outer Plate (r > {1.2*R_BALL*1e3:.2f} mm)", linewidth=1.8)
plt.axvline(40.0, color="orange", linestyle="--", label=r"Perforation of Back Face (~40 $\mu$s)")
plt.xlabel(r"Time ($\mu$s)", fontsize=11)
plt.ylabel("Number of Deleted Hosts", fontsize=11)
plt.title("Progression of Matrix Host Deletion by Radial Zone", fontsize=12, pad=10)
plt.legend(loc="upper left")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
plt.savefig(OUT_DIR / "deleted_count_vs_time.png")
plt.close()

# Figure 3: Deletion fraction per ply and per layer
plt.figure(figsize=(10, 5), dpi=200)
plies = list(range(1, 21))
rates_l0 = [100 * ((ply_idx == p) & (sublayer == 0) & is_del100).sum() / ((ply_idx == p) & (sublayer == 0)).sum() for p in plies]
rates_l1 = [100 * ((ply_idx == p) & (sublayer == 1) & is_del100).sum() / ((ply_idx == p) & (sublayer == 1)).sum() for p in plies]
rates_l2 = [100 * ((ply_idx == p) & (sublayer == 2) & is_del100).sum() / ((ply_idx == p) & (sublayer == 2)).sum() for p in plies]

width = 0.25
x = np.arange(1, 21)
plt.bar(x - width, rates_l0, width, label="Layer 0 (Bottom non-fiber)", color="#3498db")
plt.bar(x, rates_l1, width, label="Layer 1 (Middle fiber-bearing)", color="#e74c3c")
plt.bar(x + width, rates_l2, width, label="Layer 2 (Top non-fiber)", color="#2ecc71")

plt.xlabel("Ply Number (Ply 1 = Bottom/Back Face, Ply 20 = Top/Impact Face)", fontsize=11)
plt.ylabel("Deletion Fraction (%)", fontsize=11)
plt.title(r"Matrix Deletion Fraction per Sub-layer Across Plies at 100 $\mu$s", fontsize=12, pad=10)
plt.xticks(x)
plt.legend(loc="upper right")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
plt.savefig(OUT_DIR / "per_ply_sublayer_deletion.png")
plt.close()

# Figure 4: Fiber Axial Strain Distribution
plt.figure(figsize=(8, 5), dpi=200)
pt_0 = fp[199, lines[:, 0]]
pt_1 = fp[199, lines[:, 1]]
Lt = np.linalg.norm(pt_1 - pt_0, axis=1)
eps_100 = (Lt - L0) / L0
alive_100 = (fs[199] == 1)
eps_active = eps_100[alive_100]

# Clip for histogram display
plt.hist(eps_active * 100, bins=80, range=(-1.0, 2.5), color="#2c3e50", edgecolor="white", alpha=0.8)
plt.axvline(0.0, color="gray", linestyle="-", linewidth=1)
plt.axvline(2.6, color="red", linestyle="--", linewidth=1.5, label=r"Yield Strain ($\epsilon_y \approx 2.6\%$)")
plt.axvline(3.91, color="darkred", linestyle=":", linewidth=1.5, label=r"Fracture Strain ($\epsilon_f = 3.91\%$)")
plt.xlabel(r"Axial Strain $\epsilon_{axial}$ (%)", fontsize=11)
plt.ylabel("Number of Fiber Elements", fontsize=11)
plt.yscale("log")
plt.title(r"Fiber Axial Strain Distribution at 100 $\mu$s (524,157 Alive Fibers)", fontsize=12, pad=10)
plt.legend(loc="upper right")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
plt.savefig(OUT_DIR / "fiber_strain_distribution.png")
plt.close()

print("All figures successfully generated in outbox/T-054/")
