# Notes for the next reporting period's report

Written 16 Oct 2026.

## Use the wireframe videos

The best figures from the node-contact speed series are the **wireframe symmetry-plane videos**
(`reports/nc_series_video/v{100..500}_wire_sidev.mp4`). The plate is vertical, the ball travels left to
right, and the blue fibers show how the plate and fibers fail as the ball passes through. Lead with these
in the next period's report. The isometric wireframe videos (`v*_wire_iso.mp4`) are the second choice.

## What is where

| Item | Location |
|---|---|
| Video report | `reports/NODE_CONTACT_SPEED_SERIES_REPORT_VIDEOS.html` (needs `nc_series_video/` beside it) |
| Original image report (kept for reference) | `reports/NODE_CONTACT_SPEED_SERIES_REPORT.html` and `reports/nc_series_img/` |
| All 30 videos | `reports/nc_series_video/` (5 speeds x status/wire x iso/side/sidev) |
| Report builder | `verification/roar/build_nc_report.py` (writes both reports) |
| Renderer | `verification/roar/render_ghost_failure.py`, view `sidev` is the vertical-plate camera |
| Render job | `verification/roar/render_variant.sbatch` |
| Frames on ROAR | `/storage/home/zps5207/scratch/ctv/nc/vNNN/frames_video/` (150 frames per pass and view, 0 to 70 us) |

## Settings used

- 150 frames from 0 to 70 us, encoded at 24 fps (about 6 s per video), H.264, 1920x1080.
- `side` is the original horizontal-plate symmetry view. `sidev` is the same view turned so the plate is a
  vertical band and the ball moves left to right.

## Things to improve next time

- The side views leave a lot of empty white space; content sits in the upper-left of the frame. The old `side`
  images do the same, so this is how the Abaqus camera width/height is applied here, not new. A tighter crop
  (or cropping in ffmpeg) would make the videos fill the frame.
- Impact happens in roughly the first 10 to 15 frames of 150. A narrower time window (for example 0 to 25 us)
  or non-uniform frame spacing would show the failure in more detail.
- Render jobs need only about 1 to 3 minutes; request 16 GB, not 48 GB.
