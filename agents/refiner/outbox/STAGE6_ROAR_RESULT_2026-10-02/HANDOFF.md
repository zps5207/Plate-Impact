# Stage 6 yield-onset calibration handoff

## Ready-to-run files

- Deck: `Flat-vuel-ghost-yield-sync/output.inp`
- Abaqus user subroutine: `uel/VUEL_failure.for`
- Mesher source changes: `embmesh/vuelghost.py`, `embmesh/cli.py`
- Regression test: `tests/test_vuelghost.py`
- Static verifier and evidence: `verify_flat_vuel_ghost_yield_sync.py` and
  `Flat-vuel-ghost-yield-sync/static_verification.json`
- NumPy fixed-form signature output: `VUEL_failure.pyf`

SHA-256:

- `output.inp`: `1d7e39a4b05c3bf98706d0861187ff6c9df03bfb294bc2b7a794c51c6660a2c4`
- `VUEL_failure.for`: `ad65dd27ae6eacedbb64df73fea90d1f030911846ac067950b744c3cac3838ef`

## Calibration choice

The impact severity and `1e-4` step duration are unchanged. This deck moves
both deletion triggers to material yield onset:

- VUEL `EPS_FAIL = 0.113800332690901`, the engineering strain corresponding
  to the first Matrix yield stress under the VUEL's St. Venant-Kirchhoff
  strain measure:
  `sqrt(1 + 2*SIGY0/E) - 1`, with `SIGY0=611000` and `E=5080000`.
- Ghost `*Damage Initiation, criterion=DUCTILE` equivalent plastic failure
  strain is `0`, so native damage initiates on the first plastic increment.
- Ghost `*Damage Evolution, type=DISPLACEMENT` remains `0`, so deletion is
  immediate after initiation.
- `JAC_FAIL=0.05` remains a collapse backstop and is not the intended trigger.
- `DEGRADE_TIME=0` keeps VUEL removal immediate after its trigger.

This is expected to exercise deletion because the prior full-scale ROAR run
loaded the plate but used a 5.06 strain threshold, while the new threshold is
approximately 44.5 times lower and aligned with the material's first yield.
The VUEL maximum principal engineering-strain trigger and Abaqus native
ductile PEEQ trigger are not identical measures, so the requested same/plus-or-
minus-one-increment timing remains a real ROAR calibration measurement rather
than a locally proven claim.

## Exact generation command

Run from the project root after applying `embmesh/vuelghost.py` and
`embmesh/cli.py`:

```powershell
python -m embmesh.cli visualize Meshing/Flat.inp `
  --instance Plate-1 --diameter 0.001 --gap 0.001 `
  --output Flat-vuel-ghost-yield-sync --host-mode vuel-ghost `
  --vuel-eps-fail 0.113800332690901 `
  --ghost-ductile-failure-strain 0
```

The new CLI option is independent of `--vuel-eps-fail`; omitting it retains
the source material's original ductile threshold.

## Local verification

- `25 passed` in the staged pytest suite.
- The scale-aware verifier passed all checks: 24,000 VU1 hosts, 24,000
  node-identical ghosts, ghost-only embedded host set, 13 VUEL properties on
  8+5 lines, 24,000 SVAR107 initializations, matching fiber-volume values,
  scaled ghost material/mass, zero ghost initiation strain, and the calibrated
  VUEL threshold.
- Generated and reference `fibers.vtk` SHA-256 values both equal
  `3e2ebf2e5a570355ef656bb1308c123b86fa541a3c6075b408b5a891f635d601`.
- NumPy f2py read `VUEL_failure.for` as strict fixed-form and emitted
  signatures for all six routines. Its missing `vaba_param.inc` warning is
  expected outside Abaqus.

## ROAR gate

Submit with account `rhk12_cr_default`. Measure VUEL failure from SVAR49 or
the `VUEL_FAILURE` messages and ghost deletion from STATUS. The following are
not locally verified and must be checked on ROAR: an actual deletion event,
the plus-or-minus-one-increment synchronization target, completion/diagnostics,
energy and NaN behavior, Abaqus-reported mass, and post-deletion fiber
velocities.
