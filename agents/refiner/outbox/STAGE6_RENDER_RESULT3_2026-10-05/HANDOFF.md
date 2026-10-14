# Stage 6 renderer argument-recovery handoff

## Root cause and correction

ROAR Abaqus 2024 exposed this effective `sys.argv` shape to the renderer:

```text
ABQcaeK -cae -noGUI -tmpdir /tmp -lmlog ON flat_vg_r4.odb
```

The `--` separator and the passed `--output-dir` option were absent. The old
helper therefore sent Abaqus launcher flags into `argparse`.

`render_ghost_failure.py` now supports both forms:

1. If `--` survives, everything after it is parsed normally.
2. If Abaqus removes it, the helper requires exactly one token ending in
   `.odb`, uses that as the positional ODB, retains only known renderer options
   that remain, and discards Abaqus launcher flags.

The requested output directory is still exactly
`Flat-vuel-ghost-r4/frames`: that is the renderer's existing default, so
Abaqus's removal of the explicit duplicate option does not change this run.
No visualization or physics-facing setting changed.

## Explicit run-status file

Every invocation now writes `render_ghost_failure.status.json` in the launch
directory:

- `STARTED` before argument recovery/rendering;
- `FAILED` with exception type, message, traceback, and raw `sys.argv`; or
- `COMPLETE` with output directory, manifest path, and PNG count.

This file is authoritative because ROAR showed that Abaqus/CAE can swallow an
`argparse` `SystemExit` and still return shell exit code 0. Console messages
remain available in `abaqus.rpy`.

## Files and hashes

- `render_ghost_failure.py`
  SHA-256 `49cb116b29886b9f3e93223ef482633faf67d2b26e985830f38d53db459321eb`
- `probe_visualization_imports.py`
  SHA-256 `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`
- `validate_render_ghost_failure.py`
  SHA-256 `6e28f99e48c5ee82cb76af3c5fafbfb6032ef2cd0e630c2b48ae28d753d93e58`
- `RENDERING.md`

## ROAR verification sequence

The import probe is already confirmed on ROAR and is unchanged. First test only
the rewritten argument path; this does not open the 5.2GB ODB:

```text
ABQ_RENDER_ARGUMENTS_ONLY=1 abaqus cae noGUI=render_ghost_failure.py -- \
  flat_vg_r4.odb --output-dir Flat-vuel-ghost-r4/frames
```

Inspect `render_ghost_failure.status.json`. Required values:

```json
{
  "mode": "ARGUMENTS_ONLY",
  "recovered_arguments": ["flat_vg_r4.odb"],
  "status": "COMPLETE"
}
```

`raw_sys_argv` may contain `-cae`, `-noGUI`, `-tmpdir`, and `-lmlog`; none may
appear in `recovered_arguments`.

Then perform the full render:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

Do not accept the shell exit code alone. Require all of:

- `render_ghost_failure.status.json` says `COMPLETE`;
- `png_count` is 480;
- `manifest` names an existing `render_manifest.json`;
- `status/` contains 240 PNGs; and
- `displacement/` contains 240 PNGs.

## Local verification

- Syntax compilation passed for renderer, probe, and validator.
- The validator passed normal post-`--`, captured ROAR launcher, and
  no-separator-with-retained-option cases.
- The captured ROAR form parses to ODB `flat_vg_r4.odb`, default output
  `Flat-vuel-ghost-r4/frames`, and 240 frames.
- A full local harness execution used the synthetic non-`__main__` loader name,
  captured ROAR argv, and `ABQ_RENDER_ARGUMENTS_ONLY=1`; it executed the real
  top-level entry point and produced a `COMPLETE` status JSON with the recovered
  ODB argument.
- The status writer's `FAILED` payload was separately round-tripped through
  JSON.

## Remaining gate

Only the actual ROAR Abaqus 2024 runtime can confirm its raw argv, the
argument-only status file, ODB opening, and subsequent 480-frame render.
