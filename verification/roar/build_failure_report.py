"""Build reports/HOST_FAILURE_ANALYSIS_REPORT.html: do native ghosts delete too early, or is the VUEL genuinely failing?

Inputs (all produced earlier in this session):
    Meshing/plywise-500/results/vuel_failures.txt        VUEL_FAILURE lines from each run's job.stdout (ROAR)
    Meshing/plywise-500/results/vuel_vs_ghost_timing.json cumulative VUEL failures vs ghost deletions (verification/roar/vuel_vs_ghost_timing.py)
    <viewer npz>_orphans.json                             fiber-node orphaning (verification/roar/fiber_orphan_analysis.py)
    Meshing/plywise-500/results/plywise_vs_solid_stats.json   (verification/roar/build_pw_report.py)
"""
import json
import os
import re

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
RES = os.path.join(ROOT, "Meshing", "plywise-500", "results")
TEMPLATE = os.path.join(ROOT, "reports", "_flat_v2_template.html")
OUT = os.path.join(ROOT, "reports", "HOST_FAILURE_ANALYSIS_REPORT.html")
RUNS = [("flat_solid", "Flat, solid host", "#6d7a86"), ("flat_ply_v3", "Flat, plywise v3", "#1f6fb4"),
        ("cc_solid", "Concave, solid host", "#c2362f"), ("cc_ply_v3", "Concave, plywise v3", "#e08a1e")]
ORPH = {"flat_solid": os.path.join(ROOT, "verification", "roar", "t_nc", "v500star_100", "v500star_100_viewer_orphans.json"),
        "flat_ply_v3": os.path.join(RES, "pw_flat500_v3", "pw_flat500_v3_viewer_orphans.json"),
        "cc_solid": os.path.join(ROOT, "reports", "cc_run", "dl", "cc500_100", "cc500_100_viewer_orphans.json"),
        "cc_ply_v3": os.path.join(RES, "pw_cc500_v3", "pw_cc500_v3_viewer_orphans.json")}

T = json.load(open(os.path.join(RES, "vuel_vs_ghost_timing.json")))
S = json.load(open(os.path.join(RES, "plywise_vs_solid_stats.json")))
O = {k: json.load(open(p)) for k, p in ORPH.items()}
pat = re.compile(r"^(\S+)\s+\*\*\* VUEL_FAILURE \((ENG STRAIN|JACOBIAN)\):\s*elem =\s*(\d+)\s+time =\s*([0-9.eE+\-]+)")
EV = {}
for line in open(os.path.join(RES, "vuel_failures.txt")):
    m = pat.match(line)
    if m:
        EV.setdefault(m.group(1), []).append((int(m.group(3)), float(m.group(4)) * 1e6))
ALLRUNS = ["flat_solid", "flat_ply_v1", "flat_ply_v3", "cc_solid", "cc_ply_v1", "cc_ply_v3"]
NAMES = {"flat_solid": "Flat solid", "flat_ply_v1": "Flat plywise v1", "flat_ply_v3": "Flat plywise v3",
         "cc_solid": "Concave solid", "cc_ply_v1": "Concave plywise v1", "cc_ply_v3": "Concave plywise v3"}


def line_chart(series, ylabel, w=760, h=290, ymin=0.0, ymax=None, xmax=100.0, xlabel="step time (us)"):
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
        lx += 190
    o.append("</svg>")
    return "".join(o)


# cumulative VUEL failures (solid line) vs ghost deletions (dashed), one chart per run
cum_charts = ""
for key, label, color in RUNS:
    c = T[key]["cum"]
    cum_charts += '<figure class="fig"><figcaption><b>%s.</b> Cumulative VUEL failures (solid) against native ghost deletions (dashed).</figcaption>%s</figure>' % (
        label, line_chart([{"label": "VUEL failures", "color": color, "x": c["t_us"], "y": c["vuel"]},
                           {"label": "ghost deletions", "color": color, "x": c["t_us"], "y": c["ghost"], "dash": True}],
                          "elements"))
# early window zoom, plywise vs solid
zoom = []
for key, label, color in RUNS:
    c = T[key]["cum"]
    t = np.array(c["t_us"]); i = t <= 10
    zoom.append({"label": label + " VUEL", "color": color, "x": t[i].tolist(), "y": np.array(c["vuel"])[i].tolist()})
zoom_chart = line_chart(zoom, "VUEL failures", xmax=10.0)
zoomg = []
for key, label, color in RUNS:
    c = T[key]["cum"]
    t = np.array(c["t_us"]); i = t <= 10
    zoomg.append({"label": label + " ghost", "color": color, "x": t[i].tolist(), "y": np.array(c["ghost"])[i].tolist()})
