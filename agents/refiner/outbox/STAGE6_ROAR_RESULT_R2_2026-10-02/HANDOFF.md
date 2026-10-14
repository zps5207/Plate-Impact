# Stage 6 round 2: positive-epsilon ghost threshold

## Ready-to-run files

- Deck: `Flat-vuel-ghost-yield-sync-eps1e-6/output.inp`
- Abaqus user subroutine: `uel/VUEL_failure.for`
- Source changes: `embmesh/vuelghost.py`, `embmesh/cli.py`
- Regression test: `tests/test_vuelghost.py`
- Static verifier/evidence: `verify_flat_vuel_ghost_yield_sync.py` and
  `Flat-vuel-ghost-yield-sync-eps1e-6/static_verification.json`
- Fixed-form parser output: `VUEL_failure.pyf`

SHA-256:

- `output.inp`: `02726e8768425af25a188683b357a2c7143213b5bda1b8913d229db3c945df70`
- `VUEL_failure.for`: `ad65dd27ae6eacedbb64df73fea90d1f030911846ac067950b744c3cac3838ef`

## Exact round-2 fix

The rejected deck and this deck differ at exactly one Abaqus input line:

```diff
 *Damage Initiation, criterion=DUCTILE
-0, 0, 0
+1e-06, 0, 0
```

Its `report.json` correspondingly changes
`ghost_ductile_failure_strain` from `0.0` to `1e-06`. No other deck line
changed. In particular, VUEL `EPS_FAIL=0.113800332690901`, zero displacement
evolution, `JAC_FAIL=0.05`, `DEGRADE_TIME=0`, impact conditions, mesh,
embedding, and fiber geometry are unchanged.

The generator now requires an explicitly supplied
`--ghost-ductile-failure-strain` to be strictly positive. A new regression
test proves that zero is rejected before generating an Abaqus-invalid deck.

## Exact generation command

```powershell
python -m embmesh.cli visualize Meshing/Flat.inp `
  --instance Plate-1 --diameter 0.001 --gap 0.001 `
  --output Flat-vuel-ghost-yield-sync-eps1e-6 --host-mode vuel-ghost `
  --vuel-eps-fail 0.113800332690901 `
  --ghost-ductile-failure-strain 1e-6
```

## Local verification

- `26 passed` in the staged pytest suite, including the new nonpositive-value
  rejection test.
- Scale-aware verification passed every check: 24,000 VU1 hosts, 24,000
  node-identical ghosts, ghost-only embedding, 13 VUEL properties split 8+5,
  all 24,000 SVAR107 initializations, scaled ghost material/mass, exactly
  `1e-6` ghost ductile threshold, and calibrated VUEL threshold.
- Generated and reference fiber VTK SHA-256 values are identical:
  `3e2ebf2e5a570355ef656bb1308c123b86fa541a3c6075b408b5a891f635d601`.
- NumPy f2py read the unchanged `VUEL_failure.for` as strict fixed-form and
  emitted signatures for all six routines. The missing `vaba_param.inc`
  warning is expected outside Abaqus.

## ROAR gate

Submit using account `rhk12_cr_default`. Abaqus input acceptance and the full
solve remain the next gate. If it runs, measure VUEL failure from SVAR49 or
`VUEL_FAILURE` messages and ghost deletion from STATUS, then check the
plus-or-minus-one-increment synchronization target, energies/NaNs, mass, and
post-deletion fiber velocities.
