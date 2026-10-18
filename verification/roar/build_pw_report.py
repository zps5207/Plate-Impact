"""Build reports/PLYWISE_VS_SOLID_REPORT.html: plywise (8 plies, cohesive interfaces) against the solid host
(10 hex layers) for the flat and concave 500 m/s plates.

Runs compared (all 500 m/s, 100 us, VUEL + ghost host, node + element ball contact in v3):
    solid:   v500star_100 (flat), cc500_100 (concave)           -> reports/cc_run/dl/
    plywise: pw_flat500_v3, pw_cc500_v3 (final), pw_*_100 (v1: no element-based ball contact, energy only)
Inputs:
    reports/cc_run/dl/<solid>/<solid>_energy.csv, solid viewer npz (see SOLID below)
    Meshing/plywise-500/results/<run>/<run>_energy.csv and <run>_viewer.npz, frames_video/ (when downloaded)
Videos are encoded into reports/pw_video/ with the ffmpeg from imageio_ffmpeg.
"""
import csv
import json
import os
import subprocess

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DL = os.path.join(ROOT, "reports", "cc_run", "dl")
PW = os.path.join(ROOT, "Meshing", "plywise-500", "results")
VID = os.path.join(ROOT, "reports", "pw_video")
OLD_VID = os.path.join(ROOT, "reports", "cc_video")
FLAT_VID = os.path.join(ROOT, "reports", "fc_video")
TEMPLATE = os.path.join(ROOT, "reports", "_flat_v2_template.html")
OUT = os.path.join(ROOT, "reports", "PLYWISE_VS_SOLID_REPORT.html")
V0 = 500.0
os.makedirs(VID, exist_ok=True)

# key: (label, colour, energy csv, viewer npz or None)
RUNS = {
    "flat_solid": ("Flat, solid host", "#6d7a86", os.path.join(DL, "v500star_100", "v500star_100_energy.csv"),
                   os.path.join(ROOT, "verification", "roar", "t_nc", "v500star_100", "v500star_100_viewer.npz")),
    "flat_ply": ("Flat, plywise", "#1f6fb4", os.path.join(PW, "pw_flat500_v3", "pw_flat500_v3_energy.csv"),
                 os.path.join(PW, "pw_flat500_v3", "pw_flat500_v3_viewer.npz")),
    "cc_solid": ("Concave, solid host", "#c2362f", os.path.join(DL, "cc500_100", "cc500_100_energy.csv"),
                 os.path.join(DL, "cc500_100", "cc500_100_viewer.npz")),
    "cc_ply": ("Concave, plywise", "#e08a1e", os.path.join(PW, "pw_cc500_v3", "pw_cc500_v3_energy.csv"),
               os.path.join(PW, "pw_cc500_v3", "pw_cc500_v3_viewer.npz")),
}
V1 = {  # intermediate plywise runs without element-based ball contact: energy only
    "flat_ply_v1": ("Flat, plywise v1", os.path.join(PW, "pw_flat500_100", "pw_flat500_100_energy.csv")),
    "cc_ply_v1": ("Concave, plywise v1", os.path.join(PW, "pw_cc500_100", "pw_cc500_100_energy.csv")),
}
FIBER_NODES = {"flat_solid": 14192, "cc_solid": 13792}
HOSTS = {"flat_solid": 24000, "cc_solid": 24000, "flat_ply": 19200, "cc_ply": 19200}


def energy(path):
    rows = list(csv.DictReader(open(path)))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def viewer(path):
    d = np.load(path)
    t, bp, st = d["times"], d["ball_pos"].astype(np.float64), d["host_status"]
    vel = np.gradient(bp, t, axis=0)
    return {"t_us": t * 1e6, "vz": -vel[:, :, 2].mean(axis=1),
            "deleted": (st.shape[1] - st.sum(axis=1)).astype(int), "n_host": st.shape[1], "vel": vel}


E = {k: energy(v[2]) for k, v in RUNS.items()}
E1 = {k: energy(v[1]) for k, v in V1.items() if os.path.exists(v[1])}
VW = {k: viewer(v[3]) for k, v in RUNS.items() if os.path.exists(v[3])}
E0 = float(E["flat_solid"]["ETOTAL"][0])
BALL_MASS = 2 * float(E["flat_solid"]["ALLKE"][0]) / V0 ** 2


