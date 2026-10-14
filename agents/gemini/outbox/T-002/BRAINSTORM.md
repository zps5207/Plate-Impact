# T-002 Design & Brainstorming Document: Per-Element Fiber-Volume-Fraction Stiffness Correction in `uel/VUEL_failure.for`

**Task ID:** T-002  
**Role:** Gemini (Brainstorming / Architectural Design)  
**Date:** 2026-10-07  
**Target Codebase:** `uel/VUEL_failure.for`, `embmesh/vuelghost.py`  

---

## Executive Summary & Background

In embedded-fiber finite element modeling (where T3D2/B31 fiber elements are embedded inside host C3D8R/VU1 hex elements via Abaqus `*Embedded Element`), the total structural stiffness is double-counted: the host hex retains 100% of its native elastic stiffness ($E_0$), while the embedded fibers add their full structural stiffness ($\frac{\pi d^2}{4} E_{fiber}$) on top of the host. As measured in `docs/VERIFICATION_REPORT.md` Section 4, a 66:1 fiber/matrix stiffness ratio at fiber volume fraction $V_f \approx 0.58\text{--}0.79$ resulted in internal strain energies 20--27$\times$ higher than unreinforced matrix.

The objective of this design document is to evaluate how `uel/VUEL_failure.for` can efficiently receive per-element fiber volume fraction data ($V_f$) from the existing mesher pipeline (`embmesh`) and apply a stiffness correction factor $\eta(V_f)$ to the host element, eliminating double-counting without introducing runtime performance bottlenecks or breaking Abaqus Explicit subroutine conventions.

---

## Point 1: Evaluation of Per-Element Data Delivery Pipelines

### 1.1 Existing Pipeline: `*Initial Conditions, TYPE=SOLUTION` $\to$ `svars(107)`
- **Mechanism:** The mesher (`embmesh/vuelghost.py`) writes per-element $V_f$ values into the generated Abaqus deck under `*Initial Conditions, TYPE=SOLUTION` targeting state variable slot 107. Abaqus Explicit automatically loads these values into `svars(KBLOCK, 107)` at the start of the job before any subroutine calls occur.
- **Subroutine Integration:** `uel/VUEL_failure.for` already reads `FIBER_VOL_FRAC = svars(KBLOCK, 107)` on lines 432--433.
- **Pros:**
  - Zero runtime file I/O or string parsing inside Fortran.
  - Native, documented Abaqus Explicit feature supported across distributed MPI parallel domains (ROAR HPC cluster compatible).
  - Fully automated in the Python deck generator (`embmesh`).
- **Cons:**
  - Slightly inflates `.inp` deck line count (writing 106 dummy zeroes + 1 $V_f$ value per element across 14 text lines per element).

### 1.2 Alternative Pipeline A: Abaqus `*UEL Property` / `props(1:13)`
- **Mechanism:** Pass $V_f$ as a user element property.
- **Evaluation:** **Unsuitable.** In Abaqus, `props` are defined per `*UEL Property` elset, not per element. Since $V_f$ varies element-by-element across the host mesh, using `props` would require creating 24,000 distinct element sets and property cards in the `.inp` deck. This would fragment element blocks into single-element sets, destroying vectorization (`nblock = 1`) and severely degrading solver performance.

### 1.3 Alternative Pipeline B: External Database / File I/O (`UEXTERNALDB` or Fortran `OPEN`/`READ`)
- **Mechanism:** `uel/VUEL_failure.for` opens `fiber_volume.csv` from disk at step initialization (`kStepInit` / `lflags(1) == 1`) and stores values in a module array or common block.
- **Evaluation:** **High Risk / Unsuitable.** Disk file I/O inside Abaqus Explicit user subroutines is fragile across MPI distributed-memory execution nodes, risks file handle locks, requires custom element-label-to-array index mapping tables, and breaks the self-contained portability of the Abaqus input deck.

### 1.4 Verdict on Point 1
The existing **`*Initial Conditions, TYPE=SOLUTION` $\to$ `svars(107)`** pipeline is confirmed to be the most efficient, reliable, and idiomatic Abaqus/Explicit mechanism for supplying per-element data to `VUEL_failure.for`. **No replacement is needed or recommended.**

