# T-005 Design & Brainstorming Document: Preprocessed Host Volume Fraction Correction in `uel/VUEL_failure.for`

**Task ID:** T-005  
**Role:** Drafter (Brainstorming & Initial Draft Implementation)  
**Date:** 2026-10-09  
**Target Subroutine:** `uel/VUEL_failure.for` (Branch `vuel-plastic-failure`)  

---

## Executive Summary & Background

In embedded-fiber finite element modeling (where 1D fiber elements are embedded within 3D host continuum hex elements via Abaqus `*EMBEDDED ELEMENT`), the host matrix material occupies the full geometric volume of the hex element ($V_0$). However, the physical matrix volume fraction is reduced by the embedded fibers to $V_{matrix} = (1 - V_f) V_0 = \eta_k V_0$, where $V_f$ is the local fiber volume fraction and $\eta_k = 1 - V_f$.

In **Stage 7** (commit `0cc1e8f`), double-counting of host stiffness was mitigated at runtime inside `uel/VUEL_failure.for` by scaling the matrix material constants ($E_k = \eta_k E_0$, $\lambda_k = \eta_k \lambda_0$, $\mu_k = \eta_k \mu_0$, $\sigma_{y0,k} = \eta_k \sigma_{y0}$, $H_k = \eta_k H_0$). While mathematically effective for stress integration and plastic return, scaling material constants leaves material wave speed $c = \sqrt{(\lambda+2\mu)/\rho}$ implicitly altered if derived from scaled moduli, forcing `CWAVE` to be conservatively frozen at unscaled baseline values. Furthermore, Stage 7 left host mass density $\rho$ unscaled, maintaining a slight overcounting of host mass.

This document explores an alternative, physically cleaner formulation: **scaling the host element's differential integration volume ($\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$) and reference element volume ($V_{\mathrm{eff}} = \eta_k V_0$) inside `uel/VUEL_failure.for`**, while keeping intrinsic material properties ($E_0, \nu_0, \rho_0, \sigma_{y0}, H_0$) completely untouched.

---

## Point 1: Analysis of Current Volume Computation in `uel/VUEL_failure.for`

A comprehensive audit of `uel/VUEL_failure.for` reveals how volume is calculated and consumed.

### 1.1 Volume Integration Mechanics
Volume in `uel/VUEL_failure.for` is explicitly computed from the reference configuration geometry using full 2x2x2 Gauss quadrature:

1. **Gauss Point Volume Differential ($\mathrm{d}V_0$):**
   In `SHAPE8H_TL` (called at lines 529 and 615), the reference Jacobian determinant $\text{DETJ0} = \det(\mathbf{J}_0) = \det(\partial \mathbf{X} / \partial \boldsymbol{\xi})$ is calculated from the reference nodal coordinates $\mathbf{X}_{\mathrm{LOC}}$.
   At each Gauss point $g \in \{1,\dots,8\}$, the differential volume is:
   ```fortran
   DVOL = DETJ0 * WT ! (lines 534, 625: WT = 1.0D0 for 2x2x2)
   ```
2. **Total Reference Element Volume ($V_0$):**
   Accumulated across all 8 Gauss points:
   ```fortran
   ELVOL = ELVOL + DVOL ! (lines 535, 626)
   ```

### 1.2 Separability of Integration Volume from Material Stiffness
The computation of $\mathrm{d}V_0$ (`DVOL`) and $V_0$ (`ELVOL`) is **completely explicit and decoupled** from the material constitutive tensor `CMAT`. `DVOL` enters downstream calculations strictly as a linear scalar multiplier during quadrature summation:
- Internal force integration: $\mathbf{f}_{\mathrm{int}} = \sum_{g=1}^8 \mathbf{B}_{L,g}^T \mathbf{S}_g \mathrm{d}V_{0,g}$ (line 878)
- Mass matrix formulation: $m_{\mathrm{elem}} = \rho_0 V_0$ (line 538)
- Energy dissipation integrals: $U_e = \sum_{g=1}^8 \frac{1}{2} \mathbf{S}_g : \mathbf{E}_{e,g} \mathrm{d}V_{0,g}$ (line 889)

