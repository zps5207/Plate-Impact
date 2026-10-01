# Stage 4 report: dead-state hygiene (2026-10-01)

Branch: `vuel-plastic-failure`. Two real bookkeeping gaps found and fixed
in `uel/VUEL_failure.for` (not just verified -- these were genuine bugs
left over from earlier stages), plus two multi-element tests run purely
observationally, per the goal's own framing ("Report what happens to
nodes whose elements have all failed").

## Fixes made

1. **Rayleigh/bulk-viscosity dissipation kept accumulating for a failed
   element.** `ELIE`/`PLASTIC_DISSIP` were already guarded by
   `.NOT. ELEM_ALREADY_FAILED` (from Stage 1), but `DAMP_DISSIP`/
   `BV_DISSIP` were not: `STRESS_VISC`/`STRESS_BULK` are computed from the
   dead element's current strain rate (its nodes keep moving under their
   own inertia even after it dies), and without the guard that nonzero
   stress-times-strain-rate kept silently adding "dissipation" energy for
   an element whose actual force contribution (`STRESS_TOTAL`, and hence
   `FINT`) is already zero -- a real energy-bookkeeping error, exactly
   what this stage was looking for. Fixed by wrapping both accumulations
   in the same guard.
2. **`dtimeStable` was never relaxed for a failed element.** A dead
   element still has mass and the file still computed its elastic-wave-
   speed-based stable increment from its *original* (pre-failure)
   material properties, meaning it would keep capping the analysis's
   global stable time increment (Abaqus takes the minimum over all
   elements) for the rest of the run, for no physical reason. Fixed:
   `dtimeStable(KBLOCK) = 1.0D30` once `ELEM_ALREADY_FAILED`.

Kinetic energy (`ELKE`) was deliberately left untouched -- a dead
element's nodes still have real mass and velocity, and that's a genuine,
correct contribution to the model's total KE that should not disappear
just because the element stopped exerting force. Mass itself was
(already, unavoidably) left untouched -- `amass` is set once at
`jMassCalc` and this file has no hook to revisit it.

**Decision on stored elastic energy at the moment of failure, now
documented in the file header**: it is NOT preserved, redirected into
a dissipation bucket, or otherwise accounted for -- `ELIE` (recomputed
fresh from the current strain state every call, not accumulated) simply
reads `0.0` the instant the element goes inert, since the guard that
stops it accumulating starts on the very next call. This means the
whole-model `ETOTAL` balance will show a one-increment discontinuous
drop at the moment of failure, equal to whatever elastic strain energy
was stored in that element the instant before. Confirmed directly below,
not just asserted.

## Deck 1: `t10_damping_hygiene` (confirms both fixes with real numbers)

Single `VU1` hex, same uniaxial-stress BC as T6-T9, but with **nonzero**
`BETA_RAYLEIGH=1e-6` and bulk viscosity (`b1=0.06, b2=1.2`) -- every
earlier stage zeroed these to keep comparisons clean; here the point is
to have real damping active so its bookkeeping can be checked. Driven to
tension past `EPS_FAIL=0.02`. Trips via
`*** VUEL_FAILURE (ENG STRAIN): elem = 1  time = 5.0087031E-03`.

| t (s) | ALLIE (J) | ALLVD (J) |
|---:|---:|---:|
| 0.004873 | 3.6986e7 | 2.1931e4 |
| **0.005009** (last live) | **4.1073e7** | **2.3514e4** |
| **0.005144** (first dead) | **0.0** | **2.3514e4** |
| 0.005307 | 0.0 | 2.3514e4 |
| 0.005501 | 0.0 | 2.3514e4 |
| ... (every later frame) | 0.0 | 2.3514e4 (bit-identical) |

`ALLIE` drops to exactly `0.0` the frame after the trip and stays there;
`ALLVD` freezes at exactly `2.351392e4` -- bit-for-bit identical at every
subsequent output frame through the end of the run, confirming the
dissipation-accumulation fix works exactly as intended (before the fix,
with nonzero damping and a still-moving dead element, `ALLVD` would have
kept climbing). `ETOTAL` shows the corresponding large one-increment drop
(from `-2.9e2` to `-4.3e7`) at that same increment, then stays essentially
flat (drifting by ~`1e2` absolute, i.e. ~0.0003%, over the remaining 5 ms
-- consistent with ordinary KE evolution, not further energy leakage) --
directly confirming the documented "stored elastic energy vanishes at the
instant of failure, nothing else is injected or leaked afterward" design.

## Deck 2: `t10_two_element` -- genuinely orphaned node, free-flight

Two identical `VU1` hexes in series along x (sharing a 4-node interface
face), same `EPS_FAIL=0.02` for both, end-to-end tension driven from the
far end. Two equal segments in series split an imposed displacement
evenly, so both reach the threshold in the **same increment** --
confirmed:

```
*** VUEL_FAILURE (ENG STRAIN): elem = 1  time = 4.4935420E-03
*** VUEL_FAILURE (ENG STRAIN): elem = 2  time = 4.4935420E-03
```

