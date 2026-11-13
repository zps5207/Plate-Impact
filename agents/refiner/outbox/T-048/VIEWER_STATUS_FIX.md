# Fiber STATUS viewer correction

`odb_viewer.py` and `export_odb_viewer.py` here are replacement copies of the corresponding files in `verification/roar/`. The Hub can diff and apply them after review. The current viewer always draws every fiber segment; its existing exports contain only host STATUS. These replacements hide fiber segments with `STATUS=0` whenever fiber STATUS is available.

For the **existing** vp4 viewer exports, use the probe's sidecar after its frame count, time values, and fiber segment count pass validation:

```text
python odb_viewer.py vals_native_viewer.npz --fiber-status native_vp4_fiber_status.npz
python odb_viewer.py vals_vuel_viewer.npz --fiber-status vuel_vp4_fiber_status.npz
```

For a **future** ODB export, the patched `export_odb_viewer.py` writes `fiber_status` directly into its NPZ when the ODB contains fiber STATUS. The patched viewer then picks it up automatically. If no fiber STATUS exists, the exporter issues a warning and omits the array; the viewer draws all segments as before.

The sidecar produced by `vp4_odb_probe.py` uses the same sorted `FIBERS` element-set order as the original exporter. Both existing vp4 exports contain 206,930 fiber segments and exactly the probe's 200 frame indices. The probe writes `status_field_present`; the viewer rejects a sidecar whose ODB did not contain fiber STATUS. The sidecar's exact times and status width are checked when loaded. The old viewer exports do not contain per-element labels, so ordering cannot be independently proved from those files alone; the shared extraction rule is the available mapping evidence. Do not interpret a disappeared line as proof of the physical failure mechanism without the ODB fields.

Validation performed locally: Python AST parse of all three patched files; synthetic two-frame sidecar check showing a deleted line disappears; PyVista 0.49.1 line-cell replacement check; metadata match for both 200-frame vp4 exports. A production ODB extraction and full viewer render have not yet been run.
