# Stage 6 renderer STATUS-position handoff

## Root cause and correction

The prior renderer hard-coded `STATUS` at `INTEGRATION_POINT`. Abaqus's
official output-variable reference classifies `STATUS` as a whole-element
variable, which agrees with the ROAR error:

<https://docs.software.vt.edu/abaqusv2025/English/SIMACAEOUTRefMap/simaout-c-exp-wholeelementvariables.htm>

The renderer now:

1. reads the `STATUS` field locations from every selected ODB frame;
2. chooses a location common to every selected frame, preferring
   `WHOLE_ELEMENT` as documented;
3. passes that selected constant to both camera setup and the STATUS render;
4. emits the selected/common/observed positions in `render_manifest.json`;
5. includes `status_output_position` in the authoritative completion status.

The fallback preference order is `WHOLE_ELEMENT`, `CENTROID`,
`INTEGRATION_POINT`, `ELEMENT_NODAL`, then `NODAL`. If no position is common
to all selected frames, the renderer stops with a diagnostic instead of
silently selecting an invalid location.

Argument recovery, noGUI bootstrapping, camera behavior, contour ranges,
frame selection, and motion-variable positions are otherwise unchanged.

## Files and hashes

- `render_ghost_failure.py`
  SHA-256 `ead34774461ca3e9ca137c84bc015cdd6bd63cf359e98c3a71b9c3094ef476bc`
- `probe_visualization_imports.py`
  SHA-256 `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`
- `validate_render_ghost_failure.py`
  SHA-256 `102833b22c3070bff300c321c30dde538fddaf85496dfd43bdf606743b07b918`
- `RENDERING.md`
  SHA-256 `bc44aff753069280418c797ff28a90719ca9ada0d77e0a53e1b81cbaacc814e7`

## ROAR verification

Run the full renderer from the directory containing the ODB and bundle:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

The console should report a line like:

```text
STATUS output position: WHOLE_ELEMENT (common: WHOLE_ELEMENT)
```

Do not rely on the shell exit code. Require all of:

- `render_ghost_failure.status.json` says `COMPLETE`;
- `status_output_position` is `WHOLE_ELEMENT` (or the actual common ODB
  location reported by the renderer);
- `png_count` is 480;
- `render_manifest.json` exists and records the STATUS position;
- `status/` contains 240 PNGs; and
- `displacement/` contains 240 PNGs.

If it fails, return the complete status JSON. The exception now distinguishes
missing STATUS metadata from positions that vary incompatibly among frames.

## Local verification

- Python syntax compilation passed for renderer, probe, and validator.
- The complete local contract validator passed.
- The validator exercises `WHOLE_ELEMENT` selection from ODB-style
  `FieldLocation` metadata and the value-position fallback.
- The validator rejects regression to the previous hard-coded
  `outputPosition=INTEGRATION_POINT` call.
- Existing noGUI bootstrap, unconditional entry point, ROAR argument recovery,
  argument-only execution, status JSON, sampling, and camera contract checks
  still pass.

## Remaining gate

This workstation has no Abaqus command or the 5.2 GB ODB. The actual ODB
position metadata and 480-frame render therefore remain to be verified on
ROAR with Abaqus 2024.
