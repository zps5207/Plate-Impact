# Stage 6 round 4 visualization handoff

## Deliverables

- `render_ghost_failure.py` — Abaqus/CAE noGUI renderer
- `RENDERING.md` — exact invocation, defaults, camera method, output layout,
  optional velocity pass, and ffmpeg commands
- `validate_render_ghost_failure.py` — local contract checks that do not require
  Abaqus

Renderer SHA-256:
`8e7e91d543304303aa90850b878e48b9d5537aa9ebf29e8dead4c93256dd2f87`

## Run on ROAR

Place `render_ghost_failure.py` beside `flat_vg_r4.odb`, then run:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

The script opens the ODB read-only and validates `Step-1`, `Plate-1`, `Ball-1`,
`EMBMESH_GHOST_DIAGNOSTICS`, and required fields before rendering.

## Default render plan

- Window: step time `4.5e-05` through `1.0e-04` seconds.
- Sampling: 240 evenly spaced available ODB frames, endpoints included.
- Playback: 30 fps, yielding 8 seconds per pass.
- Resolution: 1920 x 1080 PNG.
- Deformation: deformed shape at physical scale 1.0.
- View: standard Abaqus `Iso`, fitted once at the first selected frame while
  the ghost plate and Ball-1 are visible, then frozen across every frame and
  both passes.
- Styling: white background, feature edges, legend and state/time annotation.
- Status pass: only the `EMBMESH_GHOST_DIAGNOSTICS` plate elements plus Ball-1
  are displayed; ghost `STATUS` is fixed to a 0–1 two-interval contour so
  deletion appears as disappearing plate elements without rescaling flicker.
- Displacement pass: Plate-1 and Ball-1 colored by nodal `U` magnitude.

Outputs are written as:

```text
Flat-vuel-ghost-r4/frames/
  status/status_0000.png ...
  displacement/displacement_0000.png ...
  frame_map.csv
  render_manifest.json
```

The manifest records the exact selected ODB frame indices/times and captured
numerical camera position, target, up vector, clipping planes, width, and
height. This supplies the brief's reproducibility note from the actual ODB,
rather than guessing numerical camera values locally.

For a velocity second pass instead:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames-status-velocity \
  --passes status,velocity
```

## Local checks

- CPython syntax compilation passed for the renderer and validator.
- `validate_render_ghost_failure.py` passed. It imports the renderer with
  stubbed Abaqus modules, verifies the 240-of-550 deterministic sampling
  contract and endpoints, case-insensitive repository lookup, JSON-safe camera
  capture, and the required render/manifest tokens.
- API usage was reviewed against Abaqus scripting documentation for display
  group leaves, viewport annotations, graphics background, output intervals,
  and contour controls.

## Not locally verifiable

There is no local Abaqus/CAE or R4 ODB, so actual ODB opening, display-group
resolution, contour rendering, offscreen OpenGL, PNG creation, runtime, and
visual quality must be checked on ROAR. If the cluster's offscreen renderer
rejects its default OpenGL backend, retry with the site's supported Mesa/Xvfb
launch wrapper; do not change the script's physics-facing selections.
