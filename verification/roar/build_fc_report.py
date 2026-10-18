"""Build reports/FIBER_CONTACT_COMPARISON_REPORT.html: v500 (no fiber contact) vs v500* (fiber contact), 0 to 100 us.

Inputs: verification/roar/t_nc/compare_fc.json   (compare_fiber_contact.py, from the viewer .npz files)
        verification/roar/t_nc/summary_fc.json   (summarize_nc.py t_nc v500_100,v500star_100 summary_fc.json, from the ODB post-processing)
        reports/fc_video/<case>_<pass>_<view>.mp4 (optional)
"""
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
T_NC = os.path.join(ROOT, "verification", "roar", "t_nc")
TEMPLATE = os.path.join(ROOT, "reports", "_flat_v2_template.html")
OUT = os.path.join(ROOT, "reports", "FIBER_CONTACT_COMPARISON_REPORT.html")
VID = os.path.join(ROOT, "reports", "fc_video")
A, B = "v500_100", "v500star_100"
CA, CB = "#6d7a86", "#c2362f"          # grey = no fiber contact, red = fiber contact
LA, LB = "v500, no fiber contact", "v500*, fiber contact"

cmp_ = json.load(open(os.path.join(T_NC, "compare_fc.json")))
rows = {}
sp = os.path.join(T_NC, "summary_fc.json")
if os.path.exists(sp):
    rows = {r["name"]: r for r in json.load(open(sp)) if "error" not in r}
css = open(TEMPLATE, encoding="utf-8", errors="replace").read()
css = css[:css.index("</style>")]
css = css.replace("<title>Flat v2 Contact Run</title>", "<title>Fiber Contact Comparison</title>")
css += """
.vids{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}
.vids figure{margin:0}.vids figcaption{font-size:13px;color:var(--mute);margin-top:4px}
@media (max-width:640px){.vids{grid-template-columns:1fr}}
.chart .line{fill:none;stroke-width:2}
</style>"""