def ball_ke(v):
    return 0.5 * BALL_MASS * (np.linalg.norm(v["vel"], axis=2) ** 2).mean(axis=1)


KE = {k: ball_ke(v) for k, v in VW.items()}
stats = {}
for k in RUNS:
    e = E[k]
    s = {"model_lost": float(E0 - e["ETOTAL"][-1]), "viscous": float(e["ALLVD"][-1]), "ie_end": float(e["ALLIE"][-1]),
         "ie_peak": float(e["ALLIE"].max()), "allke_end": float(e["ALLKE"][-1]), "n_host": HOSTS[k]}
    if k in VW:
        v = VW[k]
        s.update(ball_speed_100=float(v["vz"][-1]), ball_speed_frac=float(v["vz"][-1] / V0),
                 ball_ke_end=float(KE[k][-1]), ball_ke_lost=float(KE[k][1] - KE[k][-1]),
                 deleted=int(v["deleted"][-1]), deleted_frac=float(v["deleted"][-1] / v["n_host"]))
    stats[k] = s
for k, e in E1.items():
    stats[k] = {"model_lost": float(E0 - e["ETOTAL"][-1]), "viscous": float(e["ALLVD"][-1]),
                "ie_end": float(e["ALLIE"][-1]), "allke_end": float(e["ALLKE"][-1])}


# ---------------------------------------------------------------- ball penetration (same test as compare_fiber_contact.py)
from scipy.spatial import ConvexHull


def depth_inside(eq, pts):
    """Penetration depth (m) of each point into the convex hull of the ball; 0 outside."""
    s = pts @ eq[:, :3].T + eq[:, 3]
    m = s.max(axis=1)
    return np.where(m < 0, -m, 0.0)


def penetration(path):
    d = np.load(path)
    t, bp, fp, hp, st = d["times"], d["ball_pos"], d["fiber_pos"], d["host_pos"], d["host_status"]
    conn = d["host_conn_C3D8R"]
    rec = {"t_us": (t * 1e6).tolist(), "fiber_in": [], "fiber_depth_mm": [], "host_in": [], "host_depth_mm": [],
           "host_alive_in": [], "host_alive_depth_mm": []}
    for i in range(len(t)):
        ball = bp[i].astype(np.float64)
        eq = ConvexHull(ball).equations
        lo, hi = ball.min(axis=0) - 1e-6, ball.max(axis=0) + 1e-6

        def sub(points):
            pts = points.astype(np.float64)
            near = np.flatnonzero(np.all((pts >= lo) & (pts <= hi), axis=1))
            dep = np.zeros(len(pts))
            if len(near):
                dep[near] = depth_inside(eq, pts[near])
            return dep

        f, h = sub(fp[i]), sub(hp[i])
        alive_nodes = np.zeros(len(hp[i]), bool)
        alive_nodes[np.unique(conn[st[i] > 0])] = True
        ha = np.where(alive_nodes, h, 0.0)
        rec["fiber_in"].append(int((f > 0).sum())); rec["fiber_depth_mm"].append(float(f.max() * 1e3))
        rec["host_in"].append(int((h > 0).sum())); rec["host_depth_mm"].append(float(h.max() * 1e3))
        rec["host_alive_in"].append(int((ha > 0).sum())); rec["host_alive_depth_mm"].append(float(ha.max() * 1e3))
    return rec