Because $\mathrm{d}V_0$ and $V_0$ appear as isolated scalar weights in these integrals, volume scaling ($\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$) is **fully separable** from element geometry, shape functions, deformation gradient evaluation, and constitutive stress updates.

---

## Point 2: Traceability & Subroutine Impact of Volume Scaling

Scaling host volume by $\eta_k = 1 - V_f$ affects every subroutine module relying on element volume. Below is the complete trace of these impacts:

| Subroutine Calculation | Fortran Line(s) | Original Baseline Code | Volume-Corrected Formulation | Consistency & Physics Status |
|---|---|---|---|---|
| **Lumped Mass Matrix** | 538--545 | `ELEMASS = DENS * ELVOL`<br>`amass(...,IDOF,IDOF) = ELEMASS / 8.0D0` | `ELEMASS = DENS * (ETA_VF * ELVOL_GEOM)`<br>`amass(...,IDOF,IDOF) = ELEMASS / 8.0D0` | **Exact.** Host mass is reduced to match true matrix volume $(1-V_f)V_0$. Combined with embedded fiber mass, total mass double-counting is eliminated. |
| **Internal Force Assembly** | 876--880 | `FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_TOTAL(J) * DVOL` | `FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_TOTAL(J) * (ETA_VF * DVOL_GEOM)` | **Exact.** Internal force scales linearly by $\eta_k$. Since host mass also scales by $\eta_k$, host acceleration $\ddot{\mathbf{u}} = \mathbf{M}^{-1} \mathbf{f}_{\mathrm{int}}$ remains exact. |
| **Kinetic Energy (`ELKE`)** | 964--968 | `ELEMASS = DENS * ELVOL`<br>`ELKE = ELKE + 0.5D0 * (ELEMASS/8) * VLOC^2` | `ELEMASS = DENS * (ETA_VF * ELVOL_GEOM)`<br>`ELKE = ELKE + 0.5D0 * (ELEMASS/8) * VLOC^2` | **Exact.** Kinetic energy reflects the true reduced host mass. |
| **Strain Energy (`ELIE`) & Plastic Dissipation** | 888--899 | `ELIE = ELIE + 0.5D0 * S * Ee * DVOL`<br>`PLASTIC_DISSIP = PLASTIC_DISSIP + ... * DVOL` | `ELIE = ELIE + 0.5D0 * S * Ee * (ETA_VF * DVOL_GEOM)`<br>`PLASTIC_DISSIP = ... * (ETA_VF * DVOL_GEOM)` | **Exact.** Stored strain energy and plastic work scale cleanly with matrix volume fraction. |
| **Viscous Damping & Bulk Viscosity Dissipation** | 912--925 | `DAMP_DISSIP = ... * DVOL * dtimeCur`<br>`BV_DISSIP = ... * DVOL * dtimeCur` | `DAMP_DISSIP = ... * (ETA_VF * DVOL_GEOM) * dtimeCur`<br>`BV_DISSIP = ... * (ETA_VF * DVOL_GEOM) * dtimeCur` | **Exact.** Damping work scales with matrix volume fraction. |
| **Dilatational Wave Speed (`CWAVE`)** | 572 | `CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)` | `CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)` (Unchanged) | **Exact.** Material wave speed depends ONLY on intrinsic material moduli ($\lambda_0, \mu_0$) and density ($\rho_0$). Neither depends on volume. |
| **Characteristic Length (`CHARLEN`) & Stable Time Step** | 998--1002 | `CHARLEN = ELVOL ** (1.0D0 / 3.0D0)`<br>`OMEGA_MAX = CWAVE / CHARLEN * 2.0D0` | `CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)` (Must use geometric volume) | **Critical Distinction.** `CHARLEN` represents physical mesh element length $L_e$. Must use geometric volume $V_{0,\mathrm{geom}}^{1/3}$, NOT effective volume $(\eta_k V_0)^{1/3}$. |

