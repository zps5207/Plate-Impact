task_id: T-035
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-035/embmesh_desktop.py
  - agents/drafter/outbox/T-035/tests/test_gui_plywise.py
  - agents/drafter/outbox/T-035/embmesh.spec
summary: |
  Extended the desktop GUI plywise panel with cohesive material presets, hex layer collapse, and host-mode selection:
  1. Cohesive Material Selection & Live Readout in `embmesh_desktop.py`:
     - Added dropdown for cohesive materials: "Existing deck interaction" (default, preserving existing behavior with `--cohesion`) and preset labels from `MATERIAL_LABELS` (Dyneema HB26 (Hazzard et al. 2018)).
     - When a preset is chosen:
       * Exposes rate dropdown (`quasi-static` / `ballistic`), length units dropdown (`m` / `mm`, default `m`), and interaction name entry (default `Cohesion_Hazzard2018`).
       * Displays a one-line note that presets always overwrite existing interactions of the same name (`--cohesive-overwrite`).
       * Provides a read-only live readout displaying K_I/K_II (pairs of N/mm^3 and deck-unit values), normal/shear strengths, and fracture energies for the current ply thickness.
       * Automatically computes current ply thickness from either entered ply thickness (`thickness` mode) or plate bounding box divided by ply count when a deck is loaded (`plies` mode). Shows "enter a ply thickness or load a deck" when thickness cannot be evaluated.
       * Displays thickness and unit-mismatch warnings in the panel.
       * Emits `--cohesive-material`, `--cohesive-rate`, `--length-units`, `--cohesive-name`, `--cohesive-overwrite`, and `--cohesion-slave`.
  2. "Collapse layers to one hex" checkbox:
     - Checkbox and description label ("Use when the loaded deck has several hex layers through the thickness (virgin solid decks)").
     - Emits `--collapse-layers` when checked.
  3. Host-mode selector:
     - Selector for `native` / `vuel-ghost` (also accepts "VUEL + ghost").
     - Ghost-scale entry (default 1e-4, validated strictly `0 < ghost_scale < 1`) shown only when VUEL + ghost is selected.
     - Emits `--host-mode vuel-ghost --ghost-scale <scale>` for VUEL + ghost; leaves defaults untouched for native mode.
  4. Command building and validation:
     - Pure-function validation extended in `build_plywise_command` with comprehensive error checks (invalid host mode, ghost scale out of range, unknown cohesive material, invalid length units, invalid rate).
     - Preserves byte-identical command emission for existing non-plywise commands and unchanged existing-interaction plywise runs.
  5. PyInstaller spec:
     - Added `embmesh.cohesive_materials` and `embmesh.collapse` to `hiddenimports` in `embmesh.spec`.
checks_run:
  - Delivered test suite in `agents/drafter/outbox/T-035/tests/test_gui_plywise.py`: 22 of 22 passed:
    * `test_full_plywise_command`: full CLI command builder baseline.
    * `test_thickness_symmetric_repeat`: thickness and symmetric layup repeat command generation.
    * `test_no_layup`: fiber-free contact options.
    * `test_validation`: baseline plywise input validations.
    * `test_surface_interactions_in_stack`: interaction parser on stack.inp.
    * `test_non_plywise_argument_list_unchanged`: non-plywise command generation verified byte-identical.
    * `test_preset_ballistic_mm_command`: verified preset + ballistic + mm emits `--cohesive-material dyneema-hb26`, `--cohesive-rate ballistic`, `--length-units mm`, `--cohesive-name Cohesion_Preset`, `--cohesive-overwrite`, and omits `--cohesion`.
    * `test_preset_label_command`: verified selecting preset by display label correctly maps to canonical key.
    * `test_existing_interaction_mode_unchanged`: verified existing-interaction mode emits `--cohesion` and `--cohesion-slave` without preset flags.
    * `test_collapse_layers_flag`: verified `--collapse-layers` flag toggle.
    * `test_host_mode_flags`: verified native mode emits no host-mode flags; vuel-ghost emits `--host-mode vuel-ghost --ghost-scale 1e-4`; validates ghost-scale bounds (0 < x < 1) and raises ValueError on invalid inputs.
    * `test_live_readout_values`: verified Table 5 values for 1 mm ply in mm units (K_I 60 N/mm^3, K_II 36 N/mm^3), and stack.inp values for 0.1375 mm ply in m units (4.36e11 / 2.62e11 Pa/m).
    * `test_cohesive_validation`: verified ValueError on unknown material, invalid length units, and invalid rate.
    * `test_tk_smoke_test_toggles_new_controls`: verified interactive widget instantiation and state transitions under Tk: collapse toggle, host mode pack/pack_forget toggle for ghost scale frame, cohesive material controls, live readout updates in thickness mode (60/36 for 1 mm in mm; 4.36e11/2.62e11 for 0.1375 mm in m), unknown thickness prompt ("enter a ply thickness or load a deck"), and plies mode with loaded deck `Meshing/plate1hex_curved_ball.inp`.
  - Full existing test suite: 120 passed, 1 skipped in `tests/`.
not_verified:
  - T-038 end-to-end execution of `--host-mode` on `embmesh plywise`: as noted in brief context, T-038 is in progress, so host-mode flags are covered by command-construction tests only.
  - Abaqus solver or datacheck was not executed.
  - PyInstaller freeze executable build was not run in this dev environment.
suggestions:
  - Once T-038 lands, end-to-end integration tests for plywise + VUEL ghost conversion can be added to the test suite.
concerns:
  - None. All command lines, validations, and live readout calculations match specifications and existing test suites.
denied_actions: none
