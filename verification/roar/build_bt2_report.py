"""Build reports/VALS_BT2_BALL_TESTS_REPORT.html from the bt2 extract JSONs, viewer npz and reports/bt2_inversion.json.

bt2 = six 12 us native Vals decks: beam vs truss fibers, JC D4 = +0.002, matrix max degradation 0.8, at 1000 and 500 m/s.
References at 1000 m/s: vp5 (baseline) and b4_d4fix (truss + D4 + max degradation 1). Energy histories are mJ.
"""
import base64, io, json
from PIL import Image
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R2 = "Meshing/vals-plywise-balltests2/results"
R1 = "Meshing/vals-plywise-balltests/results"
R5 = "Meshing/vals-plywise-erode/results"
TEND = 12.0
RUNS = [  # key, label, path, speed
    ("vp5", "vp5 baseline", f"{R5}/vp5_extract2.json", 1000),
    ("b4_d4fix", "b4 truss + D4, maxdeg 1 (ref)", f"{R1}/b4_d4fix_extract.json", 1000),
    ("c1_beam_d4", "c1 beam + D4", f"{R2}/c1_beam_d4_extract.json", 1000),
    ("c2_truss_d4_md80", "c2 truss + D4 + maxdeg 0.8", f"{R2}/c2_truss_d4_md80_extract.json", 1000),
    ("c3_beam_d4_md80", "c3 beam + D4 + maxdeg 0.8", f"{R2}/c3_beam_d4_md80_extract.json", 1000),
    ("c1_beam_d4_v500", "c1 beam + D4", f"{R2}/c1_beam_d4_v500_extract.json", 500),
    ("c2_truss_d4_md80_v500", "c2 truss + D4 + maxdeg 0.8", f"{R2}/c2_truss_d4_md80_v500_extract.json", 500),
    ("c3_beam_d4_md80_v500", "c3 beam + D4 + maxdeg 0.8", f"{R2}/c3_beam_d4_md80_v500_extract.json", 500),
]
COL = {"vp5": "#444444", "b4_d4fix": "#999999", "c1_beam_d4": "#1f77b4", "c2_truss_d4_md80": "#d62728", "c3_beam_d4_md80": "#2ca02c"}
runs = {k: json.load(open(p)) for k, _, p, _ in RUNS}
labels = {k: l for k, l, _, _ in RUNS}
speed = {k: s for k, _, _, s in RUNS}
inv = json.load(open("reports/bt2_inversion.json"))


def color(k):
    return COL[k.replace("_v500", "")]


def b64fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def ser(ex, name):
    a = np.array(ex["energy"][name])
    m = a[:, 0] * 1e6 <= TEND + 1e-9
    return a[m, 0] * 1e6, a[m, 1]


def rows_of(ex):
    return [r for r in ex["status"] if r["t"] * 1e6 <= TEND + 1e-9]


def first_del(ex, g):
    for r in rows_of(ex):
        if r["cnt"][g][1] > 0:
            return r["t"] * 1e6
    return None


def inv_at_end(k):
    t = np.array(inv[k]["t"])
    f = np.array(inv[k]["inv"])
    i = np.where(t <= TEND + 1e-9)[0][-1]
    return 100 * f[i]


def panel(v):
    ks = [k for k in runs if speed[k] == v]
    fig, axs = plt.subplots(1, 4, figsize=(15, 3.4))
    for k in ks:
        ls = "--" if k in ("vp5", "b4_d4fix") else "-"
        t, et = ser(runs[k], "ETOTAL")
        axs[0].plot(t, et, color=color(k), ls=ls, label=k)
        rows = rows_of(runs[k])
        tt = np.array([r["t"] for r in rows]) * 1e6
        for ax, g in zip(axs[1:3], ("ball", "fiber")):
            n = rows[0]["cnt"][g][0]
            ax.plot(tt, [100 * r["cnt"][g][1] / n for r in rows], color=color(k), ls=ls)
        ti = np.array(inv[k]["t"])
        m = ti <= TEND + 1e-9
        axs[3].plot(ti[m], 100 * np.array(inv[k]["inv"])[m], color=color(k), ls=ls)
    for ax, ttl in zip(axs, ("ETOTAL (J)", "ball elements deleted (%)", "fibers deleted (%)", "ball hexes inverted incl. deleted (%)")):
        ax.set_title(ttl, fontsize=9)
        ax.set_xlabel("time (us)")
        ax.grid(alpha=.3)
    axs[0].legend(fontsize=6)
    return b64fig(fig)


