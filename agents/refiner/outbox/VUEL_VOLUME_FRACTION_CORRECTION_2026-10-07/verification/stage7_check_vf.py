"""Compare the Stage 7 Vf=0, Vf=0.5, and pre-Stage-7 Vf=0 ODBs.

Run with Abaqus Python:
  abaqus python stage7_check_vf.py TENSION_VF0 TENSION_VF05 TENSION_BASE \
      COMPRESSION_VF0 COMPRESSION_VF05 COMPRESSION_BASE
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb

PINNED = (1, 4, 5, 8)
E0 = 2.0e11
SIGY0 = 2.5e8


def curve(path):
    odb = openOdb(path)
    frames = list(odb.steps.values())[0].frames
    rows = []
    for frame in frames:
        u1 = None
        reaction = 0.0
        seen = 0
        for value in frame.fieldOutputs["U"].values:
            if value.nodeLabel == 2:
                u1 = float(value.data[0])
        for value in frame.fieldOutputs["RF"].values:
            if value.nodeLabel in PINNED:
                reaction += float(value.data[0])
                seen += 1
        if u1 is not None and seen == len(PINNED):
            rows.append((u1, -reaction))
    odb.close()
    return rows


def nearest(rows, strain):
    return min(rows, key=lambda row: abs(row[0] - strain))


def rel(a, b):
    return abs(a - b) / max(abs(b), 1.0)


def yield_estimate(rows, eta):
    # First point whose force departs at least 3% from the elastic PK2
    # prediction. Green strain is used because the VUEL is total Lagrangian.
    for eps, stress in rows:
        green = abs(eps + 0.5 * eps * eps)
        stress = abs(stress)
        elastic = eta * E0 * green
        if green > 2.0e-4 and stress < 0.97 * elastic:
            return green
    return None


def hardening_slope(rows, eta):
    # In monotonic uniaxial loading, PEEQ equals the magnitude of axial
    # plastic strain. Infer it from PK2 stress and Ee=S/(eta*E), then
    # regress |S| against PEEQ.
    pts = []
    for eps, stress in rows:
        green = abs(eps + 0.5 * eps * eps)
        stress = abs(stress)
        if green > 0.01:
            peeq = green - stress / (eta * E0)
            pts.append((peeq, stress))
    xm = sum(p[0] for p in pts) / len(pts)
    ym = sum(p[1] for p in pts) / len(pts)
    den = sum((p[0] - xm) ** 2 for p in pts)
    return sum((p[0] - xm) * (p[1] - ym) for p in pts) / den


def analyze(paths):
    vf0, vf05, baseline = [curve(path) for path in paths]
    sample_strains = (0.0005, 0.0009, 0.01, 0.02, 0.035)
    regression_errors = []
    half_ratio_errors = []
    for eps in sample_strains:
        target = eps if vf0[-1][0] >= 0.0 else -eps
        s0 = abs(nearest(vf0, target)[1])
        sh = abs(nearest(vf05, target)[1])
        sb = abs(nearest(baseline, target)[1])
        regression_errors.append(rel(s0, sb))
        half_ratio_errors.append(rel(sh, 0.5 * s0))
    y0 = yield_estimate(vf0, 1.0)
    yh = yield_estimate(vf05, 0.5)
    slope0 = hardening_slope(vf0, 1.0)
    slopeh = hardening_slope(vf05, 0.5)
    checks = {
        "vf0_matches_pre_stage7_max_rel_error_lt_1e-8":
            max(regression_errors) < 1.0e-8,
        "vf05_force_is_half_max_rel_error_lt_0p03":
            max(half_ratio_errors) < 0.03,
        "yield_green_strain_matches_rel_error_lt_0p03":
            y0 is not None and yh is not None and rel(yh, y0) < 0.03,
        "postyield_stress_vs_peeq_slope_is_half_rel_error_lt_0p05":
            rel(slopeh, 0.5 * slope0) < 0.05,
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "vf0_regression_max_rel_error": max(regression_errors),
        "vf05_half_force_max_rel_error": max(half_ratio_errors),
        "yield_green_strain": {"vf0": y0, "vf05": yh},
        "postyield_stress_vs_peeq_slope_Pa": {"vf0": slope0, "vf05": slopeh},
        "analytic_yield_green_strain": SIGY0 / E0,
    }


def main():
    if len(sys.argv) != 7:
        raise SystemExit("expected tension and compression Vf=0, Vf=0.5, "
                         "and baseline-Vf=0 ODB paths")
    report = {
        "tension": analyze(sys.argv[1:4]),
        "compression": analyze(sys.argv[4:7]),
    }
    report["pass"] = all(item["pass"] for item in report.values())
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
