# Stage 6 fiber styling reset correction

## Evidence and root cause

I inspected the supplied round-3 smoke PNG. It is uniformly opaque green with
thick black silhouettes: node markers are gone, but host translucency and all
three custom colors are absent exactly as reported.

The focused round-2-to-round-3 diff identifies the regression. The previous
bundle applied host translucency and leaf colors, then made a late
`CommonOptions.setValues(... colorCodeOverride=OFF ...)` call. That disabling
display update replaced the custom styling with Abaqus's uniform default green.
The manifest recorded requested settings, not proof that they survived later
viewport mutations.

The first smoke run already demonstrated that Abaqus preserves host
translucency and custom leaf colors when display options are configured first
and `setColor` operations occur last. This correction returns to that proven
ordering while retaining the useful round-2 geometry cleanup.

## Correction

`set_fiber_display()` now performs operations in this order:

1. construct the separate ghost, fiber, and ball leaves;
2. set deformed geometry;
3. configure `FREE` edges, `THICK` width, all node/label flags `OFF`, and
   `colorCodeOverride=ON`;
4. apply host `initialColor=#9EADBA` and `translucency=0.65`;
5. apply explicit bright-red edge/fill colors to the fiber leaf; and
6. apply explicit dark-gray edge/fill colors to the ball leaf.

There are no display-option mutations after the three color calls. The manifest
now accurately records `color_code_override: true`. `nodeSymbolColor` remains
absent, so the original dot-clutter trigger is not restored.

No frame, camera, display-group, energy, physics, or output-path behavior
changed.

## ROAR verification

Repeat the one-frame gate with a new directory:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r3 \
  --passes fibers --frame-count 1
```

Require `COMPLETE`, `png_count: 1`, and visually confirm:

- the plate is translucent blue-gray rather than opaque green;
- continuous thick bright-red fiber lines are visible through it;
- Ball-1 is dark gray and visually distinct;
- circular node markers remain absent; and
- the dense host surface mesh remains suppressed.

Only after that passes, run the 240-frame fiber pass:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames --passes fibers
```

Require `COMPLETE`, `png_count: 240`, manifest `render_passes: ["fibers"]`,
and 240 PNGs. Spot-check early, middle, and late frames before MP4 assembly.

## Files and SHA-256

- `render_ghost_failure.py`
  `eefec88cb9f58fc98d3009d4c72a36254793aae6cb32e850954213f5c3a8f1e4`
- `validate_render_ghost_failure.py`
  `5fe2baaa3664456aa238b687b7f6c92b880334883b7001adde02156213c516aa`
- `RENDERING.md`
  `6ae3d127e8c6a8b7fcdf0f5b16b889e1716797366360127b1b6ef551e0af7d7f`
- `extract_energy_history.py` (unchanged)
  `d3bd4f0b8f00b858443de605fd05116f3f0c6c03c147b1a968c820badc87ae95`
- `validate_energy_history.py` (unchanged)
  `845a2515b7879853bde8cd3af6822da9d9aafa2d38b8330caf69109eb313e4b1`
- `probe_visualization_imports.py` (unchanged)
  `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`

## Local verification

- All five Python files compile with Python 3.12.
- `validate_render_ghost_failure.py` passes.
- Its fixture verifies `FREE`, `THICK`, color-code override `ON`, and all
  node/label flags `OFF`.
- It enforces source ordering: the complete CommonOptions cleanup must precede
  host translucency, fiber color, and ball color calls.
- It continues to reject `nodeSymbolColor`, unsupported plural color keywords,
  and the old STATUS integration-point regression.
- Existing noGUI, argument recovery, display-group, camera, sampling, and
  status-file contracts pass.
- The unchanged energy history validator passes.

## Remaining gate

The one-frame ROAR render must confirm that the now-final `setColor` operations
survive and that `FREE`/`THICK` expose legible T3D2 centerlines. Do not start the
full render until the image meets every visual criterion above.
