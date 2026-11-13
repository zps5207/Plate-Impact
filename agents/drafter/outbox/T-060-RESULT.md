task_id: T-060
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-060/build_t060_reports.py
  - agents/drafter/outbox/T-060/VALS_BT3_BALL_TESTS_REPORT.html
  - agents/drafter/outbox/T-060/VALS_BALL_SIZE_FIX_REPORT.html
  - agents/drafter/outbox/T-060/NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html
  - agents/drafter/outbox/T-060/FIBER_HOST_CONTACT_REPORT.html
  - agents/drafter/outbox/T-060/REPORTS_INDEX.html
  - agents/drafter/outbox/T-060-RESULT.md

summary:
  Carried out Round 2 rework of T-059 per the T-060 brief. Completely eliminated invented and '~' approximate numbers, replaced ungrounded values with exact data extractions and quoted project notes, corrected overstatements across all study reports, added missing T-052 deck 12 plate metrics, updated the nv3_fhA100 placeholder, strictly aligned all 29 timeline index entries with their underlying reports, and regenerated all 5 HTML reports cleanly via build_t060_reports.py. Maintained descriptive 'pending' video panels as refiner task T-058 has not yet completed (agents/refiner/outbox/T-058-RESULT.md does not exist). All generated HTML files are well under the 60 MB limit (largest is 1.12 MB).

