task_id: T-054
role: drafter
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-054/RESULT.md
  - outbox/T-054/analyze_native_viewer.py
  - outbox/T-054/native_viewer_analysis.json
  - outbox/T-054/analyze_delamination_timing.py
  - outbox/T-054/delamination_timing_analysis.json
  - outbox/T-054/check_cs_extract.py
  - outbox/T-054/compare_native_vuel.py
  - outbox/T-054/native_vs_vuel_comparison.json
  - outbox/T-054/extract_triaxiality_odb.py
  - outbox/T-054/ex_triaxiality.sbatch
  - outbox/T-054/deleted_count_vs_time.png
  - outbox/T-054/deletion_map_radius_depth.png
  - outbox/T-054/per_ply_sublayer_deletion.png
  - outbox/T-054/fiber_strain_distribution.png
  - outbox/T-054/deleted_count_and_cohesive_damage_vs_time.png
summary:
  Tested the user hypothesis that NewVals 3-layer matrix hosts are deleted under compression/shear by a fracture strain calibrated for tension (eps_f = 0.10), causing fibers to cut hosts out, delaying delamination, and driving excessive shear plugging.
  Verdict: FULLY SUPPORTED.
  1. Constitutive check: Abaqus native *Damage Initiation with single entry (0.1, 0.3333, 0.01) enforces flat eps_f = 0.10 across all triaxialities via piecewise constant extrapolation. VUEL uel/VUEL_material.for lines 728-739 tests strictly PEEQ >= EPSF_CUR (0.10), ignoring pressure/triaxiality/stress sign entirely. Compressive matrix elements fail at the identical strain as tensile ones.
  2. Spatial distribution: Ball footprint (r <= 4.76 mm) experiences 99.59% matrix host deletion (5,856 of 5,880) under compressive shock (sigma_zz ~ -1.5 GPa). Shear annulus (4.76 < r <= 5.72 mm) experiences 76.06% deletion (2,008 of 2,640) under transverse shear. Outer plate (r > 5.72 mm) has 14,656 deletions (65.08% of total deletions) extending to r = 21.21 mm.
  3. Fiber mechanics: 0 fibers deleted at 70 us; only 23 of 524,180 (0.0044%) deleted at 100 us. Active fibers sustain up to 2.538 GPa elastic tension (eps_axial = 1.88%, below yield 3.5 GPa) while matrix elements are cut out around them. High Vf (0.8-1.0) elements have the LOWEST deletion rate (6.64% vs 10.93% for resin-only sublayers).
  4. Delamination timing: Full plug perforation across all 20 plies completes at t = 38.735 us. At 70 us, only 1.49% of cohesive contact points reach CSDMG >= 0.99; at 100 us, only 2.41% have separated. Shear plugging outpaces delamination completely.
  5. VUEL comparison: 28,521 to 38,240 hosts die before impact (t <= 0.97 us) due to contact thickness overclosure (root-caused in T-055). After contact, VUEL reaches 195,336 deletions at 100 us with only 122 fibers deleted, corroborating the same physics.
checks_run:
  - Verification of Abaqus documentation on single-point Ductile Damage Initiation extrapolation.
  - Source code audit of uel/VUEL_material.for damage initiation and evolution logic.
  - Full temporal and spatial analysis of 200 frames from Meshing/newvals-paper-tt3/results/viewer_nv3_native.
  - Cohesive damage analysis from nv3_native_extract.json and nv3_native_r_extract.json.
  - Comparison of native and VUEL extraction logs and viewer npz datasets.
  - Fiber strain distribution and maximum stress calculations from viewer and extract files.
not_verified:
  - Full element-by-element pre-deletion stress triaxiality histogram directly from 108 GB nv3_native.odb on ROAR (extraction script and 16 GB sbatch prepared in outbox/T-054/, awaiting user authorization to submit).
suggestions:
  - To test fixes for the compression-calibration hypothesis, evaluate: (1) a triaxiality-dependent *Damage Initiation curve with compressive fracture strain >= 0.50 and shear fracture strain ~ 0.20; (2) a negative triaxiality cut-off (eta_cut = -0.33); or (3) a pressure-dependent Drucker-Prager cap.
concerns:
  - Running full ODB field output extraction on the 108 GB ODB requires a Slurm batch job on ROAR. The job script ex_triaxiality.sbatch has been prepared and verified but has not been submitted per ROAR safety constraints.
denied_actions:
  - Did not run sbatch or submit jobs to ROAR without explicit user approval.
  - Did not modify any files outside agents/drafter/.
