task_id: T-036
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-036/embmesh/collapse.py
  - agents/drafter/outbox/T-036/embmesh/plywise.py
  - agents/drafter/outbox/T-036/embmesh/cli.py
  - agents/drafter/outbox/T-036/tests/test_collapse.py
  - agents/drafter/outbox/T-036/run_flatv2/flatv2_plywise_8plies.inp
  - agents/drafter/outbox/T-036/run_flatv2/meta.json
  - agents/drafter/outbox/T-036/run_concave/concave_plywise_8plies.inp
  - agents/drafter/outbox/T-036/run_concave/meta.json
  - agents/drafter/outbox/T-036/real_runs_summary.json
summary: |
  Implemented a "layers to one hex" collapse step for the plywise mesher enabling virgin multi-layer solid plate decks to go directly into `embmesh plywise`:
  - New module `embmesh/collapse.py`:
    * `collapse_layers(deck, instance='Plate-1', thickness_axis=None) -> (new Part, report)`:
      - Uses `pick_thickness_axis(nodes, thickness_axis)` and `oriented_faces` with `_SIGNS` to determine local through-thickness hex axis.
      - Chains conforming hexes into columns by matching adjacent top/bottom quad node sets.
      - Verifies column uniformity (raises `EmbmeshError` with offending columns if layer counts differ).
      - Reconstructs one trilinear C3D8 hex per column preserving bottom face nodes from the first hex and top face nodes from the last hex.
      - Preserves surviving bottom-hex element labels and node labels.
      - Computes volume before/after using `hex_volume`, volume ratio, and translation residual max/mean/p95.
    * `collapse_deck_text(lines, deck, instance='Plate-1', thickness_axis=None) -> (new_lines, report)`:
      - Replaces Part `*Node` and `*Element` blocks with the collapsed mesh.
      - Rewrites part-level and assembly-level `*Nset` (filters to surviving nodes).
      - Rewrites part-level and assembly-level `*Elset` (maps original element labels to collapsed element labels).
      - Rewrites assembly-level element-based `*Surface, type=ELEMENT` and associated `_Surf-*` elsets: maps surviving top/bottom faces to collapsed element and face IDs, drops side faces and records counts.
      - Preserves all `Ball` parts, instances, sets, and surfaces completely untouched.
    * `collapse_deck(source, output, instance='Plate-1', thickness_axis=None) -> report`: convenience wrapper for standalone collapse.
  - Integrated into `write_plywise_deck` and CLI:
    * Added `--collapse-layers` flag to `embmesh plywise`.
    * Runs in-memory collapse prior to `build_ply_part`, feeding the 1-hex plate into `plywise`.
    * Populates `meta['collapse']` with volume ratio, column count, layers per column, residuals, and rewrite metrics.
    * Added standalone `embmesh collapse` CLI command.
  - Verified symmetry sets and boundary conditions:
    * Surviving nodes of `X` and `Y` boundary sets in `Flatv2.inp` remain in their sets and are replicated across all plies (`Ply-1` to `Ply-8`) by `_rewrite_assembly_sets`.
