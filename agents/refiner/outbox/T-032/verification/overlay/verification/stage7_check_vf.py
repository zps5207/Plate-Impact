"""Check fast and 10x-slower Stage 7 volume-fraction ODBs.

Run with Abaqus Python and ten ODB paths in this order:
  fast tension (Vf0, Vf05, baseline), fast compression (same),
  slow tension (Vf0, Vf05), slow compression (Vf0, Vf05).
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb
from stage7_vf_metrics import rel

PINNED = (1, 4, 5, 8)
E0 = 2.0e11
SIGY0 = 2.5e8


def curve(path):
    """Return (time, prescribed axial displacement, total reaction)."""
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
            rows.append((float(frame.frameValue), u1, -reaction))
    odb.close()
    return rows


def nearest(rows, strain):
    return min(rows, key=lambda row: abs(row[1] - strain))


def yield_estimate(rows, eta):
    # First point whose force departs at least 3% from the elastic PK2
    # prediction. This reaction-based estimate remains rate-sensitive.
    for _, eps, stress in rows:
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
    for _, eps, stress in rows:
        green = abs(eps + 0.5 * eps * eps)
        stress = abs(stress)
        if green > 0.01:
            peeq = green - stress / (eta * E0)
            pts.append((peeq, stress))
    if len(pts) < 2:
        return None
    xm = sum(p[0] for p in pts) / len(pts)
    ym = sum(p[1] for p in pts) / len(pts)
    den = sum((p[0] - xm) ** 2 for p in pts)
    if den <= 1.0e-30:
        return None
    return sum((p[0] - xm) * (p[1] - ym) for p in pts) / den


def matching_time_elastic(vf0, vf05):
    """Compare equal-time frames below yield and retain time evidence."""
    force_errors = []
    strain_errors = []
    time_differences = []
    samples = []
    for full, half in zip(vf0, vf05):
        t0, eps0, stress0 = full
        th, epsh, stressh = half
        green = abs(eps0 + 0.5 * eps0 * eps0)
        if 2.0e-4 < green < 9.0e-4:
            time_differences.append(abs(th - t0))
            strain_errors.append(rel(abs(epsh), abs(eps0)))
            force_errors.append(rel(abs(stressh), 0.5 * abs(stress0)))
            samples.append({
                "time_vf0_s": t0,
                "time_vf05_s": th,
                "nominal_strain_vf0": eps0,
                "nominal_strain_vf05": epsh,
                "reaction_vf0": stress0,
                "reaction_vf05": stressh,
                "vf05_over_vf0_reaction_ratio":
                    abs(stressh) / abs(stress0),
            })
    return {
        "points": len(force_errors),
        "max_time_absolute_difference_s":
            max(time_differences) if time_differences else None,
        "max_nominal_strain_relative_error":
            max(strain_errors) if strain_errors else None,
        "max_half_force_relative_error":
            max(force_errors) if force_errors else None,
        "samples": samples,
    }


def analyze(paths):
    curves = [curve(path) for path in paths]
    vf0, vf05 = curves[:2]
    baseline = curves[2] if len(curves) == 3 else None
    sign = 1.0 if vf0[-1][1] >= 0.0 else -1.0
    regression_errors = []
    elastic_errors = []
    postyield_errors = []
    if baseline is not None:
        for eps in (0.0005, 0.0009, 0.01, 0.02, 0.035):
            s0 = abs(nearest(vf0, sign * eps)[2])
            sb = abs(nearest(baseline, sign * eps)[2])
            regression_errors.append(rel(s0, sb))
    for eps in (0.0005, 0.0009):
        s0 = abs(nearest(vf0, sign * eps)[2])
        sh = abs(nearest(vf05, sign * eps)[2])
        elastic_errors.append(rel(sh, 0.5 * s0))
    for eps in (0.01, 0.02, 0.035):
        s0 = abs(nearest(vf0, sign * eps)[2])
        sh = abs(nearest(vf05, sign * eps)[2])
        postyield_errors.append(rel(sh, 0.5 * s0))

    y0 = yield_estimate(vf0, 1.0)
    yh = yield_estimate(vf05, 0.5)
    slope0 = hardening_slope(vf0, 1.0)
    slopeh = hardening_slope(vf05, 0.5)
    yield_error = rel(yh, y0) if y0 is not None and yh is not None else None
    slope_error = (rel(slopeh, 0.5 * slope0)
                   if slope0 is not None and slopeh is not None else None)
    time_match = matching_time_elastic(vf0, vf05)

    checks = {
        "vf05_elastic_force_is_half_rel_error_lt_0p03":
            max(elastic_errors) < 0.03,
        "matching_time_elastic_force_is_half_rel_error_lt_0p03":
            time_match["max_half_force_relative_error"] is not None and
            time_match["max_half_force_relative_error"] < 0.03,
        "yield_green_strain_matches_rel_error_lt_0p03":
            yield_error is not None and yield_error < 0.03,
        "postyield_stress_vs_peeq_slope_is_half_rel_error_lt_0p05":
            slope_error is not None and slope_error < 0.05,
    }
    if baseline is not None:
        checks["vf0_matches_pre_stage7_max_rel_error_lt_1e-8"] = (
            max(regression_errors) < 1.0e-8)

    return {
        "checks": checks,
        "pass": all(checks.values()),
        "vf0_regression_max_relative_error":
            max(regression_errors) if regression_errors else None,
        "vf05_elastic_half_force_max_relative_error": max(elastic_errors),
        "vf05_postyield_half_force_max_relative_error":
            max(postyield_errors),
        "matching_time_elastic": time_match,
        "yield_green_strain": {"vf0": y0, "vf05": yh},
        "yield_green_strain_relative_error": yield_error,
        "postyield_stress_vs_peeq_slope_Pa":
            {"vf0": slope0, "vf05": slopeh},
        "postyield_half_slope_relative_error": slope_error,
        "analytic_yield_green_strain": SIGY0 / E0,
    }


def convergence(fast, slow):
    metrics = (
        "vf05_elastic_half_force_max_relative_error",
        "yield_green_strain_relative_error",
        "postyield_half_slope_relative_error",
    )
    reduced = {}
    for name in metrics:
        reduced[name] = (fast[name] is not None and slow[name] is not None
                         and slow[name] < fast[name])
    return {
        "errors_reduced_at_10x_slower_rate": reduced,
        "all_errors_reduced": all(reduced.values()),
        "slow_checks_pass": slow["pass"],
        "dynamic_artifact_supported": all(reduced.values()) and slow["pass"],
    }


def main():
    if len(sys.argv) != 11:
        raise SystemExit("expected ten ODB paths; see module docstring")
    fast_tension = analyze(sys.argv[1:4])
    fast_compression = analyze(sys.argv[4:7])
    slow_tension = analyze(sys.argv[7:9])
    slow_compression = analyze(sys.argv[9:11])
    report = {
        "fast": {"tension": fast_tension,
                 "compression": fast_compression},
        "slow_10x": {"tension": slow_tension,
                     "compression": slow_compression},
        "convergence": {
            "tension": convergence(fast_tension, slow_tension),
            "compression": convergence(fast_compression, slow_compression),
        },
    }
    regressions_pass = (
        fast_tension["checks"]["vf0_matches_pre_stage7_max_rel_error_lt_1e-8"]
        and fast_compression["checks"]
        ["vf0_matches_pre_stage7_max_rel_error_lt_1e-8"])
    report["pass"] = (regressions_pass and slow_tension["pass"] and
                      slow_compression["pass"])
    report["acceptance_basis"] = (
        "exact fast Vf0 regressions plus all checks at 10x slower rate")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
