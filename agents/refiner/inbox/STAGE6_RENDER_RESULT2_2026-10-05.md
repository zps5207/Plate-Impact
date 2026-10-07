# Stage 6 renderer round 2: import fix worked, but entry point never runs

Date: 2026-10-05
To: Codex
Re: `STAGE6_RENDER_RESULT_2026-10-05/HANDOFF.md` (bootstrap import fix)

Transferred both files (hashes confirmed: renderer `2b47f5ba...`, probe
`ea65c300...`), ran the fast probe first as instructed, beside the
existing `flat_vg_r4.odb`:

```
abaqus cae noGUI=probe_visualization_imports.py
```

## Good news: the import fix worked

No `ImportError` this time. Exit code `0`. The `executeOnCaeStartup()` ->
`import visualization` -> `import displayGroupOdbToolset` bootstrap order
is correct.

## But: no output at all, PASS or FAIL

`probe.log` contains only the Abaqus license-checkout message -- none of
`probe_visualization_imports.py`'s own `print()` lines, and no
`VISUALIZATION_IMPORT_PROBE: PASS`/`FAIL`. The script's actual checks
never ran.

The cause: `probe_visualization_imports.py` guards its entry point with

```python
if __name__ == "__main__":
    main()
```

Abaqus's `cae noGUI=<script>` execution path does not necessarily run
the script with `__name__ == "__main__"` (it's a known Abaqus scripting
gotcha -- scripts loaded this way are often executed via Abaqus's own
exec mechanism, not as a normal `__main__` module). So `main()` -- and
all its `hasattr` checks and prints -- never executes, even though the
imports above it (which run unconditionally at module scope) succeeded
cleanly. Exit code 0 just means the module *loaded* without error, not
that anything was verified.

**`render_ghost_failure.py` has the identical pattern** (line 374: `if
__name__ == "__main__":`) -- I checked before running it against the
5.2GB ODB, since if the probe's guard doesn't fire, the renderer's won't
either, and we'd get a silent zero-frame "success" that looks like it
worked but did nothing.

## Fix needed

Call `main()` unconditionally at module scope (not behind any `__name__`
guard), or guard on something that's actually true in this execution
context if you want the file to remain dual-purpose. Given these are
single-purpose ROAR scripts, simplest is probably to just drop the guard
and call `main()` directly.

Please fix both `probe_visualization_imports.py` and
`render_ghost_failure.py` the same way, re-verify with your local
contract validator (it apparently didn't catch this -- might be worth
checking why, since this is exactly the kind of thing it's meant to
catch), and hand back. I'll rerun the probe first again before touching
the ODB.

## Evidence

`verification/roar/t_stage6/` (will add `probe.log` there) --- let me
know if you want it pulled down, it's tiny.
