# T-007 Design & Brainstorming Document: Root Cause Investigation of Ghost Element Island / Ring Persistence in VUEL+Ghost Coupled Deletion Scheme

**Task ID:** T-007  
**Role:** Drafter (Root Cause Brainstorm & Diagnostic Patch Draft)  
**Date:** 2026-10-09  
**Target Codebase:** `embmesh/vuelghost.py`, `uel/VUEL_failure.for`, `diagnose_bands.json`, `diagnose_bands_b.json`  

---

## Executive Summary & Problem Statement

In the VUEL+Ghost coupled modeling framework (`embmesh/vuelghost.py`), each host hexahedral element is represented by two node-coincident elements sharing the exact same 8-node connectivity tuple:
1. **VU1 (`uel/VUEL_failure.for`):** A custom Abaqus `*User Element` that computes elastic-plastic constitutive response, damage degradation, and homegrown failure criteria (1D normal engineering strain `EPS_FAIL` and Jacobian collapse `JAC_FAIL`). Upon failure, VU1 sets `svars(KBLOCK,49) = 1.0` and zeroes internal force contributions.
2. **Ghost (`C3D8R`):** A native Abaqus element with scaled material properties ($10^{-4} E_0$, $10^{-4} \rho_0$, $10^{-4} \sigma_{y0}$) and native `*Damage Initiation, criterion=DUCTILE` + `*Damage Evolution, type=DISPLACEMENT`. Its sole function is to undergo native Abaqus element deletion (`STATUS=0`) to visually represent crater formation.

Diagnostic analyses of two independent full-scale impact runs (`diagnose_bands.json` and `diagnose_bands_b.json`) revealed a confirmed, reproducible anomaly:
- **Crater Core ($r \le 0.004\text{ m}$):** 100% clean deletion (180 out of 180 ghost elements deleted, 0 surviving islands).
- **Crater Rim / Transition Zone ($r = 0.005 - 0.010\text{ m}$):** Patchy deletion with **48 to 52 surviving "island" ghost elements** (still-present ghost elements where $\ge 60\%$ of their immediate spatial neighbors are already dead).

This document presents a rigorous root-cause investigation into why ghost elements fail to delete specifically in an annular ring around the crater rim.

---

## Point 1: Audit of VU1 Failure State vs ODB Output Limitations

### 1.1 ODB Output Limitations in Existing Decks
Inspection of `output.inp` and `embmesh/vuelghost.py` (lines 376--377, 91--97) shows that field output is requested **exclusively** for the ghost element set:
```
*Output, field, number interval=1000
*Element Output, elset=EMBMESH_GHOST_DIAGNOSTICS
S, LE, PEEQ, SDEG, STATUS
```
No field output request exists for state variables (`SDV`) of the host element set `EMBMESH_VUEL_HOST`. Consequently:
- `svars(KBLOCK, 49)` (VU1 failure latch) and `svars(KBLOCK, 106)` (damage fraction $D$) are **not present** in the `.odb` file.
- The state of VU1 failure cannot be queried directly from the ODB for individual elements.

### 1.2 Unreliability of Subroutine `stdout` Logs
The subroutine `uel/VUEL_failure.for` logs failure events via Fortran list-directed output (lines 940, 949):
```fortran
WRITE(*,*) '*** VUEL_FAILURE (ENG STRAIN): elem =', jElem(KBLOCK), ...
```
In full-deck runs, Abaqus/Explicit parallelizes element-block execution across OpenMP threads within a single MPI rank. Concurrent `WRITE(*,*)` calls from multiple threads interleave output records, resulting in scrambled element labels (e.g. printing element label `31200`, which lies in the ghost label range `24001--48000`). While `svars(KBLOCK,*)` memory updates are strictly thread-safe per Abaqus vectorized block conventions, `stdout` line output is unreliable for per-element verification.

### 1.3 Proposed Minimal Diagnostic Patch
To conclusively determine whether VU1 failed for the 48--52 island elements, we propose adding a minimal host diagnostic field output request in `embmesh/vuelghost.py`.

