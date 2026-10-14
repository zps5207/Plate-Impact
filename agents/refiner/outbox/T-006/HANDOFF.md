# T-006 handoff: VUEL volume-fraction integration correction

## Status

The code and ROAR verification bundle are prepared on the required
`vuel-plastic-failure` branch snapshot. Local checks pass, but this handoff is
not an acceptance report: no Abaqus or ROAR job was run from this worker.
Real ROAR job IDs and numerical results remain required before acceptance.

## Final volume split

Line references below are to `uel/VUEL_failure.for` in this bundle.

- Per element, `Vf` comes from `svars(KBLOCK,107)` and
  `ETA_VF=max(1-Vf,1e-6)` is computed inside the `KBLOCK` loop (lines 432-439).
- Geometric and effective Gauss volumes are separated as
  `DVOL_GEOM=DETJ0*WT` and `DVOL_EFF=ETA_VF*DVOL_GEOM` (lines 603-606).
- Physical internal force—PK2 plus Stage 5 residual compression—uses
  `DVOL_EFF` (lines 855-860).
- Rayleigh and bulk-viscosity internal force uses `DVOL_GEOM` (lines 861-862).
- `ELIE`, residual elastic energy, and `PLASTIC_DISSIP` use `DVOL_EFF`
  (lines 871-889).
- `DAMP_DISSIP` and `BV_DISSIP` use `DVOL_GEOM` (lines 896-906).
- Mass uses `ELVOL_EFF=ETA_VF*ELVOL_GEOM` in both mass assembly and kinetic
  energy (lines 510-511 and 948).
- Bulk-viscosity `CHARLEN` uses per-Gauss geometric volume (line 808).
- Stable-timestep `CHARLEN` uses total geometric volume (line 982).
- `CWAVE` remains based on intrinsic `ALAMBDA`, `AMU`, and `DENS` (line 550).
- Plasticity, Rayleigh stress, and residual compression use intrinsic
  `CMAT`, `SIGY0`, `HMOD`, `AMU`, and `BULK_MODULUS`; the Stage 7 `_K`
  material copies were removed (representative lines 676, 696, 727, 790,
  and 832).
- State output remains one unscaled stress value per Gauss point:
  `STRESS_TOTAL` is stored directly to `svars` (lines 840-848). No second
  volume-scaled stress copy was introduced.

The source emits bounded `T006_ETA`, `T006_MASS`, `T006_DT`, and `T006_FINT`
diagnostics during its existing early-call debug window. These let the ROAR
checker prove the mixed-Vf elements were processed in the same `nblock` and
report their distinct eta, mass, timestep, and force values.

## Deliverables

- `uel/VUEL_failure.for`: implementation; production `uel/VUEL.for` is absent
  and untouched.
- `tests/test_stage7_vf.py`: updates superseded Stage 7 source assertions to
  the T-006 formulation.
- `tests/test_t006_volume_split.py`: focused algebraic/source checks.
- `verification/make_t006_cases.py`: adapted Stage 7 case generator.
- `verification/t006_check_volcorr.py`: Abaqus-Python ODB/log checker.
- `verification/t006_vf_metrics.py`: true-relative-error helper.
- `verification/roar/t_t006_volcorr/`: generated 11-case bundle, frozen
  pre-T-006 baseline source, case-specific sources, and Slurm script.

## ROAR execution required

From a copy of the bundle on ROAR:

```bash
cd verification/roar/t_t006_volcorr
sbatch run_t006_volcorr.sbatch
```

The Slurm script runs all cases and writes `t006_volcorr_check.json`. Return:

1. the Slurm job ID and scheduler output;
2. `t006_volcorr_check.json`;
3. all case `.sta`, `.msg`, `.dat`, `.stdout`, and ODB-derived results needed
   to audit the JSON;
4. the mixed-case `T006_ETA`/`T006_MASS` diagnostics showing both elements,
   distinct eta values 0.7 and 0.4, and `nblock >= 2` in one call;
5. actual Vf=0 regression errors, slow Vf=.5 force errors, stable timesteps,
   mixed force/mass ratios, and isolated bulk-viscosity forces.

Do not accept on local tests alone. The checker thresholds are encoded in
`t006_check_volcorr.py`, but the brief specifically requires real numbers and
real ROAR job IDs.

## Local evidence

- Full isolated pytest: 46 passed in 1.45 s.
- Focused T-006 pytest: 5 passed.
- Python generator/checker/metrics compile successfully.
- Generated decks and case-specific Fortran sources were created locally.
- No executable fixed-form Fortran line exceeds column 72.

No Fortran compiler, Abaqus installation, or ROAR access was available, so
Fortran compilation and all six runtime verification items are pending.
