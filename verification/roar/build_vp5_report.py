"""Build reports/VALS_VP5_ERODING_CONTACT_REPORT.html from the vp5 extract JSON, viewer npz and vp4 native results."""
import base64, io, json, glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

R5 = "Meshing/vals-plywise-erode/results"
R4 = "Meshing/vals-plywise-del/results/native"
ex = json.load(open(f"{R5}/vp5_extract2.json"))
d5 = np.load(f"{R5}/vals_native_er_viewer.npz")
d4 = np.load(f"{R4}/vals_native_viewer.npz")
e4 = np.genfromtxt(f"{R4}/energy_native.csv", delimiter=",", names=True)
C5, C4 = "#1f77b4", "#d95f02"


def b64fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def ser(name):
    a = np.array(ex["energy"][name])
    return a[:, 0] * 1e6, a[:, 1] / 1e3


def ball_vz(d):
    t = d["times"]
    z = np.median(d["ball_pos"][:, :, 2].astype(np.float64), axis=1)
    return t * 1e6, np.gradient(z, t)


# energy
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4))
t5, ke5 = ser("ALLKE")
_, et5 = ser("ETOTAL")
axs[0].plot(e4["time"] * 1e6, e4["ALLKE"] / 1e3, C4, label="vp4 native")
axs[0].plot(t5, ke5, C5, label="vp5 eroding contact")
axs[1].plot(e4["time"] * 1e6, e4["ETOTAL"] / 1e3, C4, label="vp4 native")
axs[1].plot(t5, et5, C5, label="vp5 eroding contact")
axs[0].set_ylabel("ALLKE (J)")
axs[1].set_ylabel("ETOTAL (J)")
for a in axs:
    a.axhline(ke5[0], color="gray", ls="--", lw=1)
    a.set_xlabel("time (us)")
    a.grid(alpha=.3)
    a.legend()
img_energy = b64fig(fig)

# other energies
fig, ax = plt.subplots(figsize=(6.2, 3.4))
for n, c in (("ALLIE", "#2ca02c"), ("ALLDMD", "#9467bd"), ("ALLPD", "#8c564b"), ("ALLAE", "#e377c2")):
    t, v = ser(n)
    ax.plot(t, v, color=c, label=n)
ax.set_xlabel("time (us)")
ax.set_ylabel("energy (J)")
ax.grid(alpha=.3)
ax.legend()
img_other = b64fig(fig)

# deletion and interface damage
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4))
st = ex["status"]
tt = np.array([r["t"] for r in st]) * 1e6
for g, c in (("host", C5), ("ball", "#c0392b"), ("fiber", "#0033cc")):
    n = st[0]["cnt"][g][0]
    axs[0].plot(tt, [100 * r["cnt"][g][1] / n for r in st], color=c, label="vp5 " + g)
axs[0].plot(d4["times"] * 1e6, 100 * (1 - d4["host_status"].mean(1)), color=C4, ls="--", label="vp4 host")
axs[0].set_ylabel("deleted (%)")
axs[0].set_xlabel("time (us)")
axs[0].grid(alpha=.3)
axs[0].legend()
cs = ex["cs"]
tc = np.array([r["t"] for r in cs]) * 1e6
axs[1].plot(tc, [r["ge50"] for r in cs], label="damage >= 0.5", color="#8e44ad")
axs[1].plot(tc, [r["ge99"] for r in cs], label="damage >= 0.99 (failed)", color="#c0392b")
axs[1].set_ylabel("interface contact points (of {:,})".format(cs[0]["n"]))
axs[1].set_xlabel("time (us)")
axs[1].grid(alpha=.3)
axs[1].legend()
img_del = b64fig(fig)

# ball velocity
fig, ax = plt.subplots(figsize=(6.2, 3.4))
for d, c, lab in ((d4, C4, "vp4 native"), (d5, C5, "vp5 eroding contact")):
    t, v = ball_vz(d)
    ax.plot(t, v, color=c, label=lab)
ax.set_xlabel("time (us)")
ax.set_ylabel("ball node-median z-velocity (m/s)")
ax.grid(alpha=.3)
ax.legend()
img_vel = b64fig(fig)


