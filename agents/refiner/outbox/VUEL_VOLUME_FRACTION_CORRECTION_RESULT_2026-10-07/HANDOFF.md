# Stage 7 result-checker rework handoff

Overlay the `verification/` files from this bundle. `uel/VUEL_failure.for`
is included only to make the regenerated `_user.for` copies self-contained;
it is byte-identical to the prior Stage 7 deliverable and contains no new
constitutive edit.

Run:

1. `python verification/make_stage7_vf.py`
2. From `verification/roar/t_stage7_vf`, submit `run_stage7_vf.sbatch`.

The runner will reuse the six existing fast ODBs if their original
`run_stage7_*` directories are present, run four new 10x-slower cases, and
write a replacement `stage7_vf_check.json`. If the old ODBs are absent, it
runs all ten cases.

The corrected checker uses true relative error for strain and stress,
stores frame times, separates elastic half-force from post-yield force
diagnostics, and reports fast-to-slow convergence. Its top-level `pass`
requires exact fast Vf=0 regressions and all acceptance checks in both
slow directions.