### Key Finding on Characteristic Length ($L_e$):
If `CHARLEN` were mistakenly computed using effective volume $V_{\mathrm{eff}} = \eta_k V_{0,\mathrm{geom}}$, `CHARLEN` would shrink by $\eta_k^{1/3}$ (e.g., for $V_f=0.6$, $\eta_k=0.4$, $\eta_k^{1/3} \approx 0.737$). A smaller $L_e$ would artificially elevate $\omega_{\max} = 2 c_0 / L_e$ and reduce $\Delta t_{\mathrm{stable}}$, forcing unnecessarily small time steps. 
**Rule:** `CHARLEN` for $\Delta t_{\mathrm{stable}}$ and bulk viscosity pressure $q_{\mathrm{bulk}}$ MUST be derived from unscaled geometric volume $V_{0,\mathrm{geom}}$.

---

## Point 3: Algebraic Derivation & Comparison with Stage 7

We prove algebraically that volume scaling yields identical stress-strain response, plastic strain accumulation, and nodal accelerations as Stage 7, while providing superior wave-speed and mass consistency.

### 3.1 Stage 7 (Stiffness-Scaled) Algebra
In Stage 7, matrix moduli and yield parameters are scaled inside the VUEL by $\eta_k$:
$$\mathbf{C}_k = \eta_k \mathbf{C}_0, \quad \sigma_{y0,k} = \eta_k \sigma_{y0}, \quad H_k = \eta_k H_0$$
For an elastic trial strain $\mathbf{E}_e^{\mathrm{trial}} = \mathbf{E} - \mathbf{E}_p^{\mathrm{old}}$:
1. Trial stress: $\mathbf{S}_k^{\mathrm{trial}} = \mathbf{C}_k : \mathbf{E}_e^{\mathrm{trial}} = \eta_k (\mathbf{C}_0 : \mathbf{E}_e^{\mathrm{trial}}) = \eta_k \mathbf{S}_0^{\mathrm{trial}}$
2. Von Mises trial stress: $\sigma_k^{\mathrm{trial}} = \eta_k \sigma_0^{\mathrm{trial}}$
3. Yield stress: $\sigma_{y,k}^{\mathrm{old}} = \eta_k (\sigma_{y0} + H_0 \bar{\varepsilon}_p^{\mathrm{old}}) = \eta_k \sigma_{y0}^{\mathrm{old}}$
4. Radial return scalar $\Delta \gamma$:
   $$\Delta \gamma = \frac{\sigma_k^{\mathrm{trial}} - \sigma_{y,k}^{\mathrm{old}}}{3 \mu_k + H_k} = \frac{\eta_k \sigma_0^{\mathrm{trial}} - \eta_k \sigma_{y0}^{\mathrm{old}}}{3 (\eta_k \mu_0) + \eta_k H_0} = \frac{\sigma_0^{\mathrm{trial}} - \sigma_{y0}^{\mathrm{old}}}{3 \mu_0 + H_0}$$
   **$\eta_k$ cancels completely from numerator and denominator.**
5. Plastic strain increment: $\Delta \mathbf{E}_p = \frac{3}{2} \frac{\Delta \gamma}{\sigma_k^{\mathrm{trial}}} \mathbf{s}_k^{\mathrm{trial}} = \frac{3}{2} \frac{\Delta \gamma}{\eta_k \sigma_0^{\mathrm{trial}}} (\eta_k \mathbf{s}_0^{\mathrm{trial}}) = \frac{3}{2} \frac{\Delta \gamma}{\sigma_0^{\mathrm{trial}}} \mathbf{s}_0^{\mathrm{trial}}$ ($\eta_k$ cancels).
6. Internal force: $\mathbf{f}_{\mathrm{int}} = \int_{V_0} \mathbf{B}_L^T \mathbf{S}_k \mathrm{d}V_0 = \eta_k \int_{V_0} \mathbf{B}_L^T \mathbf{S}_0 \mathrm{d}V_0$.

