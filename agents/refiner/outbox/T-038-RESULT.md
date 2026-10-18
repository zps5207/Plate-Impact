task_id: T-038
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-038/embmesh/plywise_vuel.py (new multi-ply VU1/ghost conversion, per-ply SVAR107, surface remap, diagnostics, symmetry)
  - outbox/T-038/embmesh/plywise.py (small host-mode hook, ghost embedding, reporting)
  - outbox/T-038/embmesh/cli.py (plywise host-mode and VUEL/ghost flags)
  - outbox/T-038/tests/test_plywise_vuel.py (conversion and assembly symmetry tests)
  - outbox/T-038/HANDOFF.md (counts, findings, application instructions)
  - outbox/T-038/Flatv2_8ply/output.inp and report.json
  - outbox/T-038/concave_8ply/output.inp and report.json
  - outbox/T-038/plate1hex_curved_ball_private.inp and plate1hex_4ply/output.inp and report.json
  - outbox/T-038/run_overlay.py (private runner for outbox code)
summary: Converted the common ply Part once to node-coincident VU1 and scaled C3D8R ghosts, emitted per-instance SVAR107 fractions and diagnostic sets, remapped every ply's cohesive surfaces to ghost labels, embedded fibers in ghosts, and propagated X/Y plane constraints to fiber instance node sets. Both requested virgin decks were generated with 19,200 VU1 and 19,200 ghost elements each across eight plies; 40 fibers per ply. Ghost scale 1e-4, expected combined host mass ratio 1.0001. Small real deck generated with 9,600 VU1 and 9,600 ghosts. The unchanged solid converter preserves single-instance output. Details and per-ply fraction statistics are in HANDOFF.md and report.json.
checks_run: Two new focused tests passed; unchanged solid VUEL converter tests passed; 107 tests passed with two overlay-incompatible test files excluded; both virgin decks and small deck reparse; each virgin deck has eight SVAR107 blocks and eight ghost embedding blocks; ball node contact built for both virgin decks. Unfiltered suite returned 119 passed, one skipped, two failures because two existing tests replace the outbox overlay with project modules during collection.
not_verified: Abaqus/ROAR datacheck and 500 m/s run; Abaqus acceptance of VU1 hosts with node-coincident ghosts, multi-instance *Initial Conditions sharing one Part, and assembly-level embedded constraints; dynamic stiffness, failure, contact, and energy behavior; physical validity of volume fractions >=1; full suite against installed project files after Hub applies the deliverables.
suggestions: Hub should apply only the four code/test files named in HANDOFF.md, then run a ROAR datacheck and 500 m/s smoke test; review fiber diameter/pitch because some local fractions exceed 1 and the VUEL floors their matrix fraction.
concerns: Flatv2 has 17 cells per 0-degree ply and 21 per 90-degree ply with fraction >=1 (max 1.46035); concave has 17 and 19 (max 1.50065). Requested diameter 0.001 m is 0.8 times ply thickness. Real generated fiber nodes on X/Y planes number zero per ply; focused test verifies nonzero propagation. The brief's reference to outbox/T-037 conflicts with task ID T-038, so deliverables are under outbox/T-038 per protocol.
denied_actions: none
