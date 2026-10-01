# Stage 0 plan: elastic-plastic VUEL with homegrown failure

Branch: `vuel-plastic-failure`. Working file:
`uel/VUEL_failure.for` (already a branch of `uel/VUEL.for`; production file
stays untouched throughout). This plan is written *before* any plasticity
code is added, per the goal's Stage 0 instruction to inspect the existing
formulation first and surface anything that could change results.

## 1. What the existing formulation gives us (read in full: `uel/VUEL.for`
   / current `uel/VUEL_failure.for`, lines ~95-250, ~765-975)

- **Total Lagrangian, St. Venant-Kirchhoff elastic**: `S = C : E`, `E` =
  Green-Lagrange strain from `F = I + du/dX` (reference-config shape
  derivatives throughout — `SHAPE8H_TL` never updates with deformation).
  Both `S` (PK2 stress) and `E` are materially-frame (Lagrangian) tensors:
  **both are invariant under a superposed rigid-body rotation by
  construction**, unlike a Cauchy-stress/rate-form (hypoelastic) model,
  which needs a corotational or Jaumann rate to stay objective. This
  matters directly for the plasticity choice below.
- **Voigt convention is mixed, and matters for getting J2 right**:
  `STRAIN_VEC(4:6)` are **engineering** shear (`2*E12` etc. —
  `COMPUTE_GREEN_LAGRANGE` line ~884 says so explicitly), but
  `STRESS_VEC`/`STRESS_PK2(4:6)` are **true** tensor shear stress
  (`S12` etc., not doubled) — confirmed by `CMAT(4,4)=mu` applied directly
  to the doubled strain, giving `S12 = mu*(2*E12) = 2*mu*E12`, the correct
  tensorial relation. The existing `ELIE` energy sum
  (`0.5*STRESS_PK2(I)*STRAIN_VEC(I)`, no extra factor) is only correct
  *because* of this specific mixed convention — any new energy/invariant
  calculation I add must use the same trick (sum over i=1..6 of
  `true_stress_i * engineering_strain_i`) rather than inventing a
  different one.
- **Internal force assembly (`BL_MAT`, Step 10) only depends on
  `DEFGRAD`/shape derivatives and the stress vector it's handed** — it does
  not care how that stress vector was computed. So a plasticity model that
  produces a `STRESS_TOTAL`-shaped 6-vector in the same convention slots in
  with zero changes to `BL_MAT`, `FINT` assembly, bulk viscosity, Rayleigh
  damping, mass, or stable-`dt` logic.
- **Energy array slots**: the file already names
  `iElPd=1, iElCd=2, iElIe=3, iElTs=4, iElDd=5, iElBv=6, iElDe=7, iElHe=8,
  iElKe=9, iElTh=10, iElDmd=11, iElDc=12` but only ever writes `iElIe`,
  `iElDd`, `iElKe`, `iElBv`. These names match Abaqus's documented VUEL
  energy-array ordering, and **`iElPd` is specifically "plastic
  dissipation"** (folds into `ALLPD`/`ETOTAL` automatically) — unused so
  far, exactly what plastic dissipation should be routed into.

## 2. Plasticity formulation chosen: additive Green-Lagrange/PK2 J2 with
   linear isotropic hardening, closed-form radial return

Decompose the Green-Lagrange strain **additively**: `E = Ee + Ep`, with the
**same elastic law and the same `CMAT` already in the file**:
`S = C : Ee`. Von Mises yield (`sigma_eq <= sigma_y0 + H*PEEQ`) and
associative flow are applied directly to this `(S, E)` pair, exactly the
way a small-strain return-mapping algorithm would, just with `E`
(Green-Lagrange) standing in for infinitesimal strain and `S` (PK2) for
Cauchy stress.

