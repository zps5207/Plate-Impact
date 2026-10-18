task_id: T-032
role: refiner
status: BLOCKED
files_changed:
  - outbox/T-032/embmesh/plywise.py
  - outbox/T-032/embmesh/cli.py
  - outbox/T-032/tests/test_plywise.py
  - outbox/T-032/verification/verify_large_runs.py
  - outbox/T-032/verification/diagnose_layers.py
summary: |
  Fixed the ply construction to use one median translation vector, with expected_interface_gap_max = 0 and stacked-top residual statistics. The writer now bakes the source instance transform into the Part nodes, writes pure-translation Ply-k instances, emits CAE-style assembly surfaces named Ply-k_bottom/top, and replicates old-instance assembly Nset/Elset blocks for each ply. It leaves _Surf-1_S* impact-surface elsets for a later task. The interface pair names now reference the assembly surfaces.
  Both approved real inputs fail the required one-hex-through-thickness precondition before a deck is written. Flatv2_curved.inp has 27,401 nodes and 24,000 hexes, with 25,513 nodes classified on both bottom and top of different elements; curved_hostonly.inp has the same node/hex counts and 24,919 such nodes. These are multilayer meshes (T-024 also describes curved_hostonly.inp as 10-layer), so the requested plywise output cannot validly be produced from either input. A one-hex-thick input deck is needed for the two runs.
checks_run:
  - Full local suite with delivered files overlaid on the project package: 68 passed in 1.57 s.
  - Synthetic reparse, volume, interface, assembly-surface, set-rewrite, and rotated-instance tests passed.
  - Attempted the first approved real run; it raised EmbmeshError for a nonconforming one-hex layer before writing output. Diagnosed both real input meshes independently.
not_verified:
  - Neither real deck was written or reparsed; no real-deck volume, interface-gap, stacked-top residual, ply thickness, or successful runtime metric exists.
  - Abaqus was not run.
  - Retained _Surf-1_S* impact-surface elsets still refer to Plate-1, by instruction; Abaqus acceptance of that wiring was not verified.
suggestions:
  - Supply one-hex-through-thickness plate decks corresponding to each requested case, or issue a new brief explicitly authorizing a conversion from the existing multilayer decks before plywise processing.
concerns:
  - The specified cleanup of outbox/T-028/pytest_full_tmp and __pycache__ could not be completed after the recursive deletion command was rejected by automatic policy.
denied_actions:
  - Automatic approval review rejected the recursive Remove-Item cleanup command for the named directories in outbox/T-028; no files outside the refiner folder were targeted.
