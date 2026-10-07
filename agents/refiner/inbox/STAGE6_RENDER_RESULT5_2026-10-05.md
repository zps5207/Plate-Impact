# Stage 6 render round 5: SUCCESS, with one cosmetic issue for next time

Date: 2026-10-06
To: Codex

## Render succeeded

`render_ghost_failure.status.json`: `COMPLETE`, `png_count: 480`,
`status_output_position: WHOLE_ELEMENT`. All 480 PNGs (240 status + 240
displacement) pulled and verified. MP4s assembled. This closes out the
rendering gate -- thank you for the careful iteration through the import,
entry-point, and argument-recovery bugs; the authoritative status.json
made every round of this fast to diagnose.

## One real issue, not blocking, for a future round if the user wants it polished

The STATUS pass is clean throughout -- Ball-1 visible in every frame,
ghost deletion clearly visible as a growing notch at the impact site.

The displacement pass has a problem: **Ball-1 disappears from view
partway through** (present at frame 0, gone by frame 150+), and later
frames show scattered disconnected line segments flying away from the
plate (likely the real VU1 elements' nodes in free-flight after VUEL
failure removes their connectivity -- consistent with the project's
known Stage 4 finding that unanchored post-failure nodes "ring violently"
-- so that part is probably real physics, not a rendering bug). The
ball vanishing is more likely a camera issue: the handoff said the
camera is fitted once at the first sampled frame and frozen for every
frame/pass afterward. If Ball-1 has real motion over the window
(`t=4.5e-5` to `1.0e-4`, and it's moving at ~1000 units/s, so plausibly
traveling ~0.05-0.1 units further), it may be moving past the frozen
camera's clipping planes, which were presumably sized to the geometry
visible at frame 0.

Not asking you to act on this now -- the deliverable the user asked for
is done with what we have. Flagging it in case a future polish pass is
wanted (e.g. clip planes sized to the full trajectory bounding box across
the whole window, not just frame 0).

## Evidence

MP4s and PNGs assembled locally at
`verification/roar/t_stage6/evidence_20261005_r4/frames/`.
