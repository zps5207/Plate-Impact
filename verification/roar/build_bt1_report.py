"""Build reports/VALS_BT1_BALL_TESTS_REPORT.html from the bt1 extract JSONs and viewer npz files.

bt1 = six 12 us native Vals decks that change one ball/fiber/steel feature each (build_ball_tests.py).
Baseline is vp5 (b0_base was never run), cut to 12 us. Energy histories in the ODB are J (a quarter ball at 1000 m/s carries ~3.55 kJ).
Decks whose extract JSON is missing are skipped.
"""
import base64, io, json, os
from PIL import Image
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = "Meshing/vals-plywise-balltests/results"
R5 = "Meshing/vals-plywise-erode/results"
TEND = 12.0  # us
DECKS = [
    ("b1_beamsurf", "b1 beam fibers + element fiber surface"),
    ("b2_newball", "b2 uniform O-grid ball"),
    ("b3_both", "b3 b1 + b2"),
    ("b4_d4fix", "b4 JC D4 = +0.002"),
    ("b5_steelA", "b5 steel Option A (rate term)"),
    ("b6_316L", "b6 AISI 316L"),
]
COL = {"vp5": "#444444", "b1_beamsurf": "#1f77b4", "b2_newball": "#ff7f0e", "b3_both": "#2ca02c",
       "b4_d4fix": "#d62728", "b5_steelA": "#9467bd", "b6_316L": "#8c564b"}


def load(name, base):
    ex = json.load(open(f"{base}/{name}"))
    return ex


runs = {"vp5": json.load(open(f"{R5}/vp5_extract2.json"))}
labels = {"vp5": "vp5 baseline (12 us cut)"}
for d, lab in DECKS:
    p = f"{R}/{d}_extract.json"
    if os.path.exists(p):
        runs[d] = json.load(open(p))
        labels[d] = lab


def b64fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def ser(ex, name):
    a = np.array(ex["energy"][name])
    m = a[:, 0] * 1e6 <= TEND + 1e-9
    return a[m, 0] * 1e6, a[m, 1]


def status_at_end(ex):
    rows = [r for r in ex["status"] if r["t"] * 1e6 <= TEND + 1e-9]
    return rows


def cs_at_end(ex):
    rows = [r for r in ex["cs"] if r["t"] * 1e6 <= TEND + 1e-9]
    return rows[-1] if rows else None


def ball_vz(name):
    base = R5 if name == "vp5" else R
    fn = f"{base}/vals_native_er_viewer.npz" if name == "vp5" else f"{base}/{name}_viewer.npz"
    if not os.path.exists(fn):
        return None
    d = np.load(fn)
    t = d["times"]
    m = t * 1e6 <= TEND + 1e-9
    z = np.median(d["ball_pos"][m][:, :, 2].astype(np.float64), axis=1)
    return t[m] * 1e6, np.gradient(z, t[m])


# energy
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
for k, ex in runs.items():
    t, ke = ser(ex, "ALLKE")
    _, et = ser(ex, "ETOTAL")
    axs[0].plot(t, ke, color=COL[k], label=k, ls="--" if k == "vp5" else "-")
    axs[1].plot(t, et, color=COL[k], label=k, ls="--" if k == "vp5" else "-")
axs[0].set_ylabel("ALLKE (J)")
axs[1].set_ylabel("ETOTAL (J)")
for a in axs:
    a.set_xlabel("time (us)")
    a.grid(alpha=.3)
axs[0].legend(fontsize=7)
img_energy = b64fig(fig)

# deletion
fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
for k, ex in runs.items():
    rows = status_at_end(ex)
    tt = np.array([r["t"] for r in rows]) * 1e6
    for ax, g in zip(axs, ("ball", "host", "fiber")):
        n = rows[0]["cnt"][g][0]
        ax.plot(tt, [100 * r["cnt"][g][1] / n for r in rows], color=COL[k], label=k, ls="--" if k == "vp5" else "-")
for ax, g in zip(axs, ("ball", "host", "fiber")):
    ax.set_title(g + " elements deleted")
    ax.set_ylabel("%")
    ax.set_xlabel("time (us)")
    ax.grid(alpha=.3)
axs[0].legend(fontsize=7)
img_del = b64fig(fig)

