# Matrix material model for the hex user element: development and verification report

Date: 2026-10-19. Branch `vuel-plastic-failure`, Plate-Impact repo. Abaqus 2024 (Explicit), ROAR cluster.
Source: `uel/VUEL_material.for`. Layout reference: `docs/MATRIX_MATERIAL_PROPS_SVARS.md`. Spec and decisions: `docs/RATE_DAMAGE_MATERIAL_SPEC.md`.

## 1. Purpose

Valerie's work needs the matrix of the embedded-fiber plate model to be elastic-plastic with ductile damage, inside the hex VUEL (the user element that hosts the embedded fibers). Native Abaqus material cards cannot be used for a user element, so the constitutive law had to be written in the VUEL and then checked against native Abaqus (`C3D8R` with `*Plastic` and `*Damage Initiation/Evolution`) so that the two agree.

Matrix target (SI units): E = 700 MPa, nu = 0.45, rho = 980 kg/m^3; J2 plasticity, yield 70 MPa, no hardening; ductile damage onset at equivalent plastic strain 0.1 at 0.01 /s (triaxiality 1/3, single point); energy-based damage evolution, Gf = 1460 J/m^2.

The fiber model (uniaxial, rate-dependent, tension-only, Gf = 1 J/m^2) is a separate VUMAT and is **not** part of this report; it is paused (task T-041).

## 2. Decisions

| Question | Decision |
|---|---|
| Unit system | SI (m, kg, s, Pa, J) |
| Fiber fracture strain meaning | equivalent plastic strain (fiber work, paused) |
| Fiber tension-only | yes (fiber work, paused) |
| Where the code lives | Plate-Impact repo, branch `vuel-plastic-failure`, new files only |
| Rate interpolation | linear in log10(rate), clamped outside the table, 1e-12 /s floor |
| Rate measure | equivalent plastic strain rate by default (what native Abaqus uses), switch for total strain rate |
| Matrix damage-onset strain | **0.1, per the brief** |

