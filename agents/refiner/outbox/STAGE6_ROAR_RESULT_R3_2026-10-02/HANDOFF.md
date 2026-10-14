# Stage 6 round 3: ghost constitutive diagnostics

## Ready-to-run files

- Instrumented deck: `Flat-vuel-ghost-diagnostics/output.inp`
- Abaqus user subroutine: `uel/VUEL_failure.for` (unchanged)
- Mesher source change: `embmesh/vuelghost.py`
- Regression test: `tests/test_vuelghost.py`
- Static verifier/evidence: `verify_flat_vuel_ghost_diagnostics.py` and
  `Flat-vuel-ghost-diagnostics/static_verification.json`
- Remote ODB summarizer: `extract_ghost_diagnostics.py`
- Fixed-form parser output: `VUEL_failure.pyf`

SHA-256:

- `output.inp`: `d5f0e5d25e0432059737c4089a091e34fac36d0e6ba01777f5ee7acf3c818a3e`
- `VUEL_failure.for`: `ad65dd27ae6eacedbb64df73fea90d1f030911846ac067950b744c3cac3838ef`
- `extract_ghost_diagnostics.py`: `23fd9cbab96cbbc695195e38b006b28713298a0df7354ab0e51b9ea110dbdaf4`

## What changed

The successful round-3 physics and calibration are intentionally unchanged:

- VUEL `EPS_FAIL=0.113800332690901`
- ghost ductile failure strain `1e-6`
- zero displacement damage evolution
- `JAC_FAIL=0.05`, `DEGRADE_TIME=0`
- impact, step, mesh, materials, embedding, and fibers unchanged

The mesher now creates an assembly-level set named
`EMBMESH_GHOST_DIAGNOSTICS` containing exactly all 24,000 ghost elements and
adds this request immediately before each `*End Step`:

```text
*Output, field, number interval=1000
*Element Output, elset=EMBMESH_GHOST_DIAGNOSTICS
S, LE, PEEQ, SDEG, STATUS
```

`S` and `LE` were included with the requested `PEEQ`, `SDEG`, and `STATUS` so
the next run can distinguish among these cases:

1. the ghost never reaches its native yield surface (`PEEQ=0`);
2. plasticity occurs but ductile initiation does not (`PEEQ>0`, `SDEG=0`);
3. damage initiates without deletion (`SDEG>0`, `STATUS=1`);
4. deletion occurs (`STATUS=0`).

After mechanically removing only the new diagnostic set and output block, the
new deck is line-for-line identical to the successful round-3 deck. No new
failure threshold is guessed before observing the native constitutive state.

## Exact generation command

```powershell
python -m embmesh.cli visualize Meshing/Flat.inp `
  --instance Plate-1 --diameter 0.001 --gap 0.001 `
  --output Flat-vuel-ghost-diagnostics --host-mode vuel-ghost `
  --vuel-eps-fail 0.113800332690901 `
  --ghost-ductile-failure-strain 1e-6
```

## Local verification

- Staged pytest: `26 passed`.
- Scale-aware verifier: all 23 checks passed, including exact diagnostic-set
  membership, exact diagnostic variables, 1,000 output intervals, 24,000
  VU1/ghost pairs, SVAR107 initialization, material scaling, and calibration.
- Generated/reference fiber VTK hashes remain identical:
  `3e2ebf2e5a570355ef656bb1308c123b86fa541a3c6075b408b5a891f635d601`.
- The ODB summarizer passes local Python syntax compilation. Its Abaqus ODB API
  execution cannot be tested without Abaqus.
- NumPy f2py parsed the unchanged VUEL as strict fixed-form and emitted all six
  routine signatures; the absent `vaba_param.inc` warning is expected locally.

## ROAR run and extraction

Submit with account `rhk12_cr_default`. After completion, run on ROAR:

```text
abaqus python extract_ghost_diagnostics.py flat_vg_r4.odb \
  --output ghost_diagnostics.csv
```

The CSV reports per frame: maximum ghost Mises stress, maximum absolute
principal logarithmic strain, maximum PEEQ, maximum SDEG, minimum STATUS, and
the number of deleted ghost elements. The decisive first check is whether
`max_peeq` ever becomes positive. Keep the VUEL stdout trigger timestamps for
comparison with the CSV frame times.
