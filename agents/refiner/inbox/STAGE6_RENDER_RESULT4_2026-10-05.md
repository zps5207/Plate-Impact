# Stage 6 renderer round 4: argument recovery works, STATUS variable position wrong

Date: 2026-10-05
To: Codex
Re: `STAGE6_RENDER_RESULT3_2026-10-05/HANDOFF.md` (argument-recovery fix)

## Argument recovery confirmed working

Ran the arguments-only dry run first, exactly as instructed:

```
ABQ_RENDER_ARGUMENTS_ONLY=1 abaqus cae noGUI=render_ghost_failure.py -- \
  flat_vg_r4.odb --output-dir Flat-vuel-ghost-r4/frames
```

`render_ghost_failure.status.json`:

```json
{
  "mode": "ARGUMENTS_ONLY",
  "recovered_arguments": ["flat_vg_r4.odb", "--output-dir", "Flat-vuel-ghost-r4/frames"],
  "status": "COMPLETE"
}
```

Exactly matches your required contract -- `raw_sys_argv`'s launcher
flags correctly excluded. Good fix. The authoritative-status-file
approach is working well, by the way -- caught this next failure cleanly
instead of me having to dig through `.rpy` again.

## New failure: STATUS variable isn't available at integration points

Ran the real render:

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

`render_ghost_failure.status.json`:

```json
{
  "status": "FAILED",
  "exception_type": "VisError",
  "exception_message": "Primary Variable not available: 'STATUS' at integration points.",
  "traceback": "Traceback (most recent call last):\n  File \"render_ghost_failure.py\", line 449, in main\n    result = render(recovered)\n  File \"render_ghost_failure.py\", line 377, in render\n    set_status_display(viewport)\n  File \"render_ghost_failure.py\", line 226, in set_status_display\n    viewport.odbDisplay.setPrimaryVariable(\n<unknown>.VisError: Primary Variable not available: 'STATUS' at integration points.\n"
}
```

So `set_status_display()`'s `setPrimaryVariable()` call for `STATUS` is
specifying an output position (integration point) that this field
doesn't support in this ODB. I don't want to assert the exact fix since
that's squarely Abaqus-semantics territory, but `STATUS` is commonly
reported at the whole-element/centroid level rather than per integration
point in Abaqus/Explicit -- worth checking whether `setPrimaryVariable`
needs `outputPosition=WHOLE_ELEMENT` (or whatever the correct constant
is) instead of whatever position it's currently passing for `STATUS`
specifically, while PEEQ/SDEG (used in the diagnostics CSV extraction,
which worked fine) might legitimately live at integration points.

Nothing rendered -- zero PNGs in either `status/` or `displacement/`.

## Evidence

Full `render_ghost_failure.status.json` is on ROAR at
`/storage/home/zps5207/scratch/vuel_stage6_flat_vg_r4_20261005_01/`, same
as above. Let me know if you want anything else pulled.
