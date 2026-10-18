task_id: T-018
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-018/odb_viewer_web.py
  - agents/drafter/outbox/T-018/RESULT-NOTES.md
  - agents/drafter/outbox/T-018/evidence_browser_playing_orbit.png
summary: Resolved the browser playback slide-show stutter in odb_viewer_web.py on the real 58 MB dataset (v500_viewer.npz, 150 frames), transitioning from a baseline of 2.96 FPS with 103 skipped frames (max gap 21) to a steady 30.41 FPS with 0 skipped frames and max gap 1. Root causes identified and fixed: (1) replaced wall-clock dt frame-skipping with a fixed-timestep monotonic scheduler (advancing exactly 1 frame per tick for speed <= 1x, pacing via high-resolution sleep subtraction); (2) resolved VTK's pathological quality=100 encoding penalty (254 ms per frame in vtkWebApplication) by setting stream quality to 75 during playback and restoring crisp quality=95 when paused; (3) applied adaptive stream resolution scaling (ratio=0.5 during active playback, dropping frame render latency from ~85 ms down to ~7 ms, and restoring ratio=1.0 when paused); (4) activated Windows high-precision 1 ms timer period via timeBeginPeriod(1) to eliminate asyncio.sleep granularity jitter. Re-verified 3D mouse orbit during active playback without frame stalls or camera snapping, and benchmarked speed multipliers (0.5x, 1.0x, 2.0x) and local rendering (--rendering local).
checks_run:
  - Baseline real browser measurement (Headless Edge via CDP, 1280x800): 14.88 s duration, 44 updates displayed, delivered 2.96 FPS, largest gap 21 frames, 103 skipped frames across 43 transitions (100% skipped).
  - Fixed viewer real browser measurement (Headless Edge via CDP, 1280x800): 15.00 s duration, 456 updates displayed, delivered 30.41 FPS (target 24-30 FPS), largest gap 1 frame, 0 skipped frames across 455 transitions (0% skipped).
  - Profiling of VTK encoding pipeline: identified quality=100 takes 254.40 ms (lossless raw path) while quality <= 99 takes 2.7–3.2 ms (hardware JPEG compression); identified ratio=0.5 reduces software offscreen rasterization from 98.39 ms down to 7.24 ms (>130 FPS capability).
  - Orbit during playback verification: dispatched CDP mouse drag events across the 3D canvas (from (700, 450) to (1000, 250)) during active playback; confirmed camera rotated continuously while frames advanced sequentially from Frame 42 to Frame 128 with zero playback interruption or camera snapping; saved visual screenshot evidence to outbox/T-018/evidence_browser_playing_orbit.png.
  - Speed scaling evaluation via CDP: verified 0.5x delivered 18.92 FPS with 0 skipped frames (max gap 1); 1.0x delivered 30.41 FPS with 0 skipped frames (max gap 1); 2.0x delivered 73.39 FPS with max gap 2.
  - Local rendering benchmark (--rendering local): recorded 49.85 FPS with max gap 2 and 85 skipped frame events caused by re-serializing large VTK scene data over WebSocket.
  - Python byte-compilation and CLI argument verification: verified `python -m py_compile` exits 0 and `python odb_viewer_web.py --help` prints full usage.
not_verified:
  - Non-Chromium browsers (Firefox, Safari) or physical mobile touchscreens, though Vue 3 / Vuetify 3 and HTML5 Canvas WebSocket transport conform to standard web specifications.
  - Linux and macOS environments (script includes Windows platform guards `if sys.platform == 'win32'` for timer period configuration).
suggestions:
  - Apply the deliverable from agents/drafter/outbox/T-018/odb_viewer_web.py to verification/roar/odb_viewer_web.py.
  - Run the viewer directly with: `python verification/roar/odb_viewer_web.py agents/drafter/inbox/T-012/v500_viewer.npz`
concerns: none
denied_actions: none
