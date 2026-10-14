# Stage 6 energy and translucent-fiber handoff

## Delivered behavior

### Whole-model energy CSV

`extract_energy_history.py` opens the ODB read-only, finds the unique assembly
history region containing `ALLKE`, `ALLIE`, and `ALLWK`, and writes the full
selected step to `energy_history.csv`. It adds `ALLVD` and `ETOTAL` when they
exist in that same region. Before writing, it requires every included history
to be nonempty and to share the same sample count and time grid.

No CSV is bundled because this workstation does not have the 5.2 GB ODB or
Abaqus. Generate it on ROAR with:

```text
abaqus python extract_energy_history.py flat_vg_r4.odb \
  --output energy_history.csv
```

Expected required header prefix:

```text
time,ALLKE,ALLIE,ALLWK
```

`ALLVD` and/or `ETOTAL` follow when available. The final console message states
the sample count, selected variables, step, and history region.

### Translucent-host fiber pass

The renderer now supports a `fibers` pass composed of:

- `EMBMESH_GHOST_DIAGNOSTICS` from `PLATE-1`, colored blue-gray at 65%
  translucency;
- `EMBFIB-1.EMBMESH_FIBERS_T0` and
  `EMBFIB-1.EMBMESH_FIBERS_T90`, colored opaque red; and
- opaque dark-gray `BALL-1` for context.

It uses a deformed geometry plot with fixed instance colors rather than a
field contour. The existing 4.5e-5 to 1.0e-4 time window, 240-frame sampling,
1920x1080 output, unit deformation scale, and first-frame frozen `Iso` camera
are retained. The fibers are embedded within the same plate envelope, so the
existing camera fit remains appropriate. The complete fiber styling is saved
under `fiber_render` in `render_manifest.json`.

The default pass set is now `status,displacement,fibers`, ensuring the new pass
still runs if Abaqus strips the explicit `--passes` option. Since the first two
passes are already complete, first verify argument recovery and then request
only the new pass:

```text
ABQ_RENDER_ARGUMENTS_ONLY=1 abaqus cae noGUI=render_ghost_failure.py -- \
  flat_vg_r4.odb --output-dir Flat-vuel-ghost-r4/frames --passes fibers

abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames --passes fibers
```

If `recovered_arguments` includes `--passes`, require:

- completion status `COMPLETE` and `png_count: 240`;
- manifest `render_passes: ["fibers"]`;
- 240 files from `fibers/fibers_0000.png` through
  `fibers/fibers_0239.png`; and
- visible opaque red fibers through the translucent ghost hosts, with Ball-1
  present at least in the early frames.

If Abaqus strips `--passes fibers`, the default regenerates all three passes;
then `png_count` is 720, but the same 240 fiber PNGs are required.

## Files and SHA-256

- `render_ghost_failure.py`
  `e73ce821a8fb3c112658c44fb7e2bb29fd36567a02cfa883e1a0960debb42881`
- `extract_energy_history.py`
  `d3bd4f0b8f00b858443de605fd05116f3f0c6c03c147b1a968c820badc87ae95`
- `probe_visualization_imports.py`
  `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`
- `validate_render_ghost_failure.py`
  `f2cb41e6c19104643800faf1b93be6aefd133b72b552a48ef3e06cf5d7c68d21`
- `validate_energy_history.py`
  `845a2515b7879853bde8cd3af6822da9d9aafa2d38b8330caf69109eb313e4b1`
- `RENDERING.md`
  `0694e7fa4292f07f036842254622d52147967623a25d7d76900fbae5fce2a7b6`

## Local checks

- All five Python files compile with Python 3.12.
- `validate_render_ghost_failure.py` passes, including the established noGUI,
  argument-recovery, STATUS-position, sampling, and camera contracts plus the
  new fiber display-group membership, deformed plot state, colors, and
  translucencies.
- `validate_energy_history.py` passes with a synthetic ODB contract, exercising
  case-insensitive step lookup, assembly-region selection, all five requested
  energy columns, CSV shape and order, ODB closure, and rejection of mismatched
  history lengths.
- The source deck confirms the fiber instance and both fiber elset names used
  by the renderer.

## Remaining ROAR gates

The Abaqus 2024 `Viewport.setColor` execution, actual translucent composition,
real ODB history-region contents, energy sample count/values, and generated
CSV/PNG/manifest artifacts require the ROAR run. No calibration or physics
input was changed, and the unrelated displacement-pass ball/debris polish was
intentionally left out of scope.
