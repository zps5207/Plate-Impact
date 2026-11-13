#!/usr/bin/env python3
"""build_t060_reports.py

Builds all missing HTML reports since bt2 (4 study reports) plus the timeline index page
documenting the evolution of knowledge across the Plate Impact project.

Reports generated:
  1. VALS_BT3_BALL_TESTS_REPORT.html
  2. VALS_BALL_SIZE_FIX_REPORT.html
  3. NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html
  4. FIBER_HOST_CONTACT_REPORT.html
  5. REPORTS_INDEX.html

Usage:
  python build_t060_reports.py [out_dir]

Defaults to writing reports into the directory containing this script (agents/drafter/outbox/T-060).
If an out_dir argument is provided, writes reports there.
"""

import os
import sys
import json
import base64
import io
import re
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Path Resolution
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

def find_repo_root():
    curr = SCRIPT_DIR
    for _ in range(6):
        if (curr / "Meshing").is_dir() and (curr / "reports").is_dir():
            return curr
        curr = curr.parent
    # Fallback to current working directory
    cwd = Path.cwd()
    if (cwd / "Meshing").is_dir():
        return cwd
    if (cwd.parent.parent / "Meshing").is_dir():
        return cwd.parent.parent
    return SCRIPT_DIR.parents[3]

ROOT = find_repo_root()

# Determine output directory
if len(sys.argv) > 1:
    OUT_DIR = Path(sys.argv[1]).resolve()
else:
    OUT_DIR = SCRIPT_DIR

OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"[*] Repository root: {ROOT}")
print(f"[*] Output directory: {OUT_DIR}")

# -----------------------------------------------------------------------------
# Styling and CSS
# -----------------------------------------------------------------------------
COMMON_CSS = """
:root {
  --bg: #ffffff;
  --fg: #1c1c1c;
  --mut: #666666;
  --line: #dddddd;
  --card-bg: #f8f9fa;
  --accent: #1f77b4;
  --accent-light: rgba(31, 119, 180, 0.1);
  --success: #28a745;
  --warn-bg: #fff3cd;
  --warn-border: #ffeeba;
  --warn-fg: #856404;
  --err-bg: #f8d7da;
  --err-border: #f5c6cb;
  --err-fg: #721c24;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16181c;
    --fg: #e8e8e8;
    --mut: #a0a0a0;
    --line: #333333;
    --card-bg: #1f2328;
    --accent: #58a6ff;
    --accent-light: rgba(88, 166, 255, 0.15);
    --warn-bg: #2d2613;
    --warn-border: #594716;
    --warn-fg: #e3b341;
    --err-bg: #2e1a1e;
    --err-border: #67222a;
    --err-fg: #f85149;
  }
}
body {
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 1150px;
  margin: 0 auto;
  padding: 28px 20px;
}
h1 { font-size: 1.75rem; line-height: 1.25; margin-bottom: 0.5rem; }
h2 { font-size: 1.35rem; margin-top: 2.2rem; border-bottom: 1px solid var(--line); padding-bottom: 6px; }
h3 { font-size: 1.1rem; margin-top: 1.4rem; color: var(--fg); }
p { margin: 0.8rem 0; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.88rem; }
td, th { border-bottom: 1px solid var(--line); padding: 7px 10px; text-align: left; }
th { color: var(--mut); font-weight: 600; background: var(--card-bg); }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
img { max-width: 100%; height: auto; border-radius: 6px; }
video { width: 100%; border-radius: 6px; border: 1px solid var(--line); background: #000; }
figure { margin: 16px 0; }
figcaption { color: var(--mut); font-size: 0.82rem; margin-top: 6px; text-align: center; }
.note { color: var(--mut); font-size: 0.9rem; }
.card { background: var(--card-bg); border: 1px solid var(--line); border-radius: 6px; padding: 16px 20px; margin: 16px 0; }
.corr { border: 1px solid #c0392b; background: rgba(192, 57, 43, 0.08); padding: 12px 16px; border-radius: 6px; margin: 16px 0; }
.warn { border: 1px solid var(--warn-border); background: var(--warn-bg); color: var(--warn-fg); padding: 12px 16px; border-radius: 6px; margin: 16px 0; }
.placeholder { border: 2px dashed var(--accent); background: var(--accent-light); padding: 16px 20px; border-radius: 6px; margin: 20px 0; }
.badge { display: inline-block; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; border-radius: 4px; text-transform: uppercase; }
.badge-done { background: #28a745; color: #fff; }
.badge-warn { background: #ffc107; color: #000; }
.badge-pending { background: #17a2b8; color: #fff; }
.badge-crash { background: #dc3545; color: #fff; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 16px; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
code { background: rgba(127, 127, 127, 0.15); padding: 2px 5px; border-radius: 4px; font-size: 0.88em; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
ul, ol { padding-left: 24px; margin: 0.6rem 0; }
li { margin: 0.35rem 0; }
"""

def b64fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def read_b64(path):
    p = ROOT / path if not Path(path).is_absolute() else Path(path)
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode("ascii")
    return None

def video_player_or_placeholder(video_path, caption, label=""):
    """Embed video if present, or provide descriptive placeholder if pending."""
    b64 = read_b64(video_path)
    if b64:
        return f'''<figure>
  <video controls autoplay loop muted playsinline src="data:video/mp4;base64,{b64}"></video>
  <figcaption><strong>{label}</strong> {caption}</figcaption>
</figure>'''
    else:
        return f'''<div class="card" style="text-align:center; padding: 24px;">
  <p><strong>[Video Pending T-058 Rendering]</strong></p>
  <p class="note">Expected target: <code>{video_path}</code></p>
  <p class="note">{caption}</p>
</div>'''

def render_standard_video_panel(run_id, deck_name):
    """Render the standard 6 video block (status/wire x iso/side/sidev) with refiner video checks."""
    refiner_video_dir = ROOT / "agents" / "refiner" / "outbox" / "T-058" / "videos"
    report_video_dir = ROOT / "reports"
    
    views = [
        ("status", "sidev", "Solid STATUS, symmetry plane vertical (plate vertical, ball travels left to right)"),
        ("wire", "sidev", "Wireframe with fibers, symmetry plane vertical"),
        ("status", "iso", "Solid STATUS, isometric view"),
        ("wire", "iso", "Wireframe with fibers, isometric view"),
        ("status", "side", "Solid STATUS, symmetry plane horizontal"),
        ("wire", "side", "Wireframe with fibers, symmetry plane horizontal"),
    ]
    
    cells = []
    any_found = False
    for p, v, desc in views:
        fname = f"{run_id}_{p}_{v}.mp4"
        ref_path = refiner_video_dir / fname
        rep_path = report_video_dir / fname
        
        target = None
        if ref_path.exists():
            target = ref_path
        elif rep_path.exists():
            target = rep_path
            
        if target:
            any_found = True
            b64 = base64.b64encode(target.read_bytes()).decode("ascii")
            cells.append(f'''<figure>
  <video controls loop muted playsinline preload="metadata" src="data:video/mp4;base64,{b64}"></video>
  <figcaption><code>{p}_{v}</code>: {desc}</figcaption>
</figure>''')
        else:
            cells.append(f'''<div class="card" style="padding:14px; font-size:0.85rem;">
  <strong><code>{p}_{v}</code></strong>
  <p class="note" style="margin:4px 0;">{desc}</p>
  <p class="note" style="color:var(--mut); margin:0;">Status: Pending T-058 rendering (<code>{fname}</code>)</p>
</div>''')

    status_note = "" if any_found else '<p class="note"><em>Note: All 6 standard render videos for this run are currently pending T-058 execution by the refiner agent.</em></p>'
    return f"""<div class="video-grid" style="margin:16px 0;">
  {status_note}
  <div class="grid-3">
    {''.join(cells)}
  </div>
</div>"""

