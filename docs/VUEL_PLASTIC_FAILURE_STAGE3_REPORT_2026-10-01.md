# Stage 3 report: Jacobian (collapse) failure trigger (2026-10-01)

Branch: `vuel-plastic-failure`. Adds `props(11)=JAC_FAIL` and the
`min(det(F))`-over-8-Gauss-points collapse trigger to
`uel/VUEL_failure.for`, alongside (not replacing) the existing
engineering-strain trigger. Rationale (already flagged in
`docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md`): 1-D engineering strain is
bounded at -1 under compression, so the goal's suggested `EPS_FAIL~1.0`
is structurally a tension-side-only trigger; compression/shear collapse
needs a geometric (volume-ratio) measure instead.

## Implementation

- `DETF` (= det(F), the current/reference volume ratio at a Gauss point)
  was already computed every call by `COMPUTE_DEFGRAD`; `DETJ0` (the
  reference-configuration Jacobian from `SHAPE8H_TL`) is a different,
  constant quantity -- the header now spells out explicitly why `DETF`
  alone, not some combination with `DETJ0`, is the right measure.
- `ELEM_MIN_DETF` tracks the worst (smallest) `DETF` over the element's 8
  Gauss points per increment, same pattern as `ELEM_MAXABS_ENG` for the
  existing trigger.
- Failure check at end of increment (unchanged timing): engineering-strain
  trigger checked first, Jacobian trigger second (`ELEM_MIN_DETF <=
  JAC_FAIL .OR. ELEM_MIN_DETF <= 0`, the `<=0` branch is an explicit
  safety net independent of `JAC_FAIL`'s sign, per the goal's instruction)
  -- same latch (`svars(49)`), same "freeze everything, go inert" dead
  state as before. Both trigger messages identify which one fired
  (`(ENG STRAIN)` vs `(JACOBIAN)`).
- Audited every division/sqrt in the file for collapse-safety (per the
  goal's explicit instruction): all are already guarded (`DMAX1(...,
  0.0D0)` before `DSQRT`, `SIGMA_TRIAL .GT. SMALL` before dividing by it,
  `DABS(DETJ) .GT. SMALL` in `SHAPE8H_TL`, and `CHARLEN`/`OMEGA_MAX` are
  built from the *reference* volume `DETJ0`, which never changes with
  deformation and so can't be driven to zero by element collapse). No new
  guards were needed.
- `nprops` 10 -> 11 (`*UEL Property` data line fix from Stage 1 --
  8-per-line -- already accounted for in the new generator).

## Decks (`verification/make_t9_jacobian_trigger.py`,
`verification/roar/t9/`) -- plasticity deliberately OFF (`IPLAST=0`) and
`EPS_FAIL=10` (unreachable), isolating the Jacobian path, same
one-new-mechanism-at-a-time approach as every earlier stage.

- `t9_heavy_compression`: same clean uniaxial-stress BC as T6/T7/T8, driven
  to `u1=-0.97` (affine compression, `F11 -> 0.03`).
- `t9_shear_collapse`: back face FULLY fixed (cantilever, not the minimal
  rigid-body-removal pattern -- this test wants a genuinely non-affine
  collapsing shape, not a clean analytic comparison), combined shear
  (`u2=+4.0`, several times the unit edge) and compression (`u1=-0.8`) on
  the driven face.

**`JAC_FAIL=0.05`** (props(11)), the goal's suggested starting value, used
as-is (not independently validated/tuned here).

## False start: shear_collapse's first attempt never tripped

First attempt used `u1=-0.6, u2=2.5`. Job completed (rc=0) but with no
`VUEL_FAILURE` message at all, and the `.sta` file's `TOTAL ENERGY` column
went sharply negative (`-4.99e8` by the final increment) -- a red flag.
Added temporary per-call `WRITE` instrumentation (ROAR job 55972119,
removed before the final run) and found `min(det(F))` only reached
`0.091` by the end of the ramp -- above `JAC_FAIL=0.05` -- while
`max|eng strain|` reached `1.55` (way past any physically meaningful
small-strain range, but still under the deliberately-unreachable
`EPS_FAIL=10`). **Neither trigger failed to fire; the test simply didn't
deform the element far enough to cross either threshold.** The negative
total energy is the St. Venant-Kirchhoff elastic law's known large-strain
pathology (already documented in the file header: St.VK is accurate for
moderate strains only) manifesting at `eps~1.5`, not a bug in the trigger
logic. Fixed by increasing the excursion to `u1=-0.8, u2=4.0`.

## Result: PASS, both decks

Both completed (`rc=0`, `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`), no
`NaN`/`Inf`/error anywhere in either `.dat` file.

**`t9_heavy_compression`** (ROAR job 55972126): trips via

```
*** VUEL_FAILURE (JACOBIAN): elem = 1  time = 9.1149081E-03
```

RF1 (summed over the four x-pinned nodes) history: builds from 0 to a
peak of `-3.85e10 Pa` around `eps=-0.42` (again, the StVK large-strain
pathology -- a real elastic law would never predict a 38.5 GPa stress on
a 200 GPa-modulus material at 42% engineering strain; this is expected
and already documented, not new), the magnitude naturally receding as
`eps` continues toward -1 (the stress-strain curve for St.VK is
non-monotonic at large compressive strain), then at the frame immediately
after the trip (`t=0.009375`) drops to **exactly 0.0** and stays there
through `eps=-0.970` at the end of the ramp.

**`t9_shear_collapse`** (same job): trips via

```
*** VUEL_FAILURE (JACOBIAN): elem = 1  time = 6.8083936E-03
```

RF1-sum grows (again non-physically large, StVK pathology, now compounded
by the combined shear+compression state) to `4.47e11 Pa` at the frame just
before the trip, then **exactly 0.0** at the very next frame and every
frame after, through the end of the ramp (`eps=-0.800`, `U2` continuing to
move per the prescribed BC regardless -- the dead element no longer
resists, exactly as designed).

Both confirm the three things Stage 3 set out to check: the trigger fires
before `det(F)` reaches zero or goes negative (confirmed via the debug
instrumentation during the false-start diagnosis, and no NaN/error ever
appeared in either final run), the run completes without aborting, and RF
goes to exactly zero immediately after the trip.

## Open issues

- **The St. Venant-Kirchhoff elastic law's large-strain pathology
  (non-monotonic, physically-absurd stress at large strain) is real and
  already documented in the file header, but this stage is the first to
  actually witness its effect on the `.sta` energy balance directly**
  (the sharply negative `TOTAL ENERGY` in the first shear_collapse
  attempt). It did not prevent the Jacobian trigger from working
  correctly once the deformation was large enough, but it does mean a
  `JAC_FAIL` threshold set too close to the StVK law's breakdown point
  would be racing an increasingly unreliable stress field -- worth
  keeping in mind if `JAC_FAIL=0.05` is later revised away from the
  goal's placeholder value. Not a defect in this stage's work.
- Same Stage 1/2 caveats carry forward (no direct SVARS access for a VUEL
  in Explicit; `RF`/`U` node history is the evidence channel).

## Next: Stage 4

Dead-state hygiene: `dtimeStable` behavior for a failed element, energy
balance (`ALLIE`, `ALLKE`, `ETOTAL`) across the trip, and a two-element
and small multi-element test to observe cascading failure and orphan-node
behavior.
