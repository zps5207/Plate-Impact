task_id: T-020
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-020/REPORT.md
  - outbox/T-020/odb_viewer_web.patch
  - outbox/T-020/odb_viewer_web_fixed.py
  - outbox/T-020/reproduce_large_window.py
  - outbox/T-020/baseline_1920x1080_dpr1.json
  - outbox/T-020/baseline_1920x1080_dpr2.json
  - outbox/T-020/baseline_2560x1440_dpr1.json
  - outbox/T-020/baseline_2560x1440_dpr2.json
  - outbox/T-020/fixed_1280x800_dpr1.json
  - outbox/T-020/fixed_1920x1080_dpr1.json
  - outbox/T-020/fixed_1920x1080_dpr2.json
  - outbox/T-020/fixed_2560x1440_dpr1.json
  - outbox/T-020/fixed_2560x1440_dpr2.json
summary: >
  Confirmed that per-tick remote image pushes and quality RPCs backlog the trame
  stream at large windows, delaying the Pause RPC beyond two seconds. Replaced
  per-tick pushes with VtkRemoteView's bounded animation stream, published stopped
  state before the full-resolution still, and made playback ratio/quality tunable.
  Headless Edge DOM frame-label FPS improved from 4.55/5.44 to 10.23/13.55 at
  1920x1080 (DPR 1/2), and from 2.49/2.06 to 9.64/7.14 at 2560x1440 (DPR 1/2).
  Baseline Pause still showed PAUSE after two seconds in all four cases; patched
  Pause showed PLAY with last post-click frame at 5-176 ms. At 1280x800, patched
  playback remained sequential at 29.71 fps. Full measurements are in REPORT.md.
checks_run:
  - Headless Edge CDP reproduction at 1920x1080 and 2560x1440, DPR 1 and 2, before and after, using the real v500_viewer.npz.
  - Headless Edge at 1280x800/DPR 1 after patch.
  - Clicked Pause, Step Forward, Symmetry, and Speed through browser DOM; patched Speed input changed from 1 to 2 and Step Forward stopped playback.
  - python -m py_compile on patched script and reproduction script.
  - git apply --check on unified diff at project root.
not_verified:
  - Physical desktop GPU/browser and the user's actual display size.
  - Exact canvas image presentation time or a controlled visual sharpness score; FPS is based on DOM frame-label updates.
  - Server-side speed value and final camera orientation after browser clicks.
  - Multi-client behavior, other browsers, and local-rendering mode after patch.
suggestions: >
  Hub should apply the unified diff to the current verification/roar copy after
  reconciling T-019's concurrent Record-video changes, then test on the user's display.
concerns: >
  Large-window software rendering still runs below 30 fps. The default 0.6 ratio
  and quality 85 improve source resolution over T-018, but subjective sharpness
  was not measured; increasing --play-ratio costs throughput.
denied_actions: >
  One attempted dynamic cleanup command was rejected by automatic command review;
  the same temporary files were removed with explicit safe paths. No requested
  project action was denied.