def table(v):
    h = ""
    for k in [k for k in runs if speed[k] == v]:
        ex = runs[k]
        _, ke = ser(ex, "ALLKE")
        _, et = ser(ex, "ETOTAL")
        c = rows_of(ex)[-1]["cnt"]
        cs = [r for r in ex["cs"] if r["t"] * 1e6 <= TEND + 1e-9][-1]
        ff = first_del(ex, "fiber")
        h += "<tr><td>%s</td><td>%.2f</td><td>%+.1f%%</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%d</td><td>%.2f%%</td></tr>" % (
            labels[k], ke[0], 100 * (et[-1] / et[0] - 1),
            "{:,} ({:.1f}%)".format(c["ball"][1], 100 * c["ball"][1] / c["ball"][0]),
            "{:,}".format(c["host"][1]), "{:,}".format(c["fiber"][1]), "%.1f us" % ff if ff else "none",
            cs["ge50"], cs["ge99"], inv_at_end(k))
    return h


def jpg(fn):
    im = Image.open(fn).convert("RGB")
    im = im.resize((im.width // 2, im.height // 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def gallery(v):
    h = ""
    for k in [k for k in runs if speed[k] == v and k != "vp5"]:
        cells = "".join('<td><img alt="%s %d us" src="data:image/jpeg;base64,%s"></td>' % (k, t, jpg(f"reports/bt2_renders/{k}_t{t:02d}.png")) for t in (4, 8, 12))
        h += "<tr><th>%s</th>%s</tr>" % (labels[k], cells)
    return h


HEAD = "<tr><th>Run</th><th>ALLKE start (J)</th><th>ETOTAL end vs start</th><th>Ball deleted</th><th>Host deleted</th><th>Fibers deleted</th><th>First fiber deletion</th><th>Interface &ge;50% damage</th><th>Interface failed</th><th>Ball hexes inverted (incl. deleted)</th></tr>"
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
links = "".join('<li><a href="http://127.0.0.1:8800/viewer.html?data=/data/viewer_%s"><code>%s</code></a></li>' % (k, k)
                for k in runs if k.startswith("c"))
BODY = f"""
<h1>Vals ball-failure tests (bt2): beam vs truss fibers, D4, max degradation 0.8</h1>
<p class="note">Six 12 &micro;s native Vals decks (8 tasks, 32 GB, via <code>run.sh</code>), ROAR <code>ctv/bt2</code>. All six completed. Three variants at 1000 m/s and the same three at 500 m/s (still a 12 &micro;s window, so the ball is earlier in its penetration). 1000 m/s references: vp5 and b4_d4fix (truss + D4 + max degradation 1). There is no 500 m/s reference deck, so the 500 m/s runs are only compared with each other. Ball-hex inversion = fraction of ball C3D8R elements with a non-positive corner Jacobian in the last output frame within 12 &micro;s, computed from node positions (<code>ball_inversion.py</code>); it is a geometric count and does not know whether an element was deleted.</p>
<div class="corr"><b>Correction (2026-10-28).</b> The &ldquo;ball hexes inverted&rdquo; figures in this report were computed from node positions over all ball hexes, including elements the solver had already deleted. Matching per-element STATUS from the ODBs (b4_d4fix and c2_truss_d4_md80 at 1000 m/s) shows 609 of 610 and 618 of 619 inverted hexes were already deleted when they first inverted, and 0&ndash;1 live ball hexes are inverted at 12 &micro;s. So the inversion column measures the leftover nodes of deleted elements, not live element failure. The 12 &micro;s ball-deletion counts are unaffected. Also, ODB energies were mislabelled 1000 times too small in the first version of this report (the ODB is in J; the ball carries 3.55 kJ); this is fixed. Details: <code>verification/roar/ball_tests/t051/inv_alive_analysis.py</code>.</div><h2>1000 m/s</h2>
<table>{HEAD}{table(1000)}</table>
<img alt="1000 m/s panels" src="data:image/png;base64,{panel(1000)}">
<h2>500 m/s</h2>
<table>{HEAD}{table(500)}</table>
<img alt="500 m/s panels" src="data:image/png;base64,{panel(500)}">
<h2>Analysis</h2>
<ul>
<li><b>Energy is fine everywhere.</b> ETOTAL ends within 0.3% of its start in all runs.</li>
<li><b>Beam fibers + D4 (c1) are not clearly more stable at 1000 m/s.</b> Ball inversion ends at 3.3%, against 3.6% for b4 (truss + D4) and 3.9% for vp5: a small difference from one run each. Ball deletion is lower (728 against 840), but beam fibers delete 63 fibers from 4.5 &micro;s, against 11 for b4. Interface points past 50% damage are 934 against 912.</li>
<li><b>Max degradation 0.8 does not change the picture.</b> c2 (truss) against b4: 784 against 840 ball deletions, 3.57% against 3.55% inverted, and 0 failed interface points against 13. c3 (beam) against c1: 753 against 728 ball deletions, identical 3.28% inversion. As flagged beforehand, it only acts on the matrix; the ball and fibers fail abruptly.</li>
<li><b>Beam fibers vs truss.</b> Beam decks delete 63&ndash;68 fibers at 1000 m/s against 11&ndash;16 for truss, and 4&ndash;5 against 0 at 500 m/s. They also cost about 3.5 times the run time (5.3 h against 1.5 h at 1000 m/s). First fiber deletion is only slightly earlier with beams (4.2&ndash;4.5 &micro;s against 4.5&ndash;5.4 &micro;s).</li>
<li><b>At 500 m/s</b> ball deletion is 1.8&ndash;2.0% and inversion 1.5&ndash;1.7% at 12 &micro;s, with no spread worth reading between variants. Erosion starts at 3.3 &micro;s, later than at 1000 m/s (1.8 &micro;s).</li>
<li><b>Overall:</b> none of the three changes stops ball erosion. The spread between variants is a few percent of the ball, each is one run with no repeat, and the deletion count is roughly 4&ndash;5% at 1000 m/s for every deck, so it looks set by the ball and impact rather than by these material choices. (The inversion column should not be read as live-element failure; see the correction above.)</li>
</ul>
<p class="note">Limits: one run per variant, 12 &micro;s only, output frames sampled coarsely (vp5 about every 1.75 &micro;s, bt2 about every 0.3 &micro;s), so first-deletion times are not comparable between vp5 and the rest. vp5 is read at its last frame within 12 &micro;s (10.5 &micro;s).</p>
<h2>Symmetry-plane views, 1000 m/s</h2>
<table><tr><th></th><th>4 &micro;s</th><th>8 &micro;s</th><th>12 &micro;s</th></tr>{gallery(1000)}</table>
<h2>Symmetry-plane views, 500 m/s</h2>
<table><tr><th></th><th>4 &micro;s</th><th>8 &micro;s</th><th>12 &micro;s</th></tr>{gallery(500)}</table>
<h2>Interactive viewer</h2>
<p class="note"><code>python agents/drafter/outbox/T-021/serve_viewer.py Meshing/vals-plywise-balltests2/results --port 8800</code></p>
<ul>{links}</ul>
"""
html = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Vals BT2 Ball Tests</title><style>" + CSS + "</style></head><body>" + BODY + "</body></html>")
open("reports/VALS_BT2_BALL_TESTS_REPORT.html", "w", encoding="utf-8").write(html)
print("ok", len(html) // 1024, "KB")
