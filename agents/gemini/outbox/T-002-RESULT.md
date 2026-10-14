task_id: T-002
role: gemini
status: DONE
files_changed:
  - agents/gemini/outbox/T-002/BRAINSTORM.md
summary: Authored a comprehensive architectural brainstorming and design document (BRAINSTORM.md) evaluating data delivery pipelines, timing hooks, constitutive stress matrix application methods, and plastic yield stress (SIGY0) interaction risks for implementing a per-element fiber-volume-fraction stiffness correction in uel/VUEL_failure.for. Confirmed the existing *Initial Conditions, TYPE=SOLUTION -> svars(107) data pipeline is optimal. Compared timing strategies (on-the-fly vs jMassCalc caching) and demonstrated mathematical equivalence/6x speedup of scalar stress scaling over per-element 6x6 matrix assembly. Explicitly surfaced the SIGY0 / Stage 1/2 yield strain calibration shift with 3 concrete options for human decision.
checks_run:
  - Inspected existing mesher data pipeline in embmesh/vuelghost.py (lines 216-227) and confirmed *Initial Conditions, TYPE=SOLUTION populates svars(KBLOCK, 107).
  - Inspected uel/VUEL_failure.for subroutine structure (lines 160-182, 379-401, 429-436, 469-530) to verify block-level CMAT assembly, svars layout, and operation codes (jMassCalc, jIntForceAndDtStable).
  - Verified mathematical equivalence of scalar stress scaling vs 6x6 matrix assembly for isotropic linear elasticity.
  - Reviewed Stage 1 (J2 plasticity) and Stage 2 (engineering-strain failure) calibration reports to trace yield strain shift mechanism when elastic modulus is scaled.
not_verified:
  - Live Abaqus/Explicit compilation and execution of proposed Fortran modifications (no solver execution or ROAR cluster access performed in brainstorming phase per brief constraints).
  - Empirical timing benchmark of on-the-fly FLOP overhead vs jMassCalc svars caching on real HPC cluster hardware.
suggestions:
  - Present Option 4A (scaling SIGY0 and HMOD proportionally by eta_k) to the human for approval if preserving Stage 1 & Stage 2 plastic and failure calibrations is desired.
  - Implement Option 3B (scalar stress tensor scaling with shared CMAT) in uel/VUEL_failure.for for optimal Fortran performance.
concerns:
  - Unscaled SIGY0 (Option 4B) will shift the initial yield strain from 0.00125 to 0.00125 / eta_k, invalidating Stage 1 plastic hardening and Stage 2 failure calibration curves. Human sign-off on the physics model choice is required before code implementation.
denied_actions: none
