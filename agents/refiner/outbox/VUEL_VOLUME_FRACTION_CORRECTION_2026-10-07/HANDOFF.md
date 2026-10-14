# Stage 7 handoff

Apply `uel/VUEL_failure.for` to the same project path. The production
`uel/VUEL.for` is intentionally absent and unchanged.

The implementation reads `SVAR107` per element, uses
`eta=max(1-Vf,1e-6)`, and rebuilds the elastic/plastic constants and
matrix inside the `KBLOCK` loop. Density, bulk viscosity, stable-time wave
speed, and geometric failure thresholds remain on their original paths.

For ROAR verification, copy the bundle into the repository, run
`python verification/make_stage7_vf.py`, then submit
`verification/roar/t_stage7_vf/run_stage7_vf.sbatch`. The job runs the
two requested Stage 7 variants in both tension and compression, plus a
frozen pre-Stage-7 Vf=0 regression for each direction, and writes
`stage7_vf_check.json`. The ODB checker evaluates the Vf=0 regression,
half-force response, common yield strain, and post-yield
stress-versus-inferred-PEEQ slope in both directions.

The frozen baseline source is verification-only. Do not install it under
`uel/`.