zoomg_chart = line_chart(zoomg, "ghost deletions", xmax=10.0, ymax=max(max(z["y"]) for z in zoom) * 1.08)

orph_chart = line_chart([{"label": l, "color": c, "x": O[k]["t_us"], "y": [100 * v for v in O[k]["orphan_frac"]]} for k, l, c in RUNS],
                        "fiber nodes whose host is deleted (%)")
spd_chart = line_chart([{"label": l, "color": c, "x": O[k]["t_us"], "y": O[k]["speed_orphaned_mean"]} for k, l, c in RUNS],
                       "mean speed of orphaned fiber nodes (m/s)")

# tables
rows = []
for k in ALLRUNS:
    e = np.array([t for _, t in EV[k]])
    g = T.get(k, {}).get("n_ghost_deleted")
    rows.append((NAMES[k], len(e), int((e < 0.1).sum()), int((e < 5).sum()), "%.1f" % np.percentile(e, 50), g if g is not None else "n/a"))
early_table = "<tr><th>Run</th><th class=\"n\">VUEL failures, total</th><th class=\"n\">before 0.1 us</th><th class=\"n\">before 5 us</th><th class=\"n\">median failure time (us)</th><th class=\"n\">ghost deletions, total</th></tr>" + "".join(
    "<tr><td>%s</td>%s</tr>" % (r[0], "".join('<td class="n">%s</td>' % x for x in r[1:])) for r in rows)

pts = (5, 10, 20, 50, 100)
cm_rows = ""
for key, label, color in RUNS:
    c = T[key]["cum"]; t = np.array(c["t_us"])
    cells = ""
    for x in pts:
        i = int(np.argmin(abs(t - x)))
        cells += '<td class="n">%d / %d</td>' % (c["vuel"][i], c["ghost"][i])
    cm_rows += "<tr><td>%s</td>%s</tr>" % (label, cells)
cum_table = "<tr><th>Run (VUEL failed / ghost deleted)</th>" + "".join('<th class="n">%d us</th>' % x for x in pts) + "</tr>" + cm_rows

o_rows = ""
for key, label, color in RUNS:
    r = O[key]; t = np.array(r["t_us"])
    at = lambda x: int(np.argmin(abs(t - x)))
    o_rows += '<tr><td>%s</td><td class="n">%.1f%%</td><td class="n">%.1f%%</td><td class="n">%.1f%%</td><td class="n">%.0f / %.1f</td></tr>' % (
        label, 100 * r["orphan_frac"][at(25)], 100 * r["orphan_frac"][at(50)], 100 * r["orphan_frac"][-1],
        r["speed_orphaned_mean"][-1], r["speed_attached_mean"][-1])
orph_table = '<tr><th>Run</th><th class="n">orphaned at 25 us</th><th class="n">at 50 us</th><th class="n">at 100 us</th><th class="n">mean speed at 100 us, orphaned / attached (m/s)</th></tr>' + o_rows

fe = {k: len([1 for _, t in EV[k] if t < 0.1]) for k in ("flat_ply_v3", "cc_ply_v3")}
css = open(TEMPLATE, encoding="utf-8", errors="replace").read()
css = css[:css.index("</style>")].replace("<title>Flat v2 Contact Run</title>", "<title>Host failure analysis</title>")
css += """
.note{color:var(--mute);font-size:13.5px}
</style>"""

