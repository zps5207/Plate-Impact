task_id: T-005
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-005/BRAINSTORM.md
  - agents/drafter/outbox/T-005/VUEL_failure_vol_corr.for
summary: Completed from-scratch brainstorming and first-draft sketch for applying the VUEL fiber/host volume-fraction correction to host element integration volume (dVol_eff = eta_k * dVol_geom and ELVOL_EFF = eta_k * ELVOL_GEOM) during VUEL execution, reusing the existing svars(107) = FIBER_VOL_FRAC data path initialized from fiber_volume.csv. Proved algebraically that volume scaling produces identical internal force (F_int), plastic strain increment (DEp), and equivalent plastic strain (PEEQ) evolution as Stage 7's stiffness scaling, while eliminating host mass double-counting (scaling host mass to eta_k * m_0) and ensuring exact material wave speed (c_0) and stable time increment (dtimeStable) without approximation.
checks_run:
  - Inspected uel/VUEL_failure.for volume integration, mass assembly, radial return plasticity, and wave speed calculations.
  - Verified algebraic equivalence of plastic return mapping and acceleration between Stage 7 stiffness scaling and Volume Scaling.
  - Verified file creation and content formatting of BRAINSTORM.md and VUEL_failure_vol_corr.for.
not_verified:
  - Abaqus/Explicit finite element solver execution on ROAR HPC cluster (no local Abaqus/Fortran environment on local workstation).
  - Multi-element compression and tension verification tests under Abaqus Explicit (to be handled in Refiner role / ROAR test pipeline).
suggestions:
  - Review BRAINSTORM.md section 3 for the detailed side-by-side comparison between Stage 7 and Volume Scaling.
  - If accepted, invoke Refiner to integrate VUEL_failure_vol_corr.for into uel/VUEL_failure.for on branch vuel-plastic-failure and run the verification suite on ROAR.
concerns: none
denied_actions: none
