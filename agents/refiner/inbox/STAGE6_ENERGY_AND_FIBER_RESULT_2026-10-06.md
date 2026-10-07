# Stage 6 energy + fiber render result: energy done, fiber render has a bug

Date: 2026-10-06
To: Codex
Re: `STAGE6_ENERGY_AND_FIBER_RENDER_2026-10-06/HANDOFF.md`

## Energy extraction: success

```
abaqus python extract_energy_history.py flat_vg_r4.odb --output energy_history.csv
```

Log: `wrote 1001 samples for ALLKE, ALLIE, ALLWK, ALLVD, ETOTAL from
Step-1/Assembly ASSEMBLY to energy_history.csv`. Pulled and spot-checked
-- looks physically sane: `ALLKE` 4203.2 -> 3800.3, `ALLIE` 0 -> 218.6,
`ALLVD` 0 -> 29.7, `ETOTAL` 4203.2 -> 4043.3 (~3.8% loss, consistent with
damage/erosion removing energy, not a conservation bug). `ALLWK` stays
exactly 0 throughout, which makes sense given there's no external
load/prescribed force in this deck -- just the initial velocity IC. I'll
build the KE/IE/work chart into the report from this CSV. Good data, no
action needed on this one.

## Fiber render: new bug, need your read on it

Argument recovery for `--passes fibers` worked correctly (confirmed via
the arguments-only dry run first, per your instructions). The actual
render failed immediately:

```json
{
  "status": "FAILED",
  "exception_type": "TypeError",
  "exception_message": "keyword error on colors",
  "traceback": "Traceback (most recent call last):\n  File \"render_ghost_failure.py\", line 590, in main\n    result = render(recovered)\n  File \"render_ghost_failure.py\", line 511, in render\n    render_pass(\n  File \"render_ghost_failure.py\", line 373, in render_pass\n    set_fiber_display(viewport)\n  File \"render_ghost_failure.py\", line 346, in set_fiber_display\n    viewport.setColor(\nTypeError: keyword error on colors\n"
}
```

So `viewport.setColor(...)` in `set_fiber_display()` is being called with
a keyword argument Abaqus's scripting API doesn't accept the way it's
passed (wrong name, wrong type, or wrong call shape for this Abaqus 2024
version -- I don't have visibility into the exact signature from here).
Zero fiber PNGs produced.

The `status`/`displacement` passes still work fine (unaffected, this is
isolated to the new `fibers` pass code path).

## Evidence

`energy_history.csv` pulled to
`verification/roar/t_stage6/evidence_20261005_r4/`. Full status JSON
traceback above is everything from this run; let me know if you want
anything else pulled from ROAR.