**Why this is the "simplest update consistent with the existing
formulation"**, not a compromise:
- It reuses the existing `CMAT`, `BL_MAT`, stress-storage, and energy
  machinery completely unchanged — only the "compute `STRESS_PK2` from
  `STRAIN_VEC`" step gets an elastic-predictor/plastic-corrector split
  instead of a single matrix multiply.
- It is **exactly as objective as the existing elastic model** under
  superposed rigid rotation, because the whole calculation stays in the
  Lagrangian `(S, E)` pair — no Jaumann/corotational correction is needed
  (that need is specific to rate-form hypoelastic-plastic models, which
  this is not).
- Linear hardening + J2 give a **closed-form** return (no local Newton
  iteration): `Δγ = (sigma_trial - sigma_y_old)/(3*mu + H)`. This is
  standard, textbook (Simo & Hughes-style small-strain radial return,
  just applied in `E`/`S` instead of `ε`/`σ`), and gives an exact analytic
  target to check Stage 1 against.
- Plastic dissipation is exactly `0.5*(sigma_y_old+sigma_y_new)*Δγ` per
  unit reference volume for *linear* hardening (the trapezoidal rule is
  exact here, not an approximation, because `sigma_y` is linear in `PEEQ`)
  — goes into `energy(KBLOCK,iElPd)`.

**What this is *not*, stated plainly (the limitation to document in the
file header)**: this is **not** a modern multiplicative `F = Fe·Fp`
finite-strain plasticity model. It decomposes *strain* additively rather
than the *deformation gradient* multiplicatively, so at very large
stretches (well beyond the moderate deformations this project's plate-impact
use case is centered on) it will diverge from a rigorous large-strain
model — e.g. it does not exactly preserve isochoric (volume-preserving)
plastic flow under large volumetric distortion the way an `Fe·Fp` model
does by construction. For the regime this project cares about (host
elements straining before they fail/collapse, not elements already deep
into post-failure crush), it is the right level of complexity: consistent
with the existing St. Venant-Kirchhoff elastic law (which has the same
moderate-strain-accuracy caveat already, undocumented in the current file
header — I'll note that too), easy to verify analytically, and reuses
100% of the existing architecture.

### Algorithm per Gauss point per force-call (only while the element is not
already failed)

State added to `svars` per Gauss point: plastic Green-Lagrange strain
tensor `Ep` (6 components, **same engineering-shear-Voigt convention as
`STRAIN_VEC`**, so it can be subtracted from it directly) + accumulated
equivalent plastic strain `PEEQ` (1 scalar) = 7 values/GP x 8 GP = 56,
plus the existing 48 (stress) + 1 (failure flag, keeping its slot at
`svars(49)` for compatibility with the `t6` decks and
`VUEL_FAILURE_CRITERION_REPORT_2026-10-01.md`) = **nsvars = 105**.

1. `Ee_trial_VEC = STRAIN_VEC - EP_VEC_old` (direct Voigt subtraction, both
   engineering convention).