changed_numbers:
  1. VALS_BALL_SIZE_FIX_REPORT.html (Simulation Results Table):
     - Metric: Oversized 3/4-in ball baseline comparator column.
     - Old: '~3150 J' ALLKE, '~3430 J (-3.2%)' ETOTAL, '~1,800 / 80,500 (2.2%)' host cells, '~70' fibers (ungrounded approximations).
     - New: Exact metrics from d6_rigid_matched_100us evaluated at t = 70.0 us (same end time as vrb):
       - ROAR Solve Job ID: 56873219
       - Initial ALLKE: 3546.1 J
       - Final ALLKE @ 70 us: 3110.7 J (-12.3%)
       - Final ETOTAL @ 70 us: 3464.2 J (-2.31%)
       - Host Cells Deleted: 1,704 / 80,500 (2.12%)
       - Fibers Deleted: 83 / 206,930 (0.040%)
       - Cohesion Damage ge50: 34,664
       - Cohesion Failed (ge99): 4,790
       - Source: Meshing/vals-plywise-balltests3/results/d6_rigid_matched_100us_extract.json at t = 70.0 us.
     - VUEL host cell pairing & validation tone:
       - Old: Reported as 'validating the volume-corrected VUEL formulation'.
       - New: Reported raw numbers and pairing without claiming validation: native C3D8R deletes 611 of 80,500 host cells (0.76%); VUEL deletes 1,222 of 161,000 total sub-elements (80,500 VUEL + 80,500 ghost C3D8R), corresponding to 611 host cell pairs (0.76%).
     - VUEL -20.1% energy loss:
       - Old: 'attributable to internal numerical damping and dead-element energy clearing in the user subroutine' (speculation).
       - New: 'The physical or numerical mechanism driving this difference (-20.1% vs -6.3% in native) remains unexplained / open.'

  2. VALS_BT3_BALL_TESTS_REPORT.html:
     - Row t052_08 (Table 2):
       - Old: '~4.0%' ball deleted.
       - New: 'result not recorded' (Source: project notes ball-inversion-investigation.md line 23; rerun solve 56847359 completed but numerical deletion was never recorded in project notes).
     - Row t052_12 (Table 2):
       - Old: Missing detailed plate response metrics.
       - New: Stiff elastic ball (10x E: 2.03 TPa): 0.0% ball deleted, 0 alive-inv, stable to 12 us; back-face uz = -2.8 mm; plate hosts deleted 16.7% (13,443 / 80,500), fibers deleted 0 / 1,632 (Source: project notes line 25 and reports/t052_plate_response.png).
     - Row d3_elastic_100us (Table 4):
       - Old: ALLKE End '~3100 (22.8 us)', Host Deleted '~600', Fibers Deleted '~30' (invented).
       - New: ALLKE End 'not pulled', Host Deleted 'not pulled', Fibers Deleted 'not pulled'. Retained verified facts: solve 56849548 crashed at 22.77 us, ETOT ratio 0.991 (-0.90%), dt collapsed 1.03e-9 -> 1e-14 s (Source: project notes line 33; extract NPZ on ROAR scratch, not pulled).
     - Row vr_native:
       - Old: '~3150 (70 us)', '-3.2%', '~1,800', '~70' in Tables 3 and 4.
       - New: Removed from BT3 tables as bt3 consists strictly of d1 through d7. 70 us oversized comparison is handled via d6_rigid_matched_100us in the ball-size report.
     - Section 1 Ball Erosion Intro:
       - Old: 'destroying 17% of the ball by 70 us'.
       - New: vp5 deleted 3,161 of 18,500 ball elements (17.1%) by 70 us (Source: vp5-eroding-contact-results.md and VALS_VP5_ERODING_CONTACT_REPORT.html); d4_weldox_100us reached 17.3% ball deletion (3,206 of 18,500 elements) at 100 us (Source: d4_weldox_100us_extract.json and project notes line 37).
     - Section 7 KE Retention & Perforation:
       - Old: 'retaining over 90-97% of its initial kinetic energy. The plate absorbs only ~100-450 J ... projectile perforates the 25.4 mm plate'.
       - New: Clarified as total model kinetic energy retention (ALLKE end / ALLKE start, debris included): d4 = 97.2% (3445.6 J / 3546.1 J), d5 = 88.5% (3139.5 J / 3546.1 J), d6 = 87.3% (3096.6 J / 3546.1 J). Perforation evidence cited from project notes (91-93% of ball nodes past z = -25.4 mm by 50 us) and video reports/d4_weldox_100us.mp4; noted full perforation was not independently re-checked for d5/d6 in this report.

  3. FIBER_HOST_CONTACT_REPORT.html:
     - Section 3 Coupon cx057b Call Mechanism:
       - Old: 'confirming finite-difference perturbation calls'.
       - New: 'the underlying reason for 4 calls per increment is not established'.
     - Section 4 nv3_fhA100 Placeholder Table:
       - Old: Target / Expected predicted values '~435-440 J', '~400 J', '~35,000-40,000', '< 100'.
       - New: Deleted all predicted values; set every metric cell to 'Pending' awaiting ROAR job 57328143 completion.

  4. REPORTS_INDEX.html:
     - Audited all 29 chronological study entries to align strictly with each report's text and numbers:
       - Flat v2 (#10): 85 ghost islands within 10 mm of axis; 1,357 ghosts deleted of 24,000 (flat_v2_report.html).
       - Flat v2 Diagnostics (#11): 74 of 85 surviving ghosts had intact VU1s; ball kept 983 of 1000 m/s and entered all 58 surviving islands while alive (flat_v2_diagnostics_report.html).
       - Flat v2 Workarounds (#12): Node surface deleted all 802 ghost elements within 10 mm of axis (flat_v2_workarounds_report.html).
       - Speed Series (#13, #14): 8 islands at 100 m/s, 2 at 200 m/s, 0 at 300-500 m/s; 30 MP4 videos across all 5 speeds (NODE_CONTACT_SPEED_SERIES_REPORT.html).
       - Fiber Contact (#15): Peak fiber nodes inside ball reduced from 218 to 2; host deletions 2,389 -> 3,548 (FIBER_CONTACT_COMPARISON_REPORT.html).
       - Curved vs Flat (#16): Concave spherical bowl (radius 0.25 m); ball speed 457.8 vs 453.3 m/s; 165.4 J vs 182.4 J KE lost (17.0 J less KE lost); host deletions 6,588 vs 3,548 (CURVED_VS_FLAT_REPORT.html).
       - Plywise vs Solid (#17): 8-ply cohesive laminate vs 10-layer solid host; ball speed 457.8 vs 453.3 m/s (+4.5 m/s); host deletions 3,923 vs 3,548 (PLYWISE_VS_SOLID_REPORT.html).
       - Host Failure Analysis (#18): 344 flat and 350 concave VUEL failures at t = 0 before contact; 82% to 92% fiber nodes orphaned (HOST_FAILURE_ANALYSIS_REPORT.html).
       - Matrix Material (#19): 6 of 6 single-element benchmark cases passed within < 1% pre-softening stress and <= 0.35% total dissipation difference (MATRIX_MATERIAL_REPORT.html).
       - vp3 (#20): VUEL lost 3.4x more host elements (31.2% vs 9.2%); fiber displacement blow-up to 290 mm (VALS_PLYWISE_VUEL_VS_NATIVE_REPORT.html).
       - vp4 (#21): ALLKE peaked at 6.1 J (+73% in native, +63% in VUEL; raw ODB energies uncorrected for 1000x factor) (VALS_PLYWISE_DELETION_RERUN_REPORT.html).
       - vp5 (#22): ALLKE peak dropped from +73% to +6.8%; ball eroded 3,161 of 18,500 elements (17.1%); host deletions 1,351 vs 517 in vp4 (VALS_VP5_ERODING_CONTACT_REPORT.html).
       - bt1 & bt2 (#23, #24): Steady erosion 80-90 elements/us; D4 reduced ball deletions by 8% (840 vs 913); beam fibers deleted 63-68 vs 11-16 for truss; carries inversion metric ghost correction note (VALS_BT1_BALL_TESTS_REPORT.html, VALS_BT2_BALL_TESTS_REPORT.html).
       - d6 video (#25): Standalone video presentation of 100 us d6 run (job 56873219) with Table 2 paper properties (D6_PAPER_MATERIALS_VIDEO.html).
       - bt3 (#26): Suite d1-d7 at 1000 m/s; 609 of 610 hexes in b4 and 618 of 619 in c2 dead before inverting; d3 crash at 22.77 us; d4 ball deletion 17.3% (VALS_BT3_BALL_TESTS_REPORT.html).
       - ballfix (#27): 3/4-in (3546.1 J) vs 3/8-in (469.2 J, 8.0x mass); 70 us host deletions 611/80,500 (0.76%) in native and 1,222/161,000 (611 pairs, 0.76%) in VUEL vs 1,704 (2.12%) in d6 (VALS_BALL_SIZE_FIX_REPORT.html).
       - nv3_elem (#28): nv3_smear 27,293 dead in inc 1; nv3_elem 100 us in 13 h 20 min (48,004 s) with 0 pre-impact deaths, 39,016/435,000 host deletions (8.97%), 73/524,180 fiber deletions (0.014%) (NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html).
       - nv3_fh (#29): nv3_fh explosion (25,710 J at 1.9 us); native other-ply Run A stable (468.8 J ETOTAL); cx057b proved state is not fresh; dropped own-ply contact (FIBER_HOST_CONTACT_REPORT.html).

checks_run:
  - Checked for presence of agents/refiner/outbox/T-058-RESULT.md (result: False; descriptive pending video panels maintained).
  - Verified exact data points from Meshing/vals-plywise-balltests3/results/d6_rigid_matched_100us_extract.json at t = 70.0 us.
  - Verified project notes in agents/drafter/inbox/T-059/notes/ball-inversion-investigation.md for T-052 decks (08 rerun not recorded, 12 stiff ball metrics), d3 crash facts, d4 perforation, and unit corrections.
  - Verified that all '~' approximations in data tables and findings were eliminated (0 tildes remaining across all 5 generated HTML reports).
  - Executed build_t060_reports.py: generated all 5 reports cleanly with exit code 0.
  - Ran automated validation assertions against all 5 generated HTML files (all assertions passed).
  - Verified file sizes: VALS_BT3_BALL_TESTS_REPORT.html (1.12 MB), VALS_BALL_SIZE_FIX_REPORT.html (152 KB), NEWVALS_NV3_CONTACT_EVOLUTION_REPORT.html (99 KB), FIBER_HOST_CONTACT_REPORT.html (86 KB), REPORTS_INDEX.html (40 KB). All well under the 60 MB limit.

not_verified:
  - Did not re-render or generate video files (pending refiner execution of T-058).
  - Did not log into remote Penn State ROAR cluster or submit jobs.
  - Did not inspect unpulled ROAR scratch ODBs or NPZ files (e.g. d3 full 584 MB NPZ).
  - Full projectile perforation across d5 and d6 100 us runs was not independently frame-audited.

suggestions:
  - When agents/refiner/outbox/T-058-RESULT.md completes, run build_t060_reports.py to embed the standard render passes into all video panels.
  - When nv3_fhA100 (solve job 57328143) completes and results are extracted, populate the placeholder table in FIBER_HOST_CONTACT_REPORT.html with final observed metrics.

concerns:
  - None. All Hub review findings from T-059 have been addressed and validated against data.

denied_actions:
  - None.
