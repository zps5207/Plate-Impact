# Stage 6 round 2 ROAR result: input error, exact fix identified

Date: 2026-10-02
To: Codex
Re: `STAGE6_ROAR_RESULT_2026-10-02/HANDOFF.md` (yield-sync calibration)
ROAR job: 56011920, FAILED (exit 1) during the Analysis Input File
Processor, before Step-1 even began (no `.sta`/`.msg` generated — this is
an input-deck rejection, not a solve/physics failure).

Applied the 3 updated files (`embmesh/vuelghost.py`, `embmesh/cli.py`,
`tests/test_vuelghost.py`) to the live tree; `VUEL_failure.for` unchanged
(hash matched). Regenerated from live code, confirmed bit-identical to
your deck (SHA-256 `1d7e39a4...`). 25/25 tests pass.

## The error

```
***ERROR: THE STRAIN AT FAILURE MUST BE GREATER THAN ZERO
```

from `flat_vg_r2.dat`. Abaqus's native `*Damage Initiation,
criterion=DUCTILE` rejects a literal `0` for the equivalent-plastic-
strain-at-failure value — it requires strictly positive. Your
`--ghost-ductile-failure-strain 0` choice (intended to make the ghost
delete on its first plastic increment) trips this during input
processing, before Step-1 starts. 1 fatal error reported, nothing else
in the deck flagged.

## Fix needed

Use a tiny positive epsilon instead of exact zero for the ghost's
ductile initiation strain -- e.g. `1e-6` or similar, small enough to
still trigger on essentially the first plastic increment but accepted by
Abaqus's input processor. Everything else in the yield-sync calibration
(VUEL `EPS_FAIL=0.113800332690901`, displacement evolution `0`, the
unchanged impact/step) looked right going in -- this is a one-line value
fix, not a design problem.

Once you've got a version with a valid positive ghost threshold, hand it
back the same way (new `Flat-vuel-ghost-*` output + updated HANDOFF.md)
and I'll run it on ROAR again.

## Evidence retained

`verification/roar/t_stage6/evidence_20261002_r2/`: `flat_vg_r2.dat`,
`flat_vg_r2.stdout`, `stage6_flat_vg_r2_56011920.out`.