---

## Point 2: Timing & Hooking of Correction Calculation

We evaluate three operational strategies for computing the stiffness correction factor $\eta = g(V_f)$ inside `VUEL_failure.for`.

| Strategy | Hook Location | Computation Frequency | Memory (`svars`) Impact | CPU Overhead | Implementation Risk |
|---|---|---|---|---|---|
| **Option 2A: Per-Increment On-the-Fly** | `jIntForceAndDtStable` (`lflags(3) == 4`) inside `KBLOCK` loop | Every explicit increment for every element ($3.6 \times 10^8$ calls for 24k elements $\times$ 15k steps) | Zero (uses existing `svars(107)`) | Extremely Low ($< 0.5\%$) for linear $\eta = 1 - V_f$; Moderate for complex non-linear functions | Lowest; no extra `svars` state management |
| **Option 2B: Initial Mass Calc Caching** | `jMassCalc` (`lflags(3) == 1`) | Once per element at job initialization ($t = 0$) | Requires 1 new slot (`nsvars` 107 $\to$ 108) to cache $\eta$ | Zero during time-stepping | Low; relies on `jMassCalc` execution guarantee |
| **Option 2C: Pre-Calculated in Python Deck Generator** | `embmesh` Python script | Once during mesh generation | Zero (writes pre-computed $\eta$ into `svars(107)` directly) | Zero in Fortran | High maintenance coupling; changing formula requires re-meshing |

### Detailed Tradeoff Analysis for Point 2:

1. **Option 2A (Per-Increment On-the-Fly):**
   For a standard linear correction formula $\eta(V_f) = 1 - V_f$, computing `ETA = 1.0D0 - FIBER_VOL_FRAC` requires a single scalar subtraction per element block iteration. Across 24,000 elements and 15,000 increments, this adds $3.6 \times 10^8$ FLOPs total, which takes less than 0.05 seconds on modern CPUs. It avoids adding state variables and avoids relying on initialization operation codes.

2. **Option 2B (Initial Mass Calculation Caching):**
   `jMassCalc` (`lflags(3) == 1`) runs once per element during model initialization to compute element mass matrices. Pre-computing $\eta(V_f)$ here and storing it in `svars(KBLOCK, 108)` (bumping `nsvars` to 108) eliminates repetitive math entirely. However, Abaqus Explicit operation codes during initial setup (`lflags(1)` and `lflags(3)`) can vary depending on solver options (e.g. mass scaling), so caching requires verifying that `svars(108)` is preserved across all step initialization phases.

3. **Option 2C (Python Generator Pre-Computation):**
   While Python pre-computation is trivial, it hardcodes the physics formula into the deck generator (`embmesh`). If a user wishes to test linear vs. Mori-Tanaka vs. Voigt/Reuss bounds, they would have to regenerate the entire 13 MB deck each time rather than editing subroutine properties.

### Recommendation on Point 2:
- Start with **Option 2A (Per-Increment On-the-Fly)** for simple correction formulas ($\eta = 1 - V_f$).
- Move to **Option 2B (Caching in `svars(108)`)** if the human selects a complex non-linear micro-mechanics formula (e.g. Eshelby/Mori-Tanaka inclusion bounds requiring `LOG`, `SQRT`, or tensor inverses).

---

## Point 3: Application of Correction to Constitutive Response (`CMAT` / Stress Tensor)

In `uel/VUEL_failure.for`, the isotropic linear elasticity tensor `CMAT` (Lame parameters $\lambda, \mu$) is currently constructed **once per subroutine call** (lines 379--401) before entering the element loop (`DO KBLOCK = 1, nblock`), and is shared across all elements in the block.

We compare two methods for applying the per-element correction factor $\eta_k$:

### Option 3A: Rebuilding Per-Element Matrix $\mathbf{C}_k$ Inside `KBLOCK` Loop
- **Mechanism:** For each element $k$, calculate modified modulus $E_k = \eta_k E_0$, recompute Lame parameters $\lambda_k, \mu_k$, and construct a per-element 6x6 elasticity matrix $\mathbf{C}_k$.
- **Computational Cost:** Re-evaluating Lame parameters and building $\mathbf{C}_k$ inside the loop adds 36 multiplications/additions per Gauss point $\times$ 8 Gauss points = 288 FLOPs per element per increment.