# -----------------------------------------------------------------------------
# 1. VALS_BT3_BALL_TESTS_REPORT.html
# -----------------------------------------------------------------------------
def build_bt3_report():
    print("[*] Generating VALS_BT3_BALL_TESTS_REPORT.html...")
    
    r3_dir = ROOT / "Meshing" / "vals-plywise-balltests3" / "results"
    
    # Load JSON data
    d1 = json.load(open(r3_dir / "d1_fullfix_extract.json"))
    d2 = json.load(open(r3_dir / "d2_elastic_extract.json"))
    d4 = json.load(open(r3_dir / "d4_weldox_100us_extract.json"))
    d5 = json.load(open(r3_dir / "d5_rigid_100us_extract.json"))
    d6 = json.load(open(r3_dir / "d6_rigid_matched_100us_extract.json"))
    d7 = json.load(open(r3_dir / "d7_brittle_fiber_100us_extract.json"))
    
    # Inversion data
    inv_bt2 = json.load(open(ROOT / "reports" / "bt2_inversion.json"))
    inv_b4 = json.load(open(ROOT / "reports" / "inv_alive_b4.json"))
    inv_c2 = json.load(open(ROOT / "reports" / "inv_alive_c2.json"))
    
    # Generate Chart 1: Energy & Deletion Overview
    fig, axs = plt.subplots(1, 4, figsize=(16, 3.6))
    
    runs_data = [
        ("d1_fullfix", d1, "#1f77b4", "-"),
        ("d2_elastic", d2, "#2ca02c", "-"),
        ("d4_weldox_100us", d4, "#d62728", "-"),
        ("d5_rigid_100us", d5, "#9467bd", "-"),
        ("d6_rigid_matched_100us", d6, "#8c564b", "-"),
        ("d7_brittle_fiber_100us", d7, "#e377c2", "--"),
    ]
    
    for name, data, col, ls in runs_data:
        etot = np.array(data["energy"]["ETOTAL"])
        allke = np.array(data["energy"]["ALLKE"])
        axs[0].plot(etot[:, 0]*1e6, etot[:, 1], color=col, ls=ls, label=name)
        axs[1].plot(allke[:, 0]*1e6, allke[:, 1], color=col, ls=ls)
        
        st = data["status"]
        t_st = [s["t"]*1e6 for s in st]
        host_del = [s["cnt"]["host"][1] for s in st]
        fiber_del = [s["cnt"]["fiber"][1] for s in st]
        axs[2].plot(t_st, host_del, color=col, ls=ls)
        axs[3].plot(t_st, fiber_del, color=col, ls=ls)
        
    axs[0].set_title("Total Energy ETOTAL (J)", fontsize=10)
    axs[1].set_title("Kinetic Energy ALLKE (J)", fontsize=10)
    axs[2].set_title("Host Deletions (of 80,500)", fontsize=10)
    axs[3].set_title("Fiber Deletions (of 206,930)", fontsize=10)
    
    for ax in axs:
        ax.set_xlabel("Time (us)", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    axs[0].legend(fontsize=7, loc="lower left")
    
    chart1_b64 = b64fig(fig)
    
    # Generate Chart 2: T-051 Inversion Alive vs Dead Analysis
    fig2, axs2 = plt.subplots(1, 2, figsize=(11, 3.4))
    t_b4 = np.array(inv_b4["t"])
    axs2[0].plot(t_b4, inv_b4["dead_inv"], color="#d62728", label="Inverted Dead (Ghost) Elements")
    axs2[0].plot(t_b4, inv_b4["alive_inv"], color="#2ca02c", lw=2, label="Inverted Alive Elements (Max 1)")
    axs2[0].set_title("b4_d4fix (1000 m/s): Inversion vs Status", fontsize=10)
    axs2[0].set_xlabel("Time (us)", fontsize=9)
    axs2[0].set_ylabel("Element Count", fontsize=9)
    axs2[0].grid(True, alpha=0.3)
    axs2[0].legend(fontsize=8)
    
    t_c2 = np.array(inv_c2["t"])
    axs2[1].plot(t_c2, inv_c2["dead_inv"], color="#d62728", label="Inverted Dead (Ghost) Elements")
    axs2[1].plot(t_c2, inv_c2["alive_inv"], color="#2ca02c", lw=2, label="Inverted Alive Elements (Max 1)")
    axs2[1].set_title("c2_truss_d4_md80 (1000 m/s): Inversion vs Status", fontsize=10)
    axs2[1].set_xlabel("Time (us)", fontsize=9)
    axs2[1].set_ylabel("Element Count", fontsize=9)
    axs2[1].grid(True, alpha=0.3)
    axs2[1].legend(fontsize=8)
    
    chart2_b64 = b64fig(fig2)
    
    # Embed existing media
    img_bt3_comp = read_b64("reports/bt3_compare.png")
    img_t052_resp = read_b64("reports/t052_plate_response.png")
    img_t052_prof = read_b64("reports/t052_plate_profiles.png")
    
    vid_bt3_comp = read_b64("reports/bt3_compare.mp4")
    vid_d4 = read_b64("reports/d4_weldox_100us.mp4")
    vid_d6 = read_b64("reports/d6_rigid_matched_100us.mp4")
    
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Vals BT3 Ball Tests Report</title>
  <style>{COMMON_CSS}</style>
</head>
<body>
  <h1>Vals Ball Tests Suite 3 (bt3): Projectile Erosion, Inversion Resolution, and 100 &mu;s Perforation</h1>
  <p class="note"><strong>Author:</strong> Drafter (T-060) &middot; <strong>Date:</strong> 2026-10-31 &middot; <strong>Decks:</strong> <code>Meshing/vals-plywise-balltests3/</code> &middot; <strong>ROAR directory:</strong> <code>ctv/bt3/</code></p>

  <div class="corr">
    <strong>Resolution of the "Ball Inversion" Mystery (T-051 / T-052 Investigation):</strong><br>
    In prior bt1 and bt2 reports, the metric "ball hexes inverted" was computed purely from nodal coordinates across all ball elements without filtering by Abaqus element <code>STATUS</code>. Detailed extraction of ODB status fields in T-051 (jobs 56845585 and 56845586) proved that <strong>609 of 610 hexes in b4</strong> and <strong>618 of 619 hexes in c2</strong> were <em>already deleted</em> when they first showed a non-positive Jacobian. At 12 &mu;s, exactly <strong>0 to 1 live ball elements are inverted</strong>. The perceived inversion was a post-deletion ghost tracking artifact of orphan nodes tumbling in space, not live element breakdown. Furthermore, ODB energy histories were corrected by a factor of 1000 (quarter-ball kinetic energy starts at 3.55 kJ, not 3.55 J).
  </div>

  <h2>1. Purpose & Overview</h2>
  <p>The bt3 test suite was designed to resolve the severe steel ball erosion and deformation observed during 1000 m/s impact onto the 20-ply Valerie plate model. Prior runs (vp5) showed substantial erosion of ball elements (3,161 of 18,500 deleted by 70 &mu;s, 17.1%), and in d4_weldox_100us ball erosion reached 17.3% (3,206 of 18,500 elements) at 100 &mu;s. bt3 evaluated:
  (1) Combined numerical fixes from coupon testing (O-grid, enhanced hourglass, distortion control, thin fiber contact in <code>d1_fullfix</code>);
  (2) Elastic non-eroding ball models (<code>d2_elastic</code> and <code>d3_elastic_100us</code>);
  (3) Johnson-Cook rate-dependent Weldox 460E steel with energy-based damage evolution (<code>d4_weldox_100us</code>);
  (4) Rigid body ball representations (<code>d5_rigid_100us</code>, <code>d6_rigid_matched_100us</code>, and <code>d7_brittle_fiber_100us</code>); and
  (5) 70 &micro;s native reference <code>vr_native</code>.</p>

  <h2>2. T-052 12 &mu;s Coupon Matrix Findings</h2>
  <p>Prior to full 20-ply runs, 12 single-variable coupon decks were tested in ROAR <code>ctv/t052/</code> (jobs 56846110&ndash;112, 56847359&ndash;360; source: <code>verification/roar/ball_tests/t052/</code> and project notes):</p>
  <table>
    <thead>
      <tr>
        <th>Coupon Deck</th>
        <th>Modification vs Baseline</th>
        <th class="n">Ball Deleted (%)</th>
        <th class="n">Alive Inverted</th>
        <th>Key Observation / Numerical Behavior</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>t052_01_ref</td><td>Reference truss D4</td><td class="n">5.6%</td><td class="n">0</td><td>Baseline coupon erosion rate; 0 live inverted elements.</td></tr>
      <tr><td>t052_02_dist</td><td>Distortion control = YES (ratio 0.1)</td><td class="n">5.6%</td><td class="n">0</td><td>No measurable effect on ball deletion.</td></tr>
      <tr><td>t052_03_enh_hg</td><td>Hourglass = ENHANCED</td><td class="n">6.0%</td><td class="n">0</td><td>Slight increase in deletion; prevents corner folding.</td></tr>
      <tr><td>t052_04_visc_hg</td><td>Hourglass = VISCOUS</td><td class="n">8.5%</td><td class="n">0</td><td>ETOTAL jumped +38%, premature deletion from 0.6 &mu;s (unstable).</td></tr>
      <tr><td>t052_05_no_del</td><td>Element deletion disabled</td><td class="n">0.0%</td><td class="n">254 (1.5%)</td><td>Ball cannot delete; 254 elements invert alive under extreme compression.</td></tr>
      <tr><td>t052_06_thin_fc</td><td>Fiber contact thickness = 0.05 mm</td><td class="n">4.9%</td><td class="n">0</td><td>Slight reduction in localized contact shock.</td></tr>
      <tr><td>t052_07_no_fc</td><td>Fiber contact omitted</td><td class="n">3.8%</td><td class="n">0</td><td>Modest reduction in erosion; ball-host contact dominates.</td></tr>
      <tr><td>t052_08_ogrid</td><td>Uniform 64-hex O-grid ball mesh</td><td>result not recorded</td><td class="n">0</td><td>Removes pole wedges; initial solve ODB corrupted; rerun 56847359 completed but result was never recorded in project notes.</td></tr>
      <tr><td>t052_09_plain</td><td>Plain elastic plate (no fibers/cohesion)</td><td class="n">9.5%</td><td class="n">0</td><td>Highest deletion! Proves ball erosion is driven by shock on steel, not fiber geometry.</td></tr>
      <tr><td>t052_10_comb</td><td>Combined best practice (02+03+06+08)</td><td class="n">2.2%</td><td class="n">0</td><td>First deletion delayed to 2.1 &mu;s; best deformable configuration.</td></tr>
      <tr><td>t052_11_elastic</td><td>Pure elastic steel (E = 203 GPa)</td><td class="n">0.0%</td><td class="n">Crash @ 6.5 &mu;s</td><td>Solver died: deformation speed exceeded wave speed in nose hexes.</td></tr>
      <tr><td>t052_12_stiff</td><td>Stiff elastic ball (10&times; E: 2.03 TPa)</td><td class="n">0.0%</td><td class="n">0</td><td>Stable to 12 &mu;s; 0 alive-inv; plate back-face <i>u<sub>z</sub></i> = -2.8 mm; plate hosts deleted 16.7% (257/1,536 coupon hosts, t052_12_ball_stiff_elastic_plate.npz), fibers 0/1,632 (from notes and <code>t052_plate_response.png</code>).</td></tr>
    </tbody>
  </table>

  <h3>Inversion Proof: Ghost Elements vs Live Elements</h3>
  <figure>
    <img alt="Inversion Proof" src="data:image/png;base64,{chart2_b64}">
    <figcaption><strong>Figure 1:</strong> Evaluation of element status for inverted hexes in <code>b4_d4fix</code> and <code>c2_truss_d4_md80</code>. Across all frames, inverted elements are already deleted ghosts (red); live inverted elements (green) remain zero to one.</figcaption>
  </figure>

  <h2>3. Full 20-Ply Decks Setup</h2>
  <table>
    <thead>
      <tr>
        <th>Deck Name</th>
        <th>ROAR Job ID</th>
        <th>Ball Formulation</th>
        <th>Fiber Model</th>
        <th>Matrix Model</th>
        <th>Step Time</th>
        <th>Wall Time</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr><td><code>d1_fullfix</code></td><td>56846110 (notes)</td><td>Deformable O-grid, JC D4, Enh HG</td><td>T3D2 Truss</td><td>C3D8R, maxdeg 0.8</td><td>12 &mu;s</td><td>1.5 h (notes)</td><td><span class="badge badge-done">Completed</span></td></tr>
      <tr><td><code>d2_elastic</code></td><td>56847359 (notes)</td><td>Elastic only (E = 203 GPa)</td><td>T3D2 Truss</td><td>C3D8R, maxdeg 0.8</td><td>12 &mu;s</td><td>1.5 h (notes)</td><td><span class="badge badge-done">Completed</span></td></tr>
      <tr><td><code>d3_elastic_100us</code></td><td>56849548</td><td>Elastic only (E = 203 GPa)</td><td>T3D2 Truss</td><td>C3D8R, maxdeg 0.8</td><td>100 &mu;s</td><td>29 min</td><td><span class="badge badge-crash">Crashed @ 22.8 &mu;s</span></td></tr>
      <tr><td><code>d4_weldox_100us</code></td><td>56851073</td><td>Weldox 460E JC, Gf = 54.9 J/m&sup2;</td><td>T3D2 Truss</td><td>C3D8R, maxdeg 0.8</td><td>100 &mu;s</td><td>2h 13m</td><td><span class="badge badge-done">Completed</span></td></tr>
      <tr><td><code>d5_rigid_100us</code></td><td>ctv/bt3 (notes)</td><td>Rigid Body (steel density)</td><td>T3D2 Truss</td><td>C3D8R, maxdeg 0.8</td><td>100 &mu;s</td><td>1.8 h (notes)</td><td><span class="badge badge-done">Completed</span></td></tr>
      <tr><td><code>d6_rigid_matched_100us</code></td><td>56873219</td><td>Rigid Body (steel density)</td><td>Ductile energy (1 J/m&sup2;)</td><td>Fracture strain 0.1</td><td>100 &mu;s</td><td>1h 48m</td><td><span class="badge badge-done">Completed</span></td></tr>
      <tr><td><code>d7_brittle_fiber_100us</code></td><td>ctv/bt3 (notes)</td><td>Rigid Body (steel density)</td><td>Elastic-brittle (1e-4)</td><td>Fracture strain 0.1</td><td>100 &mu;s</td><td>1.8 h (notes)</td><td><span class="badge badge-done">Completed</span></td></tr>
    </tbody>
  </table>

  <h2>4. Results & Energy Balance</h2>
  <figure>
    <img alt="BT3 Energy and Deletion Charts" src="data:image/png;base64,{chart1_b64}">
    <figcaption><strong>Figure 2:</strong> Energy histories and element deletion counts across the bt3 simulation suite (data extracted from <code>Meshing/vals-plywise-balltests3/results/*_extract.json</code>).</figcaption>
  </figure>

  <table>
    <thead>
      <tr>
        <th>Run Name</th>
        <th class="n">ALLKE Start (J)</th>
        <th class="n">ALLKE End (J)</th>
        <th class="n">ETOTAL End vs Start</th>
        <th class="n">Ball Deleted (%)</th>
        <th class="n">Host Deleted</th>
        <th class="n">Fibers Deleted</th>
        <th>Source File</th>
      </tr>
    </thead>
    <tbody>
      <tr><td><code>d1_fullfix</code></td><td class="n">3577.2</td><td class="n">3467.0</td><td class="n">-0.30%</td><td class="n">555 / 17,248 (3.2%)</td><td class="n">212</td><td class="n">0</td><td><code>d1_fullfix_extract.json</code></td></tr>
      <tr><td><code>d2_elastic</code></td><td class="n">3546.1</td><td class="n">3333.3</td><td class="n">-0.74%</td><td class="n">0 / 18,500 (0.0%)</td><td class="n">310</td><td class="n">17</td><td><code>d2_elastic_extract.json</code></td></tr>
      <tr><td><code>d3_elastic_100us</code></td><td class="n">3546.1</td><td class="n">not pulled</td><td class="n">-0.90%</td><td class="n">0 / 18,500 (0.0%)</td><td class="n">not pulled</td><td class="n">not pulled</td><td>Project notes (ROAR 56849548: crash @ 22.77 &mu;s, ETOT ratio 0.991, dt 1.03e-9 &rarr; 1e-14 s, extract not pulled)</td></tr>
      <tr><td><code>d4_weldox_100us</code></td><td class="n">3546.1</td><td class="n">3445.6</td><td class="n">-0.65%</td><td class="n">3,206 / 18,500 (17.3%)</td><td class="n">1,443</td><td class="n">47</td><td><code>d4_weldox_100us_extract.json</code></td></tr>
      <tr><td><code>d5_rigid_100us</code></td><td class="n">3546.1</td><td class="n">3139.5</td><td class="n">-3.51%</td><td class="n">0 (Rigid body)</td><td class="n">2,260</td><td class="n">67</td><td><code>d5_rigid_100us_extract.json</code></td></tr>
      <tr><td><code>d6_rigid_matched_100us</code></td><td class="n">3546.1</td><td class="n">3096.6</td><td class="n">-2.22%</td><td class="n">0 (Rigid body)</td><td class="n">1,927</td><td class="n">86</td><td><code>d6_rigid_matched_100us_extract.json</code></td></tr>
      <tr><td><code>d7_brittle_fiber_100us</code></td><td class="n">3546.1</td><td class="n">3119.5</td><td class="n">-2.36%</td><td class="n">0 (Rigid body)</td><td class="n">1,506</td><td class="n">451</td><td><code>d7_brittle_fiber_100us_extract.json</code></td></tr>
    </tbody>
  </table>

  <h2>5. Plate Response & Deformation Profiles</h2>
  <div class="grid-2">
    <div>
      <figure>
        <img alt="Plate Response" src="data:image/png;base64,{img_t052_resp}">
        <figcaption><strong>Figure 3:</strong> Plate back-face displacement vs time under deformable, combined, elastic, and stiff projectiles (<code>reports/t052_plate_response.png</code>).</figcaption>
      </figure>
    </div>
    <div>
      <figure>
        <img alt="Plate Profiles" src="data:image/png;base64,{img_t052_prof}">
        <figcaption><strong>Figure 4:</strong> Back-face profile and bulging across the coupon plate (<code>reports/t052_plate_profiles.png</code>).</figcaption>
      </figure>
    </div>
  </div>

  <h2>6. Video Evidence</h2>
  <div class="grid-2">
    {video_player_or_placeholder("reports/bt3_compare.mp4", "Direct side-by-side comparison of d1_fullfix (left) vs baseline c2 (right) at 12 us.", "bt3 Comparison")}
    {video_player_or_placeholder("reports/d4_weldox_100us.mp4", "Perforation of 25.4 mm plate by Weldox 460E steel ball out to 100 us. Severe ball erosion plateaus at 17.3%.", "d4 Weldox 100 us")}
  </div>
  <div style="margin-top:16px;">
    {video_player_or_placeholder("reports/d6_rigid_matched_100us.mp4", "Rigid ball perforation with Valerie paper matched materials (Table 2). Dedicated study report available: <a href='D6_PAPER_MATERIALS_VIDEO.html'>D6_PAPER_MATERIALS_VIDEO.html</a>.", "d6 Rigid Matched 100 us")}
  </div>

  <h3>Standard Render Passes (Status & Wireframe)</h3>
  {render_standard_video_panel("d6", "d6_rigid_matched_100us")}

  <h2>7. Findings & Conclusions</h2>
  <ul>
    <li><strong>Deformable Ball Deletion is Governed by Shock Physics:</strong> Numerical tweaks (O-grid, enhanced hourglass, thin contact) delay deletion slightly (d1: 3.2% vs c2: 4.3%), but cannot halt severe erosion. The plain elastic plate test (t052_09) showed 9.5% deletion, proving that the ball erosion is an intrinsic consequence of the Johnson-Cook steel model under gigapascal contact shock.</li>
    <li><strong>Pure Elastic Ball Fails Numerically at High Speeds:</strong> In both coupon t052_11 (6.5 &mu;s) and full deck d3_elastic_100us (22.77 &mu;s), the elastic ball without a damage cutoff crashed when the physical deformation speed exceeded the dilatational wave speed ($c_d \approx 5900$ m/s), driving time increments down to $10^{-14}$ s.</li>
    <li><strong>Low Plate Resistance / Model Kinetic Energy Retention:</strong> At 100 &mu;s, total model kinetic energy retention (ALLKE end / ALLKE start) is 97.2% in d4 (3445.6 J / 3546.1 J), 88.5% in d5 (3139.5 J / 3546.1 J), and 87.3% in d6 (3096.6 J / 3546.1 J). Note that ALLKE is the total kinetic energy of the entire model (including ejected plate debris), not solely the projectile kinetic energy. Regarding perforation: in d4, project notes record 91&ndash;93% of ball nodes past the plate back face (<i>z</i> &lt; -25.4 mm) by 50 &mu;s (verified in <code>reports/d4_weldox_100us.mp4</code>); for d5 and d6, full perforation was not independently re-checked in this report.</li>
    <li><strong>Rigid Ball is the Physically Robust Solution:</strong> Consistent with Valerie's original HB26 Dyneema experimental setup, treating the hardened steel ball as an analytical or element-based rigid body eliminates artificial erosion modes and allows clean modeling of composite damage and delamination.</li>
  </ul>

  <h2>8. What Changed Next</h2>
  <p>During analysis of the 3.55 kJ energy values in bt3, cross-examination against Valerie's experimental paper revealed that <code>Meshing/Vals.inp</code> used an oversized projectile: <strong>radius 9.525 mm (3/4 in diameter) instead of 3/8 in diameter</strong>. This critical discovery led directly to the ball-size correction suite documented in <a href="VALS_BALL_SIZE_FIX_REPORT.html">VALS_BALL_SIZE_FIX_REPORT.html</a>.</p>

  <h2>9. Not Verified / Open Questions</h2>
  <ul>
    <li>The d3 crash extraction NPZ (584 MB) remains on ROAR scratch storage; local extraction only captured status up to 22.8 &mu;s.</li>
    <li>Triaxiality and plastic strain invariants inside the core of the Weldox projectile were not saved in field output due to preselected variable limits.</li>
  </ul>
</body>
</html>
"""
    out_file = OUT_DIR / "VALS_BT3_BALL_TESTS_REPORT.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[*] Wrote {out_file} ({len(html)//1024} KB)")

# -----------------------------------------------------------------------------
# 2. VALS_BALL_SIZE_FIX_REPORT.html
# -----------------------------------------------------------------------------
def build_ballfix_report():
    print("[*] Generating VALS_BALL_SIZE_FIX_REPORT.html...")
    
    r_dir = ROOT / "Meshing" / "vals-plywise-ballfix" / "results"
    native_data = json.load(open(r_dir / "vrb_native_extract.json"))
    vuel_data = json.load(open(r_dir / "vrb_vuel_extract.json"))
    
    # Generate Charts
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.6))
    
    # Energy
    etot_nat = np.array(native_data["energy"]["ETOTAL"])
    allke_nat = np.array(native_data["energy"]["ALLKE"])
    etot_vuel = np.array(vuel_data["energy"]["ETOTAL"])
    allke_vuel = np.array(vuel_data["energy"]["ALLKE"])
    
    axs[0].plot(etot_nat[:, 0]*1e6, etot_nat[:, 1], color="#1f77b4", label="Native ETOTAL")
    axs[0].plot(allke_nat[:, 0]*1e6, allke_nat[:, 1], color="#1f77b4", ls="--", label="Native ALLKE")
    axs[0].plot(etot_vuel[:, 0]*1e6, etot_vuel[:, 1], color="#d62728", label="VUEL ETOTAL")
    axs[0].plot(allke_vuel[:, 0]*1e6, allke_vuel[:, 1], color="#d62728", ls="--", label="VUEL ALLKE")
    axs[0].set_title("Energy Balance (J)", fontsize=10)
    axs[0].legend(fontsize=7)
    
    # Host Deletion
    st_nat = native_data["status"]
    st_vuel = vuel_data["status"]
    axs[1].plot([s["t"]*1e6 for s in st_nat], [s["cnt"]["host"][1] for s in st_nat], color="#1f77b4", label="Native (of 80,500)")
    # VUEL tracks 2 sub-elements per host cell
    axs[1].plot([s["t"]*1e6 for s in st_vuel], [s["cnt"]["host"][1]/2.0 for s in st_vuel], color="#d62728", ls="--", label="VUEL Host Cells (of 80,500)")
    axs[1].set_title("Host Cells Deleted", fontsize=10)
    axs[1].legend(fontsize=7)
    
    # Delamination
    cs_nat = native_data["cs"]
    cs_vuel = vuel_data["cs"]
    axs[2].plot([c["t"]*1e6 for c in cs_nat], [c["ge50"] for c in cs_nat], color="#1f77b4", label="Native CSDMG >= 0.5")
    axs[2].plot([c["t"]*1e6 for c in cs_nat], [c["ge99"] for c in cs_nat], color="#1f77b4", ls=":", label="Native CSDMG >= 0.99")
    axs[2].plot([c["t"]*1e6 for c in cs_vuel], [c["ge50"] for c in cs_vuel], color="#d62728", label="VUEL CSDMG >= 0.5")
    axs[2].plot([c["t"]*1e6 for c in cs_vuel], [c["ge99"] for c in cs_vuel], color="#d62728", ls=":", label="VUEL CSDMG >= 0.99")
    axs[2].set_title("Cohesive Interface Damage", fontsize=10)
    axs[2].legend(fontsize=6)
    
    for ax in axs:
        ax.set_xlabel("Time (us)", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
        
    chart_b64 = b64fig(fig)
    
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Vals Ball Size Error & Correction Report</title>
  <style>{COMMON_CSS}</style>
</head>
<body>
  <h1>Vals Projectile Geometry Correction: Resolving the 3/4-inch vs 3/8-inch Discrepancy (vrb_native &amp; vrb_vuel)</h1>
  <p class="note"><strong>Author:</strong> Drafter (T-060) &middot; <strong>Date:</strong> 2026-11-02 &middot; <strong>Decks:</strong> <code>Meshing/vals-plywise-ballfix/</code> &middot; <strong>ROAR directory:</strong> <code>ctv/bt3/vrb_native</code> and <code>vrb_vuel</code></p>

  <div class="corr">
    <strong>Discovery of the 8&times; Projectile Mass Error:</strong><br>
    On 2026-11-02, an audit against Valerie's experimental paper (<code>References/Valerie's Paper.pdf</code>, HB26 Dyneema plate impact) revealed a fundamental discrepancy in the root input deck <code>Meshing/Vals.inp</code>. The Ball part in <code>Vals.inp</code> was defined with a radius of $R = 9.525$ mm ($3/8$ in radius, i.e. $3/4$ in diameter). The experiment and paper explicitly specify a <strong>3/8-inch diameter ball</strong> ($R = 4.7625$ mm). Because spherical volume scales as $R^3$, all previous Vals-derived models (vp3, vp4, vp5, bt1, bt2, bt3 d1&ndash;d7, vr_native) used a projectile with <strong>eight times the true mass and kinetic energy</strong> (3546 J vs 469 J in quarter model).
  </div>

  <h2>1. Purpose & Physical Impact</h2>
  <p>The purpose of the <code>vals-plywise-ballfix</code> study was to correct the projectile geometry to the true experimental 3/8-inch diameter, re-center the projectile with the proper 1.5 mm standoff, apply the experimental impact velocity of 1028 m/s, and evaluate plate penetration response in both native C3D8R and Stage 7 VUEL models.</p>

  <h2>2. Projectile Model Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Parameter</th>
        <th>Oversized Baseline (Vals.inp / bt3)</th>
        <th>Corrected Decks (vrb_native / vrb_vuel)</th>
        <th>Physical Impact / Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Ball Diameter</td><td class="n">19.05 mm (3/4 in)</td><td class="n"><strong>9.525 mm (3/8 in)</strong></td><td>Radius reduced from 9.525 mm to 4.7625 mm.</td></tr>
      <tr><td>Discretization</td><td>C3D8R + C3D6 wedges</td><td><strong>64-hex uniform O-grid</strong></td><td>Element size 1.19 mm matching host mesh size.</td></tr>
      <tr><td>Initial Standoff Gap</td><td class="n">1.475 mm (center z = 11.0 mm)</td><td class="n"><strong>1.500 mm (center z = 6.2625 mm)</strong></td><td>Prevents premature 6 mm flight delay.</td></tr>
      <tr><td>Impact Velocity</td><td class="n">1000 m/s</td><td class="n"><strong>1028 m/s</strong></td><td>Exact experimental impact speed.</td></tr>
      <tr><td>Quarter Ball Mass</td><td class="n">7.09 g</td><td class="n"><strong>0.887 g</strong></td><td>Mass reduced by factor of 8.0&times;.</td></tr>
      <tr><td>Discretized Density</td><td class="n">7850 kg/m&sup3;</td><td class="n"><strong>8406 kg/m&sup3;</strong></td><td>Density scaled to match exact sphere volume.</td></tr>
      <tr><td>Quarter Initial ALLKE</td><td class="n"><strong>3546.1 J</strong></td><td class="n"><strong>469.2 J</strong></td><td>True physical energy is 7.56&times; lower!</td></tr>
      <tr><td>Full Projectile ALLKE</td><td class="n">14.18 kJ</td><td class="n">1.877 kJ</td><td>Full projectile kinetic energy.</td></tr>
    </tbody>
  </table>

  <h2>3. Simulation Results (70 &mu;s Run)</h2>
  <figure>
    <img alt="Ballfix Energy and Deletion Charts" src="data:image/png;base64,{chart_b64}">
    <figcaption><strong>Figure 1:</strong> 70 &mu;s comparison of corrected 3/8-inch ball impact: energy history, host cell deletion, and cohesive interface damage (data from <code>vrb_native_extract.json</code> and <code>vrb_vuel_extract.json</code>).</figcaption>
  </figure>

  <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Oversized Baseline: d6_rigid_matched_100us @ 70 &mu;s</th>
        <th>Corrected vrb_native (1028 m/s)</th>
        <th>Corrected vrb_vuel (1028 m/s)</th>
        <th>Source Reference</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>ROAR Solve Job ID</td><td>56873219</td><td><strong>56952459</strong></td><td><strong>56952463</strong></td><td>ROAR submit logs</td></tr>
      <tr><td>Time Evaluated</td><td class="n">70.0 &mu;s (of 100 &mu;s step)</td><td class="n">70.0 &mu;s</td><td class="n">70.0 &mu;s</td><td>Deck specification</td></tr>
      <tr><td>Initial ALLKE</td><td class="n">3546.1 J</td><td class="n">469.2 J</td><td class="n">469.2 J</td><td>ODB energy history</td></tr>
      <tr><td>Final ALLKE @ 70 &mu;s</td><td class="n">3110.7 J (-12.3%)</td><td class="n">398.3 J (-15.1%)</td><td class="n">348.3 J (-25.8%)</td><td><code>*_extract.json</code></td></tr>
      <tr><td>Final ETOTAL</td><td class="n">3464.2 J (-2.31%)</td><td class="n">439.6 J (-6.3%)</td><td class="n">375.1 J (-20.1%)</td><td><code>*_extract.json</code></td></tr>
      <tr><td>Host Cells Deleted</td><td class="n">1,704 / 80,500 (2.12%)</td><td class="n"><strong>611 / 80,500 (0.76%)</strong></td><td class="n"><strong>611 host eq.* (0.76%)</strong></td><td><code>*_extract.json</code></td></tr>
      <tr><td>Fibers Deleted</td><td class="n">83 / 206,930 (0.040%)</td><td class="n">0 / 206,930</td><td class="n">0 / 206,930</td><td><code>*_extract.json</code></td></tr>
      <tr><td>Cohesion Damage &ge; 0.50</td><td class="n">34,664</td><td class="n">10,157</td><td class="n">13,171</td><td><code>*_extract.json</code></td></tr>
      <tr><td>Cohesion Failed (&ge; 0.99)</td><td class="n">4,790</td><td class="n">1,077</td><td class="n">1,137</td><td><code>*_extract.json</code></td></tr>
    </tbody>
  </table>
  <p class="note">* Note: <code>vrb_vuel</code> tracks 2 sub-elements per host cell (161,000 total sub-elements: 80,500 VUEL + 80,500 ghost C3D8R); 1,222 sub-elements deleted corresponds to 611 host cell pairs (0.76%).</p>

  <h2>4. Standard Video Panel</h2>
  {render_standard_video_panel("vrb", "vrb_native / vrb_vuel")}

  <h2>5. Findings & Architectural Impact</h2>
  <ul>
    <li><strong>Host Deletion Drops Under Realistic Mass:</strong> Host element deletion dropped from 2.12% (1,704 cells in 3/4-inch d6 at 70 &mu;s) to 0.76% (611 cells in 3/8-inch vrb_native), reflecting the lower momentum of the true 3/8-inch sphere.</li>
    <li><strong>Host Deletion Numbers:</strong> Native C3D8R deletes 611 of 80,500 host cells (0.76%). VUEL deletes 1,222 of 161,000 total sub-elements (each host cell is represented by 2 sub-elements: 1 VUEL and 1 ghost C3D8R), corresponding to 611 host cell pairs (0.76%).</li>
    <li><strong>Energy Dissipation Differences:</strong> VUEL exhibits higher total energy loss (-20.1% vs -6.3% in native). This difference remains unexplained / open.</li>
    <li><strong>Adoption as Project Standard:</strong> The 3/8-inch rigid ball at 1028 m/s was adopted immediately as the mandatory baseline for all subsequent NewVals (NV3) decks.</li>
  </ul>

  <h2>6. What Changed Next</h2>
  <p>With the projectile geometry corrected, the project advanced to 3-elements-per-ply meshing (T-053). When these 3-layer decks were run with node-based contact, an unexpected pre-impact overclosure pathology emerged, leading to <a href="NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html">NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html</a>.</p>

  <h2>7. Not Verified / Open Questions</h2>
  <ul>
    <li>Fibers did not delete in either 70 &mu;s run (0 of 206,930), indicating that 70 &mu;s captures the initial indentation and delamination phase rather than full plate exit.</li>
    <li>The original vr_vuel chain (56950156) was cancelled before completion once the ball error was found.</li>
  </ul>
</body>
</html>
"""
    out_file = OUT_DIR / "VALS_BALL_SIZE_FIX_REPORT.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[*] Wrote {out_file} ({len(html)//1024} KB)")

# -----------------------------------------------------------------------------
# 3. NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html
# -----------------------------------------------------------------------------
def build_nv3_report():
    print("[*] Generating NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html...")
    
    elem_dir = ROOT / "Meshing" / "newvals-elemcontact-tt3" / "results"
    elem_data = json.load(open(elem_dir / "nv3_elem_extract.json"))
    
    # Generate Chart
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.6))
    
    # Energies
    for name, col in [("ETOTAL", "#1f77b4"), ("ALLKE", "#2ca02c"), ("ALLIE", "#d62728"), ("ALLDMD", "#9467bd")]:
        if name in elem_data["energy"]:
            a = np.array(elem_data["energy"][name])
            axs[0].plot(a[:, 0]*1e6, a[:, 1], color=col, label=name)
    axs[0].set_title("nv3_elem 100 us Energies (J)", fontsize=10)
    axs[0].legend(fontsize=7)
    
    # Host Deletion
    st = elem_data["status"]
    t_st = [s["t"]*1e6 for s in st]
    host_del = [s["cnt"]["host"][1] for s in st]
    fiber_del = [s["cnt"]["fiber"][1] for s in st]
    
    axs[1].plot(t_st, host_del, color="#d62728", lw=1.8, label="Host Deleted (of 435,000)")
    axs[1].set_title("Host Element Deletions", fontsize=10)
    axs[1].legend(fontsize=7)
    
    # Fiber Deletion
    axs[2].plot(t_st, fiber_del, color="#1f77b4", lw=1.8, label="Fibers Deleted (of 524,180)")
    axs[2].set_title("Fiber Element Deletions", fontsize=10)
    axs[2].legend(fontsize=7)
    
    for ax in axs:
        ax.set_xlabel("Time (us)", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
        
    chart_b64 = b64fig(fig)
    
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>NewVals NV3 Contact Evolution Report</title>
  <style>{COMMON_CSS}</style>
</head>
<body>
  <h1>NewVals NV3 Contact Evolution: Contact Overclosure Pathology, Eroding Element Contact, and Interior Faces</h1>
  <p class="note"><strong>Author:</strong> Drafter (T-060) &middot; <strong>Date:</strong> 2026-11-06 &middot; <strong>Decks:</strong> <code>Meshing/newvals-*/</code> &middot; <strong>ROAR directory:</strong> <code>ctv/bt3/nv3_*</code></p>

  <div class="corr">
    <strong>Discovery of the Contact Thickness Overclosure Pathology:</strong><br>
    When advancing to the 3-elements-per-ply architecture (NV3, 0.423 mm hex thickness), the initial deck <code>nv3_smear</code> suffered catastrophic failure: <strong>27,293 host elements deleted in increment 1</strong>, before the ball ever reached the plate! Investigation revealed that the mesher option <code>--plate-node-contact</code> assigned an automatic contact thickness of 0.2117 mm (half host edge) to all ply nodes. Across cohesive inter-ply interfaces, this artificial thickness caused severe geometric overclosure, triggering immediate matrix crushing prior to projectile impact (t &le; 0.97 &mu;s).
  </div>

  <h2>1. Overview & Architectural Progression</h2>
  <p>The NewVals NV3 series represents the production meshing architecture for the 25.4 mm composite plate: 20 plies with 3 hex elements through the thickness of each ply (435,000 host hexes, 524,180 fiber trusses), paper Table 2 material cards, and the corrected 3/8-inch rigid sphere at 1028 m/s. This study chronicles the transition from flawed node contact to eroding element contact and interior face self-contact:</p>

  <table>
    <thead>
      <tr>
        <th>Simulation Deck</th>
        <th>ROAR Job ID</th>
        <th>Plate Contact Surface</th>
        <th>Assigned Thickness</th>
        <th>Step Time</th>
        <th class="n">Pre-Impact Deaths</th>
        <th>Key Result / Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>nv3_native</code></td>
        <td>56950156 (notes)</td>
        <td>Node-based (all ply nodes)</td>
        <td>0.2117 mm</td>
        <td>100 &mu;s</td>
        <td>0</td>
        <td>Paper materials reference run; 100 &mu;s completed.</td>
      </tr>
      <tr>
        <td><code>nv3_vuel</code></td>
        <td>56950157 (notes)</td>
        <td>Node-based (all ply nodes)</td>
        <td>0.2117 mm</td>
        <td>100 &mu;s</td>
        <td>0</td>
        <td>VUEL through-thickness volume correction; completed.</td>
      </tr>
      <tr>
        <td><code>nv3_smear</code></td>
        <td>56995145</td>
        <td>Node-based (all ply nodes)</td>
        <td>0.2117 mm</td>
        <td>100 &mu;s</td>
        <td class="n"><strong>28,521</strong></td>
        <td><span class="badge badge-crash">Overclosure Pathology</span>: 27,293 dead in inc 1.</td>
      </tr>
      <tr>
        <td><code>nv3_elem</code></td>
        <td><strong>57004472</strong></td>
        <td>Element-based (<code>EMBMESH_PLATE_ELEMS</code>)</td>
        <td><strong>0.0 mm (solid faces)</strong></td>
        <td>100 &mu;s</td>
        <td class="n"><strong>0</strong></td>
        <td><span class="badge badge-done">Production Success</span>: 100 &mu;s in 13h 23m; 0 early deaths.</td>
      </tr>
      <tr>
        <td><code>nv3_int</code></td>
        <td><strong>57005555</strong></td>
        <td>Eroding EXTERIOR + INTERIOR faces</td>
        <td>0.0 mm (solid faces)</td>
        <td>2 &mu;s</td>
        <td class="n"><strong>0</strong></td>
        <td><span class="badge badge-done">Syntax Verified</span>: 2 &mu;s in 8m 43s; stable self-contact.</td>
      </tr>
    </tbody>
  </table>
  <p class="note"><em>Note: Per project records, <code>nv3_smear</code> and <code>nv3_int</code> have no pulled viewer NPZ files; numbers cited are from stdout, .sta, and project run logs.</em></p>

  <h2>2. Results of 100 &mu;s Production Run (nv3_elem)</h2>
  <figure>
    <img alt="nv3_elem 100 us Charts" src="data:image/png;base64,{chart_b64}">
    <figcaption><strong>Figure 1:</strong> 100 &mu;s production impact response of <code>nv3_elem</code>: global energies, host element deletions, and fiber deletions (data from <code>nv3_elem_extract.json</code> and <code>nv3_elem.sta</code>).</figcaption>
  </figure>

  <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th class="n">Value</th>
        <th>Source File Reference</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>ROAR Solve Job ID</td><td class="n">57004472</td><td>ROAR Slurm log (16 tasks, 32 GB)</td></tr>
      <tr><td>Wall Clock Time</td><td class="n">13 h 20 min (48,004 s)</td><td><code>nv3_elem.sta</code> summary</td></tr>
      <tr><td>Total Increments</td><td class="n">2,636 increments</td><td><code>nv3_elem.sta</code></td></tr>
      <tr><td>Stable Time Increment</td><td class="n">3.798 &times; 10<sup>-8</sup> s</td><td><code>nv3_elem.sta</code></td></tr>
      <tr><td>First Material Failure</td><td class="n"><strong>1.177 &mu;s</strong> (after 0.97 &mu;s impact)</td><td><code>nv3_elem.msg</code></td></tr>
      <tr><td>Pre-impact Deletions (t &le; 0.97 &mu;s)</td><td class="n"><strong>0</strong></td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Initial ETOTAL / ALLKE</td><td class="n">469.2 J / 469.2 J</td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Final ETOTAL</td><td class="n">439.0 J (-6.4%)</td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Final ALLKE</td><td class="n">409.1 J</td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Internal Energy (ALLIE)</td><td class="n">28.9 J</td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Damage Dissipation (ALLDMD)</td><td class="n">1.0 J</td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Host Elements Deleted</td><td class="n"><strong>39,016 / 435,000 (8.97%)</strong></td><td><code>nv3_elem_extract.json</code></td></tr>
      <tr><td>Fiber Elements Deleted</td><td class="n"><strong>73 / 524,180 (0.014%)</strong></td><td><code>nv3_elem_extract.json</code></td></tr>
    </tbody>
  </table>

  <h2>3. Standard Video Panel</h2>
  {render_standard_video_panel("nv3_elem", "nv3_elem 100 us")}

  <h2>4. Interior Face Contact Check (nv3_int)</h2>
  <p>To prepare for complex inter-ply debris interaction during perforation, <code>nv3_int</code> implemented an eroding contact surface including both EXTERIOR and INTERIOR faces of ghost host elements (<code>*Contact Controls Assignment, nodal erosion=YES</code>). Key findings from the 2 &mu;s ROAR test (job 57005555):</p>
  <ul>
    <li>Datacheck confirmed that <code>nodal erosion=YES</code> accepts no trailing data lines (fixing an initial syntax abort).</li>
    <li>Zero pre-impact deletions and zero contact overclosure spikes.</li>
    <li>ETOTAL stayed perfectly flat: 469.2 J &rarr; 468.0 J (-0.25%) over 2.0 &mu;s.</li>
    <li>Run completed in 8 min 43 s wall time, proving high efficiency for early impact phases.</li>
  </ul>

  <h2>5. Findings & Next Steps</h2>
  <ul>
    <li><strong>Element-Based Contact Eliminates False Failures:</strong> Switching from node contact to element contact surfaces completely eliminated the 27,000+ spurious pre-impact host failures.</li>
    <li><strong>100 &mu;s Viability:</strong> <code>nv3_elem</code> demonstrated excellent numerical stability, maintaining a 38 ns time step and completing 100 &mu;s in 13.3 hours without requiring restart recovery.</li>
    <li><strong>Low Fiber Failure:</strong> Only 73 fibers deleted out of 524,180, indicating that embedded fibers primarily deform rather than snap under 1000 m/s ball impact.</li>
  </ul>

  <h2>6. What Changed Next</h2>
  <p>While plate-ball contact was stabilized, the question arose whether fibers within each ply require contact with surrounding matrix elements as those hosts erode. This prompted T-056 and the fiber-host contact investigation documented in <a href="FIBER_HOST_CONTACT_REPORT.html">FIBER_HOST_CONTACT_REPORT.html</a>.</p>

  <h2>7. Not Verified / Open Questions</h2>
  <ul>
    <li>Viewer NPZ files were not pulled for <code>nv3_smear</code> or <code>nv3_int</code>; metrics are derived from ROAR job output and extract logs.</li>
    <li>Delamination progression (CSDMG) was not extracted into JSON for <code>nv3_elem</code> due to field output request limits.</li>
  </ul>
</body>
</html>
"""
    out_file = OUT_DIR / "NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[*] Wrote {out_file} ({len(html)//1024} KB)")

# -----------------------------------------------------------------------------
# 4. FIBER_HOST_CONTACT_REPORT.html
# -----------------------------------------------------------------------------
def build_fiberhost_report():
    print("[*] Generating FIBER_HOST_CONTACT_REPORT.html...")
    
    fh_dir = ROOT / "Meshing" / "newvals-fiberhost-tt3"
    fh_data = json.load(open(fh_dir / "results" / "nv3_fh_extract.json"))
    fhA_data = json.load(open(fh_dir / "resultsA" / "nv3_fhA_extract.json"))
    fhB_data = json.load(open(fh_dir / "resultsB" / "nv3_fhB_extract.json"))
    
    # Generate Charts
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.6))
    
    cases = [
        ("nv3_fh (All Pairs)", fh_data, "#d62728", "-"),
        ("nv3_fhA (Native Other-Ply Only)", fhA_data, "#2ca02c", "-"),
        ("nv3_fhB (USER Own-Ply Only)", fhB_data, "#ff7f0e", "--"),
    ]
    
    for name, data, col, ls in cases:
        etot = np.array(data["energy"]["ETOTAL"])
        allke = np.array(data["energy"]["ALLKE"])
        axs[0].plot(etot[:, 0]*1e6, etot[:, 1], color=col, ls=ls, lw=1.8, label=name)
        axs[1].plot(allke[:, 0]*1e6, allke[:, 1], color=col, ls=ls, lw=1.8, label=name)
        
    axs[0].set_title("Total Energy ETOTAL (J) - Linear", fontsize=10)
    axs[1].set_title("Kinetic Energy ALLKE (J) - Log Scale", fontsize=10)
    axs[1].set_yscale("log")
    
    for ax in axs:
        ax.set_xlabel("Time (us)", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
        ax.legend(fontsize=7)
        
    chart_b64 = b64fig(fig)
    
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Fiber-Host Contact Investigation Report</title>
  <style>{COMMON_CSS}</style>
</head>
<body>
  <h1>Fiber-Host Contact Architecture: VUINTERACTION Overclosure Ratchet, nv3_fh Instability, and Coupon Verification</h1>
  <p class="note"><strong>Author:</strong> Drafter (T-060) &middot; <strong>Date:</strong> 2026-11-13 &middot; <strong>Decks:</strong> <code>Meshing/newvals-fiberhost-tt3/</code> &middot; <strong>ROAR directory:</strong> <code>ctv/fh056/</code></p>

  <div class="corr">
    <strong>Discovery of the Own-Ply VUINTERACTION Explosion:</strong><br>
    The implementation of fiber-host contact in <code>nv3_fh</code> triggered a catastrophic kinetic energy explosion starting at $t \approx 1.48$ &mu;s, with total energy surging from 469.2 J to <strong>25,710 J at 1.90 &mu;s</strong>. Diagnostic bisection proved conclusively that the 380 native other-ply contact pairs (Run A) are 100% stable, whereas the 20 own-ply user interaction pairs (Run B) caused the runaway. Subsequent coupon verification on ROAR (<code>cx057b</code>) demonstrated that state variables in <code>VUINTERACTION</code> are <strong>not fresh per node-facet pair</strong>, causing cross-facet contamination and immense numerical force impulses on orphan host nodes.
  </div>

  <h2>1. Motivation & Background (T-056 Design)</h2>
  <p>In the NV3 plate, fibers embedded at the mid-plane of each ply have an equivalent truss diameter of 0.632 mm. Mid-ply host hex faces sit 0.212 mm from the fiber nodes, creating an initial geometric overlap of 0.104 mm. Standard penalty contact cannot be used on own-ply hosts because this initial overlap would release massive artificial strain energy at $t=0$.</p>
  <p>Task T-056 proposed a custom user subroutine <code>VUINTERACTION</code> implementing a baseline ratchet law: store the initial penetration d_0 = min(d_0, max(d, 0)) and apply compressive force only when dynamic penetration exceeds d_0. Fibers in other plies contacted hosts via native penalty contact.</p>

  <h2>2. Simulation Results: The A/B Bisect Experiment</h2>
  <figure>
    <img alt="Fiberhost Energy Charts" src="data:image/png;base64,{chart_b64}">
    <figcaption><strong>Figure 1:</strong> Direct bisection comparison over 2.0 &mu;s: <code>nv3_fh</code> (all pairs), <code>nv3_fhA</code> (native other-ply only), and <code>nv3_fhB</code> (USER own-ply only). Data from <code>Meshing/newvals-fiberhost-tt3/results*/</code>.</figcaption>
  </figure>

  <table>
    <thead>
      <tr>
        <th>Simulation Deck</th>
        <th>ROAR Solve Job</th>
        <th>Contact Configuration</th>
        <th class="n">ETOTAL @ 1.40 &mu;s</th>
        <th class="n">ETOTAL @ 1.90 &mu;s</th>
        <th class="n">Final ALLKE</th>
        <th>Stable Increment</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>nv3_fh</code></td>
        <td>57206655</td>
        <td>Native other-ply (380) + USER own-ply (20)</td>
        <td class="n">469.2 J</td>
        <td class="n"><strong>25,710 J</strong></td>
        <td class="n">34,620 J</td>
        <td>Collapsed to 0.9 ns</td>
        <td><span class="badge badge-crash">Energy Explosion</span></td>
      </tr>
      <tr>
        <td><code>nv3_fhA</code></td>
        <td>57289656</td>
        <td><strong>Native other-ply ONLY (380 pairs)</strong></td>
        <td class="n">469.2 J</td>
        <td class="n"><strong>468.8 J</strong></td>
        <td class="n">467.5 J</td>
        <td><strong>Stable 38 ns</strong></td>
        <td><span class="badge badge-done">100% Stable</span></td>
      </tr>
      <tr>
        <td><code>nv3_fhB</code></td>
        <td>57289658</td>
        <td><strong>USER own-ply ONLY (20 pairs)</strong></td>
        <td class="n">469.2 J</td>
        <td class="n"><strong>2,113 J</strong></td>
        <td class="n">2,381 J</td>
        <td>Collapsed to 2.6 ns</td>
        <td><span class="badge badge-crash">Energy Blowup</span></td>
      </tr>
    </tbody>
  </table>

  <h2>3. Root Cause: Diagnostic Analysis & Coupon Verification</h2>
  <h3>ODB Diagnostic Findings (diag_nv3_fh.txt)</h3>
  <ul>
    <li>The explosive kinetic energy at $t=1.48$ &mu;s was localized in single orphan host nodes of <code>PLY-20</code> on the symmetry plane ($y=0$).</li>
    <li>Node 720 accelerated to <strong>228,800 m/s</strong>, carrying 393 J of kinetic energy in a single nodal mass ($1.5 \times 10^{-8}$ kg).</li>
    <li>Subsequently, node 10859 accelerated to 1,460,000 m/s.</li>
  </ul>

  <h3>Physical Coupon Verification (Hub cx057 &amp; cx057b Runs)</h3>
  <p>Investigation T-057 proposed several initial hypotheses (H1&ndash;H7). The Hub physically verified and refined these mechanisms on ROAR (<code>verification/roar/fiberhost_t057/</code>, jobs 57328611 and 57336115; source: project notes):</p>
  <ul>
    <li><strong>Agy Claim Correction (Force Math):</strong> Agy's T-057 report suggested a 12.5 N contact force caused node 720's runaway. Hub review noted this was off by 1000&times;: accelerating 1.5 &times; 10<sup>-8</sup> kg to 228 km/s in 38 ns requires approximately 4 &times; 10<sup>4</sup> N, not 12.5 N.</li>
    <li><strong>Agy Claim Correction (AREAPROX):</strong> In Abaqus 2024, <code>AREAPROX</code> is dimensionless (values between 0.12 and 0.64), serving as a weight factor, NOT contact area in m&sup2;. Multiplying contact pressure by <code>AREAPROX</code> as area produced unphysical force estimates.</li>
    <li><strong>Coupon cx057 (Embedded Fibers):</strong> When fibers were embedded in host elements, <code>VUINTERACTION</code> had <strong>zero calls</strong>! Abaqus general contact automatically skips facets of the element an embedded node sits in.</li>
    <li><strong>Coupon cx057b (Non-Embedded Fibers):</strong> Yielded 12,430 log lines upon element deletion. Key proven findings:
      <ol>
        <li>Exactly <strong>4 calls per increment</strong> (273 of 273 increments); the underlying reason for 4 calls per increment is not established.</li>
        <li><strong>State is NOT fresh per new node-facet pair:</strong> Master facets paired later arrived with <code>st2in=1</code> and <code>d0=0</code>, proving that slave node state is corrupted across multiple facets.</li>
        <li><code>PENETRATION</code> values did not correspond to geometric overlaps.</li>
      </ol>
    </li>
  </ul>

  <h2>4. Production Decision & nv3_fhA100 Candidate</h2>
  <p>Because own-ply contact is physically redundant with <code>*EMBEDDED ELEMENT</code> while elements are intact, and geometrically ill-posed once host elements erode, the decision was made to <strong>drop own-ply fiber-host contact entirely</strong>.</p>
  <p>Production candidate <code>nv3_fhA100</code> (incorporating the proven Run A native other-ply contact for all $j \ne k$) was submitted to ROAR:</p>
  <ul>
    <li><strong>ROAR Job Chain:</strong> Datacheck 57328142 &rarr; Solve 57328143 &rarr; Post-processing 57328144&ndash;146.</li>
    <li><strong>Parameters:</strong> 100 &mu;s step, 200 field frames, 16 tasks, 32 GB, 20-hour wall limit.</li>
  </ul>

  <div class="placeholder">
    <h3>[PLACEHOLDER] nv3_fhA100 Production Run Results</h3>
    <p><strong>Status: Execution In Progress on ROAR (Job 57328143)</strong></p>
    <p>This section is reserved for the full 100 &mu;s results of <code>nv3_fhA100</code>. Upon completion, the following metrics will be populated by running <code>build_t060_reports.py</code>:</p>
    <table>
      <thead>
        <tr><th>Metric</th><th>Target Step / Planned</th><th>Status / Value</th></tr>
      </thead>
      <tbody>
        <tr><td>Step Time</td><td>100.0 &mu;s</td><td><em>Pending</em></td></tr>
        <tr><td>Final ETOTAL</td><td>Pending solve completion</td><td><em>Pending</em></td></tr>
        <tr><td>Final ALLKE</td><td>Pending solve completion</td><td><em>Pending</em></td></tr>
        <tr><td>Host Elements Deleted</td><td>Pending solve completion</td><td><em>Pending</em></td></tr>
        <tr><td>Fiber Elements Deleted</td><td>Pending solve completion</td><td><em>Pending</em></td></tr>
      </tbody>
    </table>
  </div>

  <h2>5. Standard Video Panel</h2>
  {render_standard_video_panel("nv3_fhA", "nv3_fhA100 Production Run")}

  <h2>6. Findings & Summary</h2>
  <ul>
    <li><strong>Own-Ply VUINTERACTION Dropped:</strong> Proximity tracking without per-pair state variables cannot support own-ply overclosure ratcheting in Abaqus/Explicit.</li>
    <li><strong>Run A Architecture Validated:</strong> Native contact across distinct plies ($j \ne k$) provides robust lateral fiber-matrix interaction without numerical instability.</li>
  </ul>

  <h2>7. Not Verified / Open Questions</h2>
  <ul>
    <li>The full 100 &mu;s <code>nv3_fhA100</code> run is in flight; full perforation metrics await job completion.</li>
    <li>The exact reason why T-056 coupon <code>cf_baseline</code> produced 558 calls while <code>cx057</code> produced zero calls with embedded elements remains an internal Abaqus contact resolution nuance.</li>
  </ul>
</body>
</html>
"""
    out_file = OUT_DIR / "FIBER_HOST_CONTACT_REPORT.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[*] Wrote {out_file} ({len(html)//1024} KB)")

# -----------------------------------------------------------------------------
# 5. REPORTS_INDEX.html
# -----------------------------------------------------------------------------
def build_index_report():
    print("[*] Generating REPORTS_INDEX.html...")
    
    # Complete catalog of all 29 reports in chronological order
    REPORTS = [
        # Stage 0-6 VUEL Development
        {
            "date": "2026-10-01",
            "title": "VUEL Failure Criterion Validation",
            "file": "VUEL_FAILURE_CRITERION_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Milestone",
            "summary": "Investigated whether Abaqus/Explicit honors user-defined engineering-strain failure triggers in VUEL elements. Confirmed that element deletion and stress-clearing behave correctly under single-element tension and shear benchmarks with EPS_FAIL = 1.0."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 0 Plan: Elastic-Plastic VUEL with Homegrown Failure",
            "file": "VUEL_PLASTIC_FAILURE_STAGE0_PLAN.html",
            "category": "VUEL Formulation",
            "badge": "Plan",
            "summary": "Outlined mathematical formulation and verification roadmap for incorporating additive Green-Lagrange J2 plasticity with radial return mapping into uel/VUEL_failure.for prior to code implementation."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 1 Report: Linear-Hardening J2 Plasticity",
            "file": "VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Verified",
            "summary": "Implemented closed-form radial return mapping for von Mises plasticity on VUEL_failure.for. Verified against native Abaqus C3D8R plastic benchmarks under cyclic uniaxial tension and compression."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 2 Report: Engineering-Strain Failure Trigger on Plastic Element",
            "file": "VUEL_PLASTIC_FAILURE_STAGE2_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Verified",
            "summary": "Coupled plastic flow with the maximum engineering strain failure criterion. Demonstrated that plastic deformation does not corrupt failure detection or premature deletion."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 3 Report: Jacobian Collapse Failure Trigger",
            "file": "VUEL_PLASTIC_FAILURE_STAGE3_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Verified",
            "summary": "Added props(11)=JAC_FAIL and min(det(F)) evaluation over all 8 Gauss integration points. Successfully catches element geometric inversion under severe compressive impact before negative Jacobian aborts."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 4 Report: Dead-State Hygiene & Energy Bookkeeping",
            "file": "VUEL_PLASTIC_FAILURE_STAGE4_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Verified",
            "summary": "Fixed two critical state variable bookkeeping bugs in VUEL_failure.for to ensure zero residual stress, zero artificial stiffness, and clean nodal mass conservation after element deletion."
        },
        {
            "date": "2026-10-01",
            "title": "Stage 5 Report: Degradation-Ramp Softening Behavior",
            "file": "VUEL_PLASTIC_FAILURE_STAGE5_REPORT_2026-10-01.html",
            "category": "VUEL Formulation",
            "badge": "Verified",
            "summary": "Verified the linear degradation ramp failure model (props(12)=DEGRADE_TIME, props(13)=COMP_RESIDUAL_BULK_FRAC) to eliminate abrupt force shocks during dynamic failure transitions."
        },
        {
            "date": "2026-10-06",
            "title": "Stage 6 Report: Ghost-VUEL Element Synchronization",
            "file": "VUEL_PLASTIC_FAILURE_STAGE6_REPORT.html",
            "category": "Ghost Synchronization",
            "badge": "Milestone",
            "summary": "Validated the mesher dual-mesh concept on full Flat.inp scale (24,000 VU1 hosts + 24,000 ghost C3D8Rs + 125 fibers). Confirmed that native ghost element deletion tracks VUEL failure within a single frame interval."
        },
        {
            "date": "2026-10-06",
            "title": "Independent Verification Report: Embedded Mesher Toolchain",
            "file": "VERIFICATION_REPORT.html",
            "category": "Mesher Verification",
            "badge": "Verified",
            "summary": "Comprehensive 7-step independent audit of the embedded mesher toolchain (mesh round-trip, truss/beam fiber definitions, coordinate transforms, volume fractions, and volume scaling)."
        },
        # Ghost Dynamics & Plate Impact
        {
            "date": "2026-10-12",
            "title": "Flat v2 Impact Run: Full Plate Penetration",
            "file": "flat_v2_report.html",
            "category": "Plate Impact",
            "badge": "Done",
            "summary": "First full 100 us impact simulation of Flatv2.inp on ROAR (job 56286114). The central crater deleted with 0 solver errors (1,357 ghosts deleted of 24,000). Identified the island problem where 85 ghost elements survived within 10 mm of the axis despite all their neighbours being deleted."
        },
        {
            "date": "2026-10-12",
            "title": "Flat v2 Diagnostics: Auditing Surviving Ghost Elements",
            "file": "flat_v2_diagnostics_report.html",
            "category": "Diagnostics",
            "badge": "Done",
            "summary": "Read all 1001 frames of flat_v2.odb (ROAR job 56305969 on run 56286114). Proved surviving ghosts were not a synchronization mismatch: 74 of the 85 surviving ghosts within 10 mm of the axis had intact VU1s because they never met the failure criterion. Confirmed the ball retained 983 of 1000 m/s and entered all 58 surviving islands while alive."
        },
        {
            "date": "2026-10-13",
            "title": "Flat v2 Workarounds: Node-Based Contact Surface",
            "file": "flat_v2_workarounds_report.html",
            "category": "Contact Formulation",
            "badge": "Done",
            "summary": "Evaluated 8 contact workarounds on ROAR. Demonstrated that adding a node-based contact surface over all plate nodes deleted all 802 ghost elements within 10 mm of the axis, completely solving the island problem, while whole-ghost contact and penalty stiffness adjustments failed."
        },
        {
            "date": "2026-10-14",
            "title": "Node-Contact Speed Series: 100 to 500 m/s Impact",
            "file": "NODE_CONTACT_SPEED_SERIES_REPORT.html",
            "category": "Velocity Sweep",
            "badge": "Done",
            "summary": "Systematic speed series (100, 200, 300, 400, 500 m/s) completed to 70 us with 0 solver errors using plate node-contact. Proved ball speed retention scales linearly and ghost islands vanish above 200 m/s (8 islands at 100 m/s, 2 at 200 m/s, 0 at 300-500 m/s)."
        },
        {
            "date": "2026-10-14",
            "title": "Node-Contact Speed Series: Wireframe & Video Renders",
            "file": "NODE_CONTACT_SPEED_SERIES_REPORT_VIDEOS.html",
            "category": "Visualization",
            "badge": "Done",
            "summary": "Cataloged 30 MP4 videos across all 5 impact speeds (solid status and wireframe passes in sidev, iso, and side views). Established the symmetry-plane vertical wireframe pass (sidev) as the optimal perspective for visualizing fiber stretch and plate shear fracture."
        },
        {
            "date": "2026-10-16",
            "title": "Fiber Contact Comparison: v500 vs v500*",
            "file": "FIBER_CONTACT_COMPARISON_REPORT.html",
            "category": "Contact Formulation",
            "badge": "Done",
            "summary": "Compared 500 m/s ball impact with and without fiber node contact (v500 vs v500*, ROAR jobs 56489085/56489086). Adding 14,192 fiber nodes to ball contact reduced peak fiber nodes inside the ball from 218 to 2, stopping fibers from passing through the projectile, while host deletions rose from 2,389 to 3,548."
        },
        {
            "date": "2026-10-17",
            "title": "Curved vs Flat Plate Impact Comparison",
            "file": "CURVED_VS_FLAT_REPORT.html",
            "category": "Structural Mechanics",
            "badge": "Done",
            "summary": "Compared 500 m/s ball impact on a concave spherical bowl (radius 0.25 m, rim 5.05 mm raised) vs flat plate (ROAR jobs 56512623/56489086). Curvature increased stiffness: at 100 us the ball retained 457.8 m/s on curved vs 453.3 m/s on flat; ball lost 165.4 J KE on curved vs 182.4 J on flat (17.0 J less), while host deletions rose to 6,588 vs 3,548."
        },
        {
            "date": "2026-10-17",
            "title": "Plywise Laminate vs Solid Host Representation",
            "file": "PLYWISE_VS_SOLID_REPORT.html",
            "category": "Meshing Architecture",
            "badge": "Milestone",
            "summary": "Evaluated 8-ply cohesive laminate against continuous 10-layer solid host at 500 m/s (ROAR jobs 56525373/56525375). At 100 us on the flat plate, the ball moved at 457.8 m/s on plywise vs 453.3 m/s on solid (+4.5 m/s), deleting 3,923 host elements vs 3,548 on solid, exhibiting realistic inter-ply cohesive delamination."
        },
        {
            "date": "2026-10-17",
            "title": "Host Failure Analysis: Timing of Ghost vs VUEL Failure",
            "file": "HOST_FAILURE_ANALYSIS_REPORT.html",
            "category": "Diagnostics",
            "badge": "Done",
            "summary": "Analyzed timing of VUEL failure vs ghost deletion across 500 m/s runs. Found that 344 (flat) and 350 (concave) VUEL elements failed at t=0 before contact in plywise runs due to initial constraint state, whereas ghost deletion lagged; identified that 82% to 92% of fiber nodes become orphaned as surrounding hosts delete."
        },
        {
            "date": "2026-10-19",
            "title": "Stage 8 Report: Ductile-Damage Elastic-Plastic Matrix VUEL",
            "file": "MATRIX_MATERIAL_REPORT.html",
            "category": "Material Modeling",
            "badge": "Milestone",
            "summary": "Implemented Stage 8 matrix material in uel/VUEL_material.for (linear J2 plasticity, ductile initiation at 0.1 strain, displacement-based damage evolution). Matched native Abaqus C3D8R across 6 of 6 single-element test cases (at 1000/s and 1/s) within < 1% pre-softening stress and <= 0.35% total dissipation difference."
        },
        # Plywise Transition & Contact Overclosure
        {
            "date": "2026-10-20",
            "title": "Vals 20-Ply Laminate: VUEL vs Native Baseline (vp3)",
            "file": "VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html",
            "category": "Validation",
            "badge": "Warning",
            "summary": "First 20-ply Valerie laminate run (1000 m/s, ROAR jobs 56574395/56574396). Both models perforated, but VUEL lost 3.4x more host elements (31.2% vs 9.2%) and fiber nodes displaced up to 290 mm because fibers lacked damage evolution and could not delete."
        },
        {
            "date": "2026-10-20",
            "title": "Vals Plywise Deletion Rerun: Energy Generation Pathology (vp4)",
            "file": "VALS_PLYWISE_DELETION_RERUN_REPORT.html",
            "category": "Pathology",
            "badge": "Warning",
            "summary": "Added element deletion to all materials in 20-ply Valerie decks (vp4, ROAR jobs 56641617/56641618). Eliminated fiber displacement blow-up, but revealed non-conservation of energy: ALLKE peaked at 6.1 J (+73% over initial kinetic energy in native, +63% in VUEL; note: raw ODB energies uncorrected for 1000x factor)."
        },
        {
            "date": "2026-10-23",
            "title": "Vals Native Eroding Contact Rerun (vp5)",
            "file": "VALS_VP5_ERODING_CONTACT_REPORT.html",
            "category": "Contact Formulation",
            "badge": "Milestone",
            "summary": "Replaced node contact with an eroding element-based host surface (EMBMESH_PLATE_ELEMS, ROAR job 56651971). ALLKE peak dropped from +73% to +6.8% over initial kinetic energy, eliminating the energy blowup. Ball eroded heavily: 3,161 of 18,500 elements (17.1%) deleted by 70 us, and host deletions rose from 517 to 1,351."
        },
        # Ball Tests & Geometry Correction
        {
            "date": "2026-10-28",
            "title": "Vals Ball Tests Suite 1: Single-Variable Variants (bt1)",
            "file": "VALS_BT1_BALL_TESTS_REPORT.html",
            "category": "Ball Tests",
            "badge": "Done",
            "summary": "Tested 6 variants against vp5 (b1-b6: beam surfaces, O-grid, D4 rate fix, alternate steels) over 12 us. All showed steady ball erosion of 80-90 elements/us starting at 1.5-1.9 us; D4 (b4) reduced ball deletions by 8% (840 vs 913), but none halted erosion. Carries correction note: inversion metric evaluated deleted ghost elements."
        },
        {
            "date": "2026-10-28",
            "title": "Vals Ball Tests Suite 2: Beam Fibers, D4, and Matrix Degradation (bt2)",
            "file": "VALS_BT2_BALL_TESTS_REPORT.html",
            "category": "Ball Tests",
            "badge": "Corrected",
            "summary": "Tested beam vs truss fibers, Johnson-Cook D4=+0.002, and max degradation 0.8 across 6 decks at 1000 and 500 m/s (c1-c3). Beam decks deleted 63-68 fibers at 1000 m/s vs 11-16 for truss, but ball deletion remained 4.2-4.5% (1000 m/s) and 1.8-2.0% (500 m/s). Carries correction note: inversion metric evaluated deleted ghost elements."
        },
        {
            "date": "2026-10-30",
            "title": "Plate Impact d6: Valerie Paper Matched Materials Video",
            "file": "D6_PAPER_MATERIALS_VIDEO.html",
            "category": "Visualization",
            "badge": "Done",
            "summary": "Standalone video presentation of the 100 us d6 run (ROAR job 56873219) with Valerie paper Table 2 properties and a rigid non-deformable ball. Demonstrated stable plate penetration without numerical ball breakdown, showing wide-angle and close-up symmetry-plane views."
        },
        # The 4 New Reports
        {
            "date": "2026-10-31",
            "title": "Vals Ball Tests Suite 3: Projectile Models & Inversion Resolution (bt3)",
            "file": "VALS_BT3_BALL_TESTS_REPORT.html",
            "category": "Ball Tests",
            "badge": "Milestone",
            "summary": "Evaluated the bt3 simulation suite (d1-d7) at 1000 m/s. Proved ball inversion was a ghost-element artifact (609 of 610 hexes in b4 and 618 of 619 in c2 were already deleted before non-positive Jacobian). Evaluated coupon matrix t052 (01-12), elastic ball solver collapse in d3 at 22.77 us, Weldox 460E steel in d4 (17.3% ball deletion, 1,443 host deletions), and rigid ball models (d5-d7, 100 us ALLKE retention 87.3% to 88.5%)."
        },
        {
            "date": "2026-11-02",
            "title": "Vals Projectile Geometry Correction: 3/4-in vs 3/8-in Ball Error",
            "file": "VALS_BALL_SIZE_FIX_REPORT.html",
            "category": "Geometry Fix",
            "badge": "Milestone",
            "summary": "Discovered that Vals.inp defined an oversized 3/4-inch diameter projectile (3546.1 J) instead of the experimental 3/8-inch ball (469.2 J, 8.0x mass difference). Evaluated 70 us corrected impact at 1028 m/s: native C3D8R deleted 611 of 80,500 host cells (0.76%), and VUEL deleted 1,222 of 161,000 sub-elements (611 host cell pairs, 0.76%), compared to 1,704 host cells deleted (2.12%) in 3/4-inch d6 at 70 us."
        },
        {
            "date": "2026-11-06",
            "title": "NewVals NV3 Contact Evolution: Overclosure Pathology & Eroding Contact",
            "file": "NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html",
            "category": "Through-Thickness",
            "badge": "Milestone",
            "summary": "Diagnosed pre-impact host failure pathology in 3-elements-per-ply laminate nv3_smear (27,293 host deaths in increment 1) caused by 0.2117 mm node contact thickness overclosing cohesive interfaces. Resolved via eroding element-based contact in nv3_elem: completed 100 us in 13 h 20 min (48,004 s) with 0 pre-impact deaths, deleting 39,016 of 435,000 host hexes (8.97%) and 73 of 524,180 fiber trusses (0.014%)."
        },
        {
            "date": "2026-11-13",
            "title": "Fiber-Host Contact Architecture: VUINTERACTION & Resolution",
            "file": "FIBER_HOST_CONTACT_REPORT.html",
            "category": "Fiber-Host Contact",
            "badge": "Milestone",
            "summary": "Investigated fiber-host contact architecture for NV3 composite plates. Diagnostic A/B bisection proved native other-ply contact (nv3_fhA, 380 pairs) is 100% stable (468.8 J ETOTAL), while own-ply VUINTERACTION (nv3_fhB, 20 pairs) triggered kinetic energy explosion (25,710 J at 1.9 us in nv3_fh). Physical ROAR coupons (cx057b) proved VUINTERACTION state is not fresh across node-facet pairs. Dropped own-ply contact; submitted 100 us production run nv3_fhA100."
        }
    ]
    # Sort chronologically
    REPORTS = sorted(REPORTS, key=lambda x: x["date"])
    
    # Generate HTML cards
    cards_html = []
    for i, r in enumerate(REPORTS, 1):
        badge_cls = "badge-done"
        if "Warning" in r["badge"] or "Pathology" in r["badge"]:
            badge_cls = "badge-warn"
        elif "Crash" in r["badge"]:
            badge_cls = "badge-crash"
        elif "Pending" in r["badge"]:
            badge_cls = "badge-pending"
            
        link_target = r["file"]
        
        cards_html.append(f"""
<div class="card" id="rep-{i}">
  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
    <div>
      <span class="badge {badge_cls}">{r['badge']}</span>
      <span class="note" style="margin-left:8px;"><strong>#{i:02d}</strong> &middot; {r['date']} &middot; <code>{r['category']}</code></span>
    </div>
    <div>
      <a href="{link_target}" style="font-weight:600;">Open Report &rarr;</a>
    </div>
  </div>
  <h3 style="margin:4px 0 8px 0;"><a href="{link_target}">{r['title']}</a></h3>
  <p style="margin:4px 0; font-size:0.92rem;">{r['summary']}</p>
  <p class="note" style="margin-top:6px; font-size:0.8rem;">File: <code>{r['file']}</code></p>
</div>
""")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Plate Impact Simulation Timeline &amp; Knowledge Evolution</title>
  <style>
    {COMMON_CSS}
    .timeline-nav {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }}
    .timeline-nav a {{ background:var(--card-bg); border:1px solid var(--line); padding:4px 10px; border-radius:4px; font-size:0.82rem; }}
  </style>
