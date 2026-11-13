"""Build reports/VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html from the exported viewer npz and energy CSVs."""
import base64
import io

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = "Meshing/vals-plywise/results"
COL = {"vuel": "#1f77b4", "native": "#d95f02"}
data, energy = {}, {}
for c in COL:
    d = np.load(f"{R}/vals3_{c}_viewer.npz")
    t = d["times"]
    bp = d["ball_pos"].astype(np.float64)
    com = bp.mean(1)
    st = d["host_status"]
    hp = d["host_pos"].astype(np.float64)
    fp = d["fiber_pos"].astype(np.float64)
    data[c] = dict(t=t * 1e6, v=np.gradient(com[:, 2], t), com=com[:, 2] * 1e3, nose=bp[:, :, 2].min(1) * 1e3,
                   dead=100 * (1 - st.mean(1)), fd=np.linalg.norm(fp[-1] - d["fiber_coords0"], axis=1),
                   hd=np.linalg.norm(hp[-1] - d["host_coords0"], axis=1),
                   sp=np.linalg.norm(hp[-1] - hp[-2], axis=1) / (t[-1] - t[-2]))
    energy[c] = np.genfromtxt(f"{R}/energy_{c}.csv", delimiter=",", names=True)


def fig_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def line(key, ylabel, extra=None):
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    for c in COL:
        ax.plot(data[c]["t"], data[c][key], color=COL[c], label=c)
    if extra:
        extra(ax)
    ax.set_xlabel("time (us)")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=.3)
    ax.legend()
    return fig_b64(fig)


def back(ax):
    ax.axhline(-25.4, color="gray", ls="--", lw=1)
    ax.text(1, -24, "plate back face", fontsize=7, color="gray")


imgs = dict(
    vel=line("v", "ball z-velocity (m/s)"),
    dead=line("dead", "deleted host elements (%)"),
    nose=line("nose", "ball nose z (mm)", back),
)
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4))
for c in COL:
    e = energy[c]
    axs[0].plot(e["time"] * 1e6, e["ALLKE"] / 1e3, color=COL[c], label=c)
    axs[1].plot(e["time"] * 1e6, e["ETOTAL"] / 1e3, color=COL[c], label=c)
axs[0].set_ylabel("ALLKE (J)")
axs[1].set_ylabel("ETOTAL (J)")
for a in axs:
    a.set_xlabel("time (us)")
    a.grid(alpha=.3)
    a.legend()
imgs["energy"] = fig_b64(fig)

rows = []


def row(name, f):
    rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (name, f("vuel"), f("native")))


row("Final ball velocity (m/s)", lambda c: "%.0f" % data[c]["v"][-1])
row("Ball KE retained", lambda c: "%.0f%%" % (100 * (data[c]["v"][-1] / 1000.0) ** 2))
row("Ball nose z at end (mm; back face -25.4)", lambda c: "%.1f" % data[c]["nose"][-1])
row("Ball centre z at end (mm)", lambda c: "%.1f" % data[c]["com"][-1])
row("Host elements deleted at end", lambda c: "%.1f%%" % data[c]["dead"][-1])
row("Host elements deleted at 35 us", lambda c: "%.1f%%" % data[c]["dead"][100])
row("Fiber nodes displaced &gt; 5 mm", lambda c: "{:,}".format(int((data[c]["fd"] > .005).sum())))
row("Fiber nodes displaced &gt; 50 mm", lambda c: "{:,}".format(int((data[c]["fd"] > .05).sum())))
row("Host nodes displaced &gt; 100 mm", lambda c: "{:,}".format(int((data[c]["hd"] > .1).sum())))
row("Host nodes faster than 3 km/s (last frame)", lambda c: "{:,}".format(int((data[c]["sp"] > 3000).sum())))
row("Max host node speed (km/s)", lambda c: "%.0f" % (data[c]["sp"].max() / 1e3))
row("ALLKE at end (J)", lambda c: "{:,.0f}".format(energy[c]["ALLKE"][-1] / 1e3))
row("ALLIE at end (J)", lambda c: "{:,.0f}".format(energy[c]["ALLIE"][-1] / 1e3))
row("ALLVD at end (J)", lambda c: "{:,.0f}".format(energy[c]["ALLVD"][-1] / 1e3))
row("ETOTAL at end (J; starts 3.5)", lambda c: "{:,.0f}".format(energy[c]["ETOTAL"][-1] / 1e3))
rows += [
    "<tr><td>Wall time / increments</td><td>3 h 33 min / 45,337</td><td>1 h 46 min / 17,725</td></tr>",
    "<tr><td>Peak memory</td><td>16.8 GB (16 GB requested)</td><td>24.7 GB (32 GB requested)</td></tr>",
    "<tr><td>Final stable increment</td><td>1.25e-9 s</td><td>3.24e-9 s</td></tr>",
]

CSS = """
:root{--bg:#fff;--fg:#1c1c1c;--mut:#666;--line:#ddd}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}}
:root[data-theme=dark]{--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:1.6rem}h2{margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:4px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left}
th{color:var(--mut);font-weight:600}img{max-width:100%;height:auto;background:#fff;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.note{color:var(--mut)}code{background:rgba(127,127,127,.15);padding:0 4px;border-radius:3px}
"""