body = """
<main>
<h1>Are the ghosts deleting too early, or is the VUEL really failing?</h1>
<div class="meta">What the 500 m/s runs say, 17 Oct 2026 &middot; flat and concave, solid host and plywise &middot; data from job stdout, viewer exports and energy histories</div>

<div class="verdict">
<p><strong>Short answer.</strong> Neither one is simply "too early", and the problem is not the same in every run. In the solid-host runs the two mechanisms track each other closely
until late in the run. In the plywise runs about <b>%(fe_flat)d (flat) and %(fe_cc)d (concave)</b> VUEL elements fail in the <b>very first solver increment</b> (t = 6.4 ns),
before the ball has touched anything, and their ghosts do <i>not</i> delete. The solid runs have none of these. That is the clearest anomaly in the data, and it is a VUEL-side effect,
not an early ghost deletion.</p>
<p><strong>Second finding.</strong> After the first-increment failures are discounted, ghosts delete <i>more</i> elements than the VUEL fails in the concave solid run
(6,588 ghost deletions against 5,194 VUEL failures at 100 us, 27%% more) and, by a smaller margin, in both plywise runs (about 190 more). So some ghosts are deleted without their VUEL failing.
This is consistent with the ghost deleting for a reason other than the VUEL strain criterion, but the aggregate counts cannot prove it. A per-element match is needed (see What to measure next).</p>
<p><strong>Fibers.</strong> What you saw in the viewer is real and is not unique to plywise. Between %(o_lo).0f%% and %(o_hi).0f%% of fiber nodes have lost their host element by 100 us, and the orphaned nodes
move at 75 to 156 m/s while attached nodes stay near 2 m/s.</p>
</div>

<h2>How the host fails in these models</h2>
<ul>
<li>Each host element is a <b>VU1 user element</b> (the real stiffness, mass and plasticity) with a <b>native ghost element</b> on the same nodes (stiffness and mass scaled by 1e-4) that carries the embedded fibers, the contact faces and the native deletion.</li>
<li>The VU1 fails by itself when its engineering strain reaches <b>0.1138</b> (or its Jacobian drops under 0.05): it then goes inert, but Abaqus cannot delete a user element, so its mass stays in the model.</li>
<li>The ghost deletes through its own ductile damage, initiated at a strain of <b>1e-6</b> with zero damage evolution, so it is removed the moment its damage initiates. This pair was tuned on the flat solid plate so that the two events land together (first ghost deletion 1.07e-7 s after the first VUEL failure).</li>
<li>Once a ghost is deleted, fibers that were embedded in it have no host. They are then free, unconstrained nodes carrying whatever momentum they had, and only the ball contact acts on them.</li>
</ul>

<h2>Finding 1: a group of VUEL elements fails at t = 0 in every plywise run</h2>
<div class="tbl"><table>%(early_table)s</table></div>
<p class="note">VUEL failure lines come from the job stdout (every failure writes the element number, the time and the strain). Ghost deletions come from the STATUS output in the viewer export, so they are counted at 210 frames. The first VUEL failures in the plywise runs are logged at 6.4e-9 s, which is the first increment.</p>
<figure class="fig"><figcaption><b>First 10 us, VUEL failures.</b> The plywise runs jump by more than 340 immediately; the solid runs rise from zero only after the ball arrives (about 2 us).</figcaption>%(zoom_chart)s</figure>
<figure class="fig"><figcaption><b>First 10 us, ghost deletions.</b> No jump: the ghosts of those elements are not deleted.</figcaption>%(zoomg_chart)s</figure>
<ul>
<li>It appears in all four plywise decks (v1 and v3, flat and concave), so it is not caused by the contact or fiber-boundary changes made between v1 and v3.</li>
<li>It is not the elements with a fiber volume fraction of 1 or more. The mesher's clamp lines (printed for the first solver calls) list 42 (flat) and 38 (concave) such elements, and none of them is among the early failures.</li>
<li>The early failures are about 43 per ply (344 over 8 plies). The deck has 57 to 58 host cells per ply with a fiber fraction of 0.9 or more, and 19 to 23 at 1.0 or more. So the early population is of the same order as the high-fiber-fraction cells, but I could not match them element by element (see below). <b>I have not identified them.</b></li>
<li>A failure with no load behind it has to come from the element's initial state or its own constraints, not from the impact: the plate is at rest, and the ball is 1 mm away. Candidates: the high-fiber-fraction stiffness and mass scaling, the initial-solution data, or the plywise instances being translated copies of one part.</li>
</ul>

<h2>Finding 2: after the start, ghosts and VUEL track each other, with the ghosts ahead</h2>
<div class="tbl"><table>%(cum_table)s</table></div>
<p class="note">Each cell is cumulative VUEL failures / cumulative ghost deletions at that time.</p>
%(cum_charts)s
<ul>
<li><b>Flat solid:</b> the VUEL is slightly ahead (3,793 against 3,548 at 100 us). Consistent with the calibration, where the ghost follows the VUEL by about a sampling interval.</li>
<li><b>Concave solid:</b> in step until about 40 us. After that the ghosts overtake and finish 27%% ahead (6,588 against 5,194). Ghosts are being deleted at a rate the VUEL strain criterion does not account for.</li>
<li><b>Plywise:</b> excluding the first-increment group, the VUEL count is about 2,050 (flat) and 2,160 (concave) against 2,243 and 2,348 ghost deletions, so the ghosts are also ahead by roughly 190.</li>
<li>One possible reason for ghosts deleting without a VUEL failure is the ghost's own distortion: it is a native element with a 1e-4 stiffness, so it can be pulled through large deformations by the fibers embedded in it. I have not tested this.</li>
</ul>

<h2>Finding 3: what happens to the fibers</h2>
<div class="tbl"><table>%(orph_table)s</table></div>
<figure class="fig"><figcaption><b>Fiber nodes whose host element is deleted (%%).</b> Each fiber node was assigned to the host element containing it at frame 0.</figcaption>%(orph_chart)s</figure>
<figure class="fig"><figcaption><b>Mean speed of orphaned fiber nodes (m/s).</b></figcaption>%(spd_chart)s</figure>
<ul>
<li>Fibers are not stretching to failure: only 1 to 3 plywise segments exceed 10%% strain, against 50 on the flat solid. They fly free instead.</li>
<li>Orphaned plywise nodes move faster (about 155 m/s) than the concave solid's (75 m/s) even though fewer are orphaned (14%% against 35%%). I suspect the ball is carrying them through the node contact, but have not confirmed it.</li>
<li>I cannot tell from node positions whether fiber load pulls the host to failure or the host fails first and releases the fiber. Orphaned fractions rise after host deletions begin, which points to hosts failing first.</li>
</ul>

<h2>What I can and cannot say</h2>
<ul>
<li><b>Can say:</b> plywise has a population of about 1.8%% of its VUEL elements that fail at t = 0 with their ghosts intact; the ghost deletion count runs ahead of the VUEL failure count later in the run, strongly so in the concave solid run; fibers outlive their host in every run.</li>
<li><b>Cannot say yet:</b> which elements are in each group, why the t = 0 group fails, or whether the extra ghost deletions are physical. The VUEL stdout labels (up to 46,658 in a 19,200-element model) do not line up with the exported element order, so a per-element match failed (about 15 to 130 matches out of thousands, with no consistent time offset). The viewer export carries no element labels.</li>
<li>The VUEL's own state (SDV49 failure flag, SDV106 damage) cannot be written to the output database: the datacheck warns 24 times that <code>*Element Output</code> is not supported for user elements. The only VUEL record is the stdout.</li>
</ul>

<h2>What to measure next</h2>
<ol>
<li><b>Identify the t = 0 failures.</b> Add the element's coordinates, fiber fraction and local mass/stiffness factor to the VUEL failure message, and run to 1 us (a couple of minutes). This names the population directly.</li>
<li><b>Put element labels in the viewer export</b> (the exporter reads them already; they are just not saved) and add each ghost's deletion time from the full-resolution STATUS history. That gives a per-element VUEL-failure / ghost-deletion pairing for every run.</li>
<li><b>Control run without fibers.</b> Same plate and ball, no embedded fibers. If ghosts and VUEL then agree, fiber loading is what pushes the ghosts to delete early. This is the cleanest test of the idea that the fiber momentum rips the host out.</li>
<li><b>Vary one threshold at a time</b> for the new deck: the ghost's ductile failure strain (1e-6 now) and the VUEL strain limit (0.1138 now). Because the pair was tuned on one flat plate at one speed, a change of material or boundary condition can break the synchronisation.</li>
<li><b>Fixture boundary condition.</b> Any new support (instead of the full encastre on the outer edge) changes where fibers are constrained. I would keep the fiber end nodes in the same boundary sets as the host nodes, as now, and check the t = 0 count again with the new fixture.</li>
</ol>

<h2>Caveats</h2>
<ul>
<li>Ghost deletion times have a 0.49 us resolution (210 frames over 100 us). The VUEL times are exact.</li>
<li>VUEL failure counts are unique element numbers from the stdout; the plywise runs repeat the same part in 8 instances, so I could not separate plies.</li>
<li>One run per configuration, no repeats. The 4-way comparison is a visual and capability check, not a statistical one.</li>
<li>The orphan analysis assigns each fiber node to the host element containing it at frame 0; 1.3 to 1.4%% of the plywise fiber nodes (the ends on the boundary) were not assigned.</li>
</ul>
</main>
"""
html = css + body % dict(
    fe_flat=fe["flat_ply_v3"], fe_cc=fe["cc_ply_v3"], early_table=early_table, cum_table=cum_table, cum_charts=cum_charts,
    zoom_chart=zoom_chart, zoomg_chart=zoomg_chart, orph_table=orph_table, orph_chart=orph_chart, spd_chart=spd_chart,
    o_lo=min(100 * O[k]["orphan_frac"][-1] for k in O), o_hi=max(100 * O[k]["orphan_frac"][-1] for k in O))
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html))
