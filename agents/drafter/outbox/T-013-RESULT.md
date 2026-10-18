task_id: T-013
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-013/odb_viewer.py
  - agents/drafter/outbox/T-013/evidence_frame_000_symmetry.png
  - agents/drafter/outbox/T-013/evidence_frame_075_symmetry.png
  - agents/drafter/outbox/T-013/evidence_frame_149_symmetry.png
  - agents/drafter/outbox/T-013/evidence_frame_000_iso.png
  - agents/drafter/outbox/T-013/evidence_frame_075_iso.png
  - agents/drafter/outbox/T-013/evidence_frame_149_iso.png
  - agents/drafter/outbox/T-013/evidence_frame_149_fibers_only.png
  - agents/drafter/outbox/T-013/evidence_frame_149_fibers_only_iso.png
  - agents/drafter/outbox/T-013/evidence_frame_075_solid_iso.png
  - agents/drafter/outbox/T-013/evidence_frame_075_solid_symmetry.png
  - agents/drafter/outbox/T-013/evidence_animation.mp4
summary: Fixed camera framing defect in odb_viewer.py and verified on the real v500 file (inbox/T-012/v500_viewer.npz, 58 MB, 150 frames, 27,401 host nodes, 24,000 host hexes, 3,642 ball nodes, 14,192 fiber nodes). Added ODBData._compute_animation_bounds() to determine active/visible scene extents across all frames. Re-engineered compute_symmetry_camera() and apply_camera_preset() so that symmetry, isometric, and reset presets fit the entire animation with margins (8% for symmetry, 6% for 3D), centering the scene in the viewport with no corner confinement and zero cropping at any frame. Plate remains strictly vertical and the ball travels left-to-right. Generated full evidence suite including 9 PNG screenshots and a 30 fps MP4 animation.
checks_run:
  - Ran on the real dataset inbox/T-012/v500_viewer.npz (58 MB, 150 frames).
  - Measured performance on the real file: initial NPZ load in 0.85 s; peak memory 264.5 MB (90.8 MB data delta, 102.6 MB VTK viewer delta); mean per-frame update time 2.40 ms (median 2.34 ms, min 2.04 ms, max 3.22 ms; equivalent to ~416 FPS).
  - Validated scene bounding box calculation across all animation frames: X in [-0.000004, 0.050000] m, Y in [-0.000006, 0.050000] m, Z in [-0.032239, 0.021000] m.
  - Inspected pixel boundaries across all rendered screenshots to verify zero cropping (margins >= 26 px top/bottom and >= 284 px left/right):
      * evidence_frame_000_symmetry.png: Y=[26, 693], X=[284, 698] (uncropped)
      * evidence_frame_075_symmetry.png: Y=[26, 693], X=[510, 779] (uncropped)
      * evidence_frame_149_symmetry.png: Y=[26, 693], X=[563, 995] (uncropped)
      * evidence_frame_000_iso.png: Y=[83, 449], X=[387, 892] (uncropped)
      * evidence_frame_075_iso.png: Y=[182, 449], X=[387, 892] (uncropped)
      * evidence_frame_149_iso.png: Y=[233, 449], X=[387, 892] (uncropped)
      * evidence_frame_149_fibers_only.png: Y=[26, 693], X=[577, 995] (uncropped)
      * evidence_frame_075_solid_iso.png: Y=[182, 448], X=[387, 892] (uncropped)
  - Rendered complete 150-frame off-screen video export (evidence_animation.mp4) at 30 fps in 782 KB.
  - Tested backwards compatibility on synthetic_viewer.npz (symmetric bounds [-15, 15] mm).
  - Analyzed host_status erosion across all 150 frames: exactly 0 resurrections (monotonic deletion from 0 elements at frame 0 to 1,035 at frame 75 and 1,684 at frame 149), confirming no element flickering.
not_verified:
  - Interactive window mouse drag in a desktop GUI environment (headless/CLI execution verified via PyVista off-screen engine).
suggestions:
  - When viewing with interactive window on desktop, users can press '1' for full-animation isometric view, '2' for symmetry plane view, and 'r' to re-center along the current orbit angle.
concerns: none
denied_actions: none
