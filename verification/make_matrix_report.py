"""Build reports/MATRIX_MATERIAL_REPORT.html from the stored VUEL-vs-native CSVs.

Usage: python verification/make_matrix_report.py
Plots are inline SVG (no external dependencies), data from
verification/roar/matrix_material/final_gp_length_fix and the iteration folders.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "verification" / "roar" / "matrix_material"
FINAL = RES / "final_gp_length_fix"
OUT = ROOT / "reports" / "MATRIX_MATERIAL_REPORT.html"
SIZE = 1.0e-3
AREA = SIZE ** 2
VOL = SIZE ** 3
MODES = [("tension", "Tension"), ("compression", "Compression"), ("shear", "Simple shear")]


def read(p):
    with open(p) as f:
        return list(csv.DictReader(f))


def curve(d, name):
    rows = read(d / (name + "_curve.csv"))
    sz = 1.0 if d.name.startswith("iter0") else SIZE  # iter 0 used a 1 m cube
    return ([abs(float(r["u1"])) / sz for r in rows],
            [abs(float(r["F"])) / sz ** 2 / 1e6 for r in rows])


def energy(d, name):
    last = read(d / (name + "_energy.csv"))[-1]
    return {k: float(v) / VOL for k, v in last.items() if k != "t"}


def landmarks(xs, ys):
    pk = max(ys)
    ip = ys.index(pk)
    half = next((xs[i] for i in range(ip, len(ys)) if ys[i] < 0.5 * pk), None)
    zero = next((xs[i] for i in range(ip, len(ys)) if ys[i] < 0.01 * pk), None)
    return pk, xs[ip], half, zero


def fmt(x):
    return "%.3f" % x if x is not None else "n/a"


def plot(d, mode, tag, w=420, h=300):
    ml, mr, mt, mb = 46, 10, 12, 34
    v = curve(d, "vuel_%s_%s" % (mode, tag))
    n = curve(d, "native_%s_%s" % (mode, tag))
    xmax = max(max(v[0]), max(n[0]))
    ymax = max(max(v[1]), max(n[1])) * 1.08
    # round axes
    step = 10 if ymax < 120 else 20
    ytop = (int(ymax / step) + 1) * step
    xs = lambda x: ml + (w - ml - mr) * x / xmax
    ys = lambda y: h - mb - (h - mt - mb) * y / ytop

    def path(c, cls):
        pts = " ".join("%.1f,%.1f" % (xs(a), ys(b)) for a, b in zip(*c))
        return '<polyline class="%s" points="%s"/>' % (cls, pts)

    g = []
    for k in range(0, int(ytop) + 1, step):
        g.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text x="%d" y="%.1f" text-anchor="end">%d</text>'
                 % (ml, w - mr, ys(k), ys(k), ml - 6, ys(k) + 3, k))
    xt = 0.05 if xmax < 0.4 else (0.1 if xmax < 1.0 else float(int(xmax / 5) or 1))
    k = 0.0
    while k <= xmax + 1e-9:
        g.append('<text x="%.1f" y="%d" text-anchor="middle">%.2f</text>' % (xs(k), h - mb + 14, k))
        k += xt
    g.append('<text x="%d" y="%d" text-anchor="middle">nominal strain</text>' % ((ml + w - mr) // 2, h - 4))
    g.append('<text x="12" y="%d" transform="rotate(-90 12 %d)" text-anchor="middle">engineering stress, MPa</text>'
             % ((mt + h - mb) // 2, (mt + h - mb) // 2))
    return ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s %s stress-strain, VUEL vs native">%s%s%s</svg>'
            % (w, h, mode, tag, "".join(g), path(n, "nat"), path(v, "vue")))


def case_rows():
    rows = []
    for mode, label in MODES:
        for tag, rl in (("r1000", "1000 /s"), ("r1", "1 /s")):
            v = curve(FINAL, "vuel_%s_%s" % (mode, tag))
            n = curve(FINAL, "native_%s_%s" % (mode, tag))
            lv, ln = landmarks(*v), landmarks(*n)
            ev = energy(FINAL, "vuel_%s_%s" % (mode, tag))
            en = energy(FINAL, "native_%s_%s" % (mode, tag))
            dv, dn = ev["ALLPD"] + ev["ALLDMD"], en["ALLPD"] + en["ALLDMD"]
            ddiff = 100 * abs(dv - dn) / dn
            bal = 100 * abs(ev["ALLWK"] - (ev["ALLIE"] + dv + ev["ALLKE"])) / ev["ALLWK"]
            rows.append("<tr><td>%s %s</td><td>%.2f / %.2f</td><td>%s / %s</td><td>%s / %s</td>"
                        "<td>%.2f / %.2f</td><td>%.2f%%</td><td>%.2f%%</td></tr>"
                        % (label, rl, lv[0], ln[0], fmt(lv[2]), fmt(lv[3]), fmt(ln[2]), fmt(ln[3]),
                           dv / 1e6, dn / 1e6, ddiff, bal))
    return "\n".join(rows)


def iter_plot(folder, mode, tag, title):
    d = RES / folder
    if not (d / ("vuel_%s_%s_curve.csv" % (mode, tag))).exists():
        return ""
    return '<figure><figcaption>%s</figcaption>%s</figure>' % (title, plot(d, mode, tag))


CSS = """
:root{--bg:#f4f2ee;--surface:#fff;--fg:#1c1a17;--muted:#6b645b;--rule:#ddd7cc;--accent:#b1460a;--accent-soft:#f0ddce;
--good:#276e4d;--good-soft:#dcebe2;--vue:#b1460a;--nat:#2a5d9f;--mono:'IBM Plex Mono',ui-monospace,Consolas,monospace;
--sans:'IBM Plex Sans',system-ui,-apple-system,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15130f;--surface:#201d18;--fg:#f0ece3;--muted:#a39a8c;
--rule:#3a362e;--accent:#e67a3e;--accent-soft:#3a2415;--good:#6fcba0;--good-soft:#163427;--vue:#e67a3e;--nat:#7fb0ee;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#15130f;--surface:#201d18;--fg:#f0ece3;--muted:#a39a8c;--rule:#3a362e;--accent:#e67a3e;
--accent-soft:#3a2415;--good:#6fcba0;--good-soft:#163427;--vue:#e67a3e;--nat:#7fb0ee;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:var(--sans);margin:0;padding-inline:16px;line-height:1.5;font-size:14.5px}
.wrap{max-width:900px;margin:0 auto;padding-block:28px 64px}
.meta{display:flex;flex-wrap:wrap;gap:8px 20px;font-family:var(--mono);font-size:12px;color:var(--muted);border-bottom:1px solid var(--rule);padding-bottom:16px;margin-bottom:28px}
.meta b{color:var(--fg)}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
.sub{color:var(--muted);font-size:15px;margin:0 0 28px;max-width:68ch}
h2{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:44px 0 14px;border-top:1px solid var(--rule);padding-top:20px}
p,li{max-width:72ch}p{margin:0 0 14px}
code{font-family:var(--mono);font-size:12.5px;background:var(--accent-soft);padding:1px 5px;border-radius:4px}
.verdict{display:inline-flex;align-items:center;gap:8px;background:var(--good-soft);color:var(--good);font-family:var(--mono);font-size:12px;font-weight:600;padding:5px 12px;border-radius:999px;margin-bottom:18px}
.verdict::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--good)}
.hero{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.stat{flex:1 1 180px;background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:16px 18px}
.stat .n{font-family:var(--mono);font-size:26px;font-weight:600;color:var(--accent)}
.stat .l{font-size:12.5px;color:var(--muted);margin-top:4px}
.plots{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
figure{margin:0;background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 12px 4px}
figcaption{font-family:var(--mono);font-size:12px;color:var(--fg);margin-bottom:4px}
svg{width:100%;height:auto;display:block}svg text{fill:var(--muted);font-family:var(--mono);font-size:10px}
svg .grid{stroke:var(--rule);stroke-width:1}
svg polyline{fill:none;stroke-linejoin:round}
svg .vue{stroke:var(--vue);stroke-width:2.4}svg .nat{stroke:var(--nat);stroke-width:1.6;stroke-dasharray:5 3}
.legend{font-family:var(--mono);font-size:12px;margin:8px 0 14px;color:var(--muted)}
.legend i{display:inline-block;width:22px;height:0;border-top:3px solid var(--vue);vertical-align:middle;margin:0 6px 0 0}
.legend i.n{border-top:2px dashed var(--nat);margin-left:16px}
.tw{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:11.5px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:0}
td.m,th.m{font-family:var(--mono);font-size:12px}
.warn{background:var(--accent-soft);border:1px solid var(--accent);border-radius:8px;padding:12px 14px;margin:16px 0;font-size:13.5px}
.warn b{color:var(--accent)}
ol.steps{padding-left:20px}ol.steps li{margin-bottom:8px}
ul{padding-left:20px}ul li{margin-bottom:5px}
"""


def main():
    final_plots = "".join(
        '<figure><figcaption>%s, 1000 /s</figcaption>%s</figure>' % (label, plot(FINAL, mode, "r1000"))
        for mode, label in MODES)
    final_plots_1 = "".join(
        '<figure><figcaption>%s, 1 /s</figcaption>%s</figure>' % (label, plot(FINAL, mode, "r1"))
        for mode, label in MODES)
    it0 = iter_plot("iter0_first_pass_pk2_unit_cube", "tension", "r1000", "iter 0: PK2 J2 (tension)") or \
        iter_plot("iter0_first_pass_pk2_unit_cube", "tension", "r1", "iter 0: PK2 J2 (tension)")
    it1 = iter_plot("iter1_hencky_tension_unstable_r1000", "tension", "r1000", "iter 1: Hencky, dt too large (tension)")
    it2 = iter_plot("iter2_stable_dt_fix", "tension", "r1000", "iter 2: dt fixed, L bug (tension)")
    it3 = iter_plot("final_gp_length_fix", "tension", "r1000", "iter 3: final (tension)")

    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Matrix Material VUEL Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>@@css@@</style></head><body><div class="wrap">
<div class="meta"><span><b>Date</b> 2026-10-19</span><span><b>Branch</b> vuel-plastic-failure</span><span><b>Abaqus</b> 2024 Explicit, ROAR</span><span><b>Source</b> uel/VUEL_material.for</span></div>
<h1>Elastic-plastic matrix with ductile damage in the hex VUEL</h1>
<p class="sub">How the Stage 8 matrix material was built into the user element and checked against native Abaqus (C3D8R with *Plastic and *Damage Initiation/Evolution) on single-element tests.</p>
<div class="verdict">VUEL AGREES WITH NATIVE: 6 of 6 CASES PASS (1000 /s and 1 /s)</div>
<div class="hero">
<div class="stat"><div class="n">&lt; 1%</div><div class="l">max pre-softening stress difference to native</div></div>
<div class="stat"><div class="n">&le; 0.35%</div><div class="l">total dissipation difference (plastic + damage)</div></div>
<div class="stat"><div class="n">&lt; 0.1%</div><div class="l">VUEL energy-balance residual</div></div>
<div class="stat"><div class="n">4</div><div class="l">iterations to get there</div></div>
</div>

<h2>1. Purpose and target material</h2>
<p>Valerie's plate-impact model needs the matrix of the embedded-fiber plate to be elastic-plastic with ductile damage, inside the hex VUEL that hosts the fibers. Native material cards cannot drive a user element, so the constitutive law was written in the VUEL and verified against native Abaqus.</p>
<div class="tw"><table>
<tr><th>Property</th><th>Value (SI)</th></tr>
<tr><td>Elasticity</td><td class="m">E = 700 MPa, &nu; = 0.45, &rho; = 980 kg/m&sup3;</td></tr>
<tr><td>Plasticity</td><td class="m">J2, yield 70 MPa, no hardening</td></tr>
<tr><td>Damage onset</td><td class="m">equivalent plastic strain 0.1 at 0.01 /s, triaxiality 1/3</td></tr>
<tr><td>Damage evolution</td><td class="m">energy based, linear, Gf = 1460 J/m&sup2;</td></tr>
</table></div>
<p style="margin-top:14px">The fiber model (uniaxial, rate-dependent, tension-only) is a separate VUMAT and is paused; it is not covered here.</p>
<div class="warn"><b>Open item.</b> Valerie's deck <code>Meshing/Vals.inp</code> uses a matrix fracture strain of <b>0.01</b>, the brief says <b>0.1</b>. The brief was kept authoritative and all tests use 0.1. It is a single constant (<code>EPS_F</code> in the case generator) if this should change.</div>

<h2>2. Final agreement: VUEL against native</h2>
<div class="legend"><i></i>VUEL &nbsp;<i class="n"></i>native Abaqus C3D8R &nbsp;&middot;&nbsp; 1 mm cube, engineering stress</div>
<div class="plots">@@final_plots@@</div>
<p style="margin-top:14px">The 1 /s curves are the same to plotting precision, as expected for a rate-independent matrix:</p>
<div class="plots">@@final_plots_1@@</div>

<h2>3. Numbers</h2>
<div class="tw"><table>
<tr><th>Case</th><th>Peak MPa<br>VUEL / native</th><th class="m">Strain at 50% / 99% loss<br>VUEL</th><th class="m">same,<br>native</th><th>Dissipation MJ/m&sup3;<br>VUEL / native</th><th>Diss. diff.</th><th>VUEL energy balance</th></tr>
@@rows@@
</table></div>
<p style="margin-top:14px">Peak stress is the yield plateau (compression includes the load increase from area change). The largest pre-softening stress difference is 0.97% (tension), 0.87% (compression), 0.45% (shear), always at the yield knee, where the two codes' output frames fall at slightly different points: a sampling effect. Pass criteria: stress within 3%, VUEL energy balance within 3%, dissipation within 5%.</p>
<p>Dissipation split, tension 1000 /s: plastic 8.55e6 vs 8.54e6, damage 3.57e6 vs 3.54e6 J/m&sup3; (theory: plastic 7.0e6 + 1.46e6, damage 3.5e6).</p>

<h2>4. The model</h2>
<p>Selected with <code>props(14) = MAT_MODEL = 1</code>; <code>0</code> keeps the previous behaviour bit-for-bit. 39 properties, 159 state variables.</p>
<ol class="steps">
<li><b>Kinematics and stress.</b> The element stays Total Lagrangian (internal force = &int; B<sub>L</sub><sup>T</sup> S dV<sub>0</sub>, 2&times;2&times;2 Gauss). The law is multiplicative Hencky elasticity: from F and the stored C<sub>p</sub><sup>-1</sup> form b<sub>e</sub> = F C<sub>p</sub><sup>-1</sup> F<sup>T</sup>, take principal log strains, Kirchhoff stress &tau; = &lambda; tr(&epsilon;) I + 2&mu;&epsilon;, and return S = F<sup>-1</sup> &tau; F<sup>-T</sup> to the force assembly.</li>
<li><b>Yield.</b> J2 on Cauchy stress, q &le; &sigma;<sub>y</sub> J. Flow is isochoric so the radial return in log space is exact: d&gamma; = (q<sub>trial</sub> &minus; &sigma;<sub>y</sub> J)/(3&mu;). PEEQ is the logarithmic equivalent plastic strain, as native reports.</li>
<li><b>Damage onset.</b> When PEEQ &ge; &epsilon;<sub>f</sub>(rate), &sigma;<sub>y0</sub> and the rate are frozen.</li>
<li><b>Evolution</b> (Abaqus energy, linear). &#363; = L(PEEQ &minus; PEEQ<sub>onset</sub>), &#363;<sub>f</sub> = 2Gf/&sigma;<sub>y0</sub>, D = &#363;/&#363;<sub>f</sub> in [0,1], monotonic; S = (1&minus;D) S<sub>undamaged</sub>. L = (&eta; V<sub>0</sub>)<sup>1/3</sup> with full reference volume V<sub>0</sub> and &eta; = 1 &minus; V<sub>f</sub> (consistent with the embedded-fiber volume correction).</li>
<li><b>Element death.</b> Damage is per Gauss point; when all 8 reach D = 1 the element is latched dead (rhs = 0, dtimeStable = 1e30).</li>
<li><b>Energy.</b> Stress power is (1&minus;D)(d&psi; + q d&gamma;): plastic dissipation ALLPD carries a (1&minus;D) weight and ALLDMD is the released elastic energy &psi; dD (native's definition).</li>
<li><b>Rate dependence.</b> Table of yield vs rate, linear in log10(rate), clamped outside; default rate measure is the plastic strain rate (native-like), switchable to total.</li>
<li><b>Stable increment.</b> The lumped brick's volumetric mode is up to &radic;3 faster than the 1D bar estimate, so the Stage 8 path uses an extra 1/&radic;3.</li>
</ol>
<p>An independent line-by-line Python port of the return map (<code>verification/hencky_reference.py</code>) confirms: uniaxial Cauchy stress plateaus at 70.0000 MPa with PEEQ = ln &lambda; &minus; &sigma;<sub>y</sub>/E, and simple shear gives Mises 70 MPa.</p>

<h2>5. Method</h2>
<ul>
<li>Roles: the drafter agent wrote the first-pass Fortran, a Python reference, the deck generator and the sbatch (T-042); the hub (Claude Code) reviewed, ran everything on ROAR, and found and fixed the problems below.</li>
<li>Tests: a 1 mm cube in tension (0.5 nominal strain), compression (&minus;0.4) and simple shear (1.0), at 0.01, 1 and 1000 /s, smooth-step loading. Every VUEL deck has a native twin (one C3D8R, same boundary conditions and step).</li>
<li>Output: nodal displacement and reaction history plus ALLIE, ALLPD, ALLKE, ALLDMD, ALLWK, dumped to CSV on ROAR and compared locally. Native ALLIE already contains ALLPD and ALLDMD, so the native balance is ALLWK = ALLIE + ALLKE; the VUEL one is ALLWK = ALLIE + ALLPD + ALLDMD + ALLKE.</li>
</ul>

<h2>6. How it got there</h2>
<div class="plots">@@it0@@@@it1@@@@it2@@@@it3@@</div>
<div class="tw" style="margin-top:14px"><table>
<tr><th>#</th><th>Finding</th><th>Cause</th><th>Fix</th></tr>
<tr><td>0</td><td>Tension plateau 77&ndash;82 MPa vs native 62; shear 60 vs 40; damage dissipation 1.9e3 vs 3.5e6 J/m&sup3;; energy balance off by a third</td><td>(a) J2 on PK2 stress, so the true yield grew about as (1+&epsilon;)&sup2;; (b) elastic energy released at damage onset was never booked; (c) 1 m cube at 1000 /s was inertia dominated</td><td>(a) Hencky / Kirchhoff return; (b) ALLDMD = &psi; dD; (c) 1 mm cube</td></tr>
<tr><td>1</td><td>Compression and shear matched; tension died early (u &asymp; 0.18 vs 0.22), J oscillating 0.90 &harr; 1.15</td><td>Stable increment was the 1D bar value; the brick's volumetric mode is up to &radic;3 faster (1.6&times; at &nu; = 0.45)</td><td>extra 1/&radic;3 on dtimeStable</td></tr>
<tr><td>2</td><td>All 9 cases ran but softening tail too slow (99% loss at 0.32 vs 0.275) and plastic dissipation 5% high</td><td>Element volume for L was accumulated inside the Gauss-point loop, so point k used k/8 of the volume; mean Gf/L over 8 points was 1.32&times; too large (predicts +0.47e6 J/m&sup3;, exactly the excess)</td><td>pre-pass for the full reference volume</td></tr>
<tr><td>3</td><td>All 6 cases at 1000 and 1 /s PASS</td><td></td><td></td></tr>
</table></div>
<p style="margin-top:14px">Also fixed in the drafter's deliverables: the check script reported PASS while comparing nothing and crashed on a real ODB (replaced by the CSV workflow); and Abaqus/Explicit single precision refuses more than 20,000,000 increments, so the 0.01 /s step (~1.8e8 increments) needs <code>double=both</code>.</p>

<h2>7. Known deviations from native</h2>
<ul>
<li>The VUEL is full integration (8 Gauss points); native is C3D8R (1 point). Homogeneous single-element tests cannot expose hourglass or integration differences.</li>
<li>Native uses a Hughes&ndash;Winget / corotational rate form; the VUEL is hyperelastic-based. They agree to under 1% here (nominal strain up to ~0.3), but would differ for large rotations combined with plasticity, which the cantilever will show.</li>
<li>Rate dependence is log10-linear between table points; native tabular is linear in rate. They match only at table points.</li>
<li>VUEL ALLIE is elastic only; native ALLIE includes ALLPD and ALLDMD. Compare through the balance.</li>
<li>A user element cannot trigger native element deletion or SPH conversion; D = 1 zeroes the force and uses the dead-element path.</li>
<li>The Stage 8 stable increment is 1/&radic;3 smaller than before, up to 1.7&times; more increments. The legacy <code>MAT_MODEL = 0</code> path is unchanged and its estimate looks marginal for &nu; = 0.45 (not re-examined).</li>
</ul>

<h2>8. Not yet verified</h2>
<ul>
<li>The 0.01 /s set on the fixed Fortran (the earlier run used pre-fix code and was cancelled). The matrix is rate independent so it adds little.</li>
<li>The multi-point rate table path against Abaqus (a one-point table only so far).</li>
<li>Embedded fibers (&eta; &lt; 1), the combined matrix-and-fiber case, and the cantilever case.</li>
<li>Wave propagation and non-uniform softening, and the interaction of Gauss-point damage with the all-points death rule.</li>
<li>The <code>Vals.inp</code> fracture strain of 0.01 versus the brief's 0.1.</li>
</ul>

<h2>9. Files</h2>
<div class="tw"><table>
<tr><th>File</th><th>Role</th></tr>
<tr><td class="m">uel/VUEL_material.for</td><td>element with the Stage 8 material (HENCKY_RETURN, EIG3_JACOBI, INTERP_RATE_TABLE_VUEL)</td></tr>
<tr><td class="m">docs/MATRIX_MATERIAL_PROPS_SVARS.md</td><td>props / svars layout, equations, energy</td></tr>
<tr><td class="m">docs/RATE_DAMAGE_MATERIAL_SPEC.md</td><td>agreed spec and decisions</td></tr>
<tr><td class="m">docs/MATRIX_MATERIAL_DEVELOPMENT_REPORT.md</td><td>text version of this report</td></tr>
<tr><td class="m">verification/hencky_reference.py</td><td>Python port and unit checks of the return map</td></tr>
<tr><td class="m">verification/make_matrix_material_cases.py</td><td>generates the 18 decks and the deck list</td></tr>
<tr><td class="m">verification/roar/matrix_material.sbatch</td><td>one job per rate tag, optional Abaqus options</td></tr>
<tr><td class="m">verification/dump_matrix_curves.py</td><td>ODB to CSV (abaqus python)</td></tr>
<tr><td class="m">verification/analyze_matrix_material.py</td><td>VUEL vs native comparison and PASS/FAIL</td></tr>
<tr><td class="m">verification/make_matrix_report.py</td><td>builds this page from the stored CSVs</td></tr>
<tr><td class="m">verification/roar/matrix_material/*</td><td>curves and energies for every iteration</td></tr>
</table></div>
<p style="margin-top:14px">Reproduce: generate the decks, copy the folder, <code>matrix_material.sbatch</code> and <code>dump_matrix_curves.py</code> to ROAR scratch, <code>sbatch matrix_material.sbatch r1000</code> (and <code>r1</code>), fetch the CSVs, then <code>python verification/analyze_matrix_material.py &lt;folder&gt; r1000 r1</code>.</p>
</div></body></html>
"""
    for k, v in dict(css=CSS, final_plots=final_plots, final_plots_1=final_plots_1, rows=case_rows(),
                     it0=it0, it1=it1, it2=it2, it3=it3).items():
        html = html.replace("@@%s@@" % k, v)
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, len(html))


if __name__ == "__main__":
    main()