### 3.2 Volume-Scaled Algebra
In the Volume-Scaling formulation, material properties remain unscaled baseline values ($\mathbf{C}_0, \sigma_{y0}, H_0$), while integration volume is scaled ($\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$):
1. Trial stress: $\mathbf{S}^{\mathrm{trial}} = \mathbf{C}_0 : \mathbf{E}_e^{\mathrm{trial}} = \mathbf{S}_0^{\mathrm{trial}}$
2. Von Mises trial stress: $\sigma^{\mathrm{trial}} = \sigma_0^{\mathrm{trial}}$
3. Yield stress: $\sigma_y^{\mathrm{old}} = \sigma_{y0} + H_0 \bar{\varepsilon}_p^{\mathrm{old}} = \sigma_{y0}^{\mathrm{old}}$
4. Radial return scalar $\Delta \gamma$:
   $$\Delta \gamma = \frac{\sigma_0^{\mathrm{trial}} - \sigma_{y0}^{\mathrm{old}}}{3 \mu_0 + H_0}$$
   **Identical to Stage 7.**
5. Plastic strain increment: $\Delta \mathbf{E}_p = \frac{3}{2} \frac{\Delta \gamma}{\sigma_0^{\mathrm{trial}}} \mathbf{s}_0^{\mathrm{trial}}$ (**Identical to Stage 7**).
6. Internal force:
   $$\mathbf{f}_{\mathrm{int}} = \int_{V_0} \mathbf{B}_L^T \mathbf{S}_0 \mathrm{d}V_{\mathrm{eff}} = \int_{V_0} \mathbf{B}_L^T \mathbf{S}_0 (\eta_k \mathrm{d}V_0) = \eta_k \int_{V_0} \mathbf{B}_L^T \mathbf{S}_0 \mathrm{d}V_0$$
   **Identical to Stage 7.**

### 3.3 Comparative Summary

| Metric / Property | Stage 7 (Stiffness Scaled) | Proposed (Volume Scaled) | Advantage / Note |
|---|---|---|---|
| **Plastic Multiplier $\Delta \gamma$** | Exact baseline $\Delta \gamma_0$ | Exact baseline $\Delta \gamma_0$ | Mathematically identical |
| **Equivalent Plastic Strain ($\bar{\varepsilon}_p$)** | Exact baseline $\bar{\varepsilon}_p$ | Exact baseline $\bar{\varepsilon}_p$ | Mathematically identical |
| **Internal Force ($\mathbf{f}_{\mathrm{int}}$)** | $\eta_k \mathbf{f}_{\mathrm{int},0}$ | $\eta_k \mathbf{f}_{\mathrm{int},0}$ | Mathematically identical |
| **Host Nodal Mass Matrix ($\mathbf{M}_{\mathrm{host}}$)** | Unscaled $\mathbf{M}_0$ | Scaled $\eta_k \mathbf{M}_0$ | **Volume Scaled wins:** Eliminates host mass double-counting |
| **Wave Speed ($c_{\mathrm{dilatational}}$)** | Ambiguous if material properties scaled | Clean baseline $c_0 = \sqrt{\frac{\lambda_0+2\mu_0}{\rho_0}}$ | **Volume Scaled wins:** No material property distortion |
| **Stable Time Step ($\Delta t_{\mathrm{stable}}$)** | Conservative unscaled fallback | Exact physical value $L_e / c_0$ | **Volume Scaled wins:** Rigorous, exact derivation |

---

## Point 4: Evaluation of Data Delivery Pipeline & Preprocessing Location

### 4.1 Can Volume Correction Be Done in the Python Deck Generator (`embmesh`)?
The brief asks whether volume correction should be done in `embmesh` deck generation prior to VUEL execution.

