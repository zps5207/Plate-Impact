# Stage 6 fiber render round 2: runs clean, but two visual problems

Date: 2026-10-06
To: Codex
Re: `STAGE6_ENERGY_AND_FIBER_RESULT_2026-10-06/HANDOFF.md` (setColor fix)

## Smoke test ran successfully

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke --passes fibers --frame-count 1
```

`render_ghost_failure.status.json`: `COMPLETE`, `png_count: 1`,
`status_output_position: WHOLE_ELEMENT`. No API error this time -- the
`setColor` fix works. Pulled and looked at `fibers_0000.png` before
running the full 240-frame pass, per your instructions.

## Two visual problems, neither is the API error from last round

1. **Fibers are essentially invisible.** I see only two or three faint
   red specks near the plate's top edge and mid-face -- nothing like a
   clear fiber mesh through the translucent host. Given the fibers are
   thin T3D2 truss elements, my guess (not confirmed) is they're
   rendering as default-width 1px lines that are easy to lose against
   the translucent surface and the clutter described below -- but I
   don't know Abaqus's line-rendering options well enough to say that's
   the actual cause rather than a display-group/visibility issue. The
   red color itself does appear to be applied correctly where visible.

2. **Small circular node-symbol markers cover the entire model** -- the
   ghost plate surface and the ball are both covered in a dense dot/polka
   -dot pattern that wasn't part of the intended styling (plain
   translucent surfaces, no node markers mentioned in your handoff). My
   guess: the fiber leaf's `nodeSymbolColor` keyword from the
   `setColor(leaf=..., nodeSymbolColor=...)` call may be toggling node
   symbol *display* on more broadly than just the fiber leaf (e.g.
   globally for the viewport, or for every leaf rather than only the
   intended one), rather than just setting what color symbols *would* be
   if displayed. Again, not confirmed -- just what the image suggests.

Translucency on the host itself does look correctly applied (plate
reads as a flat gray-blue, see-through-ish surface, not opaque), so the
`initialColor`/`translucency` part of the fix seems right. It's the
fiber visibility and the node-symbol clutter that need another pass.

I have not run the full 240-frame render -- holding off until these are
fixed, per the smoke-test-first plan.

## Evidence

The smoke-test PNG is on ROAR at
`/storage/home/zps5207/scratch/vuel_stage6_flat_vg_r4_20261005_01/Flat-vuel-ghost-r4/fiber-smoke/fibers/fibers_0000.png`,
and I've pulled a copy to
`verification/roar/t_stage6/evidence_20261005_r4/fibers_0000.png` in the
repo if that helps, though I know you don't have a local way to view it
either -- describing exactly what I see above is the best I can do from
this side.
