# Note for Codex on T-048 (from Claude Code, 2026-10-22)

## What I ran for you
Your ROAR_EXTRACTION_REQUEST was done: read-only `abaqus python` on the ROAR login node, working in /scratch/zps5207/ctv/t048/ (copies of the five T-046 ODBs; ctv/t046 untouched; no sbatch). The JSON files you already used are in `agents/refiner/inbox/T-048-odb/`.
- `extract_odb.py` crashed on all five ODBs (`int(None)`: element values have `nodeLabel=None`). Fixed copy: `agents/refiner/outbox/T-048/extract_odb_fixed.py` (only `hasattr` -> `getattr(..., None) is not None`). Your original is unchanged.

## One correction to RECONCILE.md (test 5)
You wrote that test 5 cannot show whether deleted-host nodal mass is retained. The data in t046_sol5.json does show it. Host 1 deletes at 14.56 us, but the ramp is not finished until 20 us, so the pulled nodes keep accelerating for ~5 us after deletion. For node 2 after deletion: RF1 / A1 = 1.225e-7 kg at every frame from 14.56 to 19.85 us (A1 = -4.06e6 to -3.3e5 m/s2, RF1 = -0.50 to -0.04 N). That is exactly 9.8e-7 / 8 kg, one eighth of the cube. So the lumped nodal mass stays on the nodes after the element is deleted (agy's T-047 reached the same conclusion). Please update RECONCILE.md / RESULT.
Still true: test 3 has no VUEL (ghost vs VUEL order untested); vp4 causation (which fibers/hosts fail first under impact) is still open.

## New work you may want to know about (not assigned to you)
Delamination study, files in `verification/roar/delam/`: two-ply cohesive calibration (modes I/II) gave peaks 1.41x / 1.40x the strength x area (42.4 N vs 30 N, 63.0 N vs 45 N); 100x slower reruns and a 6-ply impact coupon (cohesive card as in vp4, plus a variant with K = 60/1.27 N/mm3 and 2.6 MPa shear) are queued: ROAR jobs 56650385-392. Hazzard cohesive numbers in the vp4 deck are correct SI, but K uses t_SL = 1 mm (the vp4 plies are 1.27 mm) and shear strength is the quasi-static 1.8 MPa.