# interface damage and ball velocity
fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
for k, ex in runs.items():
    cs = [r for r in ex["cs"] if r["t"] * 1e6 <= TEND + 1e-9]
    if cs:
        axs[0].plot([r["t"] * 1e6 for r in cs], [r["ge99"] for r in cs], color=COL[k], label=k, ls="--" if k == "vp5" else "-")
    v = ball_vz(k)
    if v is not None:
        axs[1].plot(v[0], v[1], color=COL[k], label=k, ls="--" if k == "vp5" else "-")
axs[0].set_ylabel("interface points failed (damage >= 0.99)")
axs[1].set_ylabel("ball node-median z-velocity (m/s)")
for a in axs:
    a.set_xlabel("time (us)")
    a.grid(alpha=.3)
axs[0].legend(fontsize=7)
img_cs = b64fig(fig)

rows_html = ""
for k, ex in runs.items():
    t, ke = ser(ex, "ALLKE")
    _, et = ser(ex, "ETOTAL")
    st = status_at_end(ex)[-1]["cnt"]
    cs = cs_at_end(ex)
    v = ball_vz(k)
    rows_html += "<tr><td>%s</td><td>%.2f</td><td>%+.1f%%</td><td>%+.1f%%</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        labels[k], ke[0], 100 * (ke.max() / ke[0] - 1), 100 * (et[-1] / et[0] - 1),
        "{:,} / {:,}".format(st["ball"][1], st["ball"][0]),
        "{:,} / {:,}".format(st["host"][1], st["host"][0]),
        "{:,} / {:,}".format(st["fiber"][1], st["fiber"][0]),
        "{:,}".format(cs["ge99"]) if cs else "-",
        "%.0f" % v[1][-1] if v is not None else "-")