**Analysis of Mesh Geometry Modifications:**
1. **Node Coordinate Shift:** Host hex elements form a continuous, conforming 3D mesh sharing nodes and faces with adjacent elements. Moving physical nodal coordinates $(X,Y,Z)$ to "shrink" host element geometric volume would tear element boundaries, create mesh voids/overlaps, cause negative Jacobians ($\det(\mathbf{J}) \le 0$), and destroy FE connectivity.
2. **Abaqus Deck Properties:** Abaqus UEL definitions (`*USER ELEMENT`) specify node topology and property array counts. Abaqus input deck syntax does not support per-element integration volume scale factors on section cards without breaking elements into 24,000 individual element sets and `*USER ELEMENT` property definitions (which destroys vectorized MPI block execution `nblock`).

### 4.2 Recommendation: Reuse the Stage 7 `svars(107)` Data Pipeline
The existing pipeline:
$$\text{Python Mesher (`embmesh`)} \xrightarrow{\text{fiber\_volume.csv}} \text{`*Initial Conditions, TYPE=SOLUTION`} \xrightarrow{} \texttt{svars(KBLOCK, 107)}$$
- Already fully functional, robust, and verified across ROAR MPI cluster runs.
- Delivers per-element fiber volume fraction $V_f$ into `svars(107)` at $t=0$ without runtime file I/O or deck restructuring.
- **Conclusion:** Reusing `svars(107)` inside `uel/VUEL_failure.for` to calculate $\eta_k = \max(1 - V_f, 10^{-6})$ and scale internal integration volume $\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$ is the cleanest, most efficient architecture.

---

## Point 5: Structural & Numerical Risk Audit

1. **Shared Nodal Mesh Connectivity:**
   Physical node positions `coords(KBLOCK, INODE, I)` are untouched. Volume scaling is strictly a quadrature integration scale factor ($\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$) within the VUEL, preserving 100% mesh connectivity.
2. **Mass Double-Counting Elimination:**
   By scaling host mass $m_{\mathrm{host}} = \eta_k \rho_0 V_0$, the host element surrenders its volume/mass fraction to the embedded fiber elements (which bring their own mass $m_{\mathrm{fiber}} = \rho_f A_f L_f$). Total dynamic mass is conserved exactly.
3. **Jacobian & Strain Failure Triggers:**
   Deformation gradient $\mathbf{F}$, Green-Lagrange strain $\mathbf{E}$, nominal engineering strain $\varepsilon_i = \lambda_i - 1$, and collapse ratio $\det(\mathbf{F})$ are derived from displacement gradients $\partial \mathbf{u} / \partial \mathbf{X}$, independent of volume scaling. Strain-based failure triggers (`EPS_FAIL`, `JAC_FAIL`) remain 100% unaffected.
4. **Post-Failure Degradation (Stage 5):**
   The unilateral residual compression stiffness $K_{\mathrm{residual}} = r K_0$ integrates over $\mathrm{d}V_{\mathrm{eff}} = \eta_k \mathrm{d}V_0$, naturally scaling host residual contact stiffness by $(1-V_f)$.

---

## Proposed Implementation Sketch (`uel/VUEL_failure.for`)

Below is the draft Fortran patch illustrating the volume-fraction volume-scaling implementation in `uel/VUEL_failure.for`.

