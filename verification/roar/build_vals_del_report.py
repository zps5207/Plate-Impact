"""Build reports/VALS_PLYWISE_DELETION_RERUN_REPORT.html from the exported viewer npz and energy CSVs."""
import base64
import io

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = "Meshing/vals-plywise-del/results"
COL = {"vuel": "#1f77b4", "native": "#d95f02"}
data, energy = {}, {}
for c in COL:
    d = np.load(f"{R}/{c}/vals_{c}_viewer.npz")
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
    energy[c] = np.genfromtxt(f"{R}/{c}/energy_{c}.csv", delimiter=",", names=True)


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
    "<tr><td>Wall time</td><td>3 h 52 min</td><td>1 h 55 min</td></tr>",
    "<tr><td>ALLKE peak (J; starts 3.5)</td><td>%.1f</td><td>%.1f</td></tr>" % (energy["vuel"]["ALLKE"].max() / 1e3, energy["native"]["ALLKE"].max() / 1e3),
    "<tr><td>Fiber max displacement (mm)</td><td>%.0f</td><td>%.0f</td></tr>" % (data["vuel"]["fd"].max() * 1e3, data["native"]["fd"].max() * 1e3),
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
<h1>Vals plywise rerun with element deletion on for all elements</h1>
<p class="note">Same 20-ply Vals deck as the first pair, ball at -1000 m/s, step 7e-5 s, 200 exported frames. Change: <code>*Damage Evolution</code> added to the fiber and steel ball materials and <code>*Section Controls element deletion=YES</code> on every section (<code>build_vals_plywise.py --element-deletion</code>). ROAR jobs 56580053 (VUEL) and 56580055 (native), directory <code>ctv/vp4</code>. Both datachecks and both solves completed with exit code 0.</p>

<h2>Summary</h2>
<ul>
<li><b>Both solves completed the full 70 us</b> (datacheck accepted <code>*Damage Evolution</code> on the T3D2 fibers).</li>
<li><b>The fiber blow-up is largely gone.</b> Peak ALLKE is about 5.8 J (VUEL) and 6.1 J (native), against 366 J and 56 J in the first pair. Maximum host node speed fell to about 35 km/s (VUEL, was 77) and 23 km/s (native, was 42).</li>
<li><b>The energy balance still does not close.</b> ALLKE ends 63% (VUEL) and 73% (native) above the 3.5 J the ball starts with, so energy is still being created somewhere.</li>
<li><b>The ball is barely slowed</b>: about 963 m/s (VUEL) and 968 m/s (native) at the end, with under 1% of host elements deleted. This is the opposite of the first pair, where the ball kept 742 and 669 m/s. I have not established why. Ball elements can now erode, so the ball centre is no longer a clean measure; treat the velocity as unconfirmed.</li>
<li><b>VUEL and native now agree closely</b> on velocity, deletion and energy, much closer than before.</li>
</ul>

<h2>Results</h2>
<table><tr><th>Metric</th><th>VUEL</th><th>Native</th></tr>@@ROWS@@</table>

<div class="grid">
<div><h3>Ball velocity</h3><img alt="ball velocity" src="data:image/png;base64,@@VEL@@"></div>
<div><h3>Ball nose position</h3><img alt="ball nose z" src="data:image/png;base64,@@NOSE@@"></div>
<div><h3>Deleted host elements</h3><img alt="deleted fraction" src="data:image/png;base64,@@DEAD@@"></div>
</div>
<h3>Energy</h3><img alt="energy" src="data:image/png;base64,@@ENERGY@@">
<p class="note">Energies are converted from mJ to J. Initial ball KE is 3.5 J.</p>
<h2>Caveats</h2>
<ul>
<li>Ball nose z is the minimum node z, so it jumps when ball elements erode and their nodes are ejected (nose ends at -85 mm VUEL, -243 mm native while the centre is near -57 mm). Use the centre only.</li>
<li>Fiber and ball deletion state is not exported, only positions, so how many fibers actually failed is not measured here.</li>
<li>Energy not conserved: the likely sources (mass of deleted nodes, excessive distortion control, contact) were not investigated in this run.</li>
<li>The first report (vp3) is <code>reports/VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html</code>.</li>
</ul>
<h2>Viewer movies</h2>
<p>Packed data: <code>Meshing/vals-plywise-del/results (pack with pack_viewer_data.py)</code> and viewer data. Serve with <code>python agents/drafter/outbox/T-021/serve_viewer.py &lt;folder&gt; --port 8800</code>; the Record button saves a WebM.</p>
"""

body = (BODY.replace("@@ROWS@@", "".join(rows)).replace("@@VEL@@", imgs["vel"]).replace("@@NOSE@@", imgs["nose"])
        .replace("@@DEAD@@", imgs["dead"]).replace("@@ENERGY@@", imgs["energy"]))
html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Vals Plywise Deletion Rerun</title><style>" + CSS + "</style></head><body>" + body + "</body></html>")
with open("reports/VALS_PLYWISE_DELETION_RERUN_REPORT.html", "w", encoding="utf-8") as fh:
    fh.write(html)
print("ok")
