# T-048 ROAR extraction handoff for Claude Code

Please run the accompanying `extract_odb.py` against the **existing** five T-046 ODBs. This is read-only ODB access; no solver job or `sbatch` is needed. Copy the resulting five JSON files back to `agents/refiner/inbox/T-048-odb/` (or give me their local path). If the script fails, return its error and the Abaqus version. Do not replace the existing ODBs or alter T-046's run directory.

## Input ODBs

Local copies are in `agents/drafter/outbox/T-046/tests/results/`:

- `t046_sol1.odb` — lone T3D2 fiber
- `t046_sol2.odb` — native host plus embedded and free fiber segments
- `t046_sol3.odb` — ghost C3D8R plus embedded and free fiber segments (**no VUEL in this deck**)
- `t046_sol4.odb` — 3 x 3 native host block plus fiber
- `t046_sol5.odb` — lone host mass test

The extraction script is `agents/refiner/outbox/T-048/extract_odb.py`. If ROAR must be used, copy the script and ODBs into an independent directory under `/storage/home/zps5207/scratch/ctv/t048/`. Example command there, repeated for `1` through `5`:

```bash
abaqus python extract_odb.py t046_sol1.odb t046_sol1.json
```

This uses Abaqus Python to read each ODB and writes per-frame STATUS, S, LE, PEEQ, U, V, A, RF, any damage and mass fields actually present, all history outputs, and the element labels/types/connectivity. It also records available field names so missing fields are explicit. Five JSON files are the preferred return data. The ODBs are small (under 2 MB each), so returning the original five ODBs is also fine if Claude Code can provide working `odbAccess` locally.

## Checks I will make from the returned data

1. **Test 1:** first frame with truss STATUS 0; preceding frame's LE11/PEEQ/S11 and node U. Compare actual failure strain with the 4.56–4.72% prescribed extension bracket from `.sta`.
2. **Tests 2–4:** first STATUS 0 frame for each host/ghost, `FIB_EMB`, and `FIB_FREE` element. State which deleted first, report frame-time uncertainty, and check stress/strain in the last alive frame. In test 4, map the nine host labels to see whether center-row failure propagated in sequence.
3. **Test 3:** check ghost-versus-fiber order only. The current deck cannot establish VUEL-versus-ghost order because it contains no VUEL.
4. **Test 5:** inspect any reported mass field/history, host STATUS, nodal V/A, and ALLKE. The existing deck keeps the pull nodes under prescribed displacement and gives no known post-deletion free-node force, so it may remain incapable of proving retained versus removed nodal mass. If no direct mass observable exists, report that explicitly; do not infer mass retention from ALLKE reaching zero.
5. **General:** identify missing requested fields, solver warnings, and whether any element disappears from an output field without an explicit STATUS 0 value. A missing field value is not by itself proof of deletion.

No new solve is requested here. If a revised test-5 solve is needed, prepare its deck and request the user's per-`sbatch` approval before submission, as required by `agents/refiner/ROAR_SSH.md`. Use an independent `ctv/t048/` directory and `t048_` job name for any approved new job.
