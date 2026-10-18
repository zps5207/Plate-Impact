task_id: T-039
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-039/embmesh/plywise_contact.py
  - agents/drafter/outbox/T-039/embmesh/plywise_vuel.py
  - agents/drafter/outbox/T-039/embmesh/plywise.py
  - agents/drafter/outbox/T-039/embmesh/plycohesive.py
  - agents/drafter/outbox/T-039/embmesh/cli.py
  - agents/drafter/outbox/T-039/embmesh_desktop.py
  - agents/drafter/outbox/T-039/tests/test_plywise_surf1.py
  - agents/drafter/outbox/T-039/tests/test_gui_plywise.py
  - agents/drafter/outbox/T-039/build_plywise_500.py
  - agents/drafter/outbox/T-039/plywise-500/flat/output.inp
  - agents/drafter/outbox/T-039/plywise-500/concave/output.inp

summary:
  1. Restored element-based ball-plate contact (`Surf-1` / `Surf-2`) in plywise decks:
     - Geometric Face Selection:
       * In Flatv2 (`Meshing/Flatv2.inp`), the collapsed plate has both S2 (2400) and S1 (2400) surviving faces (1800 side faces dropped). S2 corresponds to `PLY_BOTTOM` and S1 corresponds to `PLY_TOP`. Along the stack axis ($z$), `Ply-1` bottom face (S2) sits at $z \approx 0.0$ m while `Ply-8` top face (S1) sits at $z \approx -0.010$ m. The ball is positioned at $z \in [0.011, 0.021]$ m. `_find_plate_impact_surface` measures distance from the ball instance center to candidate centroids and selects `Ply-1` (bottom face S2, distance $\approx 0.011$ m vs $\approx 0.021$ m for `Ply-8`).
       * In Concave (`Meshing/Flat-concave-roar/concave_hostonly.inp`), the collapsed plate only has S1 (2400 faces), matching `PLY_TOP`. The algorithm maps it to `Ply-8` (top face S1).
     - Surface Construction:
       * Rebuilt `Surf-1` at assembly level in CAE style (`*Elset, elset=_Surf-1_S<n>, internal, instance=Ply-k` + `*Surface, type=ELEMENT, name=Surf-1`).
       * When `host_mode == 'vuel-ghost'`, element labels are remapped to ghost labels using `remap_surface_elsets` (reused from `plywise_vuel.py`).
       * In native mode, labels remain native ply element labels.
     - Contact Inclusions:
       * Restored all 4 element-contact inclusion lines in the `*Contact Inclusions` block formatted identically to the solid decks:
         `Surf-1 , Surf-2`
         `Surf-2 , Surf-1`
         `Surf-1 ,`
         `Surf-2 ,`
       * Ordered before node pairs (`EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF`, `EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF`) and cohesive interface pairs (`Ply-k_top , Ply-(k+1)_bottom`).
       * Single-surface self-contact `Surf-1 ,` only affects the outer impact face of `Ply-1` (or `Ply-8`), preventing self-penetration of that face during folding/erosion; it has no effect on interior cohesive interfaces, which are governed by pair-wise cohesive properties.
     - Preserved safeguards: decks without an existing plate element impact surface remain untouched; `--plate-node-contact` off retains warning behavior.

  2. Clean-up of contact-pair cohesive leftovers:
     - Removed `--cohesion-slave` flag and `cohesion_slave` argument from `embmesh/cli.py` and `embmesh/plywise.py`.
     - Removed `--cohesion-slave` CLI flag emission and UI dropdown from `embmesh_desktop.py`.
     - Annotated legacy functions `cohesive_contact_lines`, `insert_cohesive_contact`, and `insert_cohesive_contact_into_deck` in `embmesh/plycohesive.py` with `"(contact-pair form, rejected by Abaqus/Explicit)"`.
     - Updated CLI help strings and docstrings to refer to cohesive general contact.

  3. Verification and Smoke-Test Deck Generation:
     - Created `tests/test_plywise_surf1.py` with 7 test scenarios (bottom native/vuel-ghost, top native/vuel-ghost, two-sided face resolution, side face dropping, safeguards).
     - Updated `tests/test_gui_plywise.py` to assert `--cohesion-slave` is not emitted.
     - Executed full test suite: 141 tests collected, 140 passed, 1 skipped (no failures; baseline was 133).
     - Rebuilt real 500 m/s smoke decks using `build_plywise_500.py` into `outbox/T-039/plywise-500/`.

  4. Inspected Smoke Deck Contact & Surface Definitions:
     - FLAT deck (`outbox/T-039/plywise-500/flat/output.inp`):
       ```abaqus
       *Elset, elset=_Surf-1_S2, internal, instance=Ply-1
       10401, 10402, 10403, 10404, 10405, 10406, 10407, 10408, 10409, 10410, 10411, 10412, ...
       ... (2400 ghost elements: 10401 to 12800) ...
       *Surface, type=ELEMENT, name=Surf-1
       _Surf-1_S2, S2
       ...
       ** Interaction: General
       *Contact, op=NEW
       *Contact Inclusions
       Surf-1 , Surf-2
       Surf-2 , Surf-1
       Surf-1 ,
       Surf-2 ,
       EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF
       EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF
       Ply-1_top , Ply-2_bottom
       Ply-2_top , Ply-3_bottom
       ...
       *Contact Property Assignment
        ,  , General
       Ply-1_top , Ply-2_bottom , Cohesion
       ...
       ```
     - CONCAVE deck (`outbox/T-039/plywise-500/concave/output.inp`):
       ```abaqus
       *Elset, elset=_Surf-1_S1, internal, instance=Ply-8
       24001, 24002, 24003, 24004, 24005, 24006, 24007, 24008, 24009, 24010, 24011, 24012, ...
       ... (2400 ghost elements: 24001 to 26400) ...
       *Surface, type=ELEMENT, name=Surf-1
       _Surf-1_S1, S1
       ...
       ** Interaction: General
       *Contact, op=NEW
       *Contact Inclusions
       Surf-1 , Surf-2
       Surf-2 , Surf-1
       Surf-1 ,
       Surf-2 ,
       EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF
       EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF
       Ply-1_top , Ply-2_bottom
       Ply-2_top , Ply-3_bottom
       ...
       *Contact Property Assignment
        ,  , General
       Ply-1_top , Ply-2_bottom , Cohesion
       ...
       ```

checks_run:
  - `python -m pytest outbox/T-039/tests/test_plywise_surf1.py` (7 passed)
  - `python -m pytest outbox/T-039/tests/test_gui_plywise.py` (21 passed, 1 skipped for headless Tk)
  - Full test suite via scratch runner: 141 tests collected, 140 passed, 1 skipped
  - Execution of `outbox/T-039/build_plywise_500.py` to regenerate both flat and concave smoke decks
  - Verification of `output.inp` files for valid syntax, ghost label offsets, surface elset counts, and contact inclusion ordering

not_verified:
  - Abaqus/Explicit solver or datacheck was not run on the regenerated 500 m/s smoke decks (Abaqus execution is reserved for the Hub).

suggestions:
  - When merging to the main project tree, copy contents of `agents/drafter/outbox/T-039/` directly to project root.

concerns:
  - None. Concurrent edits in `finish_plywise_fibers` were preserved untouched.

denied_actions:
  - None.
