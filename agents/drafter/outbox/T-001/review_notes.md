# T-001 Review & Audit Notes: Ghost-Host VUEL + Fiber-Volume Work

**Date:** 2026-10-02  
**Reviewer:** Drafter (Antigravity Agent)  
**Target Codebase:** `agents/refiner/outbox/MESHER_VUEL_GHOST_TASK_2026-10-01/`  
**Target Deck:** `Flat-vuel-ghost/output.inp` (generated from `Meshing/Flat.inp`)  

---

## 1. Test Suite Verification (`pytest`)
- **Execution Command:** `python -m pytest ..\tests --basetemp=..\pytest-tmp` run from `runroot/` directory.
- **Results:** **24 passed, 0 failed, 1 warning** (0.53 seconds).
- **Test Modules Covered:**
  - `test_acceptance.py`: 2 passed
  - `test_cli.py`: 1 passed
  - `test_core.py`: 10 passed
  - `test_curved.py`: 3 passed
  - `test_desktop.py`: 1 passed
  - `test_visualization.py`: 1 passed
  - `test_vuelghost.py`: 3 passed
  - `test_vumat_fibers.py`: 2 passed
  - `test_writers.py`: 1 passed

---

## 2. Point-by-Point Inspection of Generated Deck (`Flat-vuel-ghost/output.inp`)

### Check 3.1: Ghost Density and Elastic Modulus Scaling
- **Requirement:** Ghost elastic modulus `E` and density `rho` must both be scaled by `~1e-4` to preserve wave speed `sqrt(E/rho)`.
- **Findings:**
  - Original material `Matrix`: `Density = 980.0`, `Elastic E = 5.08e6`, `Plastic yield stress = 611000.0`.
  - Ghost material `EMBMESH_GHOST_MATERIAL`: `Density = 0.098` (980 * 1e-4), `Elastic E = 508.0` (5.08e6 * 1e-4), `Plastic yield stress = 61.1` (611000 * 1e-4).
  - Wave speed: `sqrt(5080000 / 980) = sqrt(508 / 0.098) = 71.996 m/s` (exactly preserved).
- **Verdict:** **PASS**.

### Check 3.2: Abaqus Explicit Quirks (`*UEL Property` and Type Key)
- **Requirement:** `*UEL Property` data lines must not exceed 8 values per line, and user-element type key must start with `VU`.
- **Findings:**
  - `*User Element, type=VU1, nodes=8, coordinates=3, properties=13, variables=107`
  - `*UEL Property, elset=EMBMESH_VUEL_HOST`:
    - Line 1: `5080000, 0.4, 980, 0, 0.06, 1.2, 5.06, 611000` (8 values)
    - Line 2: `44500, 1, 0.05, 0, 0` (5 values)
  - Element type key is `VU1` (starts with `VU`).
- **Verdict:** **PASS**.

### Check 3.3: Per-Element Fiber Volume Fraction Channel (`svars(107)`)
- **Requirement:** `svars(107)` initialized per-element via `*Initial Conditions, TYPE=SOLUTION` matching `fiber_volume.csv`.
- **Findings:**
  - `nsvars` set to 107 in `*User Element` definition and `uel/VUEL_failure.for`.
  - Block `*Initial Conditions, type=SOLUTION` contains 24,000 host element entries formatted as `Plate-1.<label>, 0, ...`.
  - SVAR 107 (107th value) matches `fiber_volume.csv` `volume_fraction` column (e.g. element 401 has `volume_fraction = 1.157260035939`, and line 91196 of `output.inp` writes `1.157260035939` at position 107).
  - Subroutine `uel/VUEL_failure.for` reads `svars(KBLOCK,107)` into `FIBER_VOL_FRAC` on line 433.
- **Verdict:** **PASS**.

### Check 3.4: Ghost Native Deletion & Ductile Damage Calibration
- **Requirement:** Native ghost material must include `*Damage Initiation, criterion=DUCTILE` + `*Damage Evolution` + element deletion controls.
- **Findings:**
  - Deck contains `*Section Controls, name=EMBMESH_GHOST_CONTROLS, element deletion=YES`.
  - Material `EMBMESH_GHOST_MATERIAL` includes `*Damage Initiation, criterion=DUCTILE` with strain `5.06` and `*Damage Evolution, type=DISPLACEMENT` with displacement `0.0`.
- **Verdict:** **PASS**.

---

## 3. Bugs, Implementation Gaps & Spec Divergences Found

1. **Test Environment / CWD Sensitivity:**
   - Tests in `test_acceptance.py` and `test_visualization.py` use hardcoded relative path `'examples/flat_disc.inp'`.
   - Running `pytest` from the outbox root (`MESHER_VUEL_GHOST_TASK_2026-10-01/`) fails 3 tests unless CWD is set to `runroot/`.

2. **Potential Mis-scaling of Complex `*Plastic` Laws:**
   - In `embmesh/vuelghost.py` (`_scaled_ghost_material`), for `*Plastic` lines: `values[0] *= scale` scales only column 0.
   - For tabular `(stress, strain)` lines this works, but for `*Plastic, hardening=JOHNSON COOK` or multi-column data, column 0 (A) is scaled while column 1 (B) is unscaled.

3. **Single Host Material Assumption:**
   - `_section_material` in `vuelghost.py` raises `ValueError` if host elements belong to more than one `*Solid Section` material. Heterogeneous host meshes are not supported.

4. **SVAR 107 Debug Log Output in Fortran:**
   - In `uel/VUEL_failure.for` (line 434-436), `FIBER_VOL_FRAC` is printed to stdout only for `(NCALLS == 1) AND (KBLOCK == 1)`. Since element 1 in `Flat.inp` has 0.0 fiber volume fraction, stdout prints `FIBER_VOL_FRAC = 0.0`, which could mislead reviewers inspecting stdout logs into thinking initialization failed.

5. **Test Suite Coverage Gaps:**
   - `test_vuelghost.py` has only 3 unit tests. It lacks end-to-end integration tests for CLI flags (`--host-mode vuel-ghost`), verification of `*Embedded Element` linking to ghost element IDs, or error handling tests for missing damage keywords.
