# Fiber-volume interface

The inspected VUEL receives all material data through Abaqus `props` and contains no `UEXTERNALDB`, file open, or common-block ingestion route for fiber-volume corrections. embmesh therefore writes a deterministic CSV with columns `instance,element_label,host_volume,fiber_volume,volume_fraction,length_t0,length_t90`; a future companion UEL adapter can ingest this file without changing the copied UEL formulation. The `instance` column disambiguates `element_label` when the same part is instanced more than once (each instance's host elements otherwise reuse the same part-local labels).

The current VUEL also has no element-ID lookup or per-element property table. Therefore it cannot consume the CSV directly: the correction output is produced and documented, but applying it requires a companion UEL/VUEL revision that reads the table (or a preprocessing step that supplies one property tuple per element). The mesher does not silently alter the formulation.