PEN = {}
for k, v in RUNS.items():
    if os.path.exists(v[3]):
        PEN[k] = penetration(v[3])
        print(k, "penetration: fiber peak %d (%.3f mm), host peak %d (%.3f mm), host alive-attached peak %d (%.3f mm)" % (
            max(PEN[k]["fiber_in"]), max(PEN[k]["fiber_depth_mm"]), max(PEN[k]["host_in"]), max(PEN[k]["host_depth_mm"]),
            max(PEN[k]["host_alive_in"]), max(PEN[k]["host_alive_depth_mm"])))
        stats[k].update(fiber_in_peak=max(PEN[k]["fiber_in"]), fiber_depth_peak_mm=max(PEN[k]["fiber_depth_mm"]),
                        host_in_peak=max(PEN[k]["host_in"]), host_depth_peak_mm=max(PEN[k]["host_depth_mm"]),
                        host_alive_in_peak=max(PEN[k]["host_alive_in"]), host_alive_depth_peak_mm=max(PEN[k]["host_alive_depth_mm"]),
                        fiber_in_end=PEN[k]["fiber_in"][-1], host_alive_in_end=PEN[k]["host_alive_in"][-1])
json.dump(stats, open(os.path.join(PW, "plywise_vs_solid_stats.json"), "w"), indent=2)