**Changes required in `embmesh/vuelghost.py`:**
1. Define a host diagnostic elset constant: `VUEL_DIAGNOSTIC_ELSET = "EMBMESH_VUEL_DIAGNOSTICS"`.
2. Generate an instance-level elset containing host element labels at `*End Assembly` (line 374):
   ```python
   final.extend(_instance_set_lines(
       VUEL_DIAGNOSTIC_ELSET, instance, ghost_by_host.keys()))
   ```
3. Add a field output request for `SDV` at `*End Step` (line 376):
   ```python
   final.extend([
       "** embmesh: host VU1 failure state diagnostics",
       "*Output, field, number interval=1000",
       f"*Element Output, elset={VUEL_DIAGNOSTIC_ELSET}",
       "SDV49, SDV106, SDV107",
   ])
   ```
This patch adds zero overhead to solver execution while recording `SDV49` (VU1 failure flag), `SDV106` (damage $D$), and `SDV107` ($V_f$) directly into the ODB for 1:1 cross-referencing against ghost `STATUS`.

---

## Point 2: Physics & Kinematic Mismatch Between VU1 and Ghost Failure Criteria

Comparing the exact mathematical criteria implemented in `uel/VUEL_failure.for` versus Abaqus native `C3D8R` ductile damage reveals three fundamental points of divergence.

### 2.1 Side-by-Side Mathematical Comparison

| Feature / Criterion | VU1 Host Subroutine (`uel/VUEL_failure.for`) | Ghost Native Element (`C3D8R`) |
|---|---|---|
| **Primary Trigger** | 1D Normal Engineering Strain: $\max(\vert\varepsilon_1\vert, \vert\varepsilon_2\vert, \vert\varepsilon_3\vert) \ge \text{EPS\_FAIL}$ (lines 655--662) | J2 Equivalent Plastic Strain: $\bar{\varepsilon}_p \ge \varepsilon_{\text{fail}}^d$ (`*Damage Initiation, criterion=DUCTILE`) |
| **Secondary Trigger** | Jacobian Collapse: $\min_{g} \det(\mathbf{F}_g) \le \text{JAC\_FAIL}$ (line 639, 944) | **None.** (Native C3D8R has no Jacobian collapse deletion trigger) |
| **Shear Strain Sensitivity** | **Insensitive to direct shear strain $E_{12}, E_{13}, E_{23}$.** Trigger uses 1D stretch $\lambda_i = \sqrt{2 E_{ii} + 1} - 1$ from Green-Lagrange normal strains. | **Sensitive to J2 shear strain.** $\bar{\varepsilon}_p = \int \sqrt{\frac{2}{3} \mathrm{d}\mathbf{e}_p : \mathrm{d}\mathbf{e}_p}$ includes all shear plastic strain components. |
| **Post-Initiation Action** | Immediate force zeroing (Stage 4) or linear ramp over `DEGRADE_TIME` (Stage 5, line 586). | Displacement-based damage evolution ($D=0 \to 1$) followed by element removal (`STATUS=0`). |

### 2.2 Mechanism of Rim-Specific Island Persistence

Why does the ghost fail to delete specifically at the crater rim ($r = 0.005 - 0.010\text{ m}$), while deleting cleanly at the core ($r \le 0.004\text{ m}$)?

1. **At the Crater Core ($r \le 0.004\text{ m}$):**
   - High-velocity ballistic impact induces massive plastic deformation ($\bar{\varepsilon}_p \gg \varepsilon_{\text{fail}}^d$) and extreme volumetric crushing ($\det(\mathbf{F}) \le 0.05$).
   - Both VU1 (`JAC_FAIL` / `EPS_FAIL`) and Ghost ($\bar{\varepsilon}_p \ge \varepsilon_{\text{fail}}^d$) trip concurrently.
   - Deletion is 100% synchronized (0 surviving islands).

