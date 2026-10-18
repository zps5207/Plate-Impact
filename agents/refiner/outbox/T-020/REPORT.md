# T-020 browser playback investigation

## Reproduction and finding

The reproduction script runs the **unmodified** `verification/roar/odb_viewer_web.py` or the patched copy with the real 150-frame `v500_viewer.npz`. It starts a server bound to `127.0.0.1` on an ephemeral port, then drives headless Edge through CDP at the requested CSS window size and device scale factor. It clicks Play, waits five seconds, clicks Pause through the page's DOM, observes frame-label mutations for two more seconds, and exercises Step Forward, Symmetry, and the Speed selector. Raw runs are in the nine JSON files beside this report. The actual viewport is slightly smaller than `--window-size` because of browser chrome (for example 1896×988 for 1920×1080).

The current script calls both `set_stream_quality(75, 0.5)` and `ctrl.view_update()` on **every** animation tick. `VtkRemoteView.update()` invokes `push_image` through the trame protocol. At large windows, the browser receives fewer frames than the server requests, leaving image/protocol work queued. In the baseline runs, Edge sent the Pause trigger on its websocket, but the server did not execute `toggle_play` during the following two seconds; the button still read PAUSE and frames kept advancing. This establishes protocol backlog as the observed control failure. The exact share of cost from image rendering, encoding, and the repeated quality RPC was not isolated.

The loop also calls `viewer.plotter.render()` synchronously, so each tick blocks the Python event loop until it finishes. That cost grows at larger viewports. The `toggle_play` double expression was confusing but was not shown to be a second toggle. `timeBeginPeriod(1)` and the pacing sleep remain unchanged; they were not implicated by this test.

## Measurements

Each FPS value counts distinct, sequential browser DOM frame-label updates over approximately the last four seconds before Pause. `max gap` is the largest modulo-150 frame-number jump. Pause latency is the timestamp of the last observed frame change after the click; **0 ms** means no later frame was observed. The baseline never stopped within the two-second observation period. This method measures what the page reports, not the exact instant a new canvas image becomes visible.

| Edge window / DPR | Actual viewport | Current fps / max gap | Current Pause after 2 s | Patched fps / max gap | Patched last post-click frame | Patched Pause after 2 s |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 1920×1080 / 1 | 1896×988 | 4.55 / 1 | still PAUSE, 8 frames advanced | 10.23 / 1 | 92 ms | PLAY, stopped |
| 1920×1080 / 2 | 1896×988 | 5.44 / 1 | still PAUSE, 11 frames advanced | 13.55 / 1 | 5 ms | PLAY, stopped |
| 2560×1440 / 1 | 2536×1348 | 2.49 / 1 | still PAUSE, 5 frames advanced | 9.64 / 1 | 176 ms | PLAY, stopped |
| 2560×1440 / 2 | 2536×1348 | 2.06 / 1 | still PAUSE, 4 frames advanced | 7.14 / 1 | 75 ms | PLAY, stopped |
| 1280×800 / 1 | 1256×708 | T-018 measured 30.41 / 1 | — | 29.71 / 1 | 0 ms | PLAY, stopped |

At 1× and 1280×800 the patched loop retains approximately 30 fps and sequential frame numbers. At larger windows, software remote rendering cannot sustain 30 fps on this machine; the bounded stream keeps controls responsive and reports each sampled frame in order. Each table entry is one run, so run-to-run variation is possible.

After a second Play during the patched 2560×1440/DPR 2 run, the Symmetry button was clicked while the frame counter continued advancing, the Speed selector opened and its input changed from 1 to 2, and Step Forward changed the button to PLAY. The same baseline run still showed PAUSE after the step attempt. The test did not independently inspect the camera matrix or server-side speed value.

## Patch

`odb_viewer_web.patch` is a minimal unified diff against the current verification copy (SHA-256 `118A746025026DEFBE46748D3A7A5003CA091E5A0E4D2E2BCFB263DD2DE1CAA1`); `odb_viewer_web_fixed.py` is the complete patched script. The patch passed `git apply --check` at the project root. No project file was edited.

The patch starts `VtkRemoteView`'s bounded animation stream on Play, stops it on Pause or Step, and removes the per-tick quality RPC and explicit image push. It publishes the stopped state before scheduling the full-resolution still. Step controls use the same deferred still path. The default playback ratio rises from 0.5 to 0.6 and JPEG quality from 75 to 85: the render has 44% more source pixels by area, with less JPEG loss. `--play-ratio` and `--play-quality` let the user choose a sharper image or more speed. The still remains 95 quality at ratio 1. A trial at ratio 0.75 and quality 90 delivered only 7.39 fps at 1920×1080/DPR 1, so that setting is not the default.

The bounded stream and higher quality trade maximum large-window frame rate for responsiveness and a sharper default. The headless test did not provide a controlled visual sharpness score or a real display comparison. If the user's screen still looks soft, `--play-ratio 0.75 --play-quality 90` is available, with the measured throughput cost above.

## Checks and limits

- `python -m py_compile` passed for the patched script and reproduction script.
- `git apply --check` passed for `odb_viewer_web.patch` at the project root.
- No ROAR job or port 8780 was used.
- The browser was headless Edge with `--disable-gpu`. A physical desktop GPU, the user's exact display size, subjective picture quality, actual canvas image presentation times, non-Edge browsers, and multi-client operation were not verified.
- The Speed input changed to 2 and Symmetry accepted a click during playback, but the server-side speed and final camera orientation were not independently inspected.