BODY = """
<h1>Vals plywise laminate: VUEL (volume-corrected) vs native embedded</h1>
<p class="note">20 plies, cross-ply 0/90, fibers d = 0.632 mm (Vf about 0.39), ball at -1000 m/s, step 7e-5 s. ROAR jobs 56574395 (VUEL) and 56574397 (native); ODB exported at 200 frames. Deck builder: <code>verification/roar/build_vals_plywise.py</code>.</p>

<h2>Summary</h2>
<ul>
<li><b>Both runs completed</b> the full 70 us with no solver errors, excessive-distortion or negative-volume messages.</li>
<li><b>Both perforated the plate.</b> The ball centre ends past the back face (z = -25.4 mm) in each case. The VUEL ball keeps more velocity: <b>742 vs 669 m/s</b> (55% vs 45% of initial KE).</li>
<li>The VUEL host loses about <b>3.4x more elements</b> (31.2% vs 9.2%) and its fibers are displaced much further.</li>
<li><b>The energy balance does not close in either run</b> (see below), so treat energy numbers as diagnostic only.</li>
<li>The two decks differ in more than the volume correction (see Caveats), so the velocity difference cannot be attributed to the correction alone.</li>
</ul>

<h2>What differed between the runs</h2>
<table><tr><th>Item</th><th>VUEL</th><th>Native</th></tr>
<tr><td>Host</td><td>User element <code>VU1</code>, ductile-damage matrix (onset eps 0.1, Gf 1460); ghost C3D8R carries output and deletion (strain 0.137)</td><td>C3D8R with the Abaqus native matrix material</td></tr>
<tr><td>Fiber coupling</td><td>Embedded</td><td>Native <code>*Embedded Element</code></td></tr>
<tr><td>Volume correction</td><td><b>Yes</b>: internal integration volume scaled by eta = 1 - Vf per element (<code>DVOL_EFF</code>); wave speed and dtStable use geometric volume</td><td><b>No</b>: host keeps full volume and density, so fiber volume is double-counted</td></tr></table>

<h2>Results</h2>
<table><tr><th>Metric</th><th>VUEL</th><th>Native</th></tr>@@ROWS@@</table>

<div class="grid">
<div><h3>Ball velocity</h3><img alt="ball velocity" src="data:image/png;base64,@@VEL@@"></div>
<div><h3>Ball nose position</h3><img alt="ball nose z" src="data:image/png;base64,@@NOSE@@"></div>
<div><h3>Deleted host elements</h3><img alt="deleted fraction" src="data:image/png;base64,@@DEAD@@"></div>
</div>
<h3>Energy</h3><img alt="energy" src="data:image/png;base64,@@ENERGY@@">
<p class="note">Initial ball KE is 3.5 J. In both runs ALLKE grows far above it (VUEL 366 J, native 56 J) while ALLIE and ALLWK stay small, and ETOTAL falls negative. The last frame has host nodes moving at tens of km/s (up to 77 km/s VUEL, 42 km/s native), so the kinetic energy appears to sit in ejected nodes of deleted elements, not in the ball or the intact plate. Not confirmed: whether those nodes keep their lumped mass after deletion, or whether the energy outputs include something else. Inspect the deletion handling before quoting energy absorbed.</p>

<h2>Warnings</h2>
<p>The VUEL <code>.dat</code> has 62 warnings against 2 for native. 60 of the extra ones are "the *ELEMENT OUTPUT option is not supported for user elements" (known and harmless; VUEL state is not in the ODB). The other two warnings (rate-dependent cohesive damage interpolation, 2-D thickness note) appear in both decks.</p>

<h2>Caveats</h2>
<ul>
<li><b>Confounded comparison.</b> VUEL vs native changes the matrix model (ductile damage with deletion vs Abaqus native), the element formulation and the volume correction at once. The extra mass and stiffness in the uncorrected native host would also slow the ball more, so the correction plausibly explains part of the 73 m/s gap, but this run cannot isolate it. A third deck (native with host density and moduli scaled by 1 - Vf) would.</li>
<li>Ball velocity is the finite-difference rate of the mean ball position between exported frames; both balls are still decelerating slightly at the end.</li>
<li>Fiber failure is not measured directly: only fiber displacement is exported. Fiber nodes displaced more than 50 mm: 1,100 (VUEL) vs 3 (native).</li>
<li>Cohesive properties are the SI-literal numbers supplied, not the Hazzard set (the next run should use K = 60/t_ply[mm]).</li>
<li>The VUEL job peaked at 16.8 GB against its 16 GB request. It finished, but request more next time.</li>
</ul>

<h2>Viewer movies</h2>
<p>Packed data: <code>Meshing/vals-plywise/results/viewer_vuel</code> and <code>viewer_native</code>. Serve with <code>python agents/drafter/outbox/T-021/serve_viewer.py &lt;folder&gt; --port 8800</code>; the Record button saves a WebM.</p>
"""

body = (BODY.replace("@@ROWS@@", "".join(rows)).replace("@@VEL@@", imgs["vel"]).replace("@@NOSE@@", imgs["nose"])
        .replace("@@DEAD@@", imgs["dead"]).replace("@@ENERGY@@", imgs["energy"]))
html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Vals Plywise VUEL vs Native</title><style>" + CSS + "</style></head><body>" + body + "</body></html>")
with open("reports/VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html", "w", encoding="utf-8") as fh:
    fh.write(html)
print("ok")
