"""Build reports/CURVED_VS_FLAT_REPORT.html: concave curved plate (cc500_100) against the flat plate (v500star_100).

Inputs (reports/cc_run/dl/):
    cc500_100/cc500_100_energy.csv, cc500_100/cc500_100_viewer.npz, cc500_100/frames_video/ (iso, side, sidev), cc500_100/frames_more/
    v500star_100/v500star_100_energy.csv, v500star_100/frames_more/
    verification/roar/t_nc/v500star_100/v500star_100_viewer.npz (flat viewer export)
    reports/fc_video/v500star_100_<pass>_<iso|sidev>.mp4 (flat videos rendered earlier)
Videos are encoded into reports/cc_video/ with the ffmpeg from imageio_ffmpeg.
"""
import csv
import json
import os
import subprocess

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DL = os.path.join(ROOT, "reports", "cc_run", "dl")
VID = os.path.join(ROOT, "reports", "cc_video")
FLAT_VID = os.path.join(ROOT, "reports", "fc_video")
TEMPLATE = os.path.join(ROOT, "reports", "_flat_v2_template.html")
OUT = os.path.join(ROOT, "reports", "CURVED_VS_FLAT_REPORT.html")
CV, FL = "cc500_100", "v500star_100"
CC, CF = "#c2362f", "#6d7a86"            # red = curved, grey = flat
LC, LF = "Concave curved plate", "Flat plate"
V0 = 500.0
os.makedirs(VID, exist_ok=True)


# ---------------------------------------------------------------- data
def energy(path):
    rows = list(csv.DictReader(open(path)))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def viewer(path):
    d = np.load(path)
    t, bp, st = d["times"], d["ball_pos"].astype(np.float64), d["host_status"]
    vel = np.gradient(bp, t, axis=0)
    return {"t_us": t * 1e6,
            "vz": -vel[:, :, 2].mean(axis=1),                         # mean ball node speed toward the plate, m/s
            "vmag": np.linalg.norm(vel, axis=2).mean(axis=1),
            "deleted": (st.shape[1] - st.sum(axis=1)).astype(int),
            "n_host": st.shape[1], "vel": vel}


EC = energy(os.path.join(DL, CV, CV + "_energy.csv"))
EF = energy(os.path.join(DL, FL, FL + "_energy.csv"))
VC = viewer(os.path.join(DL, CV, CV + "_viewer.npz"))
VF = viewer(os.path.join(ROOT, "verification", "roar", "t_nc", FL, FL + "_viewer.npz"))
E0 = float(EC["ETOTAL"][0])
BALL_MASS = 2 * float(EC["ALLKE"][0]) / V0 ** 2          # initial KE is all ball KE


def ball_ke(v):                                          # from exported ball node velocities (nodes weighted equally)
    return 0.5 * BALL_MASS * (np.linalg.norm(v["vel"], axis=2) ** 2).mean(axis=1)


KEC, KEF = ball_ke(VC), ball_ke(VF)
stats = {}
for key, E, V, KE in (("curved", EC, VC, KEC), ("flat", EF, VF, KEF)):
    stats[key] = {
        "ball_speed_100": float(V["vz"][-1]), "ball_speed_frac": float(V["vz"][-1] / V0),
        "ball_ke_end": float(KE[-1]), "ball_ke_lost": float(KE[1] - KE[-1]),
        "model_lost": float(E0 - E["ETOTAL"][-1]), "viscous": float(E["ALLVD"][-1]),
        "ie_end": float(E["ALLIE"][-1]), "ie_peak": float(E["ALLIE"].max()),
        "allke_end": float(E["ALLKE"][-1]), "deleted": int(V["deleted"][-1]), "n_host": int(V["n_host"]),
    }
json.dump(stats, open(os.path.join(DL, "cc_vs_flat_stats.json"), "w"), indent=2)
S, F = stats["curved"], stats["flat"]


