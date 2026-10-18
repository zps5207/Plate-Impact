task_id: T-019
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-019/odb_viewer_web.py
  - agents/drafter/outbox/T-019/RESULT-NOTES.md
  - agents/drafter/outbox/T-019/test_v500_30f.mp4
  - agents/drafter/outbox/T-019/verification_mp4_frame0.png
  - agents/drafter/outbox/T-019/verification_screen_canvas.png
  - agents/drafter/outbox/T-019/verification_screen_before.png
  - agents/drafter/outbox/T-019/v500_viewer_frame_001_20261016_134803.png
summary: Added an offscreen "Record video" feature and snapshot export capability to the browser viewer (odb_viewer_web.py) building upon the T-018 smooth-playback release. The feature records MP4 animations directly from the user's active viewport (preserving custom orbit, zoom, pan, styling, and frame HUD overlays) without disrupting live playback or closing the VTK render window. Implemented exact camera preservation and field-of-view compensation (tan(theta_out/2) = tan(theta_in/2) * (AR_in / AR_out)) so that non-matching export aspect ratios never crop the model. Provided an interactive dialog with resolution (1280x720, 1920x1080, Current Aspect, 854x480), framerate (15 to 60 FPS), frame range, custom filename, time overlay toggle, real-time striped progress bar, cancel button, and one-click file download link served from recordings/ in cwd. Completed full end-to-end automated verification using headless Microsoft Edge via CDP on the real 58 MB simulation file (v500_viewer.npz, 150 frames).
checks_run:
  - Automated headless Edge CDP test (scratch/test_t019_verification.py, exit code 0): launched web viewer on real simulation data (v500_viewer.npz), connected headless Edge, and executed a 6-phase test suite.
  - Viewport orbit test: applied free mouse drag across the 3D canvas (from (700, 400) to (500, 260)) to verify non-default orbit and zoom persist into export.
  - Video export verification: recorded 30 frames at 1280x720 @ 30 FPS to recordings/test_v500_30f.mp4 (55,717 bytes). Verified exact frame count (30) and resolution (1280x720) via imageio.
  - Frame 0 visual fidelity: extracted video frame 0 and confirmed identical orientation, styling, and HUD microsecond time badge against on-screen canvas screenshot (54,611 non-background subject pixels).
  - Aspect ratio compensation: verified math for perspective (tan(theta_y_out/2) = tan(theta_y_in/2) * (AR_in / AR_out)) and parallel projection (scale_out = scale_in * (AR_in / AR_out)) when AR_out < AR_in, preventing horizontal cropping.
  - Cancellation test: initiated 150-frame recording and clicked "Cancel Recording" mid-render; confirmed render loop stopped cleanly, status was set to "Recording cancelled.", and partial file was deleted from disk.
  - Snapshot export: triggered snapshot button; verified generation of a valid 1280x720 PNG (117,708 bytes) and download URL in UI.
  - Live view restoration: confirmed on-screen camera, window size, and frame index were fully restored; resumed live playback and verified frames advanced sequentially (Frame 0 to Frame 60) with smooth 30 FPS playback intact.
  - Code syntax and CLI arguments: verified `python -m py_compile` exits 0 and `python odb_viewer_web.py --help` outputs complete options.
not_verified:
  - Non-Chromium browsers (Safari, Firefox), though Trame/Vuetify and HTML5 Canvas WebSocket transport use cross-browser web standards.
  - macOS and Linux environments (tested on Windows 11 with installed Python 3.12 and Edge headless).
suggestions:
  - Apply the deliverable from agents/drafter/outbox/T-019/odb_viewer_web.py to verification/roar/odb_viewer_web.py.
  - Run the viewer with: `python verification/roar/odb_viewer_web.py agents/drafter/inbox/T-012/v500_viewer.npz`
concerns: none
denied_actions: none
