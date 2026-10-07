# Stage 6 fiber render round 3: node markers fixed, but translucency/fiber color regressed to nothing

Date: 2026-10-06
To: Codex
Re: `STAGE6_FIBER_RENDER_RESULT2_2026-10-06/HANDOFF.md` (FREE edges / THICK / node-symbol cleanup fix, sha256 `0a9b3161...`)

## Smoke test ran successfully

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r2 --passes fibers --frame-count 1
```

`render_ghost_failure.status.json`: `COMPLETE`, `png_count: 1`,
`status_output_position: WHOLE_ELEMENT`. No exception. Pulled and looked
at `fibers_0000.png` before running the full 240-frame pass, per your
instructions.

## The two round-2 problems are gone, but the pass now renders nothing useful

1. **Node-symbol dot clutter: fixed.** No circular markers anywhere in
   this frame. The `nodeSymbols`/`nodeLabels` cleanup worked.
2. **New regression: the entire model renders as flat, opaque, uniform
   green -- no translucency, no red fiber lines, no distinct ball
   color.** The plate and the ball are the exact same solid green, which
   looks like Abaqus's default "no custom color applied" session color,
   not the `host_color: "#9EADBA"` / `host_translucency: 0.65` /
   `fiber_color: "#FF0000"` / `ball_color: "#606060"` your
   `render_manifest.json` claims were set for this frame (full block
   below). In round 2, translucency at least visibly worked (plate read
   as gray-blue and see-through) even though the fibers themselves were
   nearly invisible. This round, translucency does not look applied at
   all, and neither does any fiber or ball color override.

The run reports `COMPLETE` with no caught exception, and the manifest's
`fiber_render` block looks internally correct -- so whatever `setColor`/
`translucency` calls are supposed to produce this image either aren't
being reached for this leaf/viewport state, or are being overridden by
something later in the pass (display-group reset, `colorCodeOverride`
interaction, or similar), without raising.

```json
"fiber_render": {
  "ball_color": "#606060",
  "color_code_override": false,
  "edge_line_thickness": "THICK",
  "element_sets": ["EMBMESH_FIBERS_T0", "EMBMESH_FIBERS_T90"],
  "fiber_color": "#FF0000",
  "host_color": "#9EADBA",
  "host_element_set": "EMBMESH_GHOST_DIAGNOSTICS",
  "host_translucency": 0.65,
  "instance": "EMBFIB-1",
  "node_symbols": false,
  "plot_state": "DEFORMED",
  "visible_edges": "FREE"
}
```

I have not run the full 240-frame render -- holding off until the fiber
pass actually shows translucency/fiber color, per the smoke-test-first
plan.

## Evidence

The smoke-test PNG is on ROAR at
`/storage/home/zps5207/scratch/vuel_stage6_flat_vg_r4_20261005_01/Flat-vuel-ghost-r4/fiber-smoke-r2/fibers/fibers_0000.png`,
and a copy is in the repo at
`verification/roar/t_stage6/evidence_20261006_fiber_smoke_r2/fibers_0000.png`,
alongside the full `render_manifest.json` on ROAR in the same directory
if you need the rest of the captured camera/state fields.
