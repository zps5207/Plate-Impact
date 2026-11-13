task_id: T-051
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-051/analyze_inversion.py
  - outbox/T-051/inversion_summary.json
  - outbox/T-051/INVERSION_FINDINGS.md
  - outbox/T-051/extract_inversion_odb.py
summary: Analyzed all 12 bt1/bt2 local viewer datasets. First observed hex inversions occur on the nose contact surface; sampled aggregate ball deletion generally begins earlier. The all-hex O-grid still reaches 3.95% inversion at 12 us, so original short edges and wedges alone do not explain it. At 500 m/s, first inversion is delayed to 3.87–4.67 us and the 12 us fraction is about 1.5–1.7%. The report ranks candidate mechanisms and fixes, corrects the energy-label scale to J/kJ for SI input, and supplies a read-only per-element ODB extraction script for unresolved causality.
checks_run: Ran analyze_inversion.py successfully on 12 viewer NPZ files and adjacent extract JSON files; confirmed 12 nonempty result records in inversion_summary.json; parsed both Python scripts with ast.parse.
not_verified: Did not access ROAR or any ODB; did not run the Abaqus Python extraction script; did not establish per-element inversion versus deletion order, deleted-neighbor adjacency, or fully unsupported node counts; did not inspect wedge integration-point Jacobians, pair-resolved contact forces, local hourglass energy, damage variables, or installed Abaqus distortion-control syntax; did not run deck changes or new simulations.
suggestions: Run extract_inversion_odb.py on the existing bt1/bt2 ODBs, then match labels to geometric inversion and calculate alive/dead adjacency and orphaned nodes. Use pair-resolved contact output or isolated contact decks to distinguish host from fiber force.
concerns: Viewer geometry persists after element deletion, so the reported inversion fractions may include dead hexes. Aggregate STATUS and coarse frame spacing cannot prove that an element inverts before its own deletion. Contact and hourglass mechanisms remain ranked hypotheses.
denied_actions: none
