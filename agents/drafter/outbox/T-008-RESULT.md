task_id: T-008
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-008/FINDINGS.md
  - agents/drafter/outbox/T-008/NEXT_EXPERIMENTS.md
  - agents/drafter/outbox/T-008/analyze_islands_and_mismatches.py
summary: Conducted an independent physics and mechanics investigation into why ghost elements near the crater rim survive while VU1 user elements on the same nodes are destroyed around them. Established from ODB diagnostics that for 74 of the 85 surviving ghosts within 10 mm (and all 58 islands), the custom VU1 element on the same nodes has not met its failure criterion either. They survived because the ball bypassed them due to weak contact penalty stiffness (0.85 N/m) and missing interior faces in Surf-1; island peak Mises stress capped at median 30.98 Pa and max 60.34 Pa, strictly below the 61.1 Pa yield threshold, leaving PEEQ at 0.000000. For the remaining 11 near-axis hosts where VU1 failed while the ghost survived, established the root cause as a metric discrepancy under confined 1D compression: VU1 normal Green-Lagrange stretch triggers at 11.38%, whereas J2 deviatoric yield requires 16.84% (ey = sigy / 2G). When VU1 dies, its internal stress zeroes, freezing the ghost in an elastic state with Mises stress between 42.0 and 59.7 Pa. Furthermore, explained far-field deletions as the inverse mismatch driven by embedded fiber shear (ghost yields at 19.4% shear while quadratic Green-Lagrange normal stretch is only 1.9%). Provided four self-contained ROAR experiments and an automated analysis script.
checks_run:
  - Audited flat_v2_output.inp:451796-451809 and Flatv2_user.inp:59228-59238 for ghost and matrix elastic, plastic, damage, and section control definitions.
  - Processed island_history_v2.json across all 58 islands and 538 dead adjacent neighbors (displacement, velocity, Mises stress, pressure, PEEQ).
  - Audited el_elements.csv to classify all 802 near-axis hosts (717 deleted, 74 alive with VU1 intact, 11 alive with VU1 failed).
  - Derived analytical yield strain and stretch thresholds across hydrostatic compression, 1D uniaxial strain, simple shear, and uniaxial tension.
  - Executed outbox/T-008/analyze_islands_and_mismatches.py on Python 3.12 (PASS).
not_verified:
  - Execution of Abaqus/Explicit simulation runs on the ROAR HPC cluster (no local Abaqus solver; cluster runs reserved for Hub).
suggestions:
  - To eliminate the 11 criterion-mismatch ghosts without modifying Fortran code, tune the ghost initial yield stress to 41.3 Pa (ey = 0.1138 under 1D confined strain, EXP-02).
  - To eliminate the 74 bypassed ghosts (and all 58 islands), apply the T-010 Recipe 1 contact fix (whole-ghost Surf-1 + penalty scale factor 10000.0).
  - Run EXP-01 against flat_v2.odb to confirm spatial alignment of far-field deletions along fiber paths.
concerns: none
denied_actions: none
