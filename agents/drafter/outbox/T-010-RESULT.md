task_id: T-010
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-010/WORKAROUNDS.md
  - agents/drafter/outbox/T-010/EXPERIMENTS.md
  - agents/drafter/outbox/T-010/patches/patch_recipe1_penalty_scale.py
  - agents/drafter/outbox/T-010/patches/patch_recipe2_node_surface.py
summary: Evaluated the user's node-based contact idea and brainstormed all viable workarounds to stop the 1000 m/s steel ball in the VUEL+ghost scheme. Proved from evidence/ that ball penetration is governed by two compounding root causes: (1) H1 Penalty Softness—Abaqus derives element penalty stiffness from the 1e-4 ghost modulus (E=508 Pa, bulk modulus 847 Pa), producing an interface stiffness of ~0.85 N/m and a penetration force of only 0.85 mN at 1 mm penetration (5e8 times too soft relative to the 410 kN stopping force); and (2) H2 Missing Interior Faces—Surf-1 references only boundary elsets containing 6,216 elements (25.9%), leaving 17,784 interior ghosts (74.1%) completely outside the contact domain when the surface layer erodes. Delivered an honest verdict on node-based contact: while it restores mass-based penalty stiffness (~1.7e10 N/m), it introduces inter-nodal porosity, needle-point singularities, and indestructible 'zombie' nodes after material failure. Ranked 8 candidate workarounds, detailed concrete deck and mesher recipes for the top two, formulated four runnable ROAR validation experiments, and provided non-applied draft Python patches.
checks_run:
  - Quantitatively evaluated acoustic impedance and penalty stiffness across steel (Z=4.86e7 Pa*s/m), matrix (Z=9.95e4 Pa*s/m), and ghost (Z=9.95 Pa*s/m).
  - Verified member counts of _Surf-1_S2, S3, S4 in flat_v2_output.inp (6,216 boundary vs 17,784 interior ghosts).
  - Analyzed contact duration and peak CPRESS across ct_plate_nodes_contact.csv (median duration 1 frame, peak 6.12e11 Pa).
  - Audited Abaqus/Explicit keyword specifications for *Surface (type=NODE), *Contact Controls Assignment (type=SCALE FACTOR), and *Contact Inclusions.
  - Verified Python 3.12 syntax and compilation for draft patches patch_recipe1_penalty_scale.py and patch_recipe2_node_surface.py (PASS).
not_verified:
  - Execution of Abaqus/Explicit simulation jobs on ROAR HPC cluster (no local Abaqus solver; cluster runs reserved for Hub).
  - ODB extraction of contact force histories from full ROAR impact runs.
suggestions:
  - Run Experiment EXP-01 (Whole-Ghost Surf-1 + 10000.0 penalty scale factor) on ROAR as the primary zero-physics-risk test.
  - Run Experiment EXP-04 (5-second single-hex calibration smoke test) before launching full 33-minute jobs to calibrate contact penalty stiffness directly.
  - Add STATUS to Ball-1 field outputs to verify whether the projectile experiences erosion.
concerns: none
denied_actions: none
