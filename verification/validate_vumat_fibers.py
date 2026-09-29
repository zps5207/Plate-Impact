"""Independent, local material-point oracle for VUMAT_truss.for and
VUMAT_beam.for (vumat/).

This is deliberately not an Abaqus substitute -- it mirrors each Fortran
source line-for-line at the constitutive-update level and checks that
behavior against the requested truss/beam requirements (goal set
2026-09-29). It cannot check anything Abaqus itself decides: element
support for VUMAT, the real strainInc component layout at a beam section
point, or whether the RESSTIFF regularization actually satisfies Abaqus's
pre-increment-1 stiffness probe (BUG-016). Those require a real Abaqus run;
see docs/BUGS.md and the accompanying progress report for what remains
unverified.

Run from the repository root:
    python verification/validate_vumat_fibers.py
Use --strict to return nonzero when any requested behavior fails.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

E = 100.0e9
G = 50.0e9
FAILURE_STRESS = 2.0e9
RESSTIFF = 1.0e-4


def truss_update(strain_inc, stress_old, state_old, total_time):
    """Transcription of vumat/VUMAT_truss.for."""
    stress_new = list(stress_old)
    state_new = state_old
    if total_time == 0.0:
        state_new = 1.0
    if state_old == 0.0 and total_time > 0.0:
        stress_new = [0.0 for _ in stress_old]
    else:
        trial = stress_old[0] + E * strain_inc[0]
        if trial <= 0.0:
            s = RESSTIFF * E * strain_inc[0]
            stress_new[0] = s if s <= 0.0 else 0.0
        elif trial >= FAILURE_STRESS:
            stress_new[0] = 0.0
            state_new = 0.0
        else:
            stress_new[0] = trial
        for i in range(1, len(stress_new)):
            stress_new[i] = 0.0
    return stress_new, state_new


def beam_update(strain_inc, stress_old, state_old, total_time):
    """Transcription of vumat/VUMAT_beam.for.

    Component 0 = axial, component 1 (if present) = transverse shear,
    components >= 2 = bending/curvature terms (suppressed both signs).
    This layout is this project's documented ASSUMPTION, not a confirmed
    Abaqus convention -- see the source file's header comment.
    """
    ncomp = len(stress_old)
    stress_new = list(stress_old)
    state_new = state_old
    if total_time == 0.0:
        state_new = 1.0
    if state_old == 0.0 and total_time > 0.0:
        stress_new = [0.0 for _ in stress_old]
    else:
        trial = stress_old[0] + E * strain_inc[0]
        failed = False
        if trial <= 0.0:
            s = RESSTIFF * E * strain_inc[0]
            stress_new[0] = s if s <= 0.0 else 0.0
        elif trial >= FAILURE_STRESS:
            # Failure detected THIS increment: zero every component right
            # away (matches vumat/VUMAT_beam.for) so a just-broken fiber
            # does not carry a leftover increment of shear.
            stress_new = [0.0 for _ in stress_old]
            state_new = 0.0
            failed = True
        else:
            stress_new[0] = trial
        if not failed:
            if ncomp >= 2:
                stress_new[1] = stress_old[1] + G * strain_inc[1]
            for i in range(2, ncomp):
                stress_new[i] = RESSTIFF * E * strain_inc[i]
    return stress_new, state_new


def close(a, b, rel=1.0e-9):
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": detail}


def run_truss_checks():
    results = []
    s, st = truss_update([0.005], [0.0], 1.0, 1.0)
    results.append(check("truss_tension_is_elastic_100GPa", close(s[0], E * 0.005) and st == 1.0,
                          f"stress={s[0]:.9g} Pa; expected={E * 0.005:.9g} Pa"))

    s, st = truss_update([-0.001], [0.0], 1.0, 1.0)
    residual = abs(RESSTIFF * E * -0.001)
    results.append(check("truss_compression_is_near_zero_not_zero", 0.0 < abs(s[0]) <= residual + 1e-9 and st == 1.0,
                          f"stress={s[0]:.9g} Pa (residual regularization, magnitude<={residual:.3g} Pa); "
                          "note: this is RESSTIFF, not exact zero -- see VUMAT_truss.for header"))

    s, st = truss_update([FAILURE_STRESS / E], [0.0], 1.0, 1.0)
    results.append(check("truss_failure_deletes_at_threshold", s[0] == 0.0 and st == 0.0,
                          f"stress={s[0]:.9g} Pa; state={st}; threshold={FAILURE_STRESS:.9g} Pa"))

    s, st = truss_update([0.001], [0.0], 0.0, 1.0)
    results.append(check("truss_deleted_point_remains_zero", s[0] == 0.0 and st == 0.0,
                          f"stress={s[0]:.9g} Pa; state={st}"))

    s, st = truss_update([0.001, 0.01], [0.0, 5.0e6], 1.0, 1.0)
    results.append(check("truss_shear_always_discarded", s[1] == 0.0,
                          f"component 2 stress={s[1]:.9g} Pa (any pre-existing shear or shear strain "
                          "must be discarded for a tension-only truss)"))
    return results


def run_beam_checks():
    results = []
    s, st = beam_update([0.005, 0.0], [0.0, 0.0], 1.0, 1.0)
    results.append(check("beam_tension_is_elastic_100GPa", close(s[0], E * 0.005) and st == 1.0,
                          f"stress={s[0]:.9g} Pa; expected={E * 0.005:.9g} Pa"))

    gamma = 0.002
    s, st = beam_update([0.0, gamma], [0.0, 0.0], 1.0, 1.0)
    results.append(check("beam_shear_is_50GPa_times_gamma", close(s[1], G * gamma),
                          f"component 2 stress={s[1]:.9g} Pa; expected G*gamma={G * gamma:.9g} Pa"))

    s, st = beam_update([-0.001, 0.0], [0.0, 0.0], 1.0, 1.0)
    residual = abs(RESSTIFF * E * -0.001)
    results.append(check("beam_compression_is_near_zero_not_zero", 0.0 < abs(s[0]) <= residual + 1e-9,
                          f"component 1 stress={s[0]:.9g} Pa (residual regularization, magnitude<={residual:.3g} Pa)"))

    s, st = beam_update([0.0, 0.0, 0.05], [0.0, 0.0, 123.0e6], 1.0, 1.0)
    residual = abs(RESSTIFF * E * 0.05)
    results.append(check("beam_bending_component_suppressed_ignores_history", abs(s[2]) <= residual + 1e-9,
                          f"component 3 stress={s[2]:.9g} Pa despite a pre-existing 123e6 Pa 'bending' "
                          f"stress and a nonzero curvature-like strain increment; residual bound={residual:.3g} Pa"))

    s, st = beam_update([0.0, 0.0, -0.05], [0.0, 0.0, -123.0e6], 1.0, 1.0)
    results.append(check("beam_bending_component_suppressed_both_signs", abs(s[2]) <= residual + 1e-9,
                          f"component 3 stress={s[2]:.9g} Pa for the opposite-sign case "
                          "(no-bending must not be a one-sided compression-style clamp)"))

    s, st = beam_update([FAILURE_STRESS / E, 0.01], [0.0, 0.0], 1.0, 1.0)
    results.append(check("beam_failure_deletes_shear_too", s[0] == 0.0 and s[1] == 0.0 and st == 0.0,
                          f"stress={s}; state={st}"))

    s, st = beam_update([0.001, 0.0], [0.0, 0.0], 0.0, 1.0)
    results.append(check("beam_deleted_point_remains_zero", s[0] == 0.0 and s[1] == 0.0 and st == 0.0,
                          f"stress={s}; state={st}"))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--report", type=Path,
                         default=Path(__file__).resolve().parent / "evidence" / "vumat_fibers_local_validation.json")
    args = parser.parse_args()

    truss_results = run_truss_checks()
    beam_results = run_beam_checks()

    report = {
        "sources": ["vumat/VUMAT_truss.for", "vumat/VUMAT_beam.for"],
        "parameters_pa": {"E_tension": E, "G_shear": G, "failure_stress": FAILURE_STRESS, "res_stiffness_fraction": RESSTIFF},
        "scope": "local material-point transcription; NOT an Abaqus execution -- see report for what this cannot check",
        "truss_results": truss_results,
        "beam_results": beam_results,
        "all_requested_behaviors_pass": all(r["passed"] for r in truss_results + beam_results),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for label, results in (("truss", truss_results), ("beam", beam_results)):
        for r in results:
            print(("PASS" if r["passed"] else "FAIL"), f"[{label}]", r["name"], "-", r["detail"])
    print("report:", args.report)
    return 0 if not args.strict or report["all_requested_behaviors_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
