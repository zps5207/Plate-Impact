# Stage 2 report: engineering-strain failure trigger on a plastic element (2026-10-01)

Branch: `vuel-plastic-failure`. **No changes to `uel/VUEL_failure.for` were
needed for this stage** -- the engineering-strain failure check (added in
an earlier branch stage, see `docs/VUEL_FAILURE_CRITERION_REPORT_2026-10-01.md`)
reads only the Green-Lagrange normal strains and is structurally independent
of the plastic-state code Stage 1 added (confirmed by inspection when
Stage 1 was written: the failure check runs on `STRAIN_VEC`, computed
before the elastic-plastic stress update, never on `STRESS_PK2`/`EP_VEC`).
This stage exists to confirm that independence holds in practice, not
just on paper.

## Deck (`verification/make_t8_plastic_trip.py`, `verification/roar/t8/`,
ROAR job **55972088**)

Single `VU1` hex, same uniaxial-stress BC pattern as T6/T7.
`E=200 GPa, nu=0.3, SIGY0=250 MPa, HMOD=2 GPa, IPLAST=1` (same as Stage 1's
plastic decks), `EPS_FAIL=0.02` -- comfortably past yield
(`eps_y=0.00125`, so the element flows plastically for a long stretch
first) and comfortably before the deck's peak applied strain of 0.04 (so
the trigger is actually exercised, not just approached). Driven in tension
0 -> 0.04 over a 0.01 s SMOOTH STEP ramp, `B1_BULK=B2_BULK=BETA_RAYLEIGH=0`
(same reasoning as Stage 1: isolate the check from damping noise).

## Result: PASS

`run_t8_tension_trip` completed (`rc=0`, `THE ANALYSIS HAS COMPLETED
SUCCESSFULLY`). The subroutine's own failure message:

```
*** VUEL_FAILURE: ELEMENT FAILED, elem = 1  time = 5.0382130E-03
```

RF1 (summed over the four x-pinned back-face nodes, same method as Stage
1) vs. engineering strain (`U1` at node 2), pulled from the ODB:

| t (s) | eps_eng | sigma_fem (Pa) |
|---:|---:|---:|
| 0.001634 | 0.001345 | 2.59e8 |
| 0.002587 | 0.004517 | 2.71e8 |
| 0.004085 | 0.013289 | 2.89e8 |
| 0.004630 | 0.017233 | 2.87e8 |
| **0.005038** | **0.020287** | **3.01e8** |
| **0.005311** | **0.022323** | **0.0** |
| 0.006536 | 0.030816 | 0.0 |
| 0.010000 | 0.040000 | 0.0 |

This confirms all three things Stage 2 set out to check:

1. **Stress tracks the plastic hardening curve before the trip** -- the
   values above through `eps=0.0203` are the same (to within the ODB's
   frame sampling) as Stage 1's `t7_tension_plastic` deck's own hardening
   curve at the same strains, not a pure-elastic line. Plasticity and the
   not-yet-tripped failure check coexist correctly.
2. **The trip occurs at the expected strain**: the last nonzero-stress
   frame is at `eps=0.020287`, matching `EPS_FAIL=0.02` (the small
   overshoot is normal -- the trigger is evaluated once per increment at
   increment end, and increments land between sampled output frames; see
   the original failure-criterion report for the same one-increment-lag
   behavior on a purely-elastic element).
3. **RF goes to exactly zero immediately after**: `0.0` (not just
   "small") at the very next recorded frame, and stays exactly `0.0`
   through the rest of the ramp to `eps=0.04` -- the element goes
   numerically inert the increment after it fails, exactly as designed,
   with plasticity active alongside it changing nothing about that
   mechanism.

## Open issues

None new. The existing caveats from Stage 1 (no direct SVARS/element-output
access for a VUEL in Explicit; zero damping used deliberately to keep
these checks clean) carry forward unchanged.

## Next: Stage 3

Add the Jacobian (`detJ_current/detJ_initial`) collapse trigger and build
a single-hex test that collapses (heavy compression and a shear-collapse
case), confirming it trips before `detJ` goes non-positive, with no NaN
and no abort.
