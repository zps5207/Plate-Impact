# Stage 6 round 4 visualization: import error on ROAR

Date: 2026-10-05
To: Codex
Re: `STAGE6_ROAR_RESULT_R4_2026-10-05/HANDOFF.md` (render_ghost_failure.py)

Transferred `render_ghost_failure.py` (SHA-256 `8e7e91d5...`, matches
your handoff) beside `flat_vg_r4.odb` on ROAR and ran exactly:

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

## Result: immediate ImportError, zero frames rendered

```
Abaqus License Manager checked out the following license:
"cae" from Flexnet server license2.2e.hpc.psu.edu
<30 out of 50 licenses remain available>.
ImportError: No module named 'displayGroupOdbToolset'
File "render_ghost_failure.py", line 34, in <module>
    import displayGroupOdbToolset as display_group
Abaqus Error: cae exited with an error.
```

The `cae` license checked out fine (30/50 available), so this isn't a
licensing problem -- `displayGroupOdbToolset` genuinely isn't importable
in this `abaqus cae noGUI=` execution context on ROAR's Abaqus 2024
install. I don't want to guess at the right Abaqus/CAE scripting API
substitute myself (per the project's "don't guess Abaqus semantics, test
on ROAR" rule) -- this needs your investigation into either:

- a different import path/module name for this Abaqus version, or
- whether `displayGroupOdbToolset` requires a different entry point than
  `noGUI=` (e.g. some CAE display-group APIs are only available when a
  full CAE session/viewport context is active, not in pure script mode),
  or
- whether this needs `abaqus viewer -noGUI=` instead of `abaqus cae
  noGUI=` for ODB visualization specifically.

Nothing else was reached -- no frames, no manifest, no log beyond the
license checkout and this traceback. Happy to test a fixed version
immediately; the ODB (`flat_vg_r4.odb`) is already sitting on ROAR at
`/storage/home/zps5207/scratch/vuel_stage6_flat_vg_r4_20261005_01/`, so
you don't need to resend it if your fix doesn't change the script's
physics-facing selections.
