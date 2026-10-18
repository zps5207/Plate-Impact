"""Build reports/NODE_CONTACT_SPEED_SERIES_REPORT.html from verification/roar/t_nc/summary.json.

Renders (optional): put PNGs in reports/nc_series_img/<speed>_<pass>_<view>.png, e.g. v300_status_side.png,
v300_wire_iso.png; any that exist are embedded.
"""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SUMMARY = os.path.join(ROOT, "verification", "roar", "t_nc", "summary.json")
TEMPLATE = os.path.join(ROOT, "reports", "_flat_v2_template.html")
OUT = os.path.join(ROOT, "reports", "NODE_CONTACT_SPEED_SERIES_REPORT.html")
IMG = os.path.join(ROOT, "reports", "nc_series_img")
COLORS = ["#2a6f97", "#6a8d3a", "#b4540a", "#8a4f9e", "#c2362f"]
SPEEDS = [100, 200, 300, 400, 500]

rows = {r["name"]: r for r in json.load(open(SUMMARY))}
css = open(TEMPLATE, encoding="utf-8", errors="replace").read()
css = css[:css.index("</style>") + len("</style>")]


def line_chart(series, ylabel, ymax=None, w=760, h=300):
    ml, mr, mt, mb = 56, 16, 14, 40
    tmax = max(t for s in series for t, _ in s["pts"])
    vmax = ymax or max(v for s in series for _, v in s["pts"]) * 1.05
    px = lambda t: ml + (w - ml - mr) * t / tmax
    py = lambda v: mt + (h - mt - mb) * (1 - v / vmax)
    o = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, ylabel)]
    for i in range(6):
        v = vmax * i / 5
        o.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (ml, w - mr, py(v), py(v)))
        o.append('<text class="tick" x="%d" y="%.1f" text-anchor="end">%.3g</text>' % (ml - 6, py(v) + 3, v))
    for i in range(0, 8):
        t = tmax * i / 7
        o.append('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%.0f</text>' % (px(t), h - mb + 16, t * 1e6))
    o.append('<text class="axis" x="%d" y="%d" text-anchor="middle">step time (us)</text>' % ((ml + w - mr) // 2, h - 6))
    o.append('<text class="axis" transform="rotate(-90 14 %d)" x="14" y="%d" text-anchor="middle">%s</text>'
             % (h // 2, h // 2, ylabel))
    for s in series:
        d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", px(t), py(v)) for i, (t, v) in enumerate(s["pts"]))
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, s["color"]))
    lx = ml + 10
    for s in series:
        o.append('<rect x="%d" y="%d" width="14" height="3" fill="%s"/><text class="tick" x="%d" y="%d">%s</text>'
                 % (lx, mt + 4, s["color"], lx + 18, mt + 9, s["label"]))
        lx += 92
    o.append("</svg>")
    return "".join(o)


def bar_chart(vals, labels, ylabel, w=760, h=260):
    ml, mr, mt, mb = 56, 16, 24, 40
    vmax = max(vals) * 1.15 or 1
    bw = (w - ml - mr) / len(vals)
    o = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, ylabel)]
    for i in range(5):
        v = vmax * i / 4
        y = mt + (h - mt - mb) * (1 - v / vmax)
        o.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (ml, w - mr, y, y))
        o.append('<text class="tick" x="%d" y="%.1f" text-anchor="end">%.0f</text>' % (ml - 6, y + 3, v))
    for i, (v, lab) in enumerate(zip(vals, labels)):
        bh = (h - mt - mb) * v / vmax
        x = ml + i * bw + bw * 0.2
        o.append('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (x, h - mb - bh, bw * 0.6, bh))
        o.append('<text class="val" x="%.1f" y="%.1f" text-anchor="middle">%d</text>' % (x + bw * 0.3, h - mb - bh - 5, v))
        o.append('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (x + bw * 0.3, h - mb + 16, lab))
    o.append('<text class="axis" transform="rotate(-90 14 %d)" x="14" y="%d" text-anchor="middle">%s</text>'
             % (h // 2, h // 2, ylabel))
    o.append("</svg>")
    return "".join(o)


R = [rows["v%d" % s] for s in SPEEDS]
vel = [{"label": "%d m/s" % s, "color": c, "pts": [(t, v) for t, v in r["series_ball_v"]]}
       for s, c, r in zip(SPEEDS, COLORS, R)]
ke = [{"label": "%d m/s" % s, "color": c, "pts": [(t, k / r["ke0"]) for t, k in r["series_ke"]]}
      for s, c, r in zip(SPEEDS, COLORS, R)]
nrm = [{"label": s_["label"], "color": s_["color"], "pts": [(t, v / sp) for t, v in s_["pts"]]}
       for s_, sp in zip(vel, SPEEDS)]


def tr(label, key, fmt="%d"):
    return "<tr><td>%s</td>%s</tr>" % (
        label, "".join('<td class="n">%s</td>' % (fmt % r[key]) for r in R))


table = ("<tr><th>Metric</th>%s</tr>" % "".join('<th class="n">%d m/s</th>' % s for s in SPEEDS)
         + tr("Ball speed at 70 us (m/s)", "ball_v_end", "%.1f")
         + "<tr><td>Ball speed retained</td>%s</tr>" % "".join(
             '<td class="n">%.1f%%</td>' % (100 * r["ball_v_end"] / s) for r, s in zip(R, SPEEDS))
         + tr("Kinetic energy lost (%)", "ke_lost_pct", "%.1f")
         + "<tr><td>Ball lowest point z (mm)</td>%s</tr>" % "".join(
             '<td class="n">%.2f</td>' % (r["ball_zmin_end"] * 1e3) for r in R)
         + tr("Ghost elements deleted (of 24,000)", "ghost_deleted")
         + tr("VU1 elements that met the failure criterion", "vu1_predicted_failed")
         + tr("Plate nodes that ever touched the ball", "plate_nodes_ever_contact")
         + tr("Peak plate nodes in contact in one frame", "max_contact_nodes_one_frame")
         + tr("Ball nodes ever inside a live ghost (peak)", "max_ball_nodes_inside")
         + tr("Surviving-ghost islands (within 10 mm of axis)", "islands")
         + tr("Alive ghosts within 10 mm of axis", "near_alive")
         + tr("Internal energy at end (J)", "ie_end", "%.1f")
         + tr("Plastic dissipation at end (J)", "pd_end", "%.1f"))

figs = ""
if os.path.isdir(IMG):
    for sp in SPEEDS:
        cells = ""
        for p, vname in (("status", "iso"), ("status", "side"), ("wire", "iso"), ("wire", "side")):
            f = "v%d_%s_%s.png" % (sp, p, vname)
            if os.path.exists(os.path.join(IMG, f)):
                cap = ("Solid, STATUS (red = alive)" if p == "status" else "Wireframe, fibers blue") + \
                      (", isometric" if vname == "iso" else ", symmetry plane close-up")
                cells += '<figure><img src="nc_series_img/%s" style="width:100%%" alt="%s"><figcaption>%s</figcaption></figure>' % (f, cap, cap)
        if cells:
            figs += "<h3>%d m/s</h3><div class=\"vids\">%s</div>" % (sp, cells)

VID = os.path.join(ROOT, "reports", "nc_series_video")
OUT_VIDEO = os.path.join(ROOT, "reports", "NODE_CONTACT_SPEED_SERIES_REPORT_VIDEOS.html")
VIDEO_PANELS = (
    ("wire", "sidev", "Wireframe, fibers blue, symmetry plane (plate vertical, ball travels left to right)"),
    ("wire", "iso", "Wireframe, fibers blue, isometric"),
    ("status", "iso", "Solid, STATUS (red = alive), isometric"),
    ("status", "side", "Solid, STATUS (red = alive), symmetry plane close-up"),
)
figs_v = ""
if os.path.isdir(VID):
    for sp in SPEEDS:
        cells = ""
        for p, vname, cap in VIDEO_PANELS:
            f = "v%d_%s_%s.mp4" % (sp, p, vname)
            if os.path.exists(os.path.join(VID, f)):
                cells += ('<figure><video src="nc_series_video/%s" style="width:100%%" controls loop muted '
                          'playsinline preload="metadata"></video><figcaption>%s</figcaption></figure>' % (f, cap))
        if cells:
            figs_v += "<h3>%d m/s</h3><div class=\"vids\">%s</div>" % (sp, cells)

html = css + """
<main>
<h1>Node-contact impact-speed series</h1>
<div class="meta">ROAR jobs 56386750 to 56386754 &middot; branch vuel-plastic-failure &middot; 14 Oct 2026 &middot; deck <code>Meshing/Flatv2.inp</code> with mesher-generated plate node contact</div>

<div class="verdict">
<p><strong>Result.</strong> All five runs (100, 200, 300, 400 and 500 m/s) completed to 70 us with no solver errors, and the new plate node-contact surface passed the Abaqus datacheck. The ball keeps %(keep_lo).0f to %(keep_hi).0f%% of its speed at 70 us, and 3 to 9%% of its kinetic energy is lost.</p>
<p><strong>Islands.</strong> Surviving ghost islands appear only at the two lowest speeds (%(isl100)d at 100 m/s, %(isl200)d at 200 m/s) and are zero from 300 m/s upward. No ball node ever sat inside a live ghost beyond a single node at 400 m/s.</p>
</div>

<h2>Setup</h2>
<div class="tbl"><table>
<tr><th>Item</th><th>Setting</th></tr>
<tr><td>Mesher</td><td>VU1 + ghost host, <code>--plate-node-contact --ball-instance Ball-1</code>, contact thickness auto (0.489 mm = half the median host edge)</td></tr>
<tr><td>Contact</td><td>Node surface over all 27,401 plate nodes against the ball's element surface; existing <code>General</code> interaction reused (hard, friction 0.01); the original <code>Surf-1</code>/<code>Surf-2</code> element contact is kept</td></tr>
<tr><td>Ball speed</td><td>100, 200, 300, 400, 500 m/s, only the initial-velocity line differs between runs</td></tr>
<tr><td>Step</td><td>7e-5 s explicit; each run took about 4.5 hours for 100 to 300 m/s</td></tr>
<tr><td>Datacheck</td><td>Plate-only, fibers-only and combined decks all passed with 0 errors (jobs 56386652 to 56386654)</td></tr>
</table></div>

<h2>Results</h2>
<div class="tbl"><table>%(table)s</table></div>

<figure class="fig"><figcaption><b>Ball speed against time.</b> Impact happens within about 10 us at these speeds.</figcaption>%(c_vel)s</figure>
<figure class="fig"><figcaption><b>Ball speed as a fraction of impact speed.</b></figcaption>%(c_nrm)s</figure>
<figure class="fig"><figcaption><b>Total kinetic energy as a fraction of its initial value.</b></figcaption>%(c_ke)s</figure>
<figure class="fig"><figcaption><b>Ghost elements deleted by impact speed.</b></figcaption>%(c_del)s</figure>

<h2>Notes and caveats</h2>
<ul>
<li>The ball is at or near its lowest point below the plate at 70 us in every run, so it has passed through the plate even at 100 m/s while losing only about 3%% of its energy. Whether that is physical for this material is for you to judge; the extraction measures it but does not check it.</li>
<li>The fiber node surface passed datacheck but has not been solved, so no run here exercises it.</li>
<li>The island count uses the existing rule (alive ghost within 10 mm of the axis with at least 3 neighbours, at least 60%% of them deleted). At 100 m/s the crater is small, so 8 islands there are against 489 live ghosts nearby.</li>
<li>The plate-and-element extraction scripts are the ones used for the earlier flat_v2 runs, unchanged.</li>
</ul>
%(figs)s
</main>
""" % dict(
    keep_lo=min(100 * r["ball_v_end"] / s for r, s in zip(R, SPEEDS)),
    keep_hi=max(100 * r["ball_v_end"] / s for r, s in zip(R, SPEEDS)),
    isl100=rows["v100"]["islands"], isl200=rows["v200"]["islands"],
    table=table, c_vel=line_chart(vel, "ball speed (m/s)"), c_nrm=line_chart(nrm, "v / v0", ymax=1.05),
    c_ke=line_chart(ke, "KE / KE0", ymax=1.05),
    c_del=bar_chart([r["ghost_deleted"] for r in R], ["%d m/s" % s for s in SPEEDS], "ghosts deleted"),
    figs=figs)
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html))
if figs_v:
    html_v = html.replace(figs, figs_v) if figs else html.replace("</main>", figs_v + "\n</main>")
    open(OUT_VIDEO, "w", encoding="utf-8").write(html_v)
    print("wrote", OUT_VIDEO, len(html_v))