### Option 3B: Scaling Computed PK2 Stress Tensor by Scalar $\eta_k$ (Shared $\mathbf{C}_0$)
- **Mechanism:** Retain the shared block matrix $\mathbf{C}_0$ (computed using uncorrected $E_0$). Calculate uncorrected trial PK2 stress $\mathbf{S}_{0,k} = \mathbf{C}_0 : \mathbf{E}_k$, then multiply the resulting stress vector by scalar $\eta_k$:
  $$\mathbf{S}_{corrected,k} = \eta_k \cdot \mathbf{S}_{0,k}$$
- **Mathematical Proof of Equivalence:** For isotropic linear elasticity with constant Poisson's ratio $\nu$:
  $$\mathbf{C}(E_k, \nu) = E_k \cdot \mathbf{\hat{C}}(\nu) = \frac{E_k}{E_0} \mathbf{C}(E_0, \nu) = \eta_k \mathbf{C}_0$$
  $$\mathbf{S}_k = \mathbf{C}(E_k, \nu) : \mathbf{E}_k = \left( \eta_k \mathbf{C}_0 \right) : \mathbf{E}_k = \eta_k \left( \mathbf{C}_0 : \mathbf{E}_k \right)$$
  Because $\mathbf{C}$ is strictly linear in $E$, multiplying the resulting stress tensor $\mathbf{S}_{0,k}$ by scalar $\eta_k$ is **mathematically identical** to building a per-element matrix $\mathbf{C}_k$.
- **Computational Cost:** 6 scalar multiplications per Gauss point $\times$ 8 Gauss points = 48 FLOPs per element per increment (a **6x speedup** in stress assembly over Option 3A).

### Recommendation on Point 3:
**Option 3B (Scalar Stress Scaling with Shared $\mathbf{C}_0$)** is mathematically exact for isotropic elasticity and significantly faster in Fortran. Option 3A is necessary only if the human chooses an anisotropic or Poisson-varying correction model in the future.

---

## Point 4: Physics Interaction Risk with Plastic Yield Stress (`SIGY0`) and Failure Criteria

> [!IMPORTANT]
> This section surfaces a fundamental physics coupling risk. It lays out the concrete options and their consequences for human decision, but does NOT pick a solution.

### 4.1 The Physics Interaction Mechanism
In `uel/VUEL_failure.for`:
1. **Yield Condition:** von Mises yield function $f = \sigma_{eq} - (\text{SIGY0} + H \cdot \bar{\epsilon}^p) \le 0$.
2. **Elastic Trial Stress:** $\mathbf{S}_{trial} = \mathbf{S}_{old} + \mathbf{C} : \Delta \mathbf{E}$.
3. **Stage 1 & Stage 2 Calibrations:**
   - Stage 1 (`docs/VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.md`) calibrated J2 plastic return mapping against $E_0 = 200\text{ GPa}$, $\text{SIGY0} = 250\text{ MPa}$, yield strain $\epsilon_y = \frac{\text{SIGY0}}{E_0} = 0.00125$.
   - Stage 2 (`docs/VUEL_PLASTIC_FAILURE_STAGE2_REPORT_2026-10-01.md`) calibrated engineering strain failure threshold $\text{EPS\_FAIL} = 0.02$.

If host elastic stiffness is scaled down by $\eta_k = 1 - f(V_f)$ (e.g. $\eta_k = 0.5$ for $V_f = 0.5$), the elastic strain required to reach the unscaled yield stress $\text{SIGY0}$ becomes:
$$\epsilon_{yield}' = \frac{\text{SIGY0}}{\eta_k E_0} = \frac{1}{\eta_k} \epsilon_{yield}$$

**Consequence:** For $\eta_k = 0.5$, the host material would require **2$\times$ higher strain** ($\epsilon = 0.0025$ instead of $0.00125$) before plastic yielding initiates.

### 4.2 Three Concrete Options for Human Decision

