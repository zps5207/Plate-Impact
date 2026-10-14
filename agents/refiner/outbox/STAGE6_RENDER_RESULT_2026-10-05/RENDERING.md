# R4 visualization recipe

Run from the directory containing `flat_vg_r4.odb` and this bundle:

First run the fast import probe; it does not open the ODB or render frames:

```text
abaqus cae noGUI=probe_visualization_imports.py
```

Expected final line: `VISUALIZATION_IMPORT_PROBE: PASS`.

Then run the renderer:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

Defaults:

- Step: `Step-1`
- Time window: `4.5e-05` through `1.0e-04` seconds
- Sampling: 240 evenly spaced available ODB frames, including both endpoints
- Intended playback: 30 fps, 8 seconds
- Pass 1: deformed ghost plate colored by `STATUS` from 0 to 1, with Ball-1
  retained for context
- Pass 2: deformed Plate-1 and Ball-1 colored by displacement magnitude
- Deformation scale: 1.0
- Camera: Abaqus `Iso` preset, fitted once at the first sampled frame with the
  ghost plate and ball visible, then frozen for every pass and frame
- Edges/background: feature edges on a white background
- Resolution: 1920 x 1080 PNG

Outputs:

```text
Flat-vuel-ghost-r4/frames/
  status/status_0000.png ... status_0239.png
  displacement/displacement_0000.png ... displacement_0239.png
  frame_map.csv
  render_manifest.json
```

`render_manifest.json` records the exact selected ODB frame indices and step
times, all captured numerical camera parameters, view preset, fit frame,
contour settings, resolution, passes, and intended frame rate. `frame_map.csv`
provides the same frame-to-PNG mapping in compact tabular form.

Optional velocity instead of displacement:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames-status-velocity \
  --passes status,velocity
```

MP4 assembly after pulling the PNG directories:

```text
ffmpeg -framerate 30 -i status/status_%04d.png \
  -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p status.mp4

ffmpeg -framerate 30 -i displacement/displacement_%04d.png \
  -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p displacement.mp4
```

The script intentionally performs no calibration or physics changes. It opens
the existing ODB read-only and only writes PNG/CSV/JSON visualization outputs.