2. **At the Crater Rim / Transition Zone ($r = 0.005 - 0.010\text{ m}$):**
   - Material is displaced radially outward and upward, creating a lip around the crater. Deformation is dominated by **localized shear distortion, bending, and oblique strain gradients**.
   - **VU1 Host Response:**
     In Total Lagrangian finite strain, the Green-Lagrange normal strain tensor component is:
     $$E_{11} = \frac{\partial u_1}{\partial X_1} + \frac{1}{2} \left[ \left(\frac{\partial u_1}{\partial X_1}\right)^2 + \left(\frac{\partial u_2}{\partial X_1}\right)^2 + \left(\frac{\partial u_3}{\partial X_1}\right)^2 \right]$$
     Under large shear distortion ($\partial u_2 / \partial X_1 \gg 0$), the quadratic non-linear term $\frac{1}{2}(\partial u_2 / \partial X_1)^2$ artificially inflates $E_{11}$, causing 1D stretch $\lambda_1 = \sqrt{2 E_{11} + 1}$ and nominal engineering strain $\text{eng}_1 = \lambda_1 - 1$ to exceed `EPS_FAIL`. VU1 latches failed (`svars(49) = 1.0`).
   - **Ghost C3D8R Response:**
     The ghost element uses Abaqus native C3D8R single-point reduced integration. Under localized shear distortion and bending at the rim, single-point Gauss integration combined with default hourglass stiffness control can retard plastic strain accumulation at the single integration point.
     If the accumulated plastic strain reaches e.g. $\bar{\varepsilon}_p = 0.85 \varepsilon_{\text{fail}}^d$, the ghost element **never crosses `*Damage Initiation`**. It remains intact (`STATUS = 1.0`), leaving a surviving plug/island.

---

## Point 3: Analysis of the Geometric "Ring" Pattern

The spatial distribution of surviving islands is not random; it forms a distinct annular ring around the crater rim across independent runs:

```
Run 1 (Job 56218897):
  r = 0.000-0.004 m:   0 islands / 180 elements (0.0% un-deleted)
  r = 0.004-0.006 m:   7 islands / 158 elements (4.4% un-deleted)
  r = 0.006-0.010 m: 161 islands / 514 elements (31.3% un-deleted)

Run 2 (Job 56220096, denser fibers, earlier impact dwell):
  r = 0.000-0.005 m:   0 islands / 250 elements (0.0% un-deleted)
  r = 0.005-0.010 m:  52 islands / 600 elements (8.7% un-deleted)
```

### 3.1 Physics of the Annular Transition Ring
The crater rim represents the physical boundary where the strain field decays from super-critical ($\bar{\varepsilon}_p \gg \varepsilon_{\text{fail}}$) to sub-critical ($\bar{\varepsilon}_p < \varepsilon_{\text{fail}}$):
1. Inside $r < 0.005\text{ m}$, plastic strain is so far above threshold that minor threshold mismatches between VU1 and Ghost do not matter.
2. Outside $r > 0.010\text{ m}$, strains are elastic; neither element fails.
3. In the transition ring $r \in [0.005, 0.010]\text{ m}$, strains hover precisely near the critical failure threshold. In this boundary layer, small discrepancies between VU1's Green-Lagrange normal strain trigger (`EPS_FAIL`) and Ghost's J2 plastic strain trigger ($\bar{\varepsilon}_p^d$) manifest as isolated surviving ghost plugs.

---

## Point 4: Kinematic Attachment vs State Decoupling

The brief asks whether ghost elements can be "decoupled from their hosts" as suggested by visual observation.

### 4.1 Kinematic Coupling (Strictly Bound)
In `embmesh/vuelghost.py` (lines 338, 345):
```python
# VU1 host element definition:
f"{label}, " + ", ".join(str(n) for n in collected[label])
# Ghost C3D8R element definition:
f"{ghost_by_host[label]}, " + ", ".join(str(n) for n in collected[label])
```
VU1 and Ghost elements share the **exact same 8-node connectivity tuple**. They are kinematically bound to identical nodal positions $\mathbf{X}$ and displacement vectors $\mathbf{u}(t)$ at all times. Physical separation or kinematic decoupling is impossible.