def jpg(fn):
    im = Image.open(fn).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


t_us = d5["times"] * 1e6
frames = sorted({int(f.replace("\\", "/").split("/")[-1][1:4]) for f in glob.glob("reports/vp5_renders/f*_iso_solid.png")})
gal = []
for i in frames:
    cells = []
    for view, style, lab in (("iso", "solid", "Isometric, solid"), ("iso", "wire", "Isometric, wireframe"),
                             ("sym", "solid", "Symmetry plane, solid"),
                             ("sym", "wire", "Symmetry plane, wireframe + in-plane fibers")):
        cells.append('<figure><img alt="%s" src="data:image/jpeg;base64,%s"><figcaption>%s</figcaption></figure>'
                     % (lab, jpg(f"reports/vp5_renders/f{i:03d}_{view}_{style}.png"), lab))
    gal.append('<h3>t = %.1f &micro;s</h3><div class="grid4">%s</div>' % (t_us[i], "".join(cells)))

E = ex["energy"]


def fin(k):
    return E[k][-1][1] / 1e3


hostd = st[-1]["cnt"]["host"][1]
fibd = st[-1]["cnt"]["fiber"][1]
balld = st[-1]["cnt"]["ball"][1]
_, v4 = ball_vz(d4)
_, v5 = ball_vz(d5)
ke4pk = 100 * (e4["ALLKE"].max() / e4["ALLKE"][0] - 1)
ke5pk = 100 * (ke5.max() / ke5[0] - 1)
et5end = 100 * (et5[-1] / et5[0] - 1)
rows = [
    ("Wall time", "1 h 56 min", "2 h 23 min"),
    ("ALLKE start (J)", "%.2f" % (e4["ALLKE"][0] / 1e3), "%.2f" % ke5[0]),
    ("ALLKE peak (J)", "%.2f" % (e4["ALLKE"].max() / 1e3), "%.2f" % ke5.max()),
    ("ALLKE peak vs start", "+%.0f%%" % ke4pk, "+%.1f%%" % ke5pk),
    ("ETOTAL at end (J)", "%.2f" % (e4["ETOTAL"][-1] / 1e3), "%.2f" % et5[-1]),
    ("Host elements deleted at end", "517 of 80,500", "{:,} of 80,500 ({:.1f}%)".format(hostd, 100 * hostd / 80500)),
    ("Fiber elements deleted at end", "not recorded", "{:,} of 206,930".format(fibd)),
    ("Ball elements deleted at end", "not recorded", "{:,} of 18,500 ({:.0f}%)".format(balld, 100 * balld / 18500)),
    ("Interface points failed (damage &ge; 0.99)", "not recorded", "{:,}".format(cs[-1]["ge99"])),
    ("Interface points past half damage", "not recorded", "{:,} of {:,}".format(cs[-1]["ge50"], cs[-1]["n"])),
    ("Ball node-median z-velocity at end (m/s)", "%.0f" % v4[-1], "%.0f" % v5[-1]),
    ("ALLIE / ALLDMD / ALLAE at end, vp5 (J)", "-", "%.3f / %.3f / %.3f" % (fin("ALLIE"), fin("ALLDMD"), fin("ALLAE"))),
]
rows_html = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % r for r in rows)

