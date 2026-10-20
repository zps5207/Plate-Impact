# Rate-dependent elastic-plastic + damage material model (Stage 8 spec)

Status: decisions fixed by the user 2026-10-19. Branch `vuel-plastic-failure`, Plate-Impact repo. Valerie's FLagSHyP code is read-only reference.

## Decisions (answers to the brief's open questions)
1. Units: SI throughout (m, kg, s, Pa, J). Decks, props and tests all use SI.
2. Fiber fracture strains are EQUIVALENT PLASTIC STRAIN at damage onset (same meaning as Abaqus Ductile Damage), not total strain.
3. Fiber is TENSION-ONLY: compressive axial stress is zero (no residual stiffness beyond a documented tiny RESSTIFF, same as `vumat/VUMAT_tension_only.for`). Deviates from native Abaqus; native comparison is therefore done in tension, and compression is checked separately (stress must be ~0).
4. Code lives in Plate-Impact, branch `vuel-plastic-failure`. New files only; do not modify `uel/VUEL.for`, `uel/VUEL_failure.for` or existing VUMATs in place (copy then modify).
5. Rate interpolation: linear in log10(rate) between table points, clamped to the first/last value outside the range. Rate floor for log: 1e-12 /s (rate <= table min -> first value).

## Architecture
- Matrix (hex VUEL host): new `uel/VUEL_material.for`, a copy of `VUEL_failure.for` with a new material core (J2, no hardening, energy-based ductile damage). The existing failure-latch/Jacobian/ghost machinery, volume-fraction correction (svars 107) and dead-element sentinel are kept.
- Fiber (truss/beam elements embedded in the host): new `vumat/VUMAT_fiber_rd.for`, a VUMAT (fibers are native elements, not user elements). Uniaxial, tension-only, rate-dependent yield, rate-dependent damage onset, energy-based softening.

## Shared constitutive rules
- Elastic: isotropic Hooke (matrix, small-strain-consistent in the VUEL's Green-Lagrange/PK2 form as already used); uniaxial E*strain (fiber).
- Rate measure (props switch RATE_MODE): 0 (default) = equivalent PLASTIC strain rate dEpeq/dt over the increment, as native Abaqus does (rate 0 before yielding -> first table value). 1 = total equivalent strain rate (fiber: |d eps_axial / dt|; matrix: sqrt(2/3 d_dev:d_dev)). Report which was used; default 0 so the native comparison is fair.
- Yield stress sigma_y(rate), fracture strain epsf(rate): log10-linear tables as above. No hardening: sigma_y does not depend on plastic strain.
- Damage onset: when Epeq >= epsf(rate at that increment) (single triaxiality point 1/3, so no triaxiality dependence is implemented; document that triaxiality is ignored). Record the yield stress at onset sigma_y0 and the rate at onset; they are frozen for the softening phase.
- Damage evolution (Abaqus "energy, linear" form): plastic displacement ubar = L * (Epeq - Epeq_onset), L = characteristic length. Failure displacement ubar_f = 2 Gf / sigma_y0. D = ubar / ubar_f clamped to [0,1], monotonic (never decreases). Stress = (1-D) * sigma_undamaged. At D = 1 contribution is zero.
  - Matrix: L = (element volume)^(1/3) (use the volume-correction-consistent element volume).
  - Fiber: L = charLength given to the VUMAT (segment length).
  - Matrix Gf = 1460 J/m^2, fiber Gf = 1 J/m^2.
- Energy: plastic dissipation accumulated in the plastic-energy slot (enerInelas / ELPD), damage dissipation tracked in the same bucket or in a separate documented slot; internal energy uses the damaged elastic energy. State which. Total (plastic + damage) dissipation of a fully softened point under monotonic loading must be close to Gf/L per unit volume plus the plastic work before onset.
- Material tables go in via props, never hardcoded. Table sizes via props/jprops with maximum NMAXTAB (document it).

## Properties
Matrix: E 700e6, nu 0.45, rho 980, sigma_y 70e6 (single point, any rate), epsf 0.1 at 0.01 /s (brief is authoritative; Meshing/Vals.inp has 0.01, deliberately not used) /s, Gf 1460.
Fiber: E 135e9, nu 0.45, rho 981, rate / sigma_y: 0.01/3.5e9, 1/4.3e9, 1000/4.5e9; rate / epsf: 0.01/0.0391, 1/0.0251, 1000/0.01167; Gf 1.

## Deliverables per task
Fortran source with comments, a props/svars layout doc, a plain-Python reference implementation of the same update (so Fortran can be checked without Abaqus), single-element test deck generators (SI), and a native-Abaqus twin deck for each comparison case. The Hub runs everything on ROAR and runs the datacheck.

## Verification (single element first)
Uniaxial tension, compression, shear at 0.01, 1, 1000 /s. Matrix vs native (Plastic + Ductile Damage energy evolution): stress-strain and dissipated energy within tolerance. Fiber vs native truss in tension (native cannot be tension-only; compare tension and check compression gives zero). Fiber-only, matrix-only, combined. ALLIE/ALLPD/ALLKE balance, no negative Jacobian. Then the cantilever.

## Known/expected deviations to report
- Matrix VUEL is Total Lagrangian St. Venant-Kirchhoff with Green-Lagrange plasticity, native Abaqus is Hughes-Winget/log-strain: differences grow at large strain.
- Native rate dependence is linear-in-rate tabular; ours is log10-linear (matches only at table nodes).
- Tension-only fiber.
- Native element deletion and SPH conversion are not available to the VUEL (see VUEL failure-criterion finding); D = 1 zeroes the force and uses the existing dead-element path.
