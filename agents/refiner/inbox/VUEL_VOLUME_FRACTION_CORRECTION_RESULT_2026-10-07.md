# Stage 7 ROAR result: no-op regression is clean, but Vf=0.5 checks don't actually pass

Date: 2026-10-07
To: Codex
Re: `VUEL_VOLUME_FRACTION_CORRECTION_2026-10-07/HANDOFF.md`
(sha256 `c9eb75f3...`), job 56159537, `stage7_vf_check.json` below.

Ran `run_stage7_vf.sbatch` on ROAR. All six decks completed. Full
`stage7_vf_check.json` is pasted at the bottom.

## 1. Bug in `stage7_check_vf.py`'s `rel()` for sub-1.0 quantities

```python
def rel(a, b):
    return abs(a - b) / max(abs(b), 1.0)
```

For strain values (always `<1.0` here), `max(abs(b), 1.0)` forces the
denominator to a flat `1.0`, so this silently becomes an *absolute*
difference check, not a relative one. `yield_green_strain_matches_
rel_error_lt_0p03` reports `True`, but the actual numbers are:

```
tension:     vf0 yield green strain = 0.0013462588880810975
             vf05 yield green strain = 0.0016727478504808416   (~24% apart)
compression: vf0 yield green strain = 0.0013444489109661342
             vf05 yield green strain = 0.001669954435837103    (~24% apart)
```

That is not within 3% of each other. Please fix `rel()` to use true
relative error for quantities like strain (e.g. `abs(a-b)/abs(b)` with a
small-value guard, not a `max(..., 1.0)` floor that only makes sense for
stress-scale quantities) so this check actually means something, and
re-report once it does.

## 2. Two checks genuinely fail, not just a checker artifact

```
vf05_force_is_half:        tension 8.0% off, compression 8.6% off  (tol 3%)
postyield_slope_is_half:   tension 12.5% off (slope ratio 0.4375),
                            compression 19.6% off (slope ratio 0.4044)
                            (tol 5%, expected ratio exactly 0.5)
```

The `vf0` vs. pre-Stage-7 baseline regression is exact (0.0 error), so
whatever's happening is specific to the `eta=0.5` case, not a general
problem with the restructured code.

## My hypothesis -- please investigate, don't just take it as given

These decks use `*Dynamic, Explicit` with a `SMOOTH STEP` amplitude
ramp, not a quasi-static load. `Vf=0` and `Vf=0.5` have different
effective stiffness and therefore different natural periods/wave speeds.
Under the *same fixed-duration* ramp, a softer and stiffer single
element will be at different points in their own dynamic transient
(including ringing/overshoot) when they happen to cross a given nominal
**strain** value -- so comparing them at matching strain snapshots (as
`stage7_check_vf.py` currently does) may not be an apples-to-apples
comparison, even though the underlying elastic/plastic algebra is sound
(confirmed independently in the task brief and your
`LOCAL_VERIFICATION.md`). This would be a verification-methodology gap,
not a Fortran defect.

I can't confirm this without the raw force/strain-vs-**time** history,
which the current checker doesn't retain (it only keeps `(u1, -reaction)`
pairs, not `frame.frameValue`/time). Two ways to actually check this,
pick whichever is easier to add:

1. Extend `curve()` to also record simulation time per frame, then
   compare `vf0` and `vf05` at matching **time** (not matching strain)
   for the portion of the ramp before either yields. If the force ratio
   is a clean 2x there, the strain-snapshot comparison is the artifact,
   not the physics.
2. Add a slow/quasi-static-rate variant of the same tension/compression
   decks (much longer `SMOOTH STEP` ramp duration relative to the
   element's natural period) and see whether the half-force/half-slope
   checks converge to passing as the loading rate slows down. If they
   do, that's strong confirmation it's a dynamic-rate artifact, not an
   implementation bug.

If neither of those clears it up, or if you find something in the
algebra/implementation I missed, report that plainly in `concerns`
rather than reworking the formulation on your own -- the human already
signed off on the `eta=1-Vf`/scaled-SIGY0-HMOD approach, so a real
problem with that approach needs to come back to the human, not get
silently changed.

## Full `stage7_vf_check.json`

```json
{
  "compression": {
    "analytic_yield_green_strain": 0.00125,
    "checks": {
      "postyield_stress_vs_peeq_slope_is_half_rel_error_lt_0p05": false,
      "vf05_force_is_half_max_rel_error_lt_0p03": false,
      "vf0_matches_pre_stage7_max_rel_error_lt_1e-8": true,
      "yield_green_strain_matches_rel_error_lt_0p03": true
    },
    "pass": false,
    "postyield_stress_vs_peeq_slope_Pa": {
      "vf0": 1455815293.6650171,
      "vf05": 588590658.539541
    },
    "vf05_half_force_max_rel_error": 0.08589790990696328,
    "vf0_regression_max_rel_error": 0.0,
    "yield_green_strain": {
      "vf0": 0.0013444489109661342,
      "vf05": 0.001669954435837103
    }
  },
  "pass": false,
  "tension": {
    "analytic_yield_green_strain": 0.00125,
    "checks": {
      "postyield_stress_vs_peeq_slope_is_half_rel_error_lt_0p05": false,
      "vf05_force_is_half_max_rel_error_lt_0p03": false,
      "vf0_matches_pre_stage7_max_rel_error_lt_1e-8": true,
      "yield_green_strain_matches_rel_error_lt_0p03": true
    },
    "pass": false,
    "postyield_stress_vs_peeq_slope_Pa": {
      "vf0": 2121585795.3948622,
      "vf05": 928245447.4007697
    },
    "vf05_half_force_max_rel_error": 0.08038736793922302,
    "vf0_regression_max_rel_error": 0.0,
    "yield_green_strain": {
      "vf0": 0.0013462588880810975,
      "vf05": 0.0016727478504808416
    }
  }
}
```
