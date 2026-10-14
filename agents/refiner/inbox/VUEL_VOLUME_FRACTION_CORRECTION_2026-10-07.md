# VUEL volume-fraction stiffness correction (Stage 7)

Date: 2026-10-07
To: Codex
Context: Gemini brainstormed the mechanism (`agents/gemini/outbox/T-002/BRAINSTORM.md`),
the human has approved the two open physics decisions:
- correction factor **eta(Vf) = 1 - Vf** (simple rule-of-mixtures, `Vf`
  from `svars(KBLOCK,107)`, already populated per-element by the mesher
  via `*Initial Conditions, TYPE=SOLUTION` -- nothing to change there,
  confirmed already efficient);
- **SIGY0 and HMOD get scaled by the same eta**, to preserve the Stage
  1/2-calibrated yield strain. This message works out exactly how that
  has to be wired for internal consistency -- read it fully before
  starting, the naive version of this has a subtle trap.

## The problem being fixed

`docs/VERIFICATION_REPORT.md` section 4: the plain `*Embedded Element`
approach double-counts stiffness (host keeps full modulus, embedded
fiber adds its own full stiffness on top, no volume-fraction reduction
of the host). Measured effect: 20-27x too-high internal energy at
Vf~0.58-0.79 with a 66x fiber/matrix modulus ratio. Fix: reduce the
host's own elastic (and, to stay consistent, plastic-yield) contribution
by `eta = 1 - Vf` per element.

## Why this has to be done at the material-constant source, not as a late stress multiply

I worked through the algebra before writing this brief so you don't have
to re-derive it, but please verify it yourself rather than trusting it
blindly -- this is exactly the kind of thing that needs a real test
(see Verification below).

`uel/VUEL_failure.for` currently computes `ALAMBDA`, `AMU`,
`BULK_MODULUS`, and the 6x6 `CMAT` **once per subroutine call** (lines
~379-407), shared across every element in the vectorized block, from the
single scalar `EMOD = props(1)` / `ENU = props(2)`. `SIGY0 = props(8)`
and `HMOD = props(9)` are likewise call-level scalars.

A tempting shortcut is: leave all of that alone, run the existing
elastic-plastic calculation exactly as-is (which reproduces the
*uncalibrated* model exactly, since nothing changed), and multiply only
the *final* `STRESS_PK2` by `eta` once, right after the Step 6 block
(after line 749, before "Step 7: Compute VISCOUS STRESS"). That would
coincidentally preserve the yield strain too (since the internal
`SIGMA_TRIAL > SIGY_OLD` check never sees `eta` at all) -- **but it's
incomplete**, because `CMAT` and `BULK_MODULUS` are each used again
*downstream* of that point, uncorrected:
- `STRESS_VISC` (line ~762-768, Rayleigh damping) is `beta * CMAT :
  Edot` -- stiffness-proportional damping that should scale with the
  corrected stiffness it's damping, or you get an inconsistent (too
  stiff) damping term relative to the corrected elastic response.
- `STRESS_RESIDUAL`'s `P_RESIDUAL` (line ~807, the post-failure
  compression-only residual stiffness) is `COMP_RESIDUAL_FRAC *
  BULK_MODULUS * VOL_ELASTIC_STRAIN` -- same problem, uncorrected
  residual stiffness after failure.

A late single stress-multiply would miss both of these. **The correct,
fully self-consistent fix is to scale the material constants at their
source, per element**, inside the `KBLOCK` loop, so every downstream
consumer (elastic trial stress, plastic return mapping, Rayleigh
viscous stress, post-failure residual stiffness) is automatically
correct with no risk of missing a use site.

I worked out that scaling `AMU`, `ALAMBDA`, `BULK_MODULUS` (hence
`CMAT`) **and** `SIGY0`/`HMOD` by the *same* `eta_k` keeps the radial-
return algebra internally consistent: `DGAMMA = (SIGMA_TRIAL -
SIGY_OLD) / (3*AMU + HMOD)` has `eta_k` as a common factor in both the
numerator (`SIGMA_TRIAL` from scaled `CMAT`, `SIGY_OLD` from scaled
`SIGY0`/`HMOD`) and the denominator (`3*AMU + HMOD`, both scaled), so it
cancels -- **`DGAMMA` and `PEEQ` come out numerically identical to the
unscaled case**, only the stress magnitudes differ. That's the desired
outcome: same yield strain, same plastic-strain evolution, proportionally
reduced load-carrying stress. Please confirm this algebraically yourself
and in a real test, don't just take my word for it.

## What NOT to scale

- `DENS` (density) and anything derived from it for bulk viscosity
  (`QBULK`, `STRESS_BULK`, `CWAVE`) -- that's numerical stabilization
  tied to mass/wave speed, not the stiffness double-counting this fixes.
- `EPS_FAIL` (props(7)) and `JAC_FAIL` (props(11)) -- both are strain/
  Jacobian-based geometric failure triggers, compared directly against
  strain or det(F), not against a stress built from `CMAT`/`SIGY0`.
  Leave these exactly as they are; they should be unaffected by this
  change and should still trip at the same calibrated strain values.