real_runs_metrics:
  Flatv2:
    source: Meshing/Flatv2.inp (24,000 hexes, 27,401 nodes)
    output: agents/drafter/outbox/T-036/run_flatv2/flatv2_plywise_8plies.inp
    columns: 2400 (uniform 10 layers per column)
    elements_collapsed: 2400 C3D8R hexes, 4982 surviving nodes
    volume_before: 1.963369210052e-05 m^3
    volume_after: 1.963369212757e-05 m^3
    volume_ratio: 1.000000001378 (relative difference 1.38e-9)
    residual_max: 7.6772e-05 m (0.0768 mm, < 0.1034 mm tolerance)
    residual_mean: 4.3856e-06 m
    residual_p95: 1.6617e-05 m
    assembly_interface_max_gap: 6.939e-18 m (< 1e-9 m)
    plies_created: 8 (fiber-free)
    ball_instances: ["Ball-1"] (untouched)
    surviving_faces: Surf-1 has S2 (2400) and S1 (2400)
    dropped_side_faces: Surf-1 had 1800 side faces dropped
    symmetry_sets: X and Y replicated across Ply-1 through Ply-8 (9 total each including Ball-1)
  concave_hostonly:
    source: Meshing/Flat-concave-roar/concave_hostonly.inp (24,000 hexes, 27,401 nodes)
    output: agents/drafter/outbox/T-036/run_concave/concave_plywise_8plies.inp
    columns: 2400 (uniform 10 layers per column)
    elements_collapsed: 2400 C3D8R hexes, 4982 surviving nodes
    volume_before: 1.963369248114e-05 m^3
    volume_after: 1.963369248114e-05 m^3
    volume_ratio: 1.000000000000 (exact)
    residual_max: 5.0000e-11 m
    residual_mean: 2.5167e-11 m
    residual_p95: 5.0000e-11 m
    assembly_interface_max_gap: 1.939e-18 m (< 1e-9 m)
    plies_created: 8 (fiber-free)
    ball_instances: ["Ball-1"] (untouched)
    surviving_faces: Surf-1 has S1 (2400)
    dropped_side_faces: Surf-1 had 1800 side faces dropped
    symmetry_sets: X and Y replicated across Ply-1 through Ply-8 (9 total each including Ball-1)
checks_run:
  - Unit test suite in outbox/T-036/tests/test_collapse.py: 8 of 8 passed:
    * test_synthetic_flat_plate_5_layers: verified 5-layer flat plate collapses to 1 layer with matching top/bottom nodes and volume ratio 1.0.
    * test_synthetic_curved_translation_stack: verified 4-layer curved translation stack collapses to 1 layer with residual < 1e-12.
    * test_scrambled_hex_node_ordering: verified cyclic node scrambling gives identical collapsed geometry and node pairings.
    * test_non_uniform_layer_counts_raise: verified non-uniform layer counts raise EmbmeshError.
    * test_sets_and_surfaces_rewritten_no_dangling_labels: verified sets/surfaces are rewritten without dangling labels and Ball part/instance is preserved.
    * test_round_trip_through_embmesh_parser: verified parse_deck round-trips collapsed output cleanly.
    * test_plywise_pipeline_with_collapse_layers: verified write_plywise_deck end-to-end creates plies with meta['collapse'] and 0.0 interface gap.
    * test_invalid_mesh_inputs_raise: verified empty parts and non-C3D8 elements raise EmbmeshError.
  - T-034 test suite: 8 of 8 passed in agents/drafter/outbox/T-034/tests/test_plywise_cohesive_material.py.
  - Baseline test suite: 93 of 93 passed in tests/.
  - Total test count: 109 of 109 passed across all suites.
  - Full sequential runs executed on Meshing/Flatv2.inp and Meshing/Flat-concave-roar/concave_hostonly.inp:
    * Verified volume ratios (1.00000000138 on Flatv2, 1.0 on concave).
    * Verified translation residuals (max 7.68e-5 m on Flatv2, max 5.0e-11 m on concave).
    * Verified interface coincidence (< 1e-17 m on both decks, well under 1e-9 m).
    * Verified set/surface rewrite counts and dropped side-face counts (1800 on both decks).
    * Verified fiber-free 8-ply generation and Ball preservation.
not_verified:
  - Abaqus was not run (neither Abaqus solver nor datacheck was executed).
  - Meshes containing non-hexahedral elements (e.g. wedges, tetrahedra) or non-manifold topology are rejected with errors as designed.
suggestions:
  - When the GUI plywise panel is updated, a checkbox for `--collapse-layers` can be exposed so users can pass solid multi-layer decks directly from the UI.
concerns:
  - None. All geometric tolerances, volume conservation ratios, and symmetry boundary sets check out cleanly.
denied_actions: none