CSS = """
:root{--bg:#fff;--fg:#1c1c1c;--mut:#666;--line:#ddd}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}}
:root[data-theme=dark]{--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:1.6rem}h2{margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:4px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left}
th{color:var(--mut);font-weight:600}img{max-width:100%;height:auto;background:#fff;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
figure{margin:0}figcaption{color:var(--mut);font-size:.8rem}
.note{color:var(--mut)}code{background:rgba(127,127,127,.15);padding:0 4px;border-radius:3px}
"""
BODY = f"""
<h1>Vals native rerun with an eroding host contact surface (vp5)</h1>
<p class="note">Same 20-ply Vals native deck as vp4 (ball 1000 m/s, 70 &micro;s). Change: the ball contacts the host through an element-based surface (<code>EMBMESH_PLATE_ELEMS</code>) that erodes with deleted elements, instead of node-based contact on every host node at 0.635 mm thickness; <code>*Contact Output</code> added so interface damage (CSDMG) is recorded. ROAR job 56651971, directory <code>ctv/vp5/vals_native_erode</code>, completed with exit code 0.</p>
<h2>Summary</h2>
<ul>
<li><b>The kinetic-energy blow-up is gone.</b> ALLKE peaks only {ke5pk:.1f}% above the {ke5[0]:.2f} J the ball starts with (vp4: +{ke4pk:.0f}%). ETOTAL still ends {et5end:.1f}% above its start (vp4 ended {100*(e4['ETOTAL'][-1]/e4['ETOTAL'][0]-1):.0f}% below), so the balance is still not closed; it is off by a smaller amount but in the other direction. The dissipated and stored energies are tiny ({fin('ALLIE')*1e3:.0f} and {fin('ALLDMD')*1e3:.0f} mJ for ALLIE and ALLDMD), so the plate absorbs almost nothing.</li>
<li><b>Delamination is now recorded.</b> {cs[-1]['ge99']:,} interface contact points have failed and {cs[-1]['ge50']:,} are past half damage by 70 &micro;s. Damage starts at about 7 &micro;s and grows through the run.</li>
<li><b>Host deletion rose, not fell:</b> {hostd:,} hosts deleted against 517 in vp4. Most of this comes in the first 44 &micro;s. A plausible cause is that deleted elements no longer carry contact, so the ball pushes further in; I have not tested it.</li>
<li><b>Fibers rarely fail:</b> {fibd} of 206,930 fiber elements deleted.</li>
<li><b>The ball erodes heavily:</b> {balld:,} of 18,500 ball elements ({100*balld/18500:.0f}%) are deleted, and the surviving ball elements stretch into spikes (see the renders). Ball erosion was not counted in vp4, so the comparison is host-only.</li>
</ul>
<h2>Results</h2>
<table><tr><th>Metric</th><th>vp4 native</th><th>vp5 eroding contact</th></tr>{rows_html}</table>
<h3>Energy</h3><img alt="energy" src="data:image/png;base64,{img_energy}">
<p class="note">Dashed line: initial ball kinetic energy. History values are mJ in the ODB, converted to J.</p>
<div class="grid">
<div><h3>Deletion and interface damage</h3><img alt="deletion" src="data:image/png;base64,{img_del}"></div>
<div><h3>Other energies (vp5)</h3><img alt="other energies" src="data:image/png;base64,{img_other}"></div>
<div><h3>Ball velocity</h3><img alt="ball velocity" src="data:image/png;base64,{img_vel}"></div>
</div>
<h2>Impact views</h2>
<p class="note">Renders of the packed viewer data. Symmetry views look at the flat symmetry plane (y = 0) from outside the model, ball travelling left to right, zoomed on the impact zone of the 0.1 m quarter disc. Isometric views look from the side of the two flat cut faces. Fibers are drawn only in the symmetry wireframe, for fibers lying in the symmetry plane. Deleted host elements are hidden. The ball is red.</p>
{"".join(gal)}
<h2>Caveats</h2>
<ul>
<li>The viewer export keeps only 200 frames and does not carry fiber or ball deletion state, so the renders show deleted host elements removed and fibers undeleted.</li>
<li>The ball node-median velocity stays at about -1000 m/s in both runs: the ball is barely slowed by the plate. I have not established why (the plate removes under 2% of its elements).</li>
<li>Ball elements stretch to long spikes as neighbouring elements erode; the ball velocity is a node median and should be read as approximate.</li>
<li>Only the contact surface changed between vp4 and vp5. The cohesive card (K 60 N/mm&sup3;, 1.8 MPa shear) is the unfixed base version.</li>
<li>Interactive movies: <code>python agents/drafter/outbox/T-021/serve_viewer.py Meshing/vals-plywise-erode/results/viewer_vp5 --port 8820</code>. The symmetry button now frames the plate and looks at the cut face from outside.</li>
</ul>
"""
html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Vals vp5 Eroding Contact</title><style>" + CSS + "</style></head><body>" + BODY + "</body></html>")
open("reports/VALS_VP5_ERODING_CONTACT_REPORT.html", "w", encoding="utf-8").write(html)
print("ok", len(html) // 1024, "KB")