def jpg(fn):
    im = Image.open(fn).convert("RGB")
    im = im.resize((im.width // 2, im.height // 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


gal_rows = ""
for k in runs:
    cells = "".join('<td><img alt="%s %d us" src="data:image/jpeg;base64,%s"></td>' % (k, t, jpg(f"reports/bt1_renders/{k}_t{t:02d}.png"))
                    for t in (4, 8, 12))
    gal_rows += "<tr><th>%s</th>%s</tr>" % (labels[k], cells)

CSS = """
:root{--bg:#fff;--fg:#1c1c1c;--mut:#666;--line:#ddd}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}}
:root[data-theme=dark]{--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--line:#333}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1150px;margin:0 auto;padding:24px 16px}
h1{font-size:1.6rem}h2{margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:.85rem}td,th{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left}
th{color:var(--mut);font-weight:600}img{max-width:100%;height:auto;background:#fff;border-radius:4px}
.note{color:var(--mut)}.corr{border:1px solid #c0392b;background:rgba(192,57,43,.10);padding:8px 12px;border-radius:4px;margin:12px 0}code{background:rgba(127,127,127,.15);padding:0 4px;border-radius:3px}
"""
links = "".join('<li><a href="http://127.0.0.1:8800/viewer.html?data=/data/viewer_%s"><code>%s</code></a></li>' % (d, d)
                for d, _ in DECKS if os.path.exists(f"{R}/viewer_{d}/manifest.json"))
BODY = f"""
<h1>Vals ball-failure tests (bt1): six 12 &micro;s variants against vp5</h1>
<p class="note">Each deck changes one feature of the full vp5 native Vals deck and runs 12 &micro;s (8 tasks, 32 GB, via <code>run.sh</code>). vp5 is the baseline, cut to 12 &micro;s, because <code>b0_base</code> was never run. ROAR directory <code>ctv/bt1</code>.</p>
<div class="corr"><b>Correction (2026-10-28).</b> The &ldquo;ball hexes inverted&rdquo; figures in this report were computed from node positions over all ball hexes, including elements the solver had already deleted. Matching per-element STATUS from the ODBs (b4_d4fix and c2_truss_d4_md80 at 1000 m/s) shows 609 of 610 and 618 of 619 inverted hexes were already deleted when they first inverted, and 0&ndash;1 live ball hexes are inverted at 12 &micro;s. So the inversion column measures the leftover nodes of deleted elements, not live element failure. The 12 &micro;s ball-deletion counts are unaffected. Also, ODB energies were mislabelled 1000 times too small in the first version of this report (the ODB is in J; the ball carries 3.55 kJ); this is fixed. Details: <code>verification/roar/ball_tests/t051/inv_alive_analysis.py</code>.</div><h2>Summary table at 12 &micro;s</h2>
<table><tr><th>Run</th><th>ALLKE start (J)</th><th>ALLKE peak vs start</th><th>ETOTAL end vs start</th><th>Ball deleted</th><th>Host deleted</th><th>Fibers deleted</th><th>Interface failed</th><th>Ball v<sub>z</sub> end (m/s)</th></tr>{rows_html}</table>
<h2>Energy</h2><img alt="energy" src="data:image/png;base64,{img_energy}">
<h2>Deletion</h2><img alt="deletion" src="data:image/png;base64,{img_del}">
<h2>Interface damage and ball velocity</h2><img alt="interface and velocity" src="data:image/png;base64,{img_cs}">
<h2>Analysis</h2>
<ul>
<li><b>No variant changes the energy picture.</b> Over 12 &micro;s ALLKE never drops below 97.7% of its start and ETOTAL ends within 0.3% of its start in all seven runs. The energy problem seen in vp4 is not present at this time scale in any deck.</li>
<li><b>Ball erosion starts at 1.5&ndash;1.9 &micro;s and runs at a steady 80&ndash;90 elements per &micro;s in every run.</b> By 12 &micro;s that is 4&ndash;5% of the ball (b6 316L is lowest at 3.9%, b1 highest at 5.1%). None of the six changes stops it. The spread between variants is small compared with the erosion itself.</li>
<li><b>The D4 change (b4) removes about 8% of the ball deletions</b> (840 against vp5's 913) but not the erosion, so negative D4 is not the main reason the ball is eroding. The two steel cards (b5, b6) give 850 and 721 deletions; b6 deletes the least ball, and it is also the only deck with a different density.</li>
<li><b>Beam fibers (b1, b3) delete more fibers and delete them earlier:</b> first fiber deletion at 5.3&ndash;6.3 &micro;s against 8.75 &micro;s in vp5, and 41 and 24 fibers deleted against 7. The T3D2 decks give 2&ndash;14. I have not established why. vp5 was sampled every ~1.75 &micro;s, so its first-deletion times are coarse; other decks were sampled every ~0.3 &micro;s.</li>
<li><b>Interface damage tracks the material changes.</b> Points past half damage at 12 &micro;s: b4 941, b6 884, b5 857, b1 829, b3 771, vp5 767, b2 717. Points fully failed are few (5&ndash;26) and highest for the beam-fiber decks (b1 26, b3 24).</li>
<li><b>The new ball mesh (b2) is the cheap change.</b> It finished in 1 h 19 min, against 3 h 50 min for b4 (which differs from vp5 only in D4) and 4 h 11 min for b1. The stable time increment I read from the solver status files supports this: b2 was ball-limited at 2.6&times;10<sup>-8</sup> s (frame at 3.7 &micro;s), against 5&ndash;6&times;10<sup>-9</sup> s for b1 and b4 at 1&ndash;1.5 &micro;s; b3's critical element was in a fiber ply at 1.0&times;10<sup>-8</sup> s (frame at 2.1&ndash;10 &micro;s). b2 also has the lowest interface damage and the fewest fiber deletions. Its ball has 17,248 elements against 18,500, so ball deletion counts are not directly comparable by number; the fractions are 4.6% against 4.9% for vp5.</li>
<li><b>Ball z-velocity should not be over-read.</b> It is the median over ball nodes and the ball is shredded; values run from &minus;888 (b5) to &minus;1000 m/s.</li>
</ul>
<p class="note">Limits: one run per variant, 12 &micro;s only, no b0_base, element counts sampled at the output frames, and no run-to-run repeat to separate small differences from noise.</p>
<h2>Symmetry-plane views</h2>
<p class="note">Solid view of the y = 0 symmetry plane at 4, 8 and 12 &micro;s. Plate grey, ball red, deleted host elements hidden. Fibers are not drawn.</p>
<table><tr><th></th><th>4 &micro;s</th><th>8 &micro;s</th><th>12 &micro;s</th></tr>{gal_rows}</table>
<h2>Interactive viewer</h2>
<p class="note">Served locally with <code>python agents/drafter/outbox/T-021/serve_viewer.py Meshing/vals-plywise-balltests/results --port 8800</code>.</p>
<ul>{links}</ul>
"""
html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Vals BT1 Ball Tests</title><style>" + CSS + "</style></head><body>" + BODY + "</body></html>")
os.makedirs("reports", exist_ok=True)
open("reports/VALS_BT1_BALL_TESTS_REPORT.html", "w", encoding="utf-8").write(html)
print("ok", len(html) // 1024, "KB", list(runs))
