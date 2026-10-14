# Stage 6 fiber render: switch host from translucent shaded to wireframe

Date: 2026-10-07
To: Codex
Re: `STAGE6_FIBER_RENDER_RESULT3_2026-10-06/HANDOFF.md` (the fix that got
translucency/color working, sha256 `eefec88c...`)

## The fiber pass works, but translucency isn't see-through enough

The round-4 fix (colorCodeOverride ordering) is confirmed correct and
already ran successfully on ROAR for the full 240-frame render -- that
part is done, don't touch it. The host's `translucency=0.65` shaded
surface is technically applied, but it reads as a solid grey-blue plate,
not something you can see fiber geometry through. This is very likely an
inherent limit of Abaqus/CAE's shaded-translucent compositing for a thick
continuum solid (no real depth-sorted see-through), not a bug in the
script.

## Requested change

In `set_fiber_display()` (currently in
`STAGE6_FIBER_RENDER_RESULT3_2026-10-06/render_ghost_failure.py`), change
the ghost host leaf from a translucent shaded surface to **wireframe /
edges-only** (no filled faces), so the embedded fiber network
(`EMBMESH_FIBERS_T0`/`EMBMESH_FIBERS_T90`, opaque bright red) is fully
visible with nothing in front of it. Keep:

- the `FREE` visible-edges setting and `THICK` edge width from the
  previous round (so the host's outer silhouette and the fiber T3D2
  centerlines both stay legible);
- the fiber leaf's opaque bright-red color unchanged;
- Ball-1 opaque dark-gray, unchanged;
- the `colorCodeOverride=ON` + config-before-color-calls ordering from
  the last fix -- don't reopen that, it works.

Drop the `initialColor`/`translucency` call on the host (or keep
`renderStyle=WIREFRAME`/edges-only some other correct way if there's a
cleaner Abaqus 2024 API for it -- your call on the exact mechanism, I
don't know the precise keyword for this one).

## Verification

Same gate as every prior round: 1-frame smoke test first
(`--passes fibers --frame-count 1 --output-dir
Flat-vuel-ghost-r4/fiber-smoke-r4`, increment the suffix), require
`COMPLETE`/`png_count: 1`, and confirm in the HANDOFF what the frame
should show (host as visible wireframe outline only, no filled/shaded
faces, red fiber lines fully unobstructed, ball still opaque dark-gray,
no node-marker clutter). I'll run it on ROAR myself and report back
before any full 240-frame re-render.

## Separate, known issue -- not part of this brief, flagging for later

Watching the full rendered fiber/displacement videos (not just still
frames), the ball visually passes through the plate without the plate
ever showing a hole, even well after VUEL/ghost elements have failed
(confirmed failed via the diagnostics CSV -- 396/398 real deletions).
Root cause, from reading the script: `set_status_display()` plots
`STATUS` as the primary contour variable, and Abaqus natively hides
elements with `STATUS=0` only when `STATUS` is the plotted variable --
that's why the STATUS pass visibly shows the growing hole. Neither
`set_motion_display()` (displacement pass) nor `set_fiber_display()`
(fiber pass) ever sets `STATUS` as a primary variable or otherwise
excludes dead elements from the display group, so Abaqus has no reason
to drop their geometry, even though those elements are genuinely dead in
the solve. This is almost certainly the same root cause as the already-
known "scattered disconnected fragments" cosmetic issue in the
displacement pass.

Not asking for a fix in this round -- just flagging it now so it's not
forgotten. When we do pick it up, the fix is to make the fiber and
displacement passes exclude `STATUS=0` ghost elements from their display
group the same way the STATUS pass effectively does, verified on ROAR
since I don't want to guess the exact Abaqus display-group/status-variable
API here either.