# ---------------------------------------------------------------- charts
def line_chart(series, ylabel, w=760, h=300, ymin=0.0, ymax=None, xmax=100.0, xlabel="step time (us)"):
    ml, mr, mt, mb = 62, 16, 30, 40
    vmax = ymax if ymax is not None else max(float(np.max(s["y"])) for s in series) * 1.08 or 1.0
    px = lambda t: ml + (w - ml - mr) * t / xmax
    py = lambda v: mt + (h - mt - mb) * (1 - (v - ymin) / (vmax - ymin))
    o = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s" style="width:100%%;height:auto">' % (w, h, ylabel)]
    for i in range(6):
        v = ymin + (vmax - ymin) * i / 5
        o.append('<line stroke="var(--grid)" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (ml, w - mr, py(v), py(v)))
        o.append('<text fill="var(--mute)" font-size="11" x="%d" y="%.1f" text-anchor="end">%.4g</text>' % (ml - 6, py(v) + 3, v))
        t = xmax * i / 5
        o.append('<text fill="var(--mute)" font-size="11" x="%.1f" y="%d" text-anchor="middle">%.0f</text>' % (px(t), h - mb + 16, t))
    o.append('<text fill="var(--mute)" font-size="12" x="%d" y="%d" text-anchor="middle">%s</text>' % ((ml + w - mr) // 2, h - 6, xlabel))
    o.append('<text fill="var(--mute)" font-size="12" transform="rotate(-90 14 %d)" x="14" y="%d" text-anchor="middle">%s</text>' % (h // 2, h // 2, ylabel))
    for s in series:
        step = max(1, len(s["x"]) // 400)
        d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", px(s["x"][k]), py(s["y"][k])) for i, k in enumerate(range(0, len(s["x"]), step)))
        dash = ' stroke-dasharray="6 4"' if s.get("dash") else ""
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"%s/>' % (d, s["color"], dash))
    lx = ml + 6
    for s in series:
        o.append('<rect x="%d" y="11" width="14" height="3" fill="%s"/><text fill="var(--ink2)" font-size="11" x="%d" y="16">%s</text>' % (lx, s["color"], lx + 18, s["label"]))
        lx += 172
    o.append("</svg>")
    return "".join(o)


def series(fn, ykey_time="time"):
    out = []
    for k, (label, color, _, _) in RUNS.items():
        r = fn(k)
        if r is not None:
            out.append({"label": label, "color": color, "x": r[0], "y": r[1]})
    return out


tm = lambda k: E[k]["time"] * 1e6
c_lost = line_chart(series(lambda k: (tm(k), E0 - E[k]["ETOTAL"])), "model energy removed (J)")
c_vd = line_chart(series(lambda k: (tm(k), E[k]["ALLVD"])), "viscous dissipation (J)")
c_ie = line_chart(series(lambda k: (tm(k), E[k]["ALLIE"])), "internal energy (J)")
c_allke = line_chart(series(lambda k: (tm(k), E[k]["ALLKE"])), "total kinetic energy, ALLKE (J)", ymin=0)
c_speed = c_bke = c_del = ""
c_fpen = c_hpen = ""
if VW:
    c_speed = line_chart(series(lambda k: (VW[k]["t_us"], VW[k]["vz"]) if k in VW else None), "ball speed (m/s)", ymin=400, ymax=510)
    c_bke = line_chart(series(lambda k: (VW[k]["t_us"], KE[k][0] - KE[k]) if k in VW else None), "ball kinetic energy lost (J)")
    c_del = line_chart(series(lambda k: (VW[k]["t_us"], 100.0 * VW[k]["deleted"] / VW[k]["n_host"]) if k in VW else None),
                       "host elements deleted (% of host)")

if PEN:
    def pser(key):
        return [{"label": RUNS[k][0], "color": RUNS[k][1], "x": PEN[k]["t_us"], "y": PEN[k][key]} for k in PEN]
    c_fpen = line_chart(pser("fiber_in"), "fiber nodes inside the ball")
    c_hpen = line_chart(pser("host_alive_in"), "host nodes inside the ball (surviving elements)")
    c_fdep = line_chart(pser("fiber_depth_mm"), "deepest fiber-node penetration (mm)")
    c_hdep = line_chart(pser("host_alive_depth_mm"), "deepest host-node penetration (mm)")
# ---------------------------------------------------------------- videos
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def encode(src, out_name, pattern):
    if not os.path.isdir(src):
        return None
    out = os.path.join(VID, out_name)
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(src, pattern),
                        "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", out], check=True)
    return "pw_video/" + out_name


def ply_vid(run, p, v):
    return encode(os.path.join(PW, run, "frames_video", p, v), "%s_%s_%s.mp4" % (run, p, v), "%s_%s_%%04d.png" % (p, v))


def existing(path, rel):
    return rel if os.path.exists(path) else None


def solid_vid(key, p, v):
    if key == "cc_solid":
        f = "cc500_100_%s_%s.mp4" % (p, v)
        return existing(os.path.join(OLD_VID, f), "cc_video/" + f)
    f = "v500star_100_%s_%s.mp4" % (p, v)
    return existing(os.path.join(FLAT_VID, f), "fc_video/" + f)


VIEWS = [("iso", "Isometric", "Default overview."),
         ("sidev", "Symmetry plane, plate vertical, ball left to right", "Cross-section at the ball axis; the plywise runs show the ply layers and any delamination."),
         ("side", "Symmetry plane, plate horizontal", "Plywise and concave solid only; no flat solid render exists for this view.")]
PASSES = (("wire", "Wireframe, fibers blue, ball grey"), ("status", "Solid, STATUS (red = alive)"))
ORDER = (("flat_solid", None), ("flat_ply", "pw_flat500_v3"), ("cc_solid", None), ("cc_ply", "pw_cc500_v3"))
vids = ""
for v, title, note in VIEWS:
    cells = ""
    for p, plabel in PASSES:
        for key, run in ORDER:
            src = ply_vid(run, p, v) if run else solid_vid(key, p, v)
            if src:
                cells += ('<figure><video src="%s" style="width:100%%" controls loop muted playsinline preload="metadata"></video>'
                          '<figcaption>%s &middot; %s</figcaption></figure>' % (src, RUNS[key][0], plabel))
    if cells:
        vids += '<h3>%s</h3><p class="note">%s</p><div class="vids">%s</div>' % (title, note, cells)

# ---------------------------------------------------------------- page
css = open(TEMPLATE, encoding="utf-8", errors="replace").read()
css = css[:css.index("</style>")].replace("<title>Flat v2 Contact Run</title>", "<title>Plywise vs Solid Plate Impact</title>")
css += """
.vids{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}
.vids figure{margin:0}.vids figcaption{font-size:13px;color:var(--mute);margin-top:4px}
.note{color:var(--mute);font-size:13.5px;margin:-4px 0 6px}
@media (max-width:640px){.vids{grid-template-columns:1fr}}
</style>"""

cols = list(RUNS)
fmt = lambda s, key, f: (f % s[key]) if key in s else "n/a"
rows = [
    ("Ball speed at 100 us (m/s)", [fmt(stats[k], "ball_speed_100", "%.1f") for k in cols]),
    ("Ball speed retained", [("%.1f%%" % (100 * stats[k]["ball_speed_frac"])) if "ball_speed_frac" in stats[k] else "n/a" for k in cols]),
    ("Ball kinetic energy lost (J), of %.1f J" % E0, [fmt(stats[k], "ball_ke_lost", "%.1f") for k in cols]),
    ("Model energy removed (J)", [fmt(stats[k], "model_lost", "%.1f") for k in cols]),
    ("Viscous dissipation ALLVD (J)", [fmt(stats[k], "viscous", "%.1f") for k in cols]),
    ("Internal energy at 100 us (J)", [fmt(stats[k], "ie_end", "%.1f") for k in cols]),
    ("Peak internal energy (J)", [fmt(stats[k], "ie_peak", "%.1f") for k in cols]),
    ("Peak fiber nodes inside the ball", [fmt(stats[k], "fiber_in_peak", "%d") for k in cols]),
    ("Deepest fiber-node penetration (mm)", [fmt(stats[k], "fiber_depth_peak_mm", "%.3f") for k in cols]),
    ("Peak host nodes inside the ball (nodes with a surviving element)", [fmt(stats[k], "host_alive_in_peak", "%d") for k in cols]),
    ("Deepest such host-node penetration (mm)", [fmt(stats[k], "host_alive_depth_peak_mm", "%.3f") for k in cols]),
    ("Peak host nodes inside the ball (all nodes, including deleted elements)", [fmt(stats[k], "host_in_peak", "%d") for k in cols]),
    ("Host elements deleted at 100 us", [("{:,} of {:,} ({:.1f}%)".format(stats[k]["deleted"], stats[k]["n_host"], 100 * stats[k]["deleted_frac"])) if "deleted" in stats[k] else "n/a" for k in cols]),
]
table = "<tr><th>Metric</th>" + "".join('<th class="n">%s</th>' % RUNS[k][0] for k in cols) + "</tr>" + "".join(
    "<tr><td>%s</td>%s</tr>" % (lab, "".join('<td class="n">%s</td>' % c for c in cells)) for lab, cells in rows)
v1rows = "".join('<tr><td>%s</td><td class="n">%.1f</td><td class="n">%.1f</td><td class="n">%.1f</td></tr>' % (
    V1[k][0], stats[k]["model_lost"], stats[k]["viscous"], stats[k]["allke_end"]) for k in E1)

body_tpl = """
<main>
<h1>Plywise laminate against the solid host</h1>
<div class="meta">500 m/s ball impact, 0 to 100 us &middot; ROAR jobs 56525373 / 56525375 (plywise v3), 56524507 / 56524512 (plywise v1) &middot; solid baselines v500star_100 and cc500_100 &middot; branch vuel-plastic-failure &middot; 17 Oct 2026</div>

<div class="verdict">
%(verdict)s
</div>

<h2>Results</h2>
<div class="tbl"><table>%(table)s</table></div>

%(charts)s

<h2>Videos</h2>
<p>Each group shows, from left to right and top to bottom: flat solid, flat plywise, concave solid, concave plywise; 0 to 100 us.</p>
%(vids)s

<h2>What differs between solid and plywise</h2>
<div class="tbl"><table>
<tr><th>Item</th><th>Solid host (earlier runs)</th><th>Plywise (this report)</th></tr>
<tr><td>Through the thickness</td><td>10 hex layers, one continuous host</td><td>8 plies, one hex each, as separate instances (1.25 mm)</td></tr>
<tr><td>Interfaces</td><td>None (continuous)</td><td>Cohesive general contact, Hazzard 2018 Dyneema, ballistic rate</td></tr>
<tr><td>Host elements</td><td>24,000 VU1 + 24,000 ghosts</td><td>19,200 VU1 + 19,200 ghosts</td></tr>
<tr><td>Fibers</td><td>Alternating families, 8 layers (flat 14,192 / concave 13,792 nodes)</td><td>One 0/90 layer per ply, 8 plies (flat 12,864 / concave 12,912 nodes), ends on the plate boundary</td></tr>
<tr><td>Same in both</td><td colspan="2">Ghost scale 1e-4, ghost ductile failure strain 1e-6, VU1 failure strain 0.1138, 500 m/s, step 1e-4 s, output every 7e-8 s, node-based plate and fiber ball contact plus element-based Surf-1 / Surf-2</td></tr>
</table></div>

<h2>Plywise v1 runs (before the contact and fiber-boundary fixes)</h2>
<p>The first plywise decks had no element-based ball contact and fibers stopped one radius short of the boundary. They are kept as an intermediate data point.</p>
<div class="tbl"><table><tr><th>Run</th><th class="n">Model energy removed (J)</th><th class="n">ALLVD (J)</th><th class="n">ALLKE at 100 us (J)</th></tr>%(v1rows)s</table></div>

<h2>Caveats</h2>
<ul>
<li>Penetration is measured on the exported nodes against the convex hull of the exported ball nodes (the same test as the earlier fiber-contact report). The ball is nearly convex, but a surface dent would make the depth slightly too large. Host nodes with no surviving element are excluded from the main host count, since Abaqus drops them from the node contact, and are listed separately in the table.</li>
<li>This is a visual and capability check. One run per configuration, no repeat.</li>
<li>Plywise has 8 plies of 1.25 mm and the solid host has 10 layers of 1 mm, so the element counts and the element height differ; the fraction of the host deleted is the fair comparison, not the count.</li>
<li>Fiber contact thickness is the plate value in the plywise decks (0.496 mm flat, 0.499 mm concave); the solid runs used 0.471 to 0.473 mm.</li>
<li>Some host cells carry a computed fiber volume fraction at or above 1 (about 17 to 21 per ply); the VUEL floors the matrix fraction there. A 1 mm fiber in a 1.25 mm ply is at the 0.8x guidance limit.</li>
<li>Abaqus reports the cohesive interfaces as accepted; damage output of the interfaces (CSDMG) was not requested, so delamination is judged from the videos only.</li>
</ul>
</main>
"""
chart_html = ""
for cap, c in (("Ball speed (m/s). Mean ball node velocity toward the plate.", c_speed),
               ("Ball kinetic energy lost (J), from the exported ball node velocities.", c_bke),
               ("Model energy removed (J): initial total energy minus ETOTAL.", c_lost),
               ("Total kinetic energy, ALLKE (J).", c_allke),
               ("Viscous dissipation, ALLVD (J).", c_vd),
               ("Internal energy, ALLIE (J).", c_ie),
               ("Host elements deleted (% of the host).", c_del),
               ("Fiber nodes inside the ball (count per frame).", c_fpen),
               ("Deepest fiber-node penetration into the ball (mm).", c_fdep if PEN else ""),
               ("Host nodes inside the ball, nodes with a surviving element (count per frame).", c_hpen),
               ("Deepest host-node penetration into the ball (mm).", c_hdep if PEN else "")):
    if c:
        chart_html += '<figure class="fig"><figcaption><b>%s</b></figcaption>%s</figure>' % (cap, c)

# verdict text is written from the numbers
def vtxt():
    p = []
    for flat, solid, ply in (("Flat", "flat_solid", "flat_ply"), ("Concave", "cc_solid", "cc_ply")):
        a, b = stats[solid], stats[ply]
        if "ball_speed_100" in a and "ball_speed_100" in b:
            p.append("<p><strong>%s plate.</strong> At 100 us the ball is moving at %.1f m/s on the plywise plate and %.1f m/s on the solid plate "
                     "(%+.1f m/s). The ball loses %.1f J of kinetic energy on the plywise plate against %.1f J on the solid plate, and %.1f%% of the "
                     "plywise host is deleted against %.1f%% of the solid host.</p>" % (
                         flat, b["ball_speed_100"], a["ball_speed_100"], b["ball_speed_100"] - a["ball_speed_100"],
                         b["ball_ke_lost"], a["ball_ke_lost"], 100 * b["deleted_frac"], 100 * a["deleted_frac"]))
        else:
            p.append("<p><strong>%s plate.</strong> Model energy removed: %.1f J plywise, %.1f J solid.</p>" % (
                flat, b["model_lost"], a["model_lost"]))
    return "".join(p)


html = css + body_tpl % dict(verdict=vtxt(), table=table, charts=chart_html, vids=vids or "<p>No videos yet.</p>", v1rows=v1rows)
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html))
print(json.dumps(stats, indent=1))