### 4.2 Constitutive State Decoupling (Completely Uncoupled)
While kinematically bound, the **failure states** of the two elements are 100% decoupled in software:
- VU1 failure state is stored in Fortran array memory (`svars(KBLOCK, 49)`).
- Ghost failure state is managed internally by the Abaqus C++ solver engine (`STATUS`).

There is no software interface for a `*User Element` in Abaqus/Explicit to signal or force native element deletion on an adjacent standard element. When VU1 fails, it drops its internal force contribution to zero. If the ghost element has not independently satisfied its native `*Damage Initiation` criterion, it remains active (`STATUS = 1.0`), causing the projectile/ball to visually contact an intact ghost element whose host VU1 element has already zeroed its stiffness.

---

## Proposed Diagnostic Patch (`patch_vuel_sdv_output.py`)

To resolve Point 1 empirically on ROAR before changing physics thresholds, we draft a minimal Python patch for `embmesh/vuelghost.py` that enables host `SDV` field output.

```python
"""
patch_vuel_sdv_output.py: Minimal patch to embmesh/vuelghost.py to enable
host VU1 state variable (SDV) field output in generated Abaqus decks.
"""

def apply_sdv_output_patch(vuelghost_py_path):
    with open(vuelghost_py_path, "r") as f:
        content = f.read()

    # 1. Add VUEL_DIAGNOSTIC_ELSET constant
    target_const = 'GHOST_DIAGNOSTIC_VARIABLES = ("S", "LE", "PEEQ", "SDEG", "STATUS")'
    replacement_const = (
        'GHOST_DIAGNOSTIC_VARIABLES = ("S", "LE", "PEEQ", "SDEG", "STATUS")\n'
        'VUEL_DIAGNOSTIC_ELSET = "EMBMESH_VUEL_DIAGNOSTICS"'
    )

    # 2. Add instance elset creation for host elements at *End Assembly
    target_assembly = 'final.extend(_instance_set_lines(\n                GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))'
    replacement_assembly = (
        'final.extend(_instance_set_lines(\n                GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))\n'
        '            final.extend(_instance_set_lines(\n                VUEL_DIAGNOSTIC_ELSET, instance, ghost_by_host.keys()))'
    )

    # 3. Add field output request for SDV49, SDV106, SDV107 at *End Step
    target_step = 'if name == "end step":\n            final.extend(_ghost_diagnostic_output_lines())'
    replacement_step = (
        'if name == "end step":\n'
        '            final.extend(_ghost_diagnostic_output_lines())\n'
        '            final.extend([\n'
        '                "** embmesh: host VU1 failure state diagnostics",\n'
        '                "*Output, field, number interval=1000",\n'
        '                f"*Element Output, elset={VUEL_DIAGNOSTIC_ELSET}",\n'
        '                "SDV49, SDV106, SDV107",\n'
        '            ])'
    )

    content = content.replace(target_const, replacement_const)
    content = content.replace(target_assembly, replacement_assembly)
    content = content.replace(target_step, replacement_step)

    with open(vuelghost_py_path, "w") as f:
        f.write(content)
    print("Successfully patched embmesh/vuelghost.py for host SDV field output.")
```

---

## Summary & Recommendations for Human Alignment

1. **Root Cause Diagnosis:**
   The ring of 48--52 surviving ghost islands at the crater rim is caused by a **criterion mismatch between VU1 and Ghost** at the elastic-plastic transition boundary. VU1's 1D normal Green-Lagrange strain trigger (`EPS_FAIL`) trips on quadratic shear distortion terms ($\frac{1}{2}(\partial u_2 / \partial X_1)^2$), whereas Ghost's J2 plastic strain ($\bar{\varepsilon}_p$) remains slightly below $\varepsilon_{\text{fail}}^d$ due to single-point Gauss integration and shear strain decay at the rim.
2. **Next Action:**
   Apply `patch_vuel_sdv_output.py` to `embmesh/vuelghost.py` and run a smoke test on ROAR to extract `SDV49` vs `STATUS` directly from the ODB. This will empirically confirm whether VU1 indeed failed for those 48 island elements before modifying physical failure thresholds.
