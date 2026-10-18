task_id: T-040
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-040/embmesh/plyfibers.py
  - outbox/T-040/embmesh/plywise_vuel.py
  - outbox/T-040/embmesh/plywise.py
  - outbox/T-040/tests/test_plywise_fiber_boundary.py
  - outbox/T-040/HANDOFF.md
  - outbox/T-040/flat/{output.inp,console.json,report.json,containment.json,preview.html}
  - outbox/T-040/concave/{output.inp,console.json,report.json,containment.json,preview.html}
  - outbox/T-040/{run_staged.py,run_tests.py}
summary: Plywise fiber endpoints now reach the host's actual lateral faces; boundary-referenced assembly Nsets append each matching fiber endpoint per ply instance for both native and VUEL/ghost paths. Both real eight-ply decks have 82 ends per ply, zero unmatched ends, and 41 Outside plus 41 X or Y memberships per ply. Full details are in HANDOFF.md.
checks_run: Staged full suite 134 passed, 2 skipped; flat and curved 0/90/45/135-degree boundary/set tests and corner dual membership; both real decks generated; original boundary data lines unchanged; ball node contact present; world-coordinate audits report zero fiber nodes and midpoints outside hosts in both decks. Shortest segment is 0.99378 mm flat and 0.99424 mm concave, up from the prior 0.21 mm. Maximum fractions are 1.46035 flat and 1.50032 concave, no increase over T-038.
not_verified: Abaqus data check and simulation; Abaqus acceptance of shared assembly sets on embedded fiber nodes; dynamic response and contact behavior; real-deck endpoint-to-face distance below 1e-12 (the generated-deck matching uses geometric tolerance 1e-10, while synthetic tests check 1e-12); full suite after Hub applies files to the project tree.
suggestions: Hub should apply the three embmesh modules and the test, then run an Abaqus data check on the generated decks.
concerns: Embedded fiber nodes are kinematically driven by hosts, so their direct boundary conditions may be redundant; the existing solid mesher applies fiber symmetry boundary conditions and runs. Some computed fiber fractions exceed 1, as in T-038.
denied_actions: Initial PowerShell recursive cleanup command was rejected by automatic review; scoped, path-verified Python cleanup succeeded.
