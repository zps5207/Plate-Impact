task_id: T-007
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-007/BRAINSTORM.md
  - agents/drafter/outbox/T-007/patch_vuel_sdv_output.py
summary: Conducted a comprehensive root-cause investigation into the persistent ring of 48-52 surviving ghost C3D8R island elements at the crater rim (diagnose_bands.json and diagnose_bands_b.json). Established that VU1 and ghost elements are strictly kinematically bound (sharing identical node connectivity tuples), but their failure states are 100% decoupled in software. Identified the root cause as a criterion and kinematic mismatch at the crater boundary: VU1's 1D Green-Lagrange normal engineering strain trigger (EPS_FAIL) trips on quadratic shear distortion terms (0.5*(du2/dX1)^2), whereas the ghost's J2 equivalent plastic strain (PEEQ) is suppressed near the boundary by C3D8R single-point Gauss integration and hourglass control. Drafted patch_vuel_sdv_output.py to request host SDV49/SDV106/SDV107 field output in embmesh/vuelghost.py for direct empirical verification on ROAR before modifying physical failure thresholds.
checks_run:
  - Audited uel/VUEL_failure.for strain calculation (lines 655-662, 936-953) and embmesh/vuelghost.py material definition (lines 215-236, 332-352).
  - Analyzed spatial distribution and neighbor counts across diagnose_bands.json, diagnose_bands_b.json, and diagnose_central_elements2.py.
  - Verified Python 3.12 compilation for patch_vuel_sdv_output.py (PASS).
not_verified:
  - ODB state variable (SDV) extraction on ROAR HPC cluster (no local Abaqus/Explicit environment on local workstation).
  - Empirical cross-referencing of SDV49 vs ghost STATUS on full ROAR impact runs.
suggestions:
  - Apply patch_vuel_sdv_output.py to embmesh/vuelghost.py and submit a smoke job on ROAR to confirm whether VU1's SDV49 latched to 1.0 for the 48-52 island elements.
  - If SDV49 is confirmed latched for those elements, consider adding shear strain terms to VU1's EPS_FAIL trigger or tuning the ghost ductile failure strain / triaxiality table to match host deformation at the crater rim.
concerns: none
denied_actions: none
