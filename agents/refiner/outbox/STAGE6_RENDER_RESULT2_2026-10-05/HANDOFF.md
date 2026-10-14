# Stage 6 renderer entry-point fix

## Exact fix

ROAR proved that the corrected Abaqus bootstrap/import sequence succeeds. The
probe then exited without running because `cae noGUI=` did not assign
`__name__ == "__main__"`.

Both single-purpose Abaqus scripts now end with an unconditional call:

```python
main()
```

The prior `if __name__ == "__main__":` guards are gone from both
`render_ghost_failure.py` and `probe_visualization_imports.py`.

No other renderer line changed. A no-index diff confirms that all ODB
selections, visualization settings, frame sampling, camera behavior, output
paths, and read-only handling are identical to the import-fixed renderer that
loaded successfully on ROAR.

## Files and hashes

- `render_ghost_failure.py`
  SHA-256 `f03557b69796b707ed665d59be2d7275789efe60c238e5beda6de191fba8f204`
- `probe_visualization_imports.py`
  SHA-256 `87a1bdc92b0aeefa2f2f3ffc51aedb1184b9ab4b96dbafdad265bf3fd86c9c65`
- `validate_render_ghost_failure.py`
  SHA-256 `7523edabce975c539afb6c47538065d0602b2453ce591e0ee02e9170152bcc62`
- `RENDERING.md` — updated with the Abaqus entry-point explanation

## Strengthened local validator

The earlier validator imported the renderer as a normal Python module, so its
own test environment made the guarded pattern look valid and failed to model
Abaqus's loader semantics. The validator now:

1. parses both Abaqus scripts with `ast`;
2. requires the final top-level statement to be an argument-free `main()`;
3. rejects any `main()` call nested under a top-level `if`;
4. runs a regression fixture containing the old guarded pattern and proves it
   is rejected; and
5. executes the probe under the synthetic non-`__main__` module name
   `abaqus_cae_nogui_loader` and requires its PASS marker; and
6. removes only the verified final call in its local harness before loading the
   renderer helpers with stubbed Abaqus modules.

Syntax compilation and the strengthened validator both pass.

## ROAR verification order

Run the fast probe first:

```text
abaqus cae noGUI=probe_visualization_imports.py
```

It must now print its module paths/checks and end with:

```text
VISUALIZATION_IMPORT_PROBE: PASS
```

Then run the renderer:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

The renderer should print progress at frame 1, every 20 frames, and the final
frame of each pass, then report the output directory and manifest path.

## Remaining gate

The unconditional entry calls are statically and locally verified, but the
actual probe output and ODB render still require ROAR's Abaqus 2024 runtime.