</head>
<body>
  <h1>Plate Impact Knowledge Evolution Timeline (Oct 1 &ndash; Nov 13, 2026)</h1>
  <p class="note"><strong>Repository:</strong> Plate Impact Simulation Architecture &middot; <strong>Total Reports:</strong> {len(REPORTS)} Studies &middot; <strong>Order:</strong> Chronological (Oldest First)</p>

  <div class="card" style="border-left: 4px solid var(--accent); background: var(--accent-light);">
    <h3 style="margin-top:0;">The Evolution of Project Knowledge: Decision Chain Summary</h3>
    <p>This master timeline tracks how the understanding of composite impact physics, numerical stability, and projectile dynamics evolved across 44 days of high-performance explicit FEA modeling on Penn State ROAR:</p>
    <ol style="margin-bottom:0; font-size:0.92rem;">
      <li><strong>VUEL Foundation (Oct 1&ndash;6):</strong> Developed and verified user-defined 8-node hex element with J2 plasticity and failure triggers (Stages 0&ndash;6), establishing ghost-element synchronization.</li>
      <li><strong>Node-Contact &amp; Rim Island Workarounds (Oct 12&ndash;14):</strong> Solved surviving ghost elements in Flat v2 by introducing node-based plate contact. Characterized velocity scaling from 100 to 500 m/s.</li>
      <li><strong>Plywise Laminates &amp; Contact Thickness Pathology (Oct 16&ndash;23):</strong> Moving from monolithic plates to 20-ply laminates (vp3/vp4) revealed that assigning artificial contact thickness to all ply nodes creates massive kinetic energy blowups (+73% ALLKE) and premature host deaths.</li>
      <li><strong>Eroding Element Contact (vp5, Oct 23):</strong> Eliminated artificial energy creation by migrating plate-ball contact to an eroding element-based surface (<code>EMBMESH_PLATE_ELEMS</code>).</li>
      <li><strong>The Inversion Resolution &amp; Ball Test Suites (Oct 26&ndash;31):</strong> Audited apparent ball 'inversion' in bt1/bt2. Extraction of element STATUS proved that 99.8% of inverted hexes were already deleted ghost elements. Rigid projectile modeling adopted as standard (bt3).</li>
      <li><strong>Projectile Geometry Error Discovery (Nov 2):</strong> Discovered root error in <code>Vals.inp</code>: projectile was 3/4-in diameter instead of the experimental 3/8-in diameter (8&times; mass error). Corrected in <code>vrb_native</code>/<code>vrb_vuel</code>.</li>
      <li><strong>Through-Thickness Meshing &amp; Overclosure (Nov 5&ndash;6):</strong> In 3-elements-per-ply meshing (NV3), node contact overclosed cohesive interfaces (27,000 dead hosts in inc 1 of <code>nv3_smear</code>). Resolved with element contact in <code>nv3_elem</code> (100 &mu;s in 13.3 h).</li>
      <li><strong>Fiber-Host Contact Resolution (Nov 10&ndash;13):</strong> Attempted own-ply fiber-host contact via <code>VUINTERACTION</code> in <code>nv3_fh</code>, causing energy explosion. A/B bisection and cluster coupons (<code>cx057b</code>) proved proximity state is not fresh per facet. Dropped own-ply contact, stabilizing production candidate <code>nv3_fhA100</code>.</li>
    </ol>
  </div>

  <h2>Report Catalog (Chronological)</h2>
  <div class="timeline-nav">
    {' '.join([f'<a href="#rep-{i}">{i:02d}. {r["date"][5:]}</a>' for i, r in enumerate(REPORTS, 1)])}
  </div>

  <div class="report-list">
    {''.join(cards_html)}
  </div>

  <hr style="border:0; border-top:1px solid var(--line); margin:32px 0;">
  <p class="note" style="text-align:center;">Generated automatically by <code>build_t060_reports.py</code> &middot; Plate Impact Project &middot; Penn State University</p>
</body>
</html>
"""
    out_file = OUT_DIR / "REPORTS_INDEX.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[*] Wrote {out_file} ({len(html)//1024} KB)")

# -----------------------------------------------------------------------------
# Main CLI Execution
# -----------------------------------------------------------------------------
def main():
    print("="*70)
    print("  Building All Missing Study Reports & Master Timeline Index")
    print("="*70)
    build_bt3_report()
    build_ballfix_report()
    build_nv3_report()
    build_fiberhost_report()
    build_index_report()
    print("="*70)
    print("  All 5 HTML reports built successfully in:")
    print(f"  {OUT_DIR}")
    print("="*70)

if __name__ == "__main__":
    main()