def line_chart(series, ylabel, ymax=None, w=760, h=300, xmax=None):
    ml, mr, mt, mb = 60, 16, 28, 40
    tmax = xmax or max(t for s in series for t, _ in s["pts"])
    vmax = ymax or max(max(v for _, v in s["pts"]) for s in series) * 1.08 or 1
    px = lambda t: ml + (w - ml - mr) * t / tmax
    py = lambda v: mt + (h - mt - mb) * (1 - v / vmax)
    o = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s" style="width:100%%;height:auto">' % (w, h, ylabel)]
    for i in range(6):
        v = vmax * i / 5
        o.append('<line class="grid" stroke="var(--grid)" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (ml, w - mr, py(v), py(v)))
        o.append('<text class="tick" fill="var(--mute)" font-size="11" x="%d" y="%.1f" text-anchor="end">%.4g</text>' % (ml - 6, py(v) + 3, v))
    for i in range(0, 6):
        t = tmax * i / 5
        o.append('<text class="tick" fill="var(--mute)" font-size="11" x="%.1f" y="%d" text-anchor="middle">%.0f</text>' % (px(t), h - mb + 16, t))
    o.append('<text fill="var(--mute)" font-size="12" x="%d" y="%d" text-anchor="middle">step time (us)</text>' % ((ml + w - mr) // 2, h - 6))
    o.append('<text fill="var(--mute)" font-size="12" transform="rotate(-90 14 %d)" x="14" y="%d" text-anchor="middle">%s</text>' % (h // 2, h // 2, ylabel))
    for s in series:
        d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", px(t), py(v)) for i, (t, v) in enumerate(s["pts"]))
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, s["color"]))
    lx = ml + 10
    for s in series:
        o.append('<rect x="%d" y="%d" width="14" height="3" fill="%s"/><text fill="var(--ink2)" font-size="12" x="%d" y="%d">%s</text>' % (lx, 10, s["color"], lx + 18, 15, s["label"]))
        lx += 230
    o.append("</svg>")
    return "".join(o)


def series(key, scale=1.0):
    return [{"label": LA, "color": CA, "pts": list(zip(cmp_[A]["t_us"], [v * scale for v in cmp_[A][key]]))},
            {"label": LB, "color": CB, "pts": list(zip(cmp_[B]["t_us"], [v * scale for v in cmp_[B][key]]))}]


def at(c, key, t_us):
    ts = cmp_[c]["t_us"]
    i = min(range(len(ts)), key=lambda k: abs(ts[k] - t_us))
    return cmp_[c][key][i]


a, b = cmp_[A], cmp_[B]
v0 = 500.0
peak = lambda c, k: max(cmp_[c][k])
metrics = [
    ("Peak fiber nodes inside the ball (of 14,192)", "%d" % peak(A, "fiber_in_ball"), "%d" % peak(B, "fiber_in_ball")),
    ("Deepest fiber-node penetration into the ball (mm)", "%.2f" % peak(A, "fiber_max_depth_mm"), "%.2f" % peak(B, "fiber_max_depth_mm")),
    ("Peak host nodes inside the ball (control)", "%d" % peak(A, "host_in_ball"), "%d" % peak(B, "host_in_ball")),
    ("Deepest host-node penetration (mm)", "%.2f" % peak(A, "host_max_depth_mm"), "%.2f" % peak(B, "host_max_depth_mm")),
    ("Ball speed at 70 us (m/s)", "%.1f" % at(A, "ball_vz", 70), "%.1f" % at(B, "ball_vz", 70)),
    ("Ball speed at 100 us (m/s)", "%.1f" % a["ball_vz"][-1], "%.1f" % b["ball_vz"][-1]),
    ("Ball speed retained at 100 us", "%.1f%%" % (100 * a["ball_vz"][-1] / v0), "%.1f%%" % (100 * b["ball_vz"][-1] / v0)),
    ("Host (ghost) elements deleted at 70 us", "%d" % at(A, "host_deleted", 70), "%d" % at(B, "host_deleted", 70)),
    ("Host (ghost) elements deleted at 100 us (of 24,000)", "%d" % a["host_deleted"][-1], "%d" % b["host_deleted"][-1]),
    ("Fiber nodes below the plate's lower face at 100 us", "%d" % a["fiber_below_plate"][-1], "%d" % b["fiber_below_plate"][-1]),
    ("Peak fiber-segment strain (max over segments)", "%.2f" % peak(A, "fiber_strain_max"), "%.2f" % peak(B, "fiber_strain_max")),
    ("Peak segments stretched more than 10%", "%d" % peak(A, "fiber_over_10pct"), "%d" % peak(B, "fiber_over_10pct")),
    ("Largest fiber-node displacement at 100 us (mm)", "%.1f" % a["fiber_max_disp_mm"][-1], "%.1f" % b["fiber_max_disp_mm"][-1]),
]
ra, rb = rows.get(A), rows.get(B)
if ra and rb:
    odb = [
        ("Kinetic energy lost over the step (%)", "ke_lost_pct", "%.1f"),
        ("Internal energy at end (J)", "ie_end", "%.1f"),
        ("Plastic dissipation at end (J)", "pd_end", "%.1f"),
        ("Viscous dissipation at end (J)", "vd_end", "%.2f"),
        ("Plate nodes that ever touched the ball", "plate_nodes_ever_contact", "%d"),
        ("Peak plate nodes in contact in one frame", "max_contact_nodes_one_frame", "%d"),
        ("Ball nodes ever inside a live ghost (peak)", "max_ball_nodes_inside", "%d"),
    ]
    for lab, key, fmt in odb:
        metrics.append((lab, fmt % ra[key], fmt % rb[key]))
table = "<tr><th>Metric</th><th class=\"n\">%s</th><th class=\"n\">%s</th></tr>" % (LA, LB) + "".join(
    "<tr><td>%s</td><td class=\"n\">%s</td><td class=\"n\">%s</td></tr>" % m for m in metrics)

ke = ""
if ra and rb:
    ks = lambda r, c, lab: {"label": lab, "color": c, "pts": [(t * 1e6, k / r["ke0"]) for t, k in r["series_ke"]]}
    ke = ('<figure class="fig"><figcaption><b>Total kinetic energy as a fraction of its initial value.</b> '
          'From the ODB history output.</figcaption>%s</figure>' % line_chart([ks(ra, CA, LA), ks(rb, CB, LB)], "KE / KE0", ymax=1.05))

vids = ""
panels = (("wire", "sidev", "Wireframe, fibers blue, symmetry plane (plate vertical, ball left to right)"),
          ("wire", "iso", "Wireframe, fibers blue, isometric"),
          ("status", "sidev", "Solid, STATUS (red = alive), symmetry plane"),
          ("status", "iso", "Solid, STATUS (red = alive), isometric"))
if os.path.isdir(VID):
    for p, v, cap in panels:
        fa, fb = "%s_%s_%s.mp4" % (A, p, v), "%s_%s_%s.mp4" % (B, p, v)
        if os.path.exists(os.path.join(VID, fa)) and os.path.exists(os.path.join(VID, fb)):
            vids += "<h3>%s</h3><div class=\"vids\">" % cap
            for f, lab in ((fa, LA), (fb, LB)):
                vids += ('<figure><video src="fc_video/%s" style="width:100%%" controls loop muted playsinline '
                         'preload="metadata"></video><figcaption>%s</figcaption></figure>' % (f, lab))
            vids += "</div>"

d_fib = "%d to %d nodes and %.1f mm to %.2f mm" % (peak(A, "fiber_in_ball"), peak(B, "fiber_in_ball"),
                                                   peak(A, "fiber_max_depth_mm"), peak(B, "fiber_max_depth_mm"))
html = css + """
<main>
<h1>Fiber contact: v500 against v500*</h1>
<div class="meta">500 m/s ball impact, 0 to 100 us &middot; ROAR jobs 56489085 and 56489086 &middot; branch vuel-plastic-failure &middot; 16 Oct 2026</div>

<div class="verdict">
<p><strong>Result.</strong> Putting the fiber nodes into the node-based ball contact stops the fibers passing through the ball. The peak number of fiber nodes inside the ball falls from %(f0)d to %(f1)d, and the deepest penetration from %(d0).2f mm to %(d1).2f mm. The plate nodes, which were already in contact, stay outside the ball in both runs (the control).</p>
<p><strong>Side effects.</strong> With fiber contact %(del1)s host elements are deleted by 100 us against %(del0)s without it, and the ball ends at %(vb1).0f m/s against %(vb0).0f m/s. The two deletion curves are the same up to about 20 us and then separate, and the gap keeps growing through 100 us. The fibers now carry load against the ball, which changes how much of the plate fails and how much speed the ball keeps. These are one run per case; the size of the differences is not tested against mesh or setup changes.</p>
<p><strong>Fibers.</strong> In the wireframe videos the fibers no longer sit inside the ball. They are held at its surface and thrown outward as it passes. At 100 us %(fb1)s fiber nodes are below the plate's lower face against %(fb0)s, and %(s1)s segments are stretched by more than 10%% against %(s0)s. The largest segment strain is %(sm1).0f against %(sm0).0f (engineering strain: 66 means a segment stretched to 67 times its original length). I did not check whether the fiber elements have a failure criterion; strains this large suggest they do not break.</p>
</div>

<h2>What differs between the two runs</h2>
<div class="tbl"><table>
<tr><th>Item</th><th>v500 (grey)</th><th>v500* (red)</th></tr>
<tr><td>Ball contact with the plate</td><td colspan="2">Node surface over all 27,401 plate nodes against the ball element surface (existing)</td></tr>
<tr><td>Ball contact with the fibers</td><td>none</td><td>Node surface over all 14,192 fiber nodes against the same ball surface, contact thickness 0.471 mm (mesher automatic)</td></tr>
<tr><td>Everything else</td><td colspan="2">Same mesh, material, velocity (500 m/s), VU1 + ghost host, bulk viscosity and output spacing (0.07 us per frame)</td></tr>
<tr><td>Step</td><td colspan="2">1e-4 s (the earlier v500 run stopped at 7e-5 s)</td></tr>
<tr><td>Check</td><td colspan="2">The new baseline matches the earlier 70 us v500 run (1,682 against 1,684 deleted hosts at 70 us, ball speed 465.2 m/s)</td></tr>
</table></div>

<h2>Results</h2>
<div class="tbl"><table>%(table)s</table></div>

<figure class="fig"><figcaption><b>Fiber nodes inside the ball.</b> Counted per frame as nodes inside the convex hull of the deformed ball nodes.</figcaption>%(c1)s</figure>
<figure class="fig"><figcaption><b>Deepest fiber-node penetration into the ball (mm).</b></figcaption>%(c2)s</figure>
<figure class="fig"><figcaption><b>Ball speed (m/s).</b> Mean ball node velocity toward the plate.</figcaption>%(c3)s</figure>
<figure class="fig"><figcaption><b>Host (ghost) elements deleted.</b></figcaption>%(c4)s</figure>
<figure class="fig"><figcaption><b>Peak fiber-segment strain (engineering).</b> Largest stretch of any fiber segment.</figcaption>%(c5)s</figure>
<figure class="fig"><figcaption><b>Fiber nodes below the plate's lower face.</b> Fibers dragged out of the plate on the exit side.</figcaption>%(c6)s</figure>
%(ke)s

<h2>Videos</h2>
%(vids)s

<h2>Caveats</h2>
<ul>
<li>Penetration is measured on the exported nodes against the convex hull of the ball. The ball is nearly convex, but a dent in its surface would make the depth slightly too large. Host nodes are the control: they reach at most %(hd0).2f mm (v500) and %(hd1).2f mm (v500*) inside the hull, which is the noise floor of this test.</li>
<li>Both runs share the earlier finding that 821 outer-annulus host elements have a fiber volume fraction of 1 or more and therefore almost no mass or stiffness. The corrected volume fractions are not in either run.</li>
<li>The fiber contact thickness (0.471 mm) is the mesher's automatic choice and was not tuned. Abaqus may let contact take precedence over the embedded constraint for these nodes, so the fibers' response to the host could differ from the no-contact case for reasons other than the contact force.</li>
<li>One run per configuration. Differences of a few percent in deletions or ball speed would need more cases (speeds, meshes) to establish.</li>
</ul>
</main>
""" % dict(f0=peak(A, "fiber_in_ball"), f1=peak(B, "fiber_in_ball"), d0=peak(A, "fiber_max_depth_mm"), d1=peak(B, "fiber_max_depth_mm"),
           del0="{:,}".format(a["host_deleted"][-1]), del1="{:,}".format(b["host_deleted"][-1]),
           fb0=a["fiber_below_plate"][-1], fb1=b["fiber_below_plate"][-1], s0=peak(A, "fiber_over_10pct"), s1=peak(B, "fiber_over_10pct"),
           sm0=peak(A, "fiber_strain_max"), sm1=peak(B, "fiber_strain_max"), vb0=a["ball_vz"][-1], vb1=b["ball_vz"][-1],
           hd0=peak(A, "host_max_depth_mm"), hd1=peak(B, "host_max_depth_mm"),
           table=table, ke=ke, vids=vids or "<p>Videos were not rendered for this report.</p>",
           c1=line_chart(series("fiber_in_ball"), "fiber nodes inside ball"),
           c2=line_chart(series("fiber_max_depth_mm"), "depth (mm)"),
           c3=line_chart(series("ball_vz"), "ball speed (m/s)"),
           c4=line_chart(series("host_deleted"), "elements deleted"),
           c5=line_chart(series("fiber_strain_max"), "max segment strain"),
           c6=line_chart(series("fiber_below_plate"), "fiber nodes"))
html = html.replace("<main>", "<main>", 1)
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html))