```fortran
C======================================================================
C     VOLUME-FRACTION VOLUME SCALING (T-005 DRAFT)
C     Intrinsic material parameters (EMOD, ALAMBDA, AMU, DENS, SIGY0, HMOD)
C     remain UNTOUCHED baseline values. Host element integration volume
C     dV_eff = eta_k * dV_0 and element reference volume ELVOL_EFF = eta_k * ELVOL
C     carry the volume fraction correction factor eta_k = max(1 - Vf, 1e-6).
C======================================================================

      DO KBLOCK = 1, nblock
        FIBER_VOL_FRAC = 0.0D0
        IF (nsvars .GE. 107) FIBER_VOL_FRAC = svars(KBLOCK,107)
        ETA_VF_RAW = 1.0D0 - FIBER_VOL_FRAC
        ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)

C----------------------------------------------------------------------
C       MASS MATRIX CALCULATION (lflags(iOpCode) == jMassCalc)
C----------------------------------------------------------------------
        IF (lflags(iOpCode) .EQ. jMassCalc) THEN
          DO I = 1, ndofel
            DO J = 1, ndofel
              amass(KBLOCK, I, J) = 0.0D0
            END DO
          END DO

          ELVOL_GEOM = 0.0D0
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
            DVOL_GEOM = DETJ0 * WT
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
          END DO

C         Scale host mass by effective host matrix volume fraction eta_k
          ELVOL_EFF = ETA_VF * ELVOL_GEOM
          ELEMASS = DENS * ELVOL_EFF

          DO INODE = 1, 8
            DO I = 1, 3
              IDOF = (INODE - 1) * 3 + I
              amass(KBLOCK, IDOF, IDOF) = ELEMASS / 8.0D0
            END DO
          END DO
        END IF

C----------------------------------------------------------------------
C       INTERNAL FORCE & STABLE DT (lflags(iOpCode) == jIntForceAndDtStable)
C----------------------------------------------------------------------
        IF (lflags(iOpCode) .EQ. jIntForceAndDtStable) THEN
          ELVOL_GEOM = 0.0D0
          ELVOL_EFF  = 0.0D0

          DO IGAUSS = 1, 8
            ...
            CALL SHAPE8H_TL(...)
            DVOL_GEOM = DETJ0 * WT
            DVOL_EFF  = ETA_VF * DVOL_GEOM
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
            ELVOL_EFF  = ELVOL_EFF  + DVOL_EFF

            ... [Stress update computed using UNTOUCHED CMAT, SIGY0, HMOD] ...

C           Internal force integration uses DVOL_EFF
            DO I = 1, 24
              DO J = 1, 6
                FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_TOTAL(J) * DVOL_EFF
              END DO
            END DO

C           Energy integration uses DVOL_EFF
            IF (CONSTITUTIVE_ACTIVE) THEN
              DO I = 1, 6
                ELIE = ELIE + 0.5D0 * STRESS_SCALE * STRESS_PK2(I)
     *                         * EE_NEW_VEC(I) * DVOL_EFF
              END DO
              PLASTIC_DISSIP = PLASTIC_DISSIP
     *            + STRESS_SCALE * 0.5D0 * (SIGY_OLD + SIGY_NEW)
     *              * DGAMMA * DVOL_EFF
            END IF
          END DO

C         Kinetic energy uses effective host mass
          ELEMASS = DENS * ELVOL_EFF
          DO INODE = 1, 8
            DO I = 1, 3
              ELKE = ELKE + 0.5D0 * (ELEMASS / 8.0D0) * VLOC(I, INODE)**2
            END DO
          END DO

C         Stable time step uses GEOMETRIC volume for CHARLEN
          CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)
          CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)
          OMEGA_MAX = CWAVE / CHARLEN * 2.0D0
          XI_DAMP = BETA_RAYLEIGH * OMEGA_MAX / 2.0D0
          dtimeStable(KBLOCK) = (2.0D0 / OMEGA_MAX) *
     *                          (DSQRT(1.0D0 + XI_DAMP**2) - XI_DAMP)
        END IF
      END DO
```

---

## Conclusion & Next Steps for Human Decision

1. **Viability:** The volume-scaling approach is **fully viable**, mathematically sound, and superior to Stage 7 in wave speed rigor and host mass accounting.
2. **Data Path:** The existing `svars(107)` data path should be preserved.
3. **Deliverables Prepared:**
   - `agents/drafter/outbox/T-005/BRAINSTORM.md` (this file)
   - `agents/drafter/outbox/T-005/VUEL_failure_vol_corr.for` (first draft patch file)
   - `agents/drafter/outbox/T-005-RESULT.md` (task result summary)