2. `S_trial_VEC = CMAT * Ee_trial_VEC` (exactly today's elastic step).
3. Hydrostatic `P = (S_trial(1)+S_trial(2)+S_trial(3))/3`;
   deviatoric `SDEV(1:3) = S_trial(1:3) - P`, `SDEV(4:6) = S_trial(4:6)`
   (shear is already deviatoric; these are *true* stress components).
4. `sigma_trial = sqrt(1.5 * (SDEV(1)^2+SDEV(2)^2+SDEV(3)^2
   + 2*(SDEV(4)^2+SDEV(5)^2+SDEV(6)^2)))` (the `2*` on shear terms is
   required for a true-tensor double contraction — easy to get wrong,
   calling it out explicitly).
5. `sigma_y_old = SIGY0 + HMOD*PEEQ_old`. If `sigma_trial <= sigma_y_old`:
   elastic step, `S = S_trial`, `Ep`/`PEEQ` unchanged (matches today's
   code exactly when `sigma_trial` never exceeds yield, e.g. `IPLAST=0`
   or `SIGY0` huge).
6. Else (plastic step): `Δγ = (sigma_trial - sigma_y_old)/(3*mu + HMOD)`;
   `sigma_y_new = sigma_y_old + HMOD*Δγ`;
   `FACTOR = 1.5*Δγ/sigma_trial`;
   `ΔEp_VEC(1:3) = FACTOR*SDEV(1:3)`, `ΔEp_VEC(4:6) = 2*FACTOR*SDEV(4:6)`
   (the extra `2` converts true-tensor shear back to the engineering-Voigt
   convention `EP_VEC` is stored in — mirrors the existing `STRAIN_VEC`
   convention exactly);
   `S_VEC = S_trial_VEC - CMAT * ΔEp_VEC` (reuses `CMAT` again — this
   automatically leaves the hydrostatic part untouched since `ΔEp` is
   traceless, no special-casing needed);
   `EP_VEC_new = EP_VEC_old + ΔEp_VEC`; `PEEQ_new = PEEQ_old + Δγ`.
7. Energy: `ELIE += 0.5*sum_i(S_VEC(i)*Ee_new_VEC(i))*DVOL` (elastic part
   only, `Ee_new = STRAIN_VEC - EP_VEC_new`); plastic dissipation
   `energy(KBLOCK,iElPd) += 0.5*(sigma_y_old+sigma_y_new)*Δγ*DVOL` (zero
   when step was elastic).
8. Rayleigh viscous stress and bulk viscosity are computed exactly as
   today, from the *total* strain rate, and added on top of `S_VEC` —
   unaffected by plasticity (pure numerical damping, standard explicit-code
   practice).

Volumetric response stays **purely elastic** (J2 is pressure-independent
by construction — standard, not a simplification specific to this branch).

### Props / interface change (flagging per the "ask when it changes the
interface" rule — see question below)

- `props(7)` stays `EPS_FAIL` (unchanged from the current failure-only
  branch).
- New: `props(8) = SIGY0` (initial yield stress, Pa), `props(9) = HMOD`
  (linear isotropic hardening modulus, Pa), `props(10) = IPLAST` (0 =
  exactly today's pure-elastic path — old `t6` decks keep working
  unmodified by just not setting `props(8:10)`/defaulting `IPLAST=0` via
  `nprops=7` back-compatibility, 1 = elastic-plastic path, new `nprops=10`
  decks).
- `nsvars`: 49 -> 105 (layout above). Every deck generator
  (`verification/make_t6_failure.py` and any new Stage 1+ generator) needs
  the matching `*User Element ..., properties=10, variables=105` and
  `*UEL Property` line.

## 3. Jacobian trigger (Stage 3 preview, not implemented yet)

`detJ0` (reference-configuration Jacobian from `SHAPE8H_TL`) is constant
per Gauss point for a given element (undeformed geometry never changes) —
the trigger needs the **current-configuration** Jacobian instead, i.e.
`det(F) = DETF` already computed every call by `COMPUTE_DEFGRAD`. Trigger:
`min over 8 GPs of DETF_gp <= JAC_FAIL` (prop, default 0.05, explicitly a
tunable starting point per the goal, not a validated number), with
`DETF <= 0` treated as an immediate trip. Every division (`1/sigma_trial`
in step 6 above, `1/DETJ0` in `SHAPE8H_TL`, any future log/sqrt) needs a
guard so a collapsing element can't NaN before the latch catches it —
noted now so Stage 1's new divisions (`sigma_trial` in the denominator)
are written defensively from the start rather than retrofitted in Stage 3.

## 4. Open questions / decisions that could change results — asking before
   writing code, per the goal's Stage 0 instruction

See the accompanying question. Everything else above (closed-form radial
return, energy routing, Voigt conventions, svars layout) is either forced
by consistency with the existing file or standard/textbook, so I'm not
re-asking those — flagging them here for the record instead.