This makes the shared interface node (node 2 of the 4-node interface set)
**fully orphaned in one step**: every element touching it fails at once.
Its `V1` (axial velocity) history:

| t (s) | V1 (m/s) |
|---:|---:|
| 0.004357 | 9.10411 |
| 0.004630 | 9.26315 |
| **0.004793** (first frame after trip) | **9.26315** |
| 0.004989 | 9.26315 |
| 0.005507 | 9.26315 |
| 0.006653 | 9.26315 |
| 0.008570 | 9.26315 |
| 0.010000 (last frame) | 9.26315 |

`V1` locks to `9.26315` m/s the first frame after the trip and stays
**bit-identical** for every one of the ~15 remaining output frames through
the end of the run -- a textbook confirmation of Newton's first law: zero
net force (both neighboring elements dead, nothing else touches this
node) means exactly constant velocity, no drift, no instability. The
driven far-end node, by contrast, continues decelerating smoothly toward
its prescribed final displacement (kinematically controlled by the
*Boundary condition, unaffected by either element's failure).

## Deck 3: `t10_three_chain` -- cascading failure observation (per the
goal, reported descriptively, not pass/fail)

Three identical-material `VU1` hexes in series, **staggered**
`EPS_FAIL` (elem1=0.015, elem2=0.025, elem3=0.04) so they are intended to
fail in sequence as the far end is driven further. Only **elem1** ever
trips (`t=2.9956952E-03`); elem2 and elem3 never reach their thresholds
in this 0.01 s step, despite the imposed end displacement (0.3 over
length 3) being large enough that, if the structure behaved quasi-
statically, elem2 and elem3 would also have been expected to fail.

**What actually happens, from the interface nodes' `U1`/`V1` history**:
once elem1 dies, the interface node between elem1 and elem2 (node 2) is
no longer connected to the fixed wall through any live stiffness path
(elem1 is dead; the only live connection left is through elem2 toward
the still-driven far end). With zero damping (deliberately, same as
every earlier stage's isolation decks), this un-anchored node goes into
**violent, undamped oscillation** rather than settling into a new
quasi-static state: `V1` at node 2 swings from values near 10-25 m/s
(during the still-elastic early loading) to peaks over **150 m/s**
and troughs below **-90 m/s** within a few tenths of a millisecond after
elem1's death, and is still oscillating with tens-of-m/s amplitude at the
end of the run (`V1=40.5` m/s at `t=0.01`, still moving). `U1` at the same
node does not monotonically track the imposed end displacement the way
it would in a quasi-static picture -- it overshoots past 0.14, drops back
to 0.117, and ends the run at 0.328 (vs. a naive quasi-static expectation
of roughly 1/3 of 0.3 = 0.1 once two segments remain), driven by this
ringing rather than by steadily increasing strain. **Neither elem2 nor
elem3's own engineering strain ever climbs high enough, because the
energy that would have gone into monotonic stretching instead went into
this oscillation.** No NaN, no abort, `rc=0`, `THE ANALYSIS HAS COMPLETED
SUCCESSFULLY` -- the simulation itself stays numerically well-behaved
throughout, but the intended "cascading failure" narrative does not play
out the way a quasi-static mental model would predict.

**Takeaway for the real plate-impact use case**: killing one element in a
load path does not simply "redistribute load smoothly to the next
weakest link." With zero damping, it can instead destabilize the
remaining connected structure into large-amplitude dynamic ringing,
which may or may not ever revisit the strain levels needed to propagate
failure further, depending entirely on the dynamics of what's left. This
is reported as an observed fact about the current (zero-damping,
immediate-zero-force) dead-state design, not a defect -- but it's a
strong signal that Stage 5's "ramped force degradation" option (smoothing
the transition instead of an instantaneous drop to zero) could matter a
great deal for whether cascading failure propagates realistically, and
that realistic (nonzero) damping is probably necessary for any multi-
element VUEL-chain simulation to behave sensibly after the first failure.

## Open issues

- The `t10_three_chain` result above means Stage 4's "small multi-element
  test to see cascading failure" did not actually observe cascading in
  this particular configuration -- re-running with nonzero damping, or a
  slower/longer loading ramp, might produce a cleaner cascading sequence,
  but was not attempted here since the *un*-cascaded result is itself the
  more important, honestly-reported finding for this stage.
- No node in `t10_three_chain` became fully orphaned (would require BOTH
  of a node's flanking elements to fail; only elem1 ever did), so this
  deck did not exercise the fully-orphaned-node case -- `t10_two_element`
  covers that cleanly instead.

## Next: Stage 5

Only after this (Stage 1-4) baseline is accepted: ramped force
degradation before the dead state, and an optional compression-only
residual (volumetric stiffness only) for failed elements, each behind its
own prop flag, compared against this stage's zero-rhs baseline --
directly motivated by the `t10_three_chain` finding above.
