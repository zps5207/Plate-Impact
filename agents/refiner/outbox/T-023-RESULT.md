task_id: T-023
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-023/make_one_element_deck.py
  - outbox/T-023/stack_and_fibers.py
  - outbox/T-023/build_deck.py
  - outbox/T-023/check.py
  - outbox/T-023/compare_stats.py
  - outbox/T-023/Flatv2_curved_1el.inp
  - outbox/T-023/Flatv2_curved_1el.json
  - outbox/T-023/curved_10ply_d096.inp
  - outbox/T-023/curved_10ply_d096.json
  - outbox/T-023/checks.json
  - outbox/T-023/baseline_stats.json
  - outbox/T-023/COMPARE.md
summary: |
  Built a curved 10-ply 24,000-C3D8R-host Abaqus/Explicit deck with shared interface nodes and 10 per-ply embedded-fiber blocks. The fiber diameter is 0.96 mm, NOT the baseline's 1.0 mm: a 1.0 mm centered fiber exceeds the 0.98003 mm normal fit at the curved edge. Kept baseline Ball part, Fiber/Matrix/Mild Steel material laws, velocity -500 m/s, symmetry and rim BCs, 7e-05 s explicit step, bulk viscosity, and general contact. Added both plate-node and fiber-node ball contact with auto thickness. Retained the T0/T90 union fiber elsets. The duplicate-interface-nodes flag is available but was not used. Comparison, limitations, and exact commands are in COMPARE.md.
checks_run: |
  Rebuilt the one-element deck with exposed face-congruence tolerance: source top/bottom XZ mismatch max 76.4195 um, mean 4.53093 um, p95 15.9928 um; max is 8.131% of median in-plane edge. Rebuilt the full deck and ran check.py on the written coordinates. It checked all part element node labels, all set members and duplicate set/part/instance/surface names, material and section references, surface set references, 10 per-ply embedding references, contact references, and section counts. Found 0 missing or duplicate references. Sampled 126,300 segment points; 0 outside their ply. Minimum normal clearance 0.489116 mm versus radius 0.480 mm; minimum outline endpoint clearance 0.480 mm. Merged 320 near-crossing vertices; 0 segments remain shorter than 5% of their local edge. Compared Ball part and the Fiber/Matrix/Mild Steel material blocks byte-for-byte with v500; all matched. Checked velocity, BC and step/bulk-viscosity lines in both decks.
not_verified: |
  Abaqus datacheck/input acceptance, ROAR execution, actual Abaqus stable time increment, impact response, full swept-cylinder clearance against every faceted ply interface, and the unrun duplicate-interface-node variant. Local containment samples are discrete. The baseline VUEL and ghost failure behavior cannot be reproduced in the native C3D8R deck required by this brief.
suggestions: |
  Run Abaqus datacheck before the ROAR impact job. Pay attention to the fiber-controlled increment and to the constitutive difference from the VUEL baseline.
concerns: |
  Minimum segment is 28.5507 um despite passing the relative 5% threshold; length/sqrt(E/rho) is about 2.00 ns versus 65.36 ns for the shortest baseline segment. The deck's active native Matrix C3D8R plate differs materially from v500's active VU1 plus ghost host, so an impact response difference cannot be attributed only to curvature and plywise fibers. Per-ply fibers increase total fiber volume from 1.02782e-5 to 1.43971e-5 m3.
denied_actions: none

reproduce: |
  From agents/refiner:
  python -B outbox/T-023/make_one_element_deck.py inbox/T-022/Flatv2_curved.inp outbox/T-023/Flatv2_curved_1el.inp
  python -B outbox/T-023/build_deck.py outbox/T-023/Flatv2_curved_1el.inp "../../Flat-nodecontact/v500/output.inp" outbox/T-023/curved_10ply_d096.inp
  python -B outbox/T-023/check.py outbox/T-023/curved_10ply_d096.inp outbox/T-023/Flatv2_curved_1el.inp outbox/T-023/checks.json
  python -B outbox/T-023/compare_stats.py "../../Flat-nodecontact/v500/output.inp" outbox/T-023/baseline_stats.json
