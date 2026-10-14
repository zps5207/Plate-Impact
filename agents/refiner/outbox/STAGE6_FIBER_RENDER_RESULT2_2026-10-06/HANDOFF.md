# Stage 6 fiber visibility and node-clutter correction

## Evidence reviewed

I inspected the pulled 1920x1080 `fibers_0000.png`, not only the written
description. It confirms both reported problems:

- hollow circular node symbols densely cover the plate and Ball-1; and
- the intended red fiber network is not legible, with only isolated red points
  visible through the clutter.

The host translucency and broad geometry are otherwise correct, and the
successful ROAR smoke run proves the corrected `setColor` overloads execute.

## Focused correction

The fiber pass now:

1. removes `nodeSymbolColor` from both leaf-color calls;
2. explicitly forces `nodeSymbols`, `nodeLabels`, element labels, and face
   labels `OFF`;
3. applies that cleanup *after* the leaf-color calls, preventing those calls
   from leaving symbol display enabled;
4. changes visible edges from `FEATURE` to `FREE`, retaining the T3D2
   centerlines and outer solid silhouettes while suppressing the dense host
   surface mesh;
5. changes global edge thickness from Abaqus's `VERY_THIN` default to `THICK`;
6. disables ODB color-code override so the explicit fiber color is not
   replaced; and
7. brightens the fiber red from `#D00000` to `#FF0000`.

The manifest now records `visible_edges: FREE`, `edge_line_thickness: THICK`,
`node_symbols: false`, and `color_code_override: false` under `fiber_render`.
The 65% host translucency, opaque fiber/ball leaf colors, display group, time
window, sampling, resolution, and camera are unchanged.

## ROAR verification

Repeat the one-frame smoke test before rendering the movie:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r2 \
  --passes fibers --frame-count 1
```

Require `COMPLETE`, `png_count: 1`, and visually confirm all of:

- no circular node-marker field on either plate or ball;
- no dense ghost surface-mesh pattern;
- continuous bright-red fiber centerlines are visible through the host;
- the translucent host retains its outer shape; and
- Ball-1 remains visible for context.

Only after that visual gate passes, run:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames --passes fibers
```

Require `COMPLETE`, `png_count: 240`, manifest `render_passes: ["fibers"]`,
and 240 PNGs. Spot-check early, middle, and late frames before assembling the
MP4.

## Files and SHA-256

- `render_ghost_failure.py`
  `0a9b31616ca22da559713ece2949c3bc03ad339fde8983316374dd0a5edf4c8b`
- `validate_render_ghost_failure.py`
  `ada26516c810383c26960fece403069a7fd4f7f46211616dc29597c7caac3e2c`
- `RENDERING.md`
  `954b4cbbf0b2e2e8c9d0763ad40ba1a5c61b95284b3b70569145732c480e70e7`
- `extract_energy_history.py` (unchanged)
  `d3bd4f0b8f00b858443de605fd05116f3f0c6c03c147b1a968c820badc87ae95`
- `validate_energy_history.py` (unchanged)
  `845a2515b7879853bde8cd3af6822da9d9aafa2d38b8330caf69109eb313e4b1`
- `probe_visualization_imports.py` (unchanged)
  `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`

## Local verification

- All five Python files compile with Python 3.12.
- `validate_render_ghost_failure.py` passes.
- Its fiber fixture verifies `FREE`, `THICK`, color-code override `OFF`, and
  every node/label toggle `OFF`.
- It rejects both `nodeSymbolColor` calls and enforces that node-symbol cleanup
  occurs after the ball leaf-color call.
- Existing display-group, translucency, opaque-color, noGUI, argument,
  STATUS-position, camera, and sampling contracts still pass.
- The unchanged energy history validator also passes.

## Remaining gate

Only Abaqus/CAE can confirm that `FREE` exposes the T3D2 lines as expected and
that `THICK` is sufficiently legible at final resolution. The one-frame visual
smoke test remains mandatory before the full render.
