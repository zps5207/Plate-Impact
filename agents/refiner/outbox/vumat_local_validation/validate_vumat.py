"""Independent, local material-point checks for VUMAT_tension_only.for.

This is deliberately not an Abaqus substitute.  It mirrors the Fortran source
line-for-line at the constitutive-update level, and then compares that behavior
with the requested truss/beam requirements.  Run from the repository root:

    python agents/refiner/outbox/vumat_local_validation/validate_vumat.py

Use --strict to return nonzero when the current source does not meet all of the
requested requirements.  The JSON report is written beside this script unless
--report is supplied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


E = 100.0e9
G = 50.0e9
FAILURE_STRESS = 2.0e9


def fortran_update(strain_inc, stress_old, state_old, total_time):
    """Direct scalar/vector transcription of VUMAT_tension_only.for.

    ``state_old == 0`` is a deleted point.  The initial call (total_time=0)
    initializes the deletion flag to active, matching the source.
    """
    stress_new = list(stress_old)
    state_new = state_old
    if total_time == 0.0:
        state_new = 1.0
    if state_old == 0.0 and total_time > 0.0:
        stress_new = [0.0 for _ in stress_old]
    else:
        trial = stress_old[0] + E * strain_inc[0]
        if trial <= 0.0:
            stress_new[0] = 0.0
        elif trial >= FAILURE_STRESS:
            stress_new[0] = 0.0
            state_new = 0.0
        else:
            stress_new[0] = trial
        for i in range(1, len(stress_new)):
            if stress_new[i] < 0.0:
                stress_new[i] = 0.0
    return stress_new, state_new


def close(a, b, rel=1.0e-12):
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": detail}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--report", type=Path,
                        default=Path(__file__).with_name("local_vumat_validation.json"))
    args = parser.parse_args()

    results = []
    s, deleted = fortran_update([0.005], [0.0], 1.0, 1.0)
    results.append(check("truss_tension_is_elastic", close(s[0], E * 0.005) and deleted == 1.0,
                         f"stress={s[0]:.9g} Pa; expected={E * 0.005:.9g} Pa"))

    s, deleted = fortran_update([-0.001], [0.0], 1.0, 1.0)
    results.append(check("truss_compression_is_slack", s[0] == 0.0 and deleted == 1.0,
                         f"stress={s[0]:.9g} Pa; expected=0 Pa; state={deleted}"))

    s, deleted = fortran_update([FAILURE_STRESS / E], [0.0], 1.0, 1.0)
    results.append(check("truss_failure_deletes_at_threshold", s[0] == 0.0 and deleted == 0.0,
                         f"stress={s[0]:.9g} Pa; state={deleted}; threshold={FAILURE_STRESS:.9g} Pa"))

    s, deleted = fortran_update([0.001], [0.0], 0.0, 1.0)
    results.append(check("deleted_point_remains_zero", s[0] == 0.0 and deleted == 0.0,
                         f"stress={s[0]:.9g} Pa; state={deleted}"))

    # For a beam material point, component 2 represents a shear component for
    # this requirement.  The source neither reads its strain increment nor
    # applies G; this test exposes that incompatibility without assuming an
    # Abaqus element-output convention.
    gamma = 0.002
    s, deleted = fortran_update([0.0, gamma], [0.0, 0.0], 1.0, 1.0)
    tau_expected = G * gamma
    results.append(check("beam_shear_is_50_GPa_times_gamma", close(s[1], tau_expected),
                         f"source stress_component_2={s[1]:.9g} Pa; requested G*gamma={tau_expected:.9g} Pa"))

    # A positive pre-existing non-axial stress is simply retained by the source,
    # so it cannot enforce the requested no-bending response.
    s, deleted = fortran_update([0.0, 0.0], [0.0, 123.0e6], 1.0, 1.0)
    results.append(check("beam_bending_component_is_suppressed", s[1] == 0.0,
                         f"source retains positive nonaxial stress={s[1]:.9g} Pa"))

    report = {
        "source": "vumat/VUMAT_tension_only.for",
        "parameters_pa": {"E_tension": E, "G_shear": G, "failure_stress": FAILURE_STRESS},
        "scope": "local material-point transcription; not an Abaqus execution",
        "results": results,
        "all_requested_behaviors_pass": all(r["passed"] for r in results),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for r in results:
        print(("PASS" if r["passed"] else "FAIL"), r["name"], "-", r["detail"])
    print("report:", args.report)
    return 0 if not args.strict or report["all_requested_behaviors_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
