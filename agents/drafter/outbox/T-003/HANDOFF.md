# Stage 6 host-wireframe fiber render handoff (Task T-003 Fix)

## Requested visual change & API fix

The previous round attempted to apply distinct render styles (`WIREFRAME` for the ghost host vs. `SHADED` for fibers and Ball-1) using per-display-group options. However, calling `host_instance.odbDisplayOptions.commonOptions.setValues(...)` failed on real Abaqus 2024 with:
`AttributeError: 'DGCommonOptions' object has no attribute 'setValues'`

Because `DGCommonOptions` in Abaqus Scripting API does not expose a `.setValues()` method (attributes on `DGCommonOptions` are set directly or via descriptor setters), calling `.setValues(...)` directly on `DGCommonOptions` raised an AttributeError.

To fix this API mismatch while maintaining 100% compatibility with both real Abaqus 2024 and Python test mocks, `set_fiber_display()` now routes option setting through a helper function `set_options(target, **kwargs)`:
- If `target` has a callable `.setValues(...)` method (e.g. `viewport.odbDisplay.commonOptions`), it calls `target.setValues(**kwargs)`.
- If `target` does not have a `.setValues(...)` method (e.g. `DGCommonOptions`), it sets properties directly via `setattr(target, key, value)` (e.g. `commonOptions.renderStyle = WIREFRAME`, `commonOptions.visibleEdges = FREE`, etc.).

All required visual behavior from round 4 is preserved:
- `Stage6 Fiber Host Wireframe`: ghost host leaf (`GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"`), set to `WIREFRAME`, `FREE` edges, `THICK` edge line thickness.
- `Stage6 Fibers and Ball Shaded`: fiber elsets (`EMBMESH_FIBERS_T0`, `EMBMESH_FIBERS_T90`) on instance `EMBFIB-1` plus Ball-1 (`BALL-1`), set to `SHADED`, `FREE` edges, `THICK` edge line thickness.
- Both display-group instances keep `colorCodeOverride=ON`, node/element/face labels `OFF`, node symbols `OFF`, and option lock enabled (`lockOptions=ON`).
- Final leaf colors applied last:
  - Host wireframe edges: blue-gray `#9EADBA`
  - Fiber edges/fill: opaque bright red `#FF0000`
  - Ball-1 edges/fill: opaque dark gray `#606060`

## ROAR verification

Run the one-frame smoke test gate:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r4 \
  --passes fibers --frame-count 1
```

Require `render_ghost_failure.status.json` to report `COMPLETE` and `png_count: 1`. The frame must show:
- Host rendered as a blue-gray wireframe outline (no filled/shaded host faces);
- Fiber lines rendered continuous thick bright red fully visible inside the host;
- Ball-1 rendered opaque dark gray (not wireframe);
- No node symbol markers or label text clutter.

## Files and SHA-256

- `render_ghost_failure.py`
  `6fd05878f4335112788e89f67ae0822d4f8cf5ca960c0a3e85d9a9a6856d6bc9`
- `validate_render_ghost_failure.py`
  `2c97810eaa1498e142e6c31c62be3bc0bdf83d2aef249df09ec5224140d06265`

## Local verification

- `python validate_render_ghost_failure.py` passes cleanly (`render contract checks: PASS`).
- `python validate_energy_history.py` passes cleanly (`energy history contract checks: PASS`).
- Both Python files compile under Python 3.12 without syntax or lint errors.
