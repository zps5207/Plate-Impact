# R4 energy extraction and visualization recipe

Run from the directory containing `flat_vg_r4.odb` and this bundle:

First run the fast import probe; it does not open the ODB or render frames:

```text
abaqus cae noGUI=probe_visualization_imports.py
```

Expected final line: `VISUALIZATION_IMPORT_PROBE: PASS`.

Both the probe and renderer call their entry points unconditionally because
Abaqus `cae noGUI=` may execute a script under a module name other than
`__main__`.

Next verify Abaqus's rewritten argument list without opening the 5.2GB ODB:

```text
ABQ_RENDER_ARGUMENTS_ONLY=1 abaqus cae noGUI=render_ghost_failure.py -- \
  flat_vg_r4.odb --output-dir Flat-vuel-ghost-r4/frames
```

Inspect `render_ghost_failure.status.json`. It must say `"status": "COMPLETE"`,
`"mode": "ARGUMENTS_ONLY"`, and show `flat_vg_r4.odb` in
`recovered_arguments`. Abaqus launcher flags may appear in `raw_sys_argv` but
must not appear in `recovered_arguments`.

The existing STATUS and displacement passes have already completed on ROAR.
Render only the new fiber pass with:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames --passes fibers
```

If Abaqus removes `--passes fibers` from its rewritten argument list, the
renderer safely falls back to its new three-pass default, so the fiber pass is
still produced (along with regenerated STATUS and displacement frames).

To deliberately run all default passes:

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
- `STATUS` output position: detected from the selected ODB frames, preferring
  Abaqus's documented `WHOLE_ELEMENT` position; the chosen, common, and
  observed positions are recorded in the manifest
- Pass 2: deformed Plate-1 and Ball-1 colored by displacement magnitude
- Pass 3: deformed diagnostic ghost hosts at 65% translucency, opaque red
  `EMBFIB-1` fibers (`EMBMESH_FIBERS_T0` and `EMBMESH_FIBERS_T90`), and an
  opaque dark-gray Ball-1. This geometry pass uses fixed colors, not contours.
  The host uses Abaqus 2024's `initialColor`/`translucency` call; the fiber and
  ball leaves use explicit edge/fill/node color overrides so they remain
  opaque. No unsupported color-mapping dictionary keywords are used.
  Node symbols and labels are explicitly disabled. Free edges are rendered at
  `THICK` width so the T3D2 centerlines and outer solid silhouettes remain,
  while the dense host surface mesh is suppressed. These geometry options are
  set before styling, with ODB color-code override enabled; host translucency
  and explicit bright-red fiber/dark-gray ball leaf colors are applied last.
  This ordering avoids the uniform-green reset observed when a disabling
  CommonOptions update followed the color calls.
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
  fibers/fibers_0000.png ... fibers_0239.png
  frame_map.csv
  render_manifest.json
```

`render_manifest.json` records the exact selected ODB frame indices and step
times, all captured numerical camera parameters, view preset, fit frame,
contour settings, resolution, passes, intended frame rate, and the detected
`STATUS` output position. `frame_map.csv`
provides the same frame-to-PNG mapping in compact tabular form.

The manifest's `fiber_render` object records the fiber instance and elsets,
host elset, colors, translucency, and deformed plot state.

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

ffmpeg -framerate 30 -i fibers/fibers_%04d.png \
  -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p fibers.mp4
```

The script intentionally performs no calibration or physics changes. It opens
the existing ODB read-only and only writes PNG/CSV/JSON visualization outputs.
It also writes `render_ghost_failure.status.json` in the launch directory with
`STARTED`, `FAILED`, or `COMPLETE`; use this file rather than the shell exit code
because Abaqus/CAE may swallow Python `SystemExit` failures.

## Whole-model energy history

Run the extractor with Abaqus Python; this reads the ODB and writes no changes
to it:

```text
abaqus python extract_energy_history.py flat_vg_r4.odb \
  --output energy_history.csv
```

The extractor finds the unique assembly history region containing `ALLKE`,
`ALLIE`, and `ALLWK`, verifies that all selected histories share one time grid,
and writes the complete `Step-1` history. `ALLVD` and `ETOTAL` are appended when
present in that same region. Expected header when both optional variables are
available:

```text
time,ALLKE,ALLIE,ALLWK,ALLVD,ETOTAL
```

If no assembly region has all required variables, multiple matching assembly
regions exist, or the histories are not aligned, the extractor stops with an
explicit diagnostic instead of emitting a misleading CSV.