#### Option 4A: Proportionally Scale Yield Stress ($\text{SIGY0}$) and Hardening Modulus ($\text{HMOD}$)
- **Formulation:**  
  $$\text{SIGY0}_k = \eta_k \cdot \text{SIGY0}_0, \quad \text{HMOD}_k = \eta_k \cdot \text{HMOD}_0$$
- **Effect:** Preserves the exact initial yield strain $\epsilon_{yield} = \frac{\text{SIGY0}_k}{E_k} = \frac{\text{SIGY0}_0}{E_0} = 0.00125$.
- **Tradeoff:** Preserves Stage 1 and Stage 2 plastic/failure calibrations exactly. Physically represents a matrix whose effective macro load-carrying capacity (both elastic and plastic yield threshold) is reduced in proportion to host volume fraction.

#### Option 4B: Keep Yield Stress ($\text{SIGY0}$) Unscaled (Pure Elastic Reduction)
- **Formulation:** Apply $\eta_k$ to elastic stiffness only; leave $\text{SIGY0}_k = \text{SIGY0}_0$ and $\text{HMOD}_k = \text{HMOD}_0$.
- **Effect:** Increases effective macro yield strain ($\epsilon_{yield}' = \frac{1}{\eta_k} \epsilon_y$).
- **Tradeoff:** Physically assumes the intrinsic matrix yield stress is unchanged, but requires higher global strain to reach yield because host stiffness is reduced. Invalidates Stage 1 / Stage 2 calibration curves and requires recalibration of plastic response.

#### Option 4C: Strain-Based Plastic Yielding / Constitutive Formulation
- **Formulation:** Evaluate plastic yield condition using uncorrected matrix trial stress or strain-space equivalent plastic strain.
- **Effect:** Decouples elastic double-counting correction from matrix intrinsic yield criteria.
- **Tradeoff:** Requires structural modifications to the return-mapping algorithm in `uel/VUEL_failure.for`.

---

## Comparative Options Summary Matrix

| Evaluation Dimension | Option A (Recommended Architectural Choice) | Option B (Alternative Choice) | Option C (Alternative Choice) |
|---|---|---|---|
| **1. Data Pipeline** | `*Initial Conditions, TYPE=SOLUTION` $\to$ `svars(107)` (Zero Fortran I/O, native MPI safe) | `*UEL Property` (Requires 24k elsets, breaks vectorization) | `UEXTERNALDB` / CSV File I/O (Fragile across MPI nodes) |
| **2. Calculation Hook** | On-the-fly inside `jIntForceAndDtStable` (Simple, no extra `svars`) | Pre-computed during `jMassCalc` into `svars(108)` (Zero runtime math) | Pre-computed in Python generator (Hardcodes physics into deck) |
| **3. Stress Application** | Scalar Stress Scaling $\mathbf{S}_k = \eta_k (\mathbf{C}_0 : \mathbf{E}_k)$ (6x faster, mathematically exact) | Rebuild 6x6 Matrix $\mathbf{C}_k$ (Slower, needed only for anisotropy) | Pre-scale strain vector (Risk of plastic flow distortion) |
| **4. Physics Coupling** | **4A:** Scale $\text{SIGY0}_k = \eta_k \text{SIGY0}_0$ (Preserves yield strain & Stage 1/2 calibration) | **4B:** Unscaled $\text{SIGY0}$ (Increases yield strain, shifts plastic onset) | **4C:** Strain-space plasticity (Requires return-mapping refactoring) |

---

## Verification Plan & Items Requiring Live Abaqus Testing

Since this document is produced without live ROAR/Abaqus solver execution, the following items must be verified during initial implementation:
1. **SVAR Preservation in `jMassCalc`:** Confirm that caching $\eta_k$ in `svars(KBLOCK, 108)` during `jMassCalc` (`lflags(3) == 1`) persists cleanly into `jIntForceAndDtStable` (`lflags(3) == 4`) without being overwritten by Abaqus state initialization routines.
2. **Single-Element Uniaxial Verification:** Run a single-element test deck comparing uncorrected vs. corrected ($V_f = 0.5$) responses to verify that reaction forces $RF1$ scale by exactly $\eta_k$ in the elastic regime.
3. **Plastic Flow Verification:** Verify that selected yield scaling option (4A vs 4B) matches analytic bilinear stress-strain predictions under tension/compression reloading.