Discrepancy to flag: `Meshing/Vals.inp` (Valerie's deck) has the matrix `*Damage Initiation, criterion=DUCTILE` fracture strain as **0.01**, not 0.1. The brief was kept authoritative and the tests use 0.1, so the verification does not yet confirm the value Valerie's deck would use. The value is one constant in the generator (`EPS_F` in `verification/make_matrix_material_cases.py`) and one in the check script; changing it is trivial. Her fiber block also has damage initiation but no `*Damage Evolution`, unlike the brief's Gf = 1 J/m^2.

## 3. Model

Selected with `props(14) = MAT_MODEL = 1`; `0` keeps the previous behaviour bit-for-bit. 39 properties, 159 state variables (full tables in the layout doc).

1. **Kinematics and stress.** The element stays Total Lagrangian (internal force = integral of `B_L^T S dV0`, full 2x2x2 integration). The constitutive law is multiplicative Hencky elasticity: from `F` and the stored `Cp^-1` form `b_e = F Cp^-1 F^T`, take principal logarithmic strains, Kirchhoff stress `tau = lambda tr(eps) I + 2 mu eps`, then return `S = F^-1 tau F^-T` to the force assembly.
2. **Yield.** J2 on Cauchy stress: `q <= sigma_y J`. Plastic flow is isochoric, so the radial return in principal log space is exact: `dgamma = (q_trial - sigma_y J)/(3 mu)`. `PEEQ` is the logarithmic equivalent plastic strain, the same quantity native Abaqus reports.
3. **Damage onset.** When `PEEQ >= eps_f(rate)`, `sigma_y0` and the rate are frozen.
4. **Evolution (Abaqus "energy, linear" form).** `ubar = L (PEEQ - PEEQ_onset)`, `ubar_f = 2 Gf / sigma_y0`, `D = ubar / ubar_f` clamped to [0,1], monotonic; stress `S = (1-D) S_undamaged`. `L = (eta V0)^(1/3)` with `V0` the full reference element volume and `eta = 1 - Vf` (consistent with the embedded-fiber volume correction).
5. **Element death.** Damage is tracked per Gauss point; when all 8 points reach `D = 1` the element is latched dead (`rhs = 0`, `dtimeStable = 1e30`).
6. **Energy.** Stress power is `(1-D)(dpsi + q dgamma)` and stored energy is `(1-D) psi`, so plastic dissipation `ALLPD` carries a `(1-D)` weight and `ALLDMD` is the elastic energy released by damage, `psi dD` (native's definition). The `Gf/L` term is already inside the weighted plastic dissipation.
7. **Stable increment.** Lumped full-integration brick, volumetric mode: `omega^2 = 12 K / (rho L^2)`, up to sqrt(3) above the 1D-bar estimate. The Stage 8 path therefore uses an extra 1/sqrt(3).

## 4. Method

- Roles: the drafter (agy) wrote the first-pass Fortran, the Python reference, the deck generator and the sbatch (task T-042); the hub (Claude Code) reviewed it, ran everything on ROAR, found and fixed the issues below, and is the only agent that touched the cluster.
- Single-element tests: a cube with edge `SIZE = 1 mm`, tension, compression and simple shear, at 0.01, 1 and 1000 /s (smooth-step loading; mean rate as named). Each VUEL deck has a native twin (one `C3D8R`, same boundary conditions, same step) built from the brief's material card.
- Output: nodal displacement and reaction history, energies `ALLIE, ALLPD, ALLKE, ALLDMD, ALLWK`. `verification/dump_matrix_curves.py` (run with `abaqus python` on ROAR) writes CSV; `verification/analyze_matrix_material.py` compares VUEL and native locally and prints PASS/FAIL.
- Pass criteria: pre-softening engineering stress within 3% of native; energy balance `ALLWK = ALLIE + ALLPD + ALLDMD + ALLKE` within 3%; total dissipation (`ALLPD + ALLDMD`) within 5% of native. (Native `ALLIE` already contains `ALLPD`/`ALLDMD`, so native uses `ALLWK = ALLIE + ALLKE`.)
- Independent check of the return map without Abaqus: `verification/hencky_reference.py` (line-for-line Python port): uniaxial Cauchy stress plateaus at 70.0000 MPa and `PEEQ = ln(lambda) - sigma_y/E`; simple shear gives a Mises stress of 70 MPa.

## 5. What went wrong, and the fixes

The agreement was reached in four iterations. Result folders are kept under `verification/roar/matrix_material/`.

| # | Folder | Finding | Cause | Fix |
|---|---|---|---|---|
| 0 | `iter0_first_pass_pk2_unit_cube` | VUEL and native disagreed badly: tension plateau 77-82 MPa vs 62 MPa, shear 60 vs 40 MPa; damage dissipation 1.9e3 vs 3.5e6 J/m^3; the energy balance missed by a third | (a) J2 applied to the PK2 stress so the effective true yield grew roughly as (1+eps)^2; (b) elastic energy released at damage onset was never booked (native books ~3.5e6 = sigma_y^2/2E in `ALLDMD`); (c) 1 m cube at 1000 /s was inertia-dominated | (a) Hencky / Kirchhoff return (section 3); (b) `ALLDMD = psi dD`; (c) 1 mm cube |
| 1 | `iter1_hencky_tension_unstable_r1000` | Compression and shear now matched native; tension died early (u ~ 0.18 vs native onset 0.22), J alternating 0.90 <-> 1.15 each increment | Stable-increment estimate was the 1D bar value; the brick's volumetric mode is up to sqrt(3) faster (1.6x at nu = 0.45), so the explicit scheme was unstable | extra `1/sqrt(3)` on the Stage 8 `dtimeStable` |
| 2 | `iter2_stable_dt_fix` | All 9 cases at 1000 and 1 /s passed, but the VUEL softening tail was too slow (99% loss at u = 0.32 vs native 0.275) and plastic dissipation was 5% high | `ELVOL_EFF` was accumulated inside the Gauss-point loop, so point k used k/8 of the volume for `L`; the slowest point (k = 1, half the length) sets element death. The mean of `Gf/L` over the 8 points is 1.32x the correct value, which predicts +0.47e6 J/m^3, exactly the observed excess | pre-pass computes the full reference volume (`ELVOL_REF`) |
| 3 | `final_gp_length_fix` | all 6 cases at 1000 and 1 /s PASS (table below) | | |

Other problems found in the supplied drafter deliverable (fixed in the project copies):
- `check_matrix_material.py` reported PASS while comparing nothing (it looked for the ODBs in the wrong folder and treated "no cases" as success), and it crashes on a real ODB (`fieldOutputs.get` does not exist on an Abaqus repository). It now fails when nothing is compared and the CSV workflow replaces it.
- A ROAR limit: Abaqus/Explicit single precision refuses more than 20,000,000 increments. The 0.01 /s step (50 s, ~0.3 us increments, ~1.8e8 increments) needs `double=both`.

## 6. Final agreement (fix 3, tolerance columns in section 4)

Engineering stress on the 1 mm cube; peak stress is the yield plateau (compression: includes the load increase from area change).

| Case | Peak stress VUEL / native (MPa) | Strain at 50% / 99% stress loss, VUEL | same, native | Total dissipation difference | Energy balance residual (VUEL) |
|---|---|---|---|---|---|
| tension 1000 /s | 63.87 / 63.91 | 0.246 / 0.276 | 0.245 / 0.273 | 0.34% | 0.00% |
| tension 1 /s | 63.87 / 63.91 | 0.246 / 0.275 | 0.247 / 0.275 | 0.31% | 0.02% |
| compression 1000 /s | 84.43 / 84.48 | 0.199 / 0.216 | 0.199 / 0.216 | 0.34% | 0.00% |
| compression 1 /s | 84.51 / 84.61 | 0.198 / 0.215 | 0.200 / 0.217 | 0.35% | 0.03% |
| shear 1000 /s | 40.27 / 40.27 | 0.380 / 0.417 | 0.380 / 0.419 | 0.02% | 0.00% |
| shear 1 /s | 40.27 / 40.27 | 0.382 / 0.415 | 0.381 / 0.418 | 0.15% | 0.01% |

Largest pre-softening stress difference: 0.97% (tension), 0.87% (compression), 0.06-0.45% (shear). It always sits at the yield knee (strain 0.094-0.105) where the curve turns sharply and the two codes' output frames fall at slightly different points; it is a sampling effect. Dissipation split, tension 1000 /s: plastic 8.55e6 vs 8.54e6, damage 3.57e6 vs 3.54e6 J/m^3 (theory: 7.0e6 + 1.46e6 plastic, 3.5e6 damage).

Rate independence: the 1000 /s and 1 /s results are the same to the printed precision, as expected for a one-point rate table. The rate path itself (log10 interpolation between several table points) is therefore exercised only by the fiber model and by the Python reference; it is **not** verified against Abaqus for the matrix.

## 7. Known deviations from native Abaqus

- The VUEL element is full-integration (8 Gauss points); native is `C3D8R` (1 point). Homogeneous single-element tests cannot show hourglass or integration differences.
- Native uses the Hughes-Winget / corotational rate form; the VUEL is a hyperelastic-based finite-strain model. They agree here to under 1% in stress for nominal strains up to ~0.3 (tension) but would differ for large rotations combined with plasticity; the combined and cantilever cases will show this.
- Rate dependence is log10-linear between table points; native tabular rate dependence is linear in rate. They match only at table points.
- `ALLIE` is elastic energy only; native `ALLIE` includes `ALLPD` and `ALLDMD`. Compare through the balance, not the raw `ALLIE`.
- Native element deletion and SPH conversion cannot be triggered by a user element (earlier finding); `D = 1` zeroes the force and uses the dead-element path.
- The stable increment for Stage 8 is 1/sqrt(3) smaller than the previous VUEL estimate, so runs take up to 1.7x more increments. The legacy `MAT_MODEL = 0` path is untouched and still uses the old estimate, which looks marginal for nu = 0.45 (not re-examined).

## 8. Not yet verified

- The 0.01 /s set in double precision (job 56567680) is running on the **pre-fix** Fortran (it started before fix 3); its results will not be used. It needs a rerun with `sbatch ... matrix_material.sbatch r0p01 double=both` if wanted. The matrix is rate-independent, so it adds little.
- Matrix with embedded fibers (volume-fraction `eta < 1`), the combined matrix-and-fiber case, and the cantilever case.
- Beyond homogeneous deformation: wave propagation, non-uniform softening, and the interaction of the Gauss-point-wise damage with the all-points death rule.
- The `Vals.inp` value of 0.01 for the matrix fracture strain.

## 9. Files

| File | Role |
|---|---|
| `uel/VUEL_material.for` | the element with the Stage 8 material (`HENCKY_RETURN`, `EIG3_JACOBI`, `INTERP_RATE_TABLE_VUEL`) |
| `docs/MATRIX_MATERIAL_PROPS_SVARS.md` | props / svars layout, equations, energy |
| `docs/RATE_DAMAGE_MATERIAL_SPEC.md` | the agreed spec and decisions |
| `verification/hencky_reference.py` | Python port and unit checks of the return map |
| `verification/matrix_material_reference.py` | drafter's small-strain reference of the full law (superseded as the main check by the Abaqus comparison) |
| `verification/make_matrix_material_cases.py` | generates the 18 decks (VUEL and native twin) and the deck list |
| `verification/roar/matrix_material.sbatch` | one job per rate tag; optional extra Abaqus options (e.g. `double=both`) |
| `verification/dump_matrix_curves.py` | ODB to CSV (run with `abaqus python`) |
| `verification/analyze_matrix_material.py` | VUEL vs native comparison and PASS/FAIL |
| `verification/roar/matrix_material/<iteration folders>` | curves and energies for each iteration |

Reproduce: `python verification/make_matrix_material_cases.py`; copy `verification/roar/matrix_material`, `matrix_material.sbatch` and `dump_matrix_curves.py` to a ROAR scratch directory; `sbatch --job-name=mm_r1000 --time=00:30:00 matrix_material.sbatch r1000` (and `r1`); fetch the `*_curve.csv` / `*_energy.csv` files; `python verification/analyze_matrix_material.py <folder> r1000 r1`.
