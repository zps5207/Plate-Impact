task_id: T-028
role: refiner
status: BLOCKED
files_changed:
  - outbox/T-028/embmesh/plywise.py
  - outbox/T-028/embmesh/cli.py
  - outbox/T-028/tests/test_plywise.py
summary: Implemented ply-count resolution, per-hex oriented faces, translation check, ply Part and instance writer, interface pair names, and a plywise CLI command. The synthetic deck reparses, preserves total volume, and has coincident interfaces. Completion is blocked by the required approval for the two large deck runs and by conflicting geometry requirements for the original curved deck.
checks_run:
  - Full local suite with delivered plywise module and CLI injected: 67 passed.
  - Synthetic scrambled ordering, mixed local axes, rejection of nontranslation, surface IDs, material section, instance offsets, volume, interfaces, CLI and old-instance reference reporting covered by tests.
not_verified:
  - Neither requested large deck was run; approval was requested and had not arrived.
  - Abaqus was not run.
  - Original curved deck volume preservation and interface coincidence were not verified.
  - Written deck validity for retained assembly references was not verified.
suggestions:
  - Resolve the original curved deck's nonuniform top-to-bottom offsets: T-027 reports up to 76 micrometers. Per-node interpolation makes copied-ply interfaces differ by up to that residual divided by ply count; a single uniform translation can make interfaces coincide but changes the prescribed per-node geometry. Choose which requirement governs, then run the two large decks sequentially after approval.
  - Decide how assembly sets, surfaces and boundary conditions should map onto the new ply instances before using the deck in Abaqus.
concerns:
  - The original deck references Plate-1 in assembly Nsets Outside, X, Y and plate; Elsets Outside, X, Y, plate and _Surf-1_S2/S3/S4. The clean curved deck references Plate-1 in assembly Nsets Outside, X, Y and plate; Elsets plate and _Surf-1_S1/S3/S4/S5/S6. These are reported by the writer but left unchanged; the replaced instance name makes them unresolved.
  - The relative translation tolerance permits nonzero offsets that can exceed the required 1e-9 m interface coincidence threshold. The writer reports expected_interface_gap_max and does not silently claim exact coincidence.
denied_actions: none
