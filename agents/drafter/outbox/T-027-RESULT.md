task_id: T-027
role: drafter
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-027/embmesh/stacked.py
  - outbox/T-027/tests/test_stacked.py
summary: |
  Eliminated the fixed node-index ordering assumption (nodes 1-4 vs 5-8) in `embmesh/stacked.py` by implementing per-hex geometric face orientation and node pairing using the reference sign table. Auto-detects the overall stack axis when thickness_axis is None, orients every hex so the bottom face lies at lower stack coordinate, and matches opposite face nodes along identical local coordinate lines. Added layer-fitting tolerance so decks like Flatv2 (9.9999998 mm) place 10 layers instead of 9. Passed full project test suite (72 passed). Verified byte-identical output on `curved_hostonly.inp` against Codex T-025. On the original `Flatv2_curved.inp`, orientation fix reduced mismatch from 1.715 mm to 0.674 mm, but the deck fails the congruence tolerance because the CAE mesh is radially swept rather than an exact translation stack.
checks_run:
  - pytest on outbox/T-027/tests/test_stacked.py (9 passed):
    - test_flat_identical
    - test_curved_containment_and_overlap
    - test_even_chords_on_curved_plate
    - test_world_frame_and_writer
    - test_near_grid_line_has_even_segments
    - test_segment_statistics_with_short_runs_and_json_serializable
    - test_oriented_hex_faces_all_axes_and_signs (all 6 hand-built axis/sign cases)
    - test_scrambled_hex_node_ordering_identical_output (fibers and written deck identical)
    - test_non_congruent_plate_raises_mismatch_error (bumped bottom node raises ValueError)
  - Full project test suite with delivered stacked.py injected: 72 passed in 1.52s.
  - Byte-by-byte comparison on `agents/refiner/outbox/T-024/curved_hostonly.inp` output against `agents/refiner/outbox/T-025/curved_stacked/output.inp`: 100% byte-identical.
  - Mismatch audit on `Meshing/Flat-curved-p0/Flatv2_curved.inp`:
    - Tolerance: 0.0001025 m (102.5 um, 0.11 x median in-plane edge of 0.932 mm)
    - Mismatch min: 4.036e-7 m (0.40 um)
    - Mismatch median: 1.893e-4 m (189.3 um)
    - Mismatch mean: 2.441e-4 m (244.1 um)
    - Mismatch p95: 6.019e-4 m (601.9 um)
    - Mismatch max: 6.739e-4 m (673.9 um)
    - Elements exceeding tolerance: 17,199 of 24,000 (71.7%)
not_verified:
  - Abaqus was not run on the written decks.
  - CLI execution to full deck completion on `Flatv2_curved.inp` was blocked by the congruence check error (`mismatch max 0.0006739 exceeds 0.0001025 m`), as mandated by brief constraint not to loosen tolerances silently.
suggestions:
  - For CAE-exported meshes like `Flatv2_curved.inp` that have radial extrusion variations (where hex layer normals rotate with plate curvature), either: (a) provide a relaxed tolerance flag or relative tolerance based on curvature / slope, or (b) use the new plywise mesher (`plyfibers.py` / `plywise.py`), which constructs exact conforming translation plies from a single hex layer.
concerns:
  - On `Flatv2_curved.inp`, 71.7% of elements exceed the 0.11 * in-plane edge translation tolerance because the source mesh from Abaqus CAE is swept radially rather than translated along a fixed stack vector.
denied_actions: none
