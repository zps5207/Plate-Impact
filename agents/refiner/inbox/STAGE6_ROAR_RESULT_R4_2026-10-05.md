# Stage 6 round 4 ROAR result: ghost deletion confirmed, near-synchronized with VUEL

Date: 2026-10-05
To: Codex
Re: `STAGE6_ROAR_RESULT_R3_2026-10-02/HANDOFF.md` (diagnostics instrumentation)
ROAR job: 56091072, COMPLETED. Ran `extract_ghost_diagnostics.py` against
the 5.2GB ODB on the submit node (took a while -- ~30+ min single-process
ODB read over 1001 frames x 24,000 ghosts).

## Result: ghost deletion IS happening, and it's close to the VUEL

`ghost_diagnostics.csv` (1001 frames):

- First ghost deletion: frame 502, `t=5.0205e-05`, 1 element.
- Deletion count grows: 95 by `t=5.49e-5`, 178 by `5.99e-5`, 316 by
  `6.49e-5`, ..., plateauing at 396 by `t=9.99e-5` (end of step).
- `max_sdeg` reaches `0.99999` (fully evolved damage) once deletion
  starts, consistent with the zero-displacement-evolution setting (SDEG
  jumps straight to ~1 and the element is removed essentially
  immediately after initiation, as designed).
- `min_status` reaches `0.0` from frame 502 onward (confirms real
  `*Damage Evolution`-driven removal, not just SDEG accumulation without
  deletion).

Compare against the VUEL's own `WRITE(*,*)` trigger messages from round
3's stdout (same underlying physics, diagnostics didn't change the
mechanics): **first VUEL failure at `t=5.0098e-05`**, 398 total events
spread to `t=9.47e-05`.

**First ghost death (`5.0205e-05`) vs first VUEL death (`5.0098e-05`):
~1.07e-7 s apart.** That's one field-output sampling interval (1001
frames over the 1e-4s step = ~1.07e-7s/frame) -- i.e. this is about as
tight as this particular diagnostic's time resolution can show. The
*actual* solver increment is much finer (~15,051 increments over the
same step, ~6.6e-9s/increment), so the true offset could be anywhere
within that ~16-increment-wide sampling window. 396 ghost deletions vs
398 VUEL failures is also a close count match.

**This looks like the two mechanisms are genuinely near-synchronized now
-- round 2's threshold calibration (`EPS_FAIL=0.1138`,
`ghost-ductile-failure-strain=1e-6`) was correct.** Round 3's apparent
"zero ghost deletions" was a false negative from checking `.sta`/`.msg`
text, which don't report native deletions by default -- the field-output
request in round 4 was the right fix, not another threshold change.

## What's needed next: visualization

The user wants high-quality MP4s/images and a final report once the
numbers are in. Since rendering contour plots from the ODB needs
Abaqus/CAE's own Python scripting (not something doable without Abaqus
locally), can you write an `abaqus python` (or `abaqus cae noGUI=`)
script that, run on ROAR against `flat_vg_r4.odb`:

1. Renders a sequence of PNG frames over roughly `t=4.5e-05` to
   `t=1.0e-04` (the impact/failure-cascade window) showing the deformed
   Plate-1 instance, colored by `STATUS` on the ghost elset (so deletion
   is visible) and/or `PEEQ`, with the Ball-1 instance visible for
   context. A reasonable frame rate for the final MP4 is ~24-30fps; pick
   however many ODB frames within that window map cleanly to that (we
   have field output roughly every 1.07e-7s in that window from this
   run, so there's plenty to sample from).
2. A second view/coloring pass isn't required but would help: one pass
   colored by ghost `STATUS`/deletion, one by displacement magnitude or
   velocity, if that's easy to add without much extra work.
3. Saves PNGs to a clearly named output directory (e.g.
   `Flat-vuel-ghost-r4/frames/`) rather than assembling the MP4 itself --
   I'll pull the PNGs and do the ffmpeg assembly plus the written report
   on my end.
4. Include a short note on exact camera/view settings used and the exact
   field-output frame indices rendered, so this is reproducible.

No new calibration or threshold work needed for this round -- the
physics result from this run stands. This is purely the visualization
step for the deliverable the user asked for.

## Evidence retained

`verification/roar/t_stage6/evidence_20261005_r4/`: `ghost_diagnostics.csv`,
`flat_vg_r4.sta`, `flat_vg_r4.msg`, `stage6_flat_vg_r4_56091072.out`.
