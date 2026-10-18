task_id: T-015
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-015/REPORT.md
  - outbox/T-015/analyze_v500.py
  - outbox/T-015-RESULT.md
summary: The 821 v500 hosts with SVAR107 >= 1 are primarily a centerline-length-times-full-fiber-area assignment artifact in small outer-annulus host cells, not demonstrated physical fiber overlap, duplicate segments, or a units error. Four sampled high cells recompute to deck Vf, while numerical cross-section-aware estimates are below 1. Verdict and unapplied patch are in REPORT.md.
checks_run:
  - python outbox/T-015/analyze_v500.py (completed; parsed 24,000 host elements, 13,864 fiber segments, 821 Vf >= 1; recomputed selected deck values)
  - python -m py_compile outbox/T-015/analyze_v500.py (passed)
  - Read embmesh/generate.py, volume.py, geometry.py, fibers.py, writers.py, hostvtk.py, vuelghost.py, cli.py, and uel/VUEL_failure.for.
  - Searched project paths for a v500 fiber_volume.csv or original mesher invocation; none found locally.
not_verified:
  - Original source-deck regeneration or its exact mesher command/settings; the exact v500 run deck was analyzed instead.
  - Cross-section-aware Vf for all 24,000 hosts; only four high-value samples were estimated.
  - Exhaustive geometric intersection/overlap testing of all fibers; only duplicate node-pair segments and layer placement were checked.
  - Solver log mass figure supplied by the Hub, Abaqus reruns, and behavior of proposed patches.
suggestions:
  - Regenerate with cross-section-aware VUEL fractions and a reviewed matrix-fraction floor; record any capped cells and verify mass/energy response before accepting the physics.
concerns:
  - Present SVAR107 makes 821 host matrix elements effectively massless and soft through ETA_VF=1e-6; cap value 0.9 is an illustrative modeling choice requiring review.
denied_actions: none
