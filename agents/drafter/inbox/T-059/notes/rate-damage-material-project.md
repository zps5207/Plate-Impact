---
name: rate-damage-material-project
description: "Stage 8 brief for Valerie's work - rate-dependent plastic + energy damage material in VUEL (matrix) and VUMAT (fiber); decisions fixed 2026-10-19, tasks T-041/T-042"
metadata:
  node_type: memory
  type: project
  originSessionId: e2e76f4d-5787-4d32-ade3-4d40809536ca
  modified: 2026-10-19T20:07:33.417Z
---

Brief (2026-10-19): matrix J2 + energy ductile damage in the hex VUEL; fiber uniaxial rate-dependent yield/fracture + energy damage. Spec: docs/RATE_DAMAGE_MATERIAL_SPEC.md.

User decisions: SI units; fiber fracture strains = equivalent PLASTIC strain; fiber tension-only; code in Plate-Impact on branch vuel-plastic-failure; rate interpolation linear in log10(rate), clamped. Default rate measure = plastic strain rate (matches native), switch for total.

Split: matrix -> new uel/VUEL_material.for (T-042); fiber -> new vumat/VUMAT_fiber_rd.for since fibers are native truss elements (T-041). Both drafted by agy (Codex usage-constrained, see [[agent-delegation-preference]]); Hub runs ROAR verification vs native Abaqus twin decks, then combined and cantilever.

**Why:** Valerie's FLagSHyP models are the target.
**How to apply:** Related to [[vuel-plastic-failure-project]].

**Status 2026-10-19 (matrix, T-042):** brief's epsf=0.1 kept authoritative (Vals.inp has 0.01 - deliberately not used). First-pass run exposed: PK2-based J2 gave wrong true yield; elastic energy release not booked in ALLDMD; 1 m cube/1000 /s inertia-dominated; agy's check script vacuous-PASS and crashes on real ODBs.
Fixes applied in uel/VUEL_material.for: HENCKY_RETURN (Hencky elasticity, log-strain J2 return on Kirchhoff stress vs SIGY*J, state = Cp^-1 - I in the 6 plastic slots, python port verification/hencky_reference.py); ALLDMD += psi*dD, ALLPD carries (1-D), Gf/L term dropped; dtimeStable /sqrt(3) for the Stage 8 path (lumped brick volumetric mode is up to sqrt3 faster than the 1D bar estimate; caused 1000 /s tension blow-up; legacy path untouched - likely marginal in older stages too).
Suite now 1 mm cube (SIZE in make_matrix_material_cases.py), per-rate sbatch (arg = tag, optional 2nd arg abaqus options). ROAR: 0.01 /s needs `double=both` (Explicit single precision caps 20M increments). Scratch dirs mm_t042 (first pass), mm_t042c (current). Analysis: dump_matrix_curves.py (on ROAR) + analyze_matrix_material.py (local, PASS/FAIL). Result: 1000 /s and 1 /s all 9 PASS vs native (peaks within 0.2%, dissipation within ~4%, balance <0.1%); VUEL softening tail slightly slower than native. 0.01 /s (job 56567680) pending. Next: fiber VUMAT (T-041, paused by user), combined + cantilever.
ROAR batch tip: one ssh with remote loop = one Duo push.

**Update (later 2026-10-19):** found + fixed the last mismatch: ELVOL_EFF was accumulated inside the GP loop so GP k used k/8 of the volume for L (slow softening tail, +5% ALLPD). Now ELVOL_REF pre-pass. All 6 cases at 1000 and 1 /s PASS vs native (stress <1%, dissipation <0.4%, balance <0.1%). Report: docs/MATRIX_MATERIAL_DEVELOPMENT_REPORT.md; result folders under verification/roar/matrix_material/{iter0..,final_gp_length_fix}. Job 56567680 (0.01 /s, double) runs the PRE-fix Fortran - results invalid, not cancelled (user hasn't said). Vals.inp has matrix epsf 0.01 vs brief 0.1 - brief kept authoritative, flagged in report. Nothing committed yet. Next: cantilever.

**Update 2026-10-19 (later):** Stage 8 matrix committed (c8879ce). Mesher now has `--matrix-model {legacy,ductile-damage}`
(+ `--matrix-rate-mode`, `--matrix-gf`) and a GUI "Property type" dropdown (vuel-ghost only); embmesh/vuelghost.py reads
rate tables/Gf from the host Matrix card, emits 39 props/159 svars, ghost deletes at eps_f + 2Gf/(sigy L_mean) with
DISPLACEMENT 0 evolution. Vals plate decks (20 plies, d=0.632 mm, cross-ply, user cohesive numbers K=60/36 N/mm^3 literal)
built by verification/roar/build_vals_plywise.py -> Meshing/vals-plywise/{native,vuel}/output.inp. NOT yet submitted/datachecked
on ROAR; needs user=VUEL_material.for. Mesher changes not yet committed.
