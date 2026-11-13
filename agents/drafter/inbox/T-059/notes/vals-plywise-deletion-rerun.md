---
name: vals-plywise-deletion-rerun
description: "2026-10-20 Vals plywise rerun with element deletion on for all elements (fibers were never deleting): jobs 56580052-055 in ctv/vp4, what to check, fiber-blowup tasks T-043/T-044"
metadata:
  node_type: memory
  type: project
  originSessionId: 30e1470b-e980-4b87-b8d2-71d6dc0d637e
  modified: 2026-10-20T14:45:21.771Z
---

First Vals plywise pair (vp3, jobs 56574395/397, report `reports/VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html`) both perforated; fibers blew up (fiber nodes moved up to 290 mm, host node speeds to 77 km/s, ALLKE far above the 3.5 J ball). Cause found in the decks: fiber T3D2 `Fiber` material and the steel ball had `*Damage Initiation` only, no `*Damage Evolution`, and no section controls, so they could never delete.

**Rerun (user ordered 2026-10-20, 32 GB each):** decks built by `build_vals_plywise.py --element-deletion Meshing/vals-plywise Meshing/vals-plywise-del` (adds `*Damage Evolution, type=DISPLACEMENT 0.` to Fiber and Mild Steel, `*Section Controls EMBMESH_DELETE_ALL element deletion=YES`, `controls=` on every Solid Section; VUEL ghost keeps its own controls). ROAR dir `/storage/home/zps5207/scratch/ctv/vp4/{vals_vuel,vals_native}`; chain: VUEL datacheck 56580052 -> solve 56580053; native datacheck 56580054 -> solve 56580055 (waits for the VUEL solve).

**Check first:** the datacheck. Unverified: whether Abaqus accepts ductile `*Damage Evolution` on T3D2 truss elements (datacheck will show). The ball now also erodes (JC damage), a deliberate consequence of "all elements".

Viewer pipeline reused: `ctv/scripts/export_viewer_plywise.sbatch` with `export_odb_viewer_plywise.py` (native fallback host = PLY elsets), then `pack_viewer_data.py`, `serve_viewer.py`, `verification/roar/build_vals_report.py`. Briefs T-043 (Codex, data analysis) and T-044 (agy, mechanism) were written for the blow-up; not yet run by the user when written. See [[vals-plywise-run-checklist]], [[roar-ssh-access]].