- `DEGRADE_TIME`, `COMP_RESIDUAL_BULK_FRAC` -- timing/fraction
  parameters, not stiffness.
- `EP_VEC`/`PEEQ` themselves -- plastic strain state, confirmed above to
  be unaffected by `eta` (it cancels out of `DGAMMA`).

## Implementation

1. Right after `FIBER_VOL_FRAC` is read (lines ~432-433, inside the
   `DO KBLOCK = 1, nblock` loop), compute
   `ETA_VF = 1.0D0 - FIBER_VOL_FRAC`, clamped to a safe floor (e.g.
   `DMAX1(ETA_VF, 1.0D-6)`) so a bad/out-of-range `Vf` from the mesher
   can't produce zero or negative stiffness. Follow this file's existing
   clamp style (see `COMP_RESIDUAL_FRAC` at lines 374-377) and add a
   `WRITE(*,*)` warning on the clamp firing, at least on early calls,
   consistent with how other defensive checks in this file report.
2. Compute per-element scaled constants inside the `KBLOCK` loop (not
   call-level): `EMOD_K = ETA_VF * EMOD`, then the same Lame-parameter
   and `CMAT` formulas currently at lines 379-407, parameterized by
   `EMOD_K` instead of the call-level `EMOD`, producing per-element
   `ALAMBDA_K`, `AMU_K`, `BULK_MODULUS_K`, `CMAT_K(6,6)`. Also
   `SIGY0_K = ETA_VF * SIGY0`, `HMOD_K = ETA_VF * HMOD`.
3. Replace every use of `CMAT`, `AMU`, `BULK_MODULUS`, `SIGY0`, `HMOD`
   *inside the KBLOCK loop* with the `_K` per-element versions. That
   includes (line numbers from the current file, re-check them, this
   message is not a diff): `SIGY_OLD` (653), the yield/denominator check
   (703-709), `S_TRIAL_VEC` (669-675), `DEP_VEC`/`STRESS_PK2` (736-741),
   `STRESS_VISC` (762-768), `P_RESIDUAL` (803-808).
4. Leave the call-level `CMAT`/`ALAMBDA`/`AMU`/`BULK_MODULUS`/`SIGY0`/
   `HMOD` and the `jMassCalc` block (uses `DENS`, not `EMOD`) exactly as
   they are -- they're unaffected/still needed for the NCALLS==1
   diagnostic printout and mass calculation.
5. Add a first-call diagnostic print of `ETA_VF`, `EMOD_K`, `SIGY0_K` for
   one representative element (matching this file's existing
   `NCALLS .LE. 5`-style diagnostics) so this is easy to sanity-check
   from ROAR stdout without needing a debugger.
6. Update the `svars(107)` doc comment (lines 179-182) -- it currently
   says "Observation/bookkeeping only ... does not alter the
   constitutive response," which will no longer be true.

## Verification

Build a new single-element verification case (same pattern as the
existing Stage 1/2 single-element decks, e.g.
`verification/roar/t7/t7_tension_plastic_user.for` style) with two
variants, `Vf=0` and `Vf=0.5`, under the same prescribed
tension/compression loading used in Stage 1/2's analytic comparison:
- **Regression check:** `Vf=0` must reproduce bit-identical (or
  numerically identical to solver tolerance) results to the current,
  unmodified file -- this change must be a no-op when there's no fiber
  volume fraction.
- **Elastic check:** below yield, `Vf=0.5`'s reaction force must be
  exactly half of `Vf=0`'s at the same strain.
- **Yield-strain check:** both cases must yield at the *same* strain
  (within solver tolerance) -- this is the property the SIGY0/HMOD
  scaling is specifically for; if it doesn't hold, something in the
  algebra above was translated wrong.
- **Post-yield check:** post-yield hardening slope (stress vs. PEEQ) for
  `Vf=0.5` should be exactly half of `Vf=0`'s.

Run `pytest` on existing plasticity/failure tests too and report
pass/fail -- this touches code that Stage 1-6's tests already exercise.

I don't have local Abaqus access either; this needs the same "test on
ROAR" discipline as every prior stage. Don't claim the physics is
correct without a real run backing it up.

## Deliverable

Usual outbox format: deliverable files in
`agents/refiner/outbox/VUEL_VOLUME_FRACTION_CORRECTION_2026-10-07/`,
then `agents/refiner/outbox/VUEL_VOLUME_FRACTION_CORRECTION_2026-10-07-RESULT.md`
per `agents/PROTOCOL.md`. Be explicit in `not_verified` about anything
you couldn't actually run.

## Constraints

- Don't touch `uel/VUEL.for` (production), only the `vuel-plastic-
  failure` branch's `uel/VUEL_failure.for`.
- Don't change `EPS_FAIL`/`JAC_FAIL` semantics or any already-calibrated
  threshold value.
- If anything in the algebra above doesn't check out once you work
  through it in detail, say so explicitly in `concerns` rather than
  silently reworking the approach -- this is physics the human needs to
  see before it's accepted either way.
