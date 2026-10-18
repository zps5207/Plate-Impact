# T-040 handoff

Deliverable code mirrors `embmesh/` and the new test mirrors `tests/`. The two generated decks and reports are in `flat/` and `concave/`. Apply the three Python modules and the test; `run_staged.py` and `run_tests.py` are outbox-only overlay runners.

## Changes

- Ply fibers now use the full mid-surface boundary interval. The lateral radius/end offsets are removed; through-thickness diameter validation remains. Equal-chord resampling and target segment choice are unchanged.
- For every assembly `*Nset` named in a `*Boundary` data line, the finishing pass identifies per-ply lateral host faces whose four nodes belong to that set. Each fiber endpoint on a face is appended to the same assembly set for its `Fibers-Ply-k` instance. Existing `*Boundary` lines are unchanged. A corner may join multiple sets. Both native and VUEL/ghost paths use the hook.
- Metadata `fiber_boundary_nodes_per_ply` reports per-set end counts, total fiber nodes, total ends, and unmatched end labels. Zero unmatched means every end intersects some lateral face. Fiber volume uses `fiber_volume_rows`, which clips to host elements and did not assume the old inset.

## Real decks

Both commands use the options in `verification/roar/build_plywise_500.py`; its step patch was applied after deck generation. The original three boundary data lines (`Outside, ENCASTRE`, `X, XSYMM`, `Y, YSYMM`) are byte-identical in both output decks. Ball node contact is present in both reports.

| Deck | Ply angles | Fiber ends per ply | Outside | X | Y | Fiber nodes per ply | Segment min / median / max (mm) | Nodes / midpoints outside |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Flat | 0° (plies 1,3,5,7) | 82 | 41 | 41 | 0 | 1608 | 0.99378 / 1.02090 / 1.04835 | 0 / 0 |
| Flat | 90° (plies 2,4,6,8) | 82 | 41 | 0 | 41 | 1608 | 0.99378 / 1.02090 / 1.04835 | 0 / 0 |
| Concave | 0° (plies 1,3,5,7) | 82 | 41 | 41 | 0 | 1614 | 0.99424 / 1.02219 / 1.04917 | 0 / 0 |
| Concave | 90° (plies 2,4,6,8) | 82 | 41 | 0 | 41 | 1614 | 0.99424 / 1.02219 / 1.04917 | 0 / 0 |

Each ply has zero unmatched fiber ends. The shortest segment increased from the prior reported 0.21 mm to approximately 0.994 mm because paths now span the entire width and equal-chord spacing is recomputed over the full path. The target segment length remains approximately 1 mm.

The maximum computed fiber fraction is 1.46035 (flat) and 1.50032 (concave). T-038 reported 1.46035 and 1.50065 respectively, so the boundary change caused no unexplained increase. Some fractions still exceed 1, which predates this task.

The world-coordinate audit used `agents/drafter/outbox/T-029/check_written.py` on each written deck. It reports zero outside fiber nodes and zero outside segment midpoints for both. Fiber end nodes on a host boundary count as inside.

## Checks

- Staged full suite from project root: **134 passed, 2 skipped**.
- Synthetic flat and curved 0°, 90°, 45°, 135° fibers: every end matched a host boundary quad within 1e-12; face-specific memberships on two ply instances; corner joins two symmetry sets; output boundary lines unchanged.
- Both real decks generated and their output reports inspected. Ball contact was built in both.

Abaqus data check and simulation were not run. Embedded-element nodes are kinematically driven by their hosts, so direct boundary conditions on those fiber nodes may be redundant. The existing solid mesher applies symmetry conditions to fiber nodes and runs; this follows that precedent. Abaqus acceptance of the new shared assembly sets has not been verified.
