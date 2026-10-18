task_id: T-034
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-034/embmesh/plywise.py
  - agents/drafter/outbox/T-034/embmesh/cli.py
  - agents/drafter/outbox/T-034/tests/test_plywise_cohesive_material.py
  - agents/drafter/outbox/T-034/run_curved_ball/output.inp
summary: |
  Integrated cohesive *Surface Interaction generation from material presets directly into `embmesh plywise`:
  - New options in write_plywise_deck and CLI:
    * --cohesive-material (e.g. dyneema-hb26)
    * --cohesive-rate (quasi-static or ballistic, default quasi-static)
    * --cohesive-name (defaults to preset name, e.g. Cohesion_Hazzard2018)
    * --length-units (m or mm, default m; warns if ply thickness > 0.5 in m mode or < 1e-3 in mm mode)
    * --cohesive-overwrite (replaces existing *Surface Interaction in place if name collides, errors otherwise)
  - When --cohesive-material is specified:
    * Computes interaction properties from the actual resulting ply thickness (t_SL) using Hazzard et al. 2018 equations via embmesh/cohesive_materials.py.
    * Inserts the generated *Surface Interaction block before the first *Step (immediately after the last *Material block if present, else immediately before *Step).
    * Automatically turns on cohesive contact pairs referencing the generated interaction name across all adjacent ply pairs.
    * Populates meta['cohesive_interaction'] with full parameters and propagates any preset warnings into meta['warnings'].
    * Ball contact (plywise_contact) correctly identifies the generated block as cohesive via *Cohesive Behavior and avoids selecting it as the friction interaction.
generated_block: |
  ** Hazzard et al. 2018 (Dyneema HB26), t_SL = 2.5 mm, quasi-static
  *Surface Interaction, name=Cohesion
  *Cohesive Behavior
   2.4e+10, 1.44e+10, 1.44e+10
  *Damage Initiation, criterion=MAXS
   1.2e+06, 1.8e+06, 1.8e+06
  *Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1
  544, 1088, 1088
report_section: |
  {
    "plies": 4,
    "resulting_ply_thickness": 0.0025,
    "warnings": [],
    "cohesive_interaction": {
      "name": "Cohesion",
      "material": "dyneema-hb26",
      "rate": "quasi-static",
      "thickness_used": 0.0025,
      "units": "m",
      "k": [
        24000000000.0,
        14399999999.999998,
        14399999999.999998
      ],
      "strength": [
        1200000.0,
        1800000.0,
        1800000.0
      ],
      "fracture_energy": [
        544.0,
        1088.0,
        1088.0
      ],
      "warnings": []
    },
    "cohesion": {
      "interaction": "Cohesion",
      "pairs": 3
    }
  }
checks_run:
  - Unit test suite in outbox/T-034/tests/test_plywise_cohesive_material.py: 8 of 8 passed:
    * test_table5_one_mm_in_mm_units: verified K=(60, 36, 36) N/mm^3, strength=(1.2, 1.8, 1.8) MPa, energy=(0.544, 1.088, 1.088) N/mm.
    * test_reproduces_stack_inp_for_01375_mm_ply_in_m_units: verified 0.1375 mm ply in m units reproduces Meshing/stack.inp Cohesion block (4.36e11, 2.62e11, 1.2e6, 1.8e6, 544, 1088).
    * test_name_collision_and_overwrite: verified collision raises without overwrite and cleanly replaces in place with --cohesive-overwrite.
    * test_block_lands_before_step_and_after_material: verified placement order (*Material < *Surface Interaction < *Step).
    * test_contact_pairs_reference_generated_name: verified N-1 *Contact Pair blocks reference the generated interaction name.
    * test_unit_mismatch_warning: verified warnings fire for > 0.5 in m mode and < 1e-3 in mm mode.
    * test_written_deck_reparses: verified parse_deck parses output cleanly.
    * test_ball_contact_avoids_generated_cohesive_interaction: verified ball contact skips the generated cohesive interaction and throws error if explicitly passed.
  - Full existing test suite: 93 of 93 passed in tests/.
  - All delivered outbox test suites: 30 of 30 passed across T-027 (9), T-029 (6), T-030 (7), and T-034 (8).
  - Real run completed on Meshing/plate1hex_curved_ball.inp with 4 plies, --cohesive-material dyneema-hb26 --cohesive-overwrite --cohesive-name Cohesion.
not_verified:
  - Abaqus was not run (neither Abaqus solver nor datacheck was executed).
  - Dynamic crack propagation and delamination behavior under ballistic impact were not verified.
suggestions:
  - When the GUI dropdown is created in a subsequent task, it can populate the material preset and rate directly into the plywise command line.
concerns:
  - None. All equations and unit conversions match Hazzard et al. 2018 and the reference deck Meshing/stack.inp.
denied_actions: none
