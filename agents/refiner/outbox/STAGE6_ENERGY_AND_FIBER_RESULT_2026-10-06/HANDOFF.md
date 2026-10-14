# Stage 6 fiber-color API correction

## Root cause

The failed call combined a valid `Viewport.setColor(colorMapping=...)` call
with unsupported `colors` and `translucencies` dictionary keywords. Abaqus
2024 exposes three relevant, separate overloads:

1. `setColor(initialColor=..., translucency=...)`;
2. `setColor(colorMapping=...)`; or
3. `setColor(leaf=..., edgeColorWireHide=..., edgeColorFillShade=...,
   fillColor=..., nodeSymbolColor=...)`.

There is no `colors` or `translucencies` keyword, matching ROAR's immediate
`TypeError: keyword error on colors`.

## Correction

`set_fiber_display()` now builds separate ghost, fiber, and ball leaves and
uses only Abaqus 2024-supported signatures:

- the ghost leaf remains on `initialColor=#9EADBA` with
  `translucency=0.65`;
- both fiber elsets receive explicit red edge/fill/node colors through their
  shared leaf; and
- Ball-1 receives explicit dark-gray edge/fill/node colors through its leaf.

Abaqus documents translucency as applying to objects drawn using
`initialColor`. The explicitly colored fiber and ball leaves therefore remain
opaque while the ghost host is translucent. The invalid color-mapping
dictionary call was removed completely.

No field selection, frame sampling, camera, output size, argument recovery,
energy extraction, or physics behavior changed. The successful energy CSV
needs no further work.

## ROAR verification

The prior argument-only check already confirmed `--passes fibers` recovery.
First run a one-frame visual/API smoke test to avoid waiting on 240 frames if
another Abaqus-specific issue appears:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke --passes fibers --frame-count 1
```

Require:

- `render_ghost_failure.status.json` says `COMPLETE` with `png_count: 1`;
- `fiber-smoke/fibers/fibers_0000.png` exists; and
- the PNG shows red fibers through a translucent blue-gray host, with the
  dark-gray ball visible.

Then run the full fiber pass:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames --passes fibers
```

Require completion status with `png_count: 240`, manifest
`render_passes: ["fibers"]`, and exactly 240 files from
`fibers/fibers_0000.png` through `fibers/fibers_0239.png`. As in the prior
handoff, if Abaqus unexpectedly strips `--passes fibers`, the three-pass
default renders 720 PNGs; the 240 fiber PNGs are still required.

## Files and SHA-256

- `render_ghost_failure.py`
  `66379e5f6ea432e2339f81a4bf14e4122c93469735b02254c99364a3ea561ee2`
- `validate_render_ghost_failure.py`
  `d10f9a2bfa527110cce2e6376fff218ad5d0eae604d9443e40e32750add8b7db`
- `RENDERING.md`
  `5f446f7126007e763d7e02291a5fe95d8d1630ec2dce48f9366cb621ef51931d`
- `extract_energy_history.py` (unchanged)
  `d3bd4f0b8f00b858443de605fd05116f3f0c6c03c147b1a968c820badc87ae95`
- `validate_energy_history.py` (unchanged)
  `845a2515b7879853bde8cd3af6822da9d9aafa2d38b8330caf69109eb313e4b1`
- `probe_visualization_imports.py` (unchanged)
  `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`

## Local verification

- All five Python files compile with Python 3.12.
- `validate_render_ghost_failure.py` passes.
- Its strict `setColor` fixture now accepts only the exact Abaqus 2024 keyword
  sets used by the two overloads and verifies all three call payloads.
- It explicitly rejects source regression to `colors={` or
  `translucencies={`.
- The display-group test verifies separate ghost, fiber, and ball leaves plus
  the original deformed geometry state.
- `validate_energy_history.py` still passes unchanged.

## Remaining gate

This workstation has neither Abaqus nor the ODB. Actual Abaqus execution and
the visual result of the initial-color translucency plus explicit leaf-color
overrides must therefore be confirmed by the one-frame ROAR smoke test before
the full 240-frame render.