# ---------------------------------------------------------------- charts
def line_chart(series, ylabel, w=760, h=300, ymin=0.0, ymax=None, xmax=100.0, xlabel="step time (us)"):
    ml, mr, mt, mb = 62, 16, 30, 40
    vmax = ymax if ymax is not None else max(float(np.max(s["y"])) for s in series) * 1.08 or 1.0
    vmin = ymin
    px = lambda t: ml + (w - ml - mr) * t / xmax
    py = lambda v: mt + (h - mt - mb) * (1 - (v - vmin) / (vmax - vmin))
    o = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s" style="width:100%%;height:auto">' % (w, h, ylabel)]
    for i in range(6):
        v = vmin + (vmax - vmin) * i / 5
        o.append('<line stroke="var(--grid)" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (ml, w - mr, py(v), py(v)))
        o.append('<text fill="var(--mute)" font-size="11" x="%d" y="%.1f" text-anchor="end">%.4g</text>' % (ml - 6, py(v) + 3, v))
        t = xmax * i / 5
        o.append('<text fill="var(--mute)" font-size="11" x="%.1f" y="%d" text-anchor="middle">%.0f</text>' % (px(t), h - mb + 16, t))
    o.append('<text fill="var(--mute)" font-size="12" x="%d" y="%d" text-anchor="middle">%s</text>' % ((ml + w - mr) // 2, h - 6, xlabel))
    o.append('<text fill="var(--mute)" font-size="12" transform="rotate(-90 14 %d)" x="14" y="%d" text-anchor="middle">%s</text>' % (h // 2, h // 2, ylabel))
    for s in series:
        step = max(1, len(s["x"]) // 400)
        d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", px(s["x"][k]), py(s["y"][k])) for i, k in enumerate(range(0, len(s["x"]), step)))
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, s["color"]))
    lx = ml + 10
    for s in series:
        o.append('<rect x="%d" y="%d" width="14" height="3" fill="%s"/><text fill="var(--ink2)" font-size="12" x="%d" y="%d">%s</text>' % (lx, 11, s["color"], lx + 18, 16, s["label"]))
        lx += 210
    o.append("</svg>")
    return "".join(o)


def two(xc, yc, xf, yf, **kw):
    return [{"label": LC, "color": CC, "x": xc, "y": yc}, {"label": LF, "color": CF, "x": xf, "y": yf}]


tc, tf = EC["time"] * 1e6, EF["time"] * 1e6
chart_speed = line_chart(two(VC["t_us"], VC["vz"], VF["t_us"], VF["vz"]), "ball speed (m/s)", ymin=400, ymax=510)
chart_lost = line_chart(two(tc, E0 - EC["ETOTAL"], tf, E0 - EF["ETOTAL"]), "model energy removed (J)")
chart_bke = line_chart(two(VC["t_us"], KEC[0] - KEC, VF["t_us"], KEF[0] - KEF), "ball kinetic energy lost (J)")
chart_vd = line_chart(two(tc, EC["ALLVD"], tf, EF["ALLVD"]), "viscous dissipation (J)")
chart_ie = line_chart(two(tc, EC["ALLIE"], tf, EF["ALLIE"]), "internal energy (J)")
chart_del = line_chart(two(VC["t_us"], VC["deleted"], VF["t_us"], VF["deleted"]), "host elements deleted")


# ---------------------------------------------------------------- videos
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def encode(frames_dir, p, v, out_name):
    out = os.path.join(VID, out_name)
    src = os.path.join(frames_dir, p, v)
    if not os.path.isdir(src):
        return None
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i",
                        os.path.join(src, "%s_%s_%%04d.png" % (p, v)), "-vf", "scale=1280:-2",
                        "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
    return "cc_video/" + out_name


VIEWS = [
    ("cut", "Into the symmetry cut faces, elevated 35 degrees", "Shows the cross-section through the plate and the ball's path."),
    ("outer", "From the free side, elevated 35 degrees", "Looks over the plate toward the ball; shows the surface the ball strikes."),
    ("top", "Straight down onto the impact face", "Shows where the plate fails and how far damage spreads sideways."),
    ("bottom", "From beneath, the back face", "Shows what exits the back of the plate."),
    ("grazing", "Low angle along the plate surface (8 degrees)", "Shows the plate bulging and the ball leaving."),
    ("close", "Close-up of the contact region", "Zoomed on the ball and the plate directly under it."),
    ("iso", "Isometric", "Default overview."),
    ("sidev", "Symmetry plane, plate vertical, ball left to right", "Cross-section at the ball axis. Framed for a flat plate, so the curved rim runs off the top."),
    ("side", "Symmetry plane, plate horizontal", "Curved plate only; no flat render was made for this view."),
]
PASSES = (("wire", "Wireframe, fibers blue, ball grey"), ("status", "Solid, STATUS (red = alive)"))


def flat_src(p, v):
    if v in ("iso", "sidev"):
        f = "%s_%s_%s.mp4" % (FL, p, v)
        return ("fc_video/" + f) if os.path.exists(os.path.join(FLAT_VID, f)) else None
    return encode(os.path.join(DL, FL, "frames_more"), p, v, "%s_%s_%s.mp4" % (FL, p, v))


def curved_src(p, v):
    base = "frames_video" if v in ("iso", "side", "sidev") else "frames_more"
    return encode(os.path.join(DL, CV, base), p, v, "%s_%s_%s.mp4" % (CV, p, v))


vids = ""
for v, title, note in VIEWS:
    cells = ""
    for p, plabel in PASSES:
        c, f = curved_src(p, v), flat_src(p, v)
        if not c:
            continue
        for src, lab in ((c, LC), (f, LF)):
            if src:
                cells += ('<figure><video src="%s" style="width:100%%" controls loop muted playsinline preload="metadata"></video>'
                          '<figcaption>%s &middot; %s</figcaption></figure>' % (src, lab, plabel))
    if cells:
        vids += '<h3>%s</h3><p class="note">%s</p><div class="vids">%s</div>' % (title, note, cells)
print("videos:", len(os.listdir(VID)))


# ---------------------------------------------------------------- page
css = open(TEMPLATE, encoding="utf-8", errors="replace").read()
css = css[:css.index("</style>")].replace("<title>Flat v2 Contact Run</title>", "<title>Curved vs Flat Plate Impact</title>")
css += """
.vids{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}
.vids figure{margin:0}.vids figcaption{font-size:13px;color:var(--mute);margin-top:4px}
.note{color:var(--mute);font-size:13.5px;margin:-4px 0 6px}
@media (max-width:640px){.vids{grid-template-columns:1fr}}
</style>"""


def d(a, b, fmt="%.1f"):
    return fmt % (a - b)


rows = [
    ("Ball speed at 100 us (m/s)", "%.1f" % S["ball_speed_100"], "%.1f" % F["ball_speed_100"]),
    ("Ball speed retained at 100 us", "%.1f%%" % (100 * S["ball_speed_frac"]), "%.1f%%" % (100 * F["ball_speed_frac"])),
    ("Ball kinetic energy lost (J), of 1,023.4 J", "%.1f" % S["ball_ke_lost"], "%.1f" % F["ball_ke_lost"]),
    ("Model energy removed, initial minus ETOTAL (J)", "%.1f" % S["model_lost"], "%.1f" % F["model_lost"]),
    ("Viscous dissipation, ALLVD (J)", "%.1f" % S["viscous"], "%.1f" % F["viscous"]),
    ("Internal energy at 100 us (J)", "%.1f" % S["ie_end"], "%.1f" % F["ie_end"]),
    ("Peak internal energy (J)", "%.1f" % S["ie_peak"], "%.1f" % F["ie_peak"]),
    ("Host elements deleted at 100 us (of 24,000)", "{:,}".format(S["deleted"]), "{:,}".format(F["deleted"])),
]
table = '<tr><th>Metric</th><th class="n">%s</th><th class="n">%s</th></tr>' % (LC, LF) + "".join(
    '<tr><td>%s</td><td class="n">%s</td><td class="n">%s</td></tr>' % r for r in rows)

html = css + """
<main>
<h1>Concave curved plate against the flat plate</h1>
<div class="meta">500 m/s ball impact, 0 to 100 us &middot; ROAR jobs 56512623 (curved) and the earlier v500star_100 (flat) &middot; branch vuel-plastic-failure &middot; 17 Oct 2026</div>

<div class="kv">
<div><b>%(sc).1f m/s</b><span>ball speed at 100 us, curved (flat %(sf).1f)</span></div>
<div><b>%(bc).1f J</b><span>ball kinetic energy lost, curved (flat %(bf).1f)</span></div>
<div><b>%(mc).1f J</b><span>model energy removed, curved (flat %(mf).1f)</span></div>
</div>

<div class="verdict">
<p><strong>Ball speed.</strong> At 100 us the ball is moving at %(sc).1f m/s on the curved plate and %(sf).1f m/s on the flat plate, so the curved plate leaves it %(dv)s m/s faster (%(pc).1f%% of the 500 m/s retained against %(pf).1f%%). This is the mean velocity of the ball's nodes along the impact axis.</p>
<p><strong>Energy.</strong> The ball loses %(bc).1f J of kinetic energy on the curved plate and %(bf).1f J on the flat plate (of 1,023.4 J). The model as a whole loses %(mc).1f J against %(mf).1f J, measured as the initial total energy minus Abaqus's ETOTAL at 100 us. Viscous dissipation is %(vc).1f J against %(vf).1f J. In every measure the curved plate takes less energy out of the ball, by %(dpct).0f%% on ball kinetic energy.</p>
<p><strong>Damage.</strong> The curved plate has %(delc)s host elements deleted at 100 us against %(delf)s for the flat plate, so it loses more material and still takes less energy from the ball. This is one run each, and the two plates also differ in fiber layout, so I would not read a mechanism from it without more cases.</p>
</div>

<h2>Results</h2>
<div class="tbl"><table>%(table)s</table></div>

<figure class="fig"><figcaption><b>Ball speed (m/s).</b> Mean ball node velocity toward the plate, differentiated from the exported node positions.</figcaption>%(c_speed)s</figure>
<figure class="fig"><figcaption><b>Ball kinetic energy lost (J).</b> Initial ball KE minus the ball KE at each frame, from node velocities.</figcaption>%(c_bke)s</figure>
<figure class="fig"><figcaption><b>Model energy removed (J).</b> Initial total energy minus ETOTAL from the history output. This is the energy that left the model. Element deletion removes energy this way, but I have not separated it from other numerical loss.</figcaption>%(c_lost)s</figure>
<figure class="fig"><figcaption><b>Viscous dissipation (J).</b> ALLVD, the bulk-viscosity damping.</figcaption>%(c_vd)s</figure>
<figure class="fig"><figcaption><b>Internal energy (J).</b> ALLIE, elastic and plastic strain energy held in the model.</figcaption>%(c_ie)s</figure>
<figure class="fig"><figcaption><b>Host elements deleted.</b></figcaption>%(c_del)s</figure>

<h2>Videos</h2>
<p>Each pair shows the curved plate on the left and the flat plate on the right, 0 to 100 us, 210 frames at 24 fps. The wireframe videos show the fibers in blue.</p>
%(vids)s

<h2>What differs between the two runs</h2>
<div class="tbl"><table>
<tr><th>Item</th><th>Curved</th><th>Flat</th></tr>
<tr><td>Plate</td><td>Spherical concave bowl, radius 0.25 m, rim 5.05 mm above the centre; ball strikes the concave side</td><td>Flat</td></tr>
<tr><td>Fiber nodes</td><td>{:,}</td><td>{:,}</td></tr>
<tr><td>Contact thickness (plate / fiber nodes)</td><td>0.499 mm / 0.473 mm</td><td>0.489 mm / 0.471 mm</td></tr>
<tr><td>Everything else</td><td colspan="2">Same ball, 500 m/s velocity, VUEL and ghost host, node-based ball contact, step 1e-4 s, output every 7e-8 s</td></tr>
</table></div>

<h2>Caveats</h2>
<ul>
<li>The plates are not identical apart from curvature: the fiber layout follows the curved surface and the contact thickness values differ slightly (table above), so some of the difference may come from those rather than the shape.</li>
<li>The model-energy figure is a bookkeeping difference. Plastic dissipation (ALLPD) was not extracted for the curved run, so I cannot split it into plastic work and energy lost to element deletion.</li>
<li>The side-view (plate vertical) videos are framed for a flat plate, so the raised curved rim runs off the top of the frame.</li>
<li>One run per configuration; small differences in speed or energy would need more cases to establish.</li>
</ul>
</main>
""".format(13792, 14192) % dict(
    sc=S["ball_speed_100"], sf=F["ball_speed_100"], bc=S["ball_ke_lost"], bf=F["ball_ke_lost"],
    mc=S["model_lost"], mf=F["model_lost"], vc=S["viscous"], vf=F["viscous"],
    dv=d(S["ball_speed_100"], F["ball_speed_100"]), pc=100 * S["ball_speed_frac"], pf=100 * F["ball_speed_frac"],
    dpct=100 * (F["ball_ke_lost"] - S["ball_ke_lost"]) / F["ball_ke_lost"],
    delc="{:,}".format(S["deleted"]), delf="{:,}".format(F["deleted"]), table=table, vids=vids or "<p>No videos.</p>",
    c_speed=chart_speed, c_bke=chart_bke, c_lost=chart_lost, c_vd=chart_vd, c_ie=chart_ie, c_del=chart_del)
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html))
print(json.dumps(stats, indent=1))
