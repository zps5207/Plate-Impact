# Fiber-volume interface

The inspected VUEL receives all material data through Abaqus `props` and contains no `UEXTERNALDB`, file open, or common-block ingestion route for fiber-volume corrections. embmesh therefore writes a deterministic CSV with columns `element_label,host_volume,fiber_volume,volume_fraction,length_t0,length_t90`; a future companion UEL adapter can ingest this file without changing the copied UEL formulation.

