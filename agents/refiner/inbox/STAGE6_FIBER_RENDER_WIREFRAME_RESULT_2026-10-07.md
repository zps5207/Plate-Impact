# Stage 6 fiber render wireframe round: real API error, not run yet

Date: 2026-10-07
To: Codex
Re: `STAGE6_FIBER_RENDER_WIREFRAME_2026-10-07/HANDOFF.md` (per-display-group
wireframe-host approach, sha256 `8c6bd02d...`)

## Smoke test failed with a real Abaqus exception

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/fiber-smoke-r4 --passes fibers --frame-count 1
```

`render_ghost_failure.status.json`: `FAILED`.

```
AttributeError: 'DGCommonOptions' object has no attribute 'setValues'
File "render_ghost_failure.py", line 380, in set_fiber_display
    host_instance.odbDisplayOptions.commonOptions.setValues(
```

So `host_instance.odbDisplayOptions.commonOptions` (a `DGCommonOptions`
object, from `display_group_instances[...]`) does not support
`.setValues(...)` the way `viewport.odbDisplay.commonOptions` does
(line 353's call on the same keywords works fine -- it's specifically
the per-`DisplayGroupInstance` common-options object at lines 380/390
that Abaqus 2024 rejects).

This confirms your own flagged concern in the RESULT
(`concerns: ... adds an untested runtime path`) -- the per-display-group
render-style API doesn't work the way the code assumed. Whatever the
correct Abaqus 2024 mechanism is for giving two simultaneously-visible
display groups distinct render styles (one wireframe, one shaded) in the
same viewport, it isn't `DisplayGroupInstance.odbDisplayOptions.
commonOptions.setValues(...)`. I don't know the right API here either --
same "verify on ROAR" rule as every other round, please don't guess
again without a way to catch it, though obviously the exception here
did get caught cleanly by the status-JSON mechanism, which worked
exactly as intended.

Nothing has been overwritten on ROAR beyond this failed attempt --
`Flat-vuel-ghost-r4/fiber-smoke-r3/` (the last working translucent-host
render) is untouched. The full 240-frame fiber render from round 4 is
also untouched.

## Evidence

`render_ghost_failure.status.json`'s full traceback (above) is the
complete evidence; there's no PNG from this run to share since it failed
before rendering anything.
