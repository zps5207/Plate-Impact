# Stage 6 host-wireframe fiber render handoff

## Requested visual change

The fiber pass no longer relies on translucency. The ghost host is now a true
edges-only wireframe, while the embedded fibers and Ball-1 remain in a separate
shaded display group.

This requires two simultaneous Abaqus display groups because `renderStyle` is
otherwise global: setting the whole viewport to `WIREFRAME` would also turn
Ball-1 into wireframe, violating the brief.

`set_fiber_display()` now creates or refreshes:

- `Stage6 Fiber Host Wireframe`: the diagnostic ghost leaf, locked to
  `WIREFRAME`, `FREE` edges, and `THICK` edge width; and
- `Stage6 Fibers and Ball Shaded`: both fiber elsets plus Ball-1, locked to
  `SHADED`, `FREE` edges, and `THICK` edge width.

Both groups keep `colorCodeOverride=ON`, all node/label flags `OFF`, and are
made visible together. Their per-group options are locked against viewport
resynchronization. Colors are applied last:

- host wireframe edges: blue-gray `#9EADBA`;
- fiber edges/fill: opaque bright red `#FF0000`; and
- Ball-1 edges/fill: opaque dark gray `#606060`.

The host `initialColor`/`translucency` call and filled host faces are removed.
The manifest records the two display-group names, separate render styles, and
`host_filled_faces: false`.

## ROAR verification

Run only the required one-frame gate:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r4 \
  --passes fibers --frame-count 1
```

Require `render_ghost_failure.status.json` to report `COMPLETE` and
`png_count: 1`. The frame must show:

- the host as a visible blue-gray wireframe outline with no filled or shaded
  host faces;
- continuous thick bright-red fiber lines fully unobstructed inside it;
- Ball-1 still opaque dark gray, not wireframe;
- no circular node markers or labels; and
- no dense filled host surface mesh.

Do not run the full 240-frame pass until this visual gate is accepted. If the
run fails, return the complete status JSON because the new API surface is the
per-display-group `visibleDisplayGroups`/`displayGroupInstances` path.

## Files and SHA-256

- `render_ghost_failure.py`
  `8c6bd02d47a13f281d07aa89fc13a9f6ac15316ce08ba69976dea56d92f3b507`
- `validate_render_ghost_failure.py`
  `7fec90ecbbed5b2b8baea0bbc314d95b78dc38eec9cfd31c449ff5aaa176e399`
- `RENDERING.md`
  `614da4343e9fb4db8a52529f5858ceb368277f8d87b206d617445e3a2ee4cfb5`
- `extract_energy_history.py` (unchanged)
  `d3bd4f0b8f00b858443de605fd05116f3f0c6c03c147b1a968c820badc87ae95`
- `validate_energy_history.py` (unchanged)
  `845a2515b7879853bde8cd3af6822da9d9aafa2d38b8330caf69109eb313e4b1`
- `probe_visualization_imports.py` (unchanged)
  `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`

## Local verification

- All five Python files compile with Python 3.12.
- `validate_render_ghost_failure.py` passes.
- Its simulation verifies two visible named display groups, exact host/fiber/
  ball membership, host `WIREFRAME`, content `SHADED`, `FREE`/`THICK` settings,
  locked options, node/label suppression, and all three final leaf colors.
- It rejects any remaining host `initialColor`/`translucency` call and enforces
  that per-group configuration precedes every color call.
- Existing noGUI, argument recovery, STATUS position, camera, frame sampling,
  and status-file contracts still pass.
- The unchanged energy history validator passes.

## Explicitly deferred issue

Dead-element visibility in the displacement and fiber passes was not changed.
The known ball-through-unperforated-plate/scattered-fragment behavior remains
for a later brief, as requested.

## Remaining gate

This workstation has no Abaqus runtime or ODB. The one-frame ROAR smoke test
must confirm Abaqus 2024 creates both display-group instances, honors their
locked distinct render styles, and produces the expected composite image.
