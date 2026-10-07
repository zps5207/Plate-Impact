# Stage 6 follow-up: energy history extraction + translucent-host fiber render

Date: 2026-10-06
To: Codex
Re: follow-on from `STAGE6_RENDER_RESULT5_2026-10-05.md` (render success)

Two new asks from the user, both against the existing
`flat_vg_r4.odb` (job 56091072) -- no recalibration needed, the physics
result stands.

## 1. Energy history extraction (KE, IE, external work)

The deck already requests `*Output, history, variable=PRESELECT, time
interval=1e-07`, which should include the standard whole-model energy
history outputs. Please write a small ROAR-side extractor (same pattern
as `extract_ghost_diagnostics.py`) that pulls, for the whole model, over
the full step:

- `ALLKE` (kinetic energy)
- `ALLIE` (internal energy)
- `ALLWK` (external work)

into a CSV with columns `time, ALLKE, ALLIE, ALLWK` (plus `ALLVD`/`ETOTAL`
too if they're trivially available from the same history request --
useful context, not required). I'll build the actual plot on my end from
the CSV, same as I did for the ghost-deletion timeline chart in the
report -- you don't need to render an image for this one, just get the
clean data out.

## 2. Translucent-host render pass so the embedded fibers are visible

The two existing passes (`status`, `displacement`) only show the host
plate and ball -- the embedded T3D2 fibers are there in the model but
never actually visible, since they're geometrically inside the opaque
ghost/VUEL hosts. Please add a new render pass where:

- the host (ghost) elements are rendered **translucent** (roughly 50-70%
  transparency -- pick whatever actually makes the fiber mesh legible
  without losing the host's shape entirely),
- the embedded fiber elset is rendered on top, fully opaque, in a color
  that stands out against the translucent host (e.g. a solid contrasting
  color, not a field-variable contour -- this pass is about seeing fiber
  geometry/position relative to the host, not a new physics variable),
  and
- Ball-1 stays visible for context, same as the other passes.

Same time window, frame count, resolution, and camera-fit approach as
the existing passes is fine as a default, unless you think a different
window makes more sense to actually see the fibers clearly (e.g. the
fibers might be easier to see before the impact deforms things much --
your call, just say what you picked and why).

While you're in the renderer: you don't need to fix the two issues I
flagged in `STAGE6_RENDER_RESULT5_2026-10-05.md` (Ball-1 disappearing
from the displacement pass, scattered post-failure debris) as part of
this round unless it's cheap to do alongside the new pass -- those were
flagged as non-blocking polish, not part of this ask. Don't let them
block or scope-creep this one.

## Handoff

Same as before: drop the extractor + CSV (or just the extractor if
you'd rather I run it myself against the ODB, your call since you
already have the pattern from `extract_ghost_diagnostics.py`) and the
updated `render_ghost_failure.py` + updated `RENDERING.md` in your
outbox with a HANDOFF.md, and I'll run both on ROAR the same way as
every round so far.
