# Stage 6 renderer import-fix handoff

## Root cause and fix

The failed script imported `displayGroupOdbToolset` before initializing the
Abaqus Visualization module. In a `cae noGUI=` kernel, ODB-specific display
objects are loaded by the Visualization module; the corrected renderer uses
Abaqus's standard bootstrap order:

```python
from driverUtils import executeOnCaeStartup
executeOnCaeStartup()
import visualization
import displayGroupOdbToolset as display_group
```

This ordering is consistent with the Abaqus scripting reference's access path
for `viewport.odbDisplay.displayGroup` and with standard Abaqus noGUI output
scripts. `abaqus cae noGUI=` remains the correct entry point; switching to
Viewer is not required for this fix.

The renderer differs from the prior rejected file only by those bootstrap and
Visualization-import lines. All ODB selections, time window, frame sampling,
camera policy, contour variables, PNG settings, and read-only behavior are
unchanged.

## Files and hashes

- `render_ghost_failure.py`
  SHA-256 `2b47f5bab966fb612f235f2b38ea58310c43214619fd9f9731b7475ad9392da2`
- `probe_visualization_imports.py`
  SHA-256 `ea65c300430786a075979a1514ae79fb6db7d180beca6b9f82ff3939db7eb5eb`
- `RENDERING.md` — updated run sequence
- `validate_render_ghost_failure.py` — updated local import-order contract

## Fast ROAR verification first

Transfer the four files above beside `flat_vg_r4.odb`. Before touching the
5.2GB ODB, run:

```text
abaqus cae noGUI=probe_visualization_imports.py
```

Success ends with:

```text
VISUALIZATION_IMPORT_PROBE: PASS
```

The probe checks both required constructors (`LeafFromElementSets` and
`LeafFromPartInstance`) plus `session.Viewport`. It does not open the ODB.

Then rerun the unchanged render command:

```text
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

## Local checks

- CPython syntax compilation passed for the renderer, probe, and validator.
- The local contract validator passed with stubbed Abaqus, driver, Visualization,
  and display-group modules.
- The validator explicitly checks that `executeOnCaeStartup()` precedes
  `import visualization`, which precedes `import displayGroupOdbToolset`.
- A no-index diff confirmed that the renderer has no changes beyond the import
  bootstrap shown above.

## Remaining gate

Only ROAR's Abaqus 2024 installation can prove that the probe imports and the
subsequent ODB render succeed. If the probe still fails, retain its full stdout
and traceback; because it isolates startup/import behavior without the ODB,
that evidence will identify the next environment-specific issue cleanly.
