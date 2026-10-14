task_id: T-006
role: refiner
status: BLOCKED
files_changed:
  - outbox/T-006/uel/VUEL_failure.for
  - outbox/T-006/tests/test_stage7_vf.py
  - outbox/T-006/tests/test_t006_volume_split.py
  - outbox/T-006/verification/make_t006_cases.py
  - outbox/T-006/verification/t006_check_volcorr.py
  - outbox/T-006/verification/t006_vf_metrics.py
  - outbox/T-006/verification/roar/t_t006_volcorr/ (11 generated cases, sources, manifest, and Slurm script)
  - outbox/T-006/HANDOFF.md
summary: |
  Implemented the requested two-volume formulation in the branch-specific
  VUEL_failure.for deliverable. Per-element ETA_VF is read from that element's
  svars(KBLOCK,107). PK2 and Stage 5 residual-compression forces, elastic
  energy, and plastic dissipation use DVOL_EFF. Rayleigh and bulk-viscosity
  forces/dissipation use DVOL_GEOM. Host mass and kinetic energy use
  ELVOL_EFF. Bulk-viscosity and stable-timestep characteristic lengths use
  geometric volume. Intrinsic material constants remain unscaled, and state
  stress storage remains unscaled.

  Added bounded early-call diagnostics for eta, nblock, mass, stable timestep,
  and internal force. Adapted the Stage 7 tests/checking approach and generated
  ROAR cases for exact Vf=0 regression, slow Vf=.5 force scaling, mixed Vf=.3/.6
  in one block, stable timestep, and bulk-viscosity isolation.

  Implementation and local packaging are complete, but the task cannot be
  marked DONE because all six required runtime items demand real ROAR/Abaqus
  results and job IDs. This worker has no ROAR access, as the brief notes.
checks_run: |
  - Confirmed current branch is vuel-plastic-failure.
  - Full pytest in an isolated project copy: 46 passed in 1.45 s.
  - Final focused source/algebra tests: 9 passed in 0.05 s (one harmless pytest cache permission warning).
  - Python compile checks passed for generator, checker, and metrics modules.
  - Generated-case audit passed: 11 cases exist with matching input/source files.
  - Hash audit passed: all 9 non-baseline job sources exactly match the modified VUEL_failure.for; both baseline sources exactly match pre-T-006 VUEL_failure.for.
  - Fixed-form audit: zero executable Fortran lines exceed column 72.
  - Confirmed production uel/VUEL.for is not present in the deliverable and was not touched.
not_verified: |
  - No Fortran compiler was available locally; the VUEL was not compiled.
  - Abaqus was not available locally; no input deck was submitted or opened by Abaqus.
  - No ROAR job was run, so there are no real job IDs or runtime numbers.
  - Verification item 1: Vf=0 versus pre-T-006 baseline exact 0.0 relative error is not runtime-verified.
  - Verification item 2: mixed Vf=.3/.6 elements in the same actual nblock, and their distinct force/mass ratios, are not runtime-verified.
  - Verification item 3: slow/quasi-static Vf=.5 half-force/half-stiffness values are not runtime-verified.
  - Verification item 4: actual Vf=0 and Vf=.5 stable timesteps are not available.
  - Verification item 5: the isolated viscous/bulk contribution is not runtime-verified.
  - Verification item 6: local pytest passed, but the ROAR-side checker and Abaqus compilation remain unrun.
suggestions: |
  - Follow outbox/T-006/HANDOFF.md: copy the bundle to ROAR, submit verification/roar/t_t006_volcorr/run_t006_volcorr.sbatch, and return the Slurm job ID, scheduler output, t006_volcorr_check.json, and supporting job files.
  - After ROAR evidence is returned, audit every reported number before applying the VUEL and tests to the project tree.
concerns: |
  - The generated ROAR decks and checker are locally syntax-checked as Python and structurally audited, but Abaqus acceptance and the chosen runtime tolerances cannot be confirmed without the required run.
  - Acceptance must not rely on the local algebra/source tests alone.
denied_actions: none
