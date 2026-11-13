---
name: ball-size-error-vals-inp
description: "Meshing/Vals.inp ball is 3/4 in diameter (r=9.525 mm); Valerie's paper ball is 3/8 in diameter (r=4.7625 mm). User's own error from the first deck; all Vals-derived runs so far used the oversized ball"
metadata:
  node_type: memory
  type: project
  originSessionId: a887e490-d68b-4939-b7a3-2e116a3a90af
  modified: 2026-11-02T22:35:36.507Z
---

Found 2026-11-02 by comparing `References/Valerie's Paper.pdf` (HB26 Dyneema, 1 in x 8 in dia plate, 3/8 in dia steel ball, 1028 m/s, rigid ball) with `Meshing/Vals.inp`. In `Vals.inp` the Ball part spans 9.525 mm in x/y/z, so radius 9.525 mm = 3/8 in as a RADIUS, i.e. 3/4 in diameter, about 8x the mass of the paper's ball. The user confirmed this is their mistake, made in the very first deck they created, and that it distorts the expected result.

**Why:** every deck built from `Vals.inp` (vals-plywise, vp3-vp5, bt1-bt3, d1-d7, vr_native, vr_vuel) inherits the oversized ball, so penetration and ball-plate results are not comparable to the paper or experiment until fixed.
**How to apply:** before any new Vals-based comparison, rescale the ball to r = 4.7625 mm (scale ball nodes about its centre; the instance sits 11 mm above the plate surface, so reposition or the ball starts ~6 mm farther away than the old 1.5 mm gap). Check the ball element size and steel dt after halving. Other open paper differences: speed 1000 vs 1028 m/s, paper ball is rigid (Vals.inp is deformable Johnson-Cook), paper matrix fracture strain 0.1 vs Vals.inp 0.01, fiber layout (paper 1380 FpT has 0 and 90 trusses in each matrix layer, ours one orientation per ply), paper has 3 hex elements through each 1.27 mm layer vs our 1. See [[ball-inversion-investigation]], [[vals-plywise-balltests]].

**Fix in flight (2026-11-02):** `verification/roar/build_vals_ballfix.py` builds `Meshing/vals-plywise-ballfix/{native,vuel}/vrb_{native,vuel}.inp`: rigid ball R=4.7625 mm (64-hex O-grid, ~1.2 mm elements, density scaled to 8406 so rigid mass = true sphere), centre z=6.2625 mm (1.5 mm gap), 1028 m/s, step 7e-5. ROAR dirs `ctv/bt3/vrb_native`, `vrb_vuel`; chains datacheck->solve(afterok)->extract->pack: native 56952458-461, vuel 56952462-465 (16 tasks, 32 GB, 24 h solve). Old vr_vuel chain 56950156-158 cancelled by user request; vr_native/vr_vuel dirs and local `Meshing/vals-plywise-balltests3/results/viewer_vr_native` NOT yet deleted (scope unconfirmed). 3-element-per-ply mesher work delegated to agy as T-053 (`agents/drafter/inbox/T-053.md`), odd counts only. Correction: our host mesh is ~1.22 mm in plane (4025 hex/ply) vs paper 0.5 mm seed near impact (8880/layer).
