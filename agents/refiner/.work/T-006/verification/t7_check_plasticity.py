"""Stage 1 pass/fail check: compare uel/VUEL_failure.for's J2 linear-hardening
return mapping (run via verification/make_t7_plasticity.py's T7 decks) against
the analytic 1-D elastic/linear-hardening bar response.

Usage (after pulling each job's .odb to a local/ROAR path reachable by
`abaqus python`):
    abaqus python verification/t7_check_plasticity.py run_t7_tension_plastic/t7_tension_plastic.odb
    abaqus python verification/t7_check_plasticity.py run_t7_compression_plastic/t7_compression_plastic.odb
    abaqus python verification/t7_check_plasticity.py run_t7_tension_unload/t7_tension_unload.odb
    abaqus python verification/t7_check_plasticity.py run_t7_elastic_control/t7_elastic_control.odb

Must be run with `abaqus python` (odbAccess is only importable there), on
ROAR where the .odb files live -- this script has no other dependency.

Analytic model (uniaxial stress, J2 + linear isotropic hardening -- see
docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md for why this is the right
comparison for this element/BC combination):
    eps_y = SIGY0 / EMOD
    Et = EMOD*HMOD / (EMOD+HMOD)           (standard 1-D tangent modulus)
    loading, |eps| <= eps_y:  sigma = EMOD*eps
    loading, |eps| >  eps_y:  sigma = sign(eps)*(SIGY0 + Et*(|eps|-eps_y))
    unloading from (eps_max, sigma_max): sigma = sigma_max - EMOD*(eps_max-eps)
    permanent (plastic) strain after full unload: eps_p = eps_max - sigma_max/EMOD

Evidence channel: *Element Output/SVARS is NOT available for a *User
Element in Abaqus/Explicit (confirmed in docs/abaqus-explicit-quirks.md),
so there is no direct field-output path to this UEL's own PK2 stress.
Instead: node 2 (on the DRIVEN face) gives the imposed U1 = eps_eng
directly (unit reference length along x, uniform affine deformation --
confirmed for this exact BC pattern in verification/roar/t6/'s compression
test). The TOTAL axial reaction force equals the PK2 axial stress S11 in
magnitude for this unit-cross-section cube by definition of nominal/PK2
stress (force per REFERENCE area, independent of current deformation) --
but that total is the SUM of RF1 over ALL FOUR x-pinned back-face nodes
(1, 4, 5, 8; the uniaxial-stress BC pattern pins every one of them in x --
see verification/make_t7_plasticity.py), not just node 1 alone, which by
symmetry carries only about 1/4 of it (caught empirically: an earlier
version of this script that read only node 1 found FEM stress at a
roughly-constant ~0.26x of the analytic elastic value even on the
IPLAST=0 pure-elastic control deck, which should match exactly -- the
~1/4 ratio pointed straight at the missing three nodes). B1_BULK/B2_BULK
are 0 for every T7 deck so no extra bulk-viscosity stress contaminates
this reading, and BETA_RAYLEIGH=0 removes the other damping contribution
too; the SMOOTH STEP amplitude (zero velocity/acceleration at its
endpoints) keeps the dynamic (explicit) response close to quasi-static,
but some small-amplitude oscillation around the analytic envelope is
still expected and is reported, not hidden, below.
"""
import sys
import json

try:
    from odbAccess import openOdb
except ImportError:
    sys.stderr.write("This script must be run with `abaqus python`, not a "
                      "plain Python interpreter (odbAccess is unavailable).\n")
    raise

EMOD = 2.0e11
SIGY0 = 2.5e8
HMOD = 2.0e9
EPS_Y = SIGY0 / EMOD
ET = EMOD * HMOD / (EMOD + HMOD)


PINNED_BACK_NODES = (1, 4, 5, 8)


def analytic_loading(eps, iplast):
    a = abs(eps)
    s = 1.0 if eps >= 0 else -1.0
    if (not iplast) or a <= EPS_Y:
        return EMOD * eps
    return s * (SIGY0 + ET * (a - EPS_Y))


def main():
    odb_path = sys.argv[1]
    iplast = 0 if "elastic_control" in odb_path else 1
    odb = openOdb(odb_path)
    step = odb.steps[odb.steps.keys()[0]]
    frames = step.frames
    rows = []
    for fr in frames:
        u = fr.fieldOutputs['U']
        rf = fr.fieldOutputs['RF']
        u1 = None
        rf1_sum = 0.0
        rf1_seen = 0
        for v in u.values:
            if v.nodeLabel == 2:
                u1 = float(v.data[0])
        for v in rf.values:
            if v.nodeLabel in PINNED_BACK_NODES:
                rf1_sum += float(v.data[0])
                rf1_seen += 1
        eps_eng = u1  # unit reference length along x
        # Total RF1 over all four x-pinned back-face nodes balances the
        # internal axial force; sign convention: a positive (tensile)
        # internal S11 pulls the back face toward +x, so the reaction
        # opposing it is negative -- hence the sign flip to report S11
        # with the physical sign (tension positive).
        sigma_fem = -rf1_sum if rf1_seen == len(PINNED_BACK_NODES) else None
        rows.append({"t": float(fr.frameValue), "eps_eng": eps_eng,
                     "sigma_fem_Pa": sigma_fem})
    odb.close()

    # Running max |eps| for the unloading-leg analytic branch
    eps_max = 0.0
    sigma_at_max = 0.0
    out = []
    for r in rows:
        eps = r["eps_eng"]
        if abs(eps) >= abs(eps_max) - 1e-12:
            # still on (or past) the loading envelope
            sigma_analytic = analytic_loading(eps, iplast)
            if abs(eps) > abs(eps_max):
                eps_max = eps
                sigma_at_max = sigma_analytic
        else:
            # unloading leg: elastic slope back from the envelope point
            sigma_analytic = sigma_at_max - EMOD * (eps_max - eps)
        err = None
        if r["sigma_fem_Pa"] is not None and abs(sigma_analytic) > 1.0:
            err = (r["sigma_fem_Pa"] - sigma_analytic) / sigma_analytic
        out.append({"t": r["t"], "eps_eng": eps,
                    "sigma_fem_Pa": r["sigma_fem_Pa"],
                    "sigma_analytic_Pa": sigma_analytic,
                    "rel_err": err})

    eps_p_final_analytic = eps_max - sigma_at_max / EMOD
    print(json.dumps({
        "odb": odb_path,
        "eps_y": EPS_Y,
        "Et_Pa": ET,
        "eps_p_final_analytic": eps_p_final_analytic,
        "history": out,
    }, indent=2))


if __name__ == "__main__":
    main()
