# Technical Risk Analysis: 3-Element-Per-Ply Through-Thickness Subdivision ($N_t = 3$)

**Task**: T-053  
**Author**: drafter  
**Date**: November 2026  
**Scope**: Impact mechanics, numerical stability, constitutive behavior, and computational performance of $N_t = 3$ meshing for `Vals.inp`.

---

## 1. Contact Thickness vs Host Element Thickness

### Risk Description
When subdividing each $1.27\text{ mm}$ ply into $N_t = 3$ hex layers, the resulting element thickness is:
$$t_{elem} = \frac{1.27\text{ mm}}{3} \approx 0.4233\text{ mm} = 4.233 \times 10^{-4}\text{ m}$$
In Abaqus/Explicit, penalty contact applies a numerical contact thickness (or offset) around element surfaces and node sets to prevent high-velocity penetration:
- In `embmesh/plywise_contact.py`, `contact_thickness` defaults to `'auto'` (computed from ply/element thickness, typically $t_{c} \approx 0.5 \cdot t_{elem} \approx 0.21\text{ mm}$).
- If contact thickness is set too large relative to $t_{elem}$ (e.g. if legacy full-ply contact thickness $t_{c} \approx 0.635\text{ mm}$ were used), the contact shell exceeds the element thickness ($0.635\text{ mm} > 0.423\text{ mm}$). Under this condition:
  1. The contact boundary of the top face penetrates through the element and projects past the bottom face before deformation even occurs.
  2. Severe initial overclosure and explosive node ejections can be triggered on the first explicit increment.
- Under high-velocity impact ($v_0 = 1000\text{ m/s}$ steel ball), large compressive deformation rapidly flattens the $0.423\text{ mm}$ elements. If element deletion is enabled, deleting a crushed surface element suddenly exposes the underlying interior node layer to the ball. If the contact search radius is larger than the remaining element layer thickness, cross-surface penetration and snagging occur.

### Mitigation Strategies
1. **Strict Scaling of Contact Thickness**:
   Ensure `contact_thickness` is scaled proportionally with $t_{elem}$ (specifically $t_c \le 0.4 \cdot t_{elem} \approx 0.17\text{ mm}$).
2. **Double-Sided / Eroding Contact**:
   When element deletion is active, configure interior faces to become active contact surfaces (`*Contact Inclusions, all exterior`) so that when layer 0 elements erode, layer 1 elements immediately participate in contact.

---

## 2. Hourglassing of Thin Reduced-Integration Elements (C3D8R)

### Risk Description
In `Vals.inp`, the in-plane mesh discretization in the impact zone is approximately $\Delta x \approx 1.25\text{ mm}, \Delta y \approx 1.25\text{ mm}$.
- With $N_t = 1$: Aspect ratio is $\Delta x : \Delta z \approx 1.25\text{ mm} : 1.27\text{ mm} \approx 1:1$ (cubic elements).
- With $N_t = 3$: Aspect ratio is $\Delta x : \Delta z \approx 1.25\text{ mm} : 0.423\text{ mm} \approx 3:1$ (thin plate elements).

C3D8R elements use a single Gauss integration point at the element centroid. They are susceptible to 12 non-physical zero-energy deformation modes (hourglass modes).
- When an individual ply is discretized with 3 elements through thickness, through-thickness bending and transverse shear gradients within the ply are now resolved by the continuum mesh.
- Thin C3D8R elements undergoing out-of-plane flexure under localized projectile indentation can rapidly develop hourglass patterns. Because the element is 3 times thinner in $z$ than in $x/y$, transverse shear resistance is low.
- Standard default hourglass stiffness in Abaqus/Explicit may fail to restrain high-frequency kinematic modes, resulting in a "waffle" or "zigzag" grid distortion without corresponding stress generation, corrupting ballistic displacement predictions.

### Mitigation Strategies
1. **Enhanced Hourglass Control**:
   Use `*Section Controls, name=ENHANCED_HG, hourglass=ENHANCED` (or `STIFFNESS` with factor 0.1-0.2) on the matrix solid section cards.
2. **Artificial Energy Monitoring**:
   Monitor the ratio of artificial energy (`ALLAE`) to total internal energy (`ALLIE`) in the `.sta` and `.odb` history outputs. Ensure $\text{ALLAE} / \text{ALLIE} < 5\%$ throughout the 70 $\mu$s impact event.

---

## 3. Computational Scaling: Runtime & Memory Footprint

### Quantitative Scaling Analysis
Subdividing from $N_t = 1$ to $N_t = 3$ causes a quadratic increase in computational effort:

| Metric | Baseline ($N_t = 1$) | Subdivided ($N_t = 3$) | Scaling Factor |
| :--- | :--- | :--- | :--- |
| **Matrix Elements per Ply** | $4{,}025$ | $12{,}075$ | $\mathbf{3.0\times}$ |
| **Total Plate Matrix Elements** ($20\text{ plies}$) | $80{,}500$ | $241{,}500$ | $\mathbf{3.0\times}$ |
| **Nodes per Ply** | $8{,}272$ | $24{,}816$ | $\mathbf{3.0\times}$ |
| **Total Plate Nodes** | $165{,}440$ | $496{,}320$ | $\mathbf{3.0\times}$ |
| **Characteristic Element Length** ($L_{min}$) | $\approx 1.27\text{ mm}$ | $\approx 0.423\text{ mm}$ | $\mathbf{0.333\times}$ |
| **Explicit Stable Time Increment** ($\Delta t_{stable}$) | $\approx 2.4 \times 10^{-8}\text{ s}$ | $\approx 0.8 \times 10^{-8}\text{ s}$ | $\mathbf{0.333\times}$ |
| **Total Time Steps** ($T = 70\,\mu\text{s}$) | $\approx 2{,}900$ steps | $\approx 8{,}750$ steps | $\mathbf{3.0\times}$ |
| **Total Explicit Solves** ($N_{elem} \times N_{steps}$) | $2.33 \times 10^8$ ops | $2.11 \times 10^9$ ops | $\mathbf{9.0\times}$ |

### Runtime & Memory Consequences
1. **$9\times$ CPU Runtime**:
   The stable time increment in explicit dynamics is bounded by the Courant-Friedrichs-Lewy (CFL) condition:
   $$\Delta t \le \frac{L_{min}}{c_d}, \quad c_d = \sqrt{\frac{E(1-\nu)}{\rho(1+\nu)(1-2\nu)}}$$
   Because $L_{min}$ is reduced by factor 3, the time step drops by factor 3, requiring $3\times$ more increments. Combined with $3\times$ more elements per increment, the total execution time scales as $3 \times 3 = 9\times$. A simulation taking 2 hours on ROAR (24 cores) for $N_t = 1$ will take $\approx 18$ hours for $N_t = 3$.
2. **VUEL Ghost Mesh Doubling**:
   When running `--host-mode vuel-ghost`, every matrix element is coupled to a ghost element. The total element count in the plate becomes:
   $$241{,}500 \text{ (VUEL)} + 241{,}500 \text{ (Ghost)} = 483{,}000 \text{ elements}$$
   Plus $605{,}160$ embedded fiber truss elements, totaling over **1.08 million elements**.
3. **Memory Footprint**:
   With 112 state variables (SVARs) per integration point in `VUEL_material.for`, storing SVAR history for $241{,}500$ VUEL elements requires:
   $$241{,}500 \times 112 \times 8 \text{ bytes} \approx 216\text{ MB}$$
   in active memory per thread, plus ODB output frame buffering.

---

## 4. VUEL Volume Fraction Clamping & Matrix Failure Localization

### Physics & Subroutine Behavior
In `uel/VUEL_material.for`, the interaction between the embedded fiber bed and the host continuum matrix is governed by the matrix volume fraction $\eta = 1 - V_f$:

1. **Volume Fraction Discontinuity**:
   - In physical reality, fibers in each ply have finite diameter $d = 0.632\text{ mm}$ and occupy the entire central region of the $1.27\text{ mm}$ ply.
   - In the mesher, the fiber bed is placed as a 2D sheet on the mid-plane ($z = 0.5 \cdot t_{ply}$).
   - For $N_t = 3$, all fiber segments fall strictly inside layer $m = 1$ (thickness $0.423\text{ mm}$).
   - Layer 0 and Layer 2 contain zero fiber segments:
     $$V_{f, outer} = 0.0 \implies \eta_{outer} = 1.0$$
   - Layer 1 contains all fibers:
     $$V_{f, mid} \approx 3 \times 0.39 = 1.17 \implies 1 - V_f = -0.17$$
2. **Subroutine Clamping**:
   - In `VUEL_material.for` (lines 440-455):
     ```fortran
     eta = max(1.0d0 - Vf, 1.0d-6)
     ```
     Because $V_f \ge 1.0$, $\eta$ clamps to $10^{-6}$.
3. **Matrix Stress & Inertia Collapse in Center Layer**:
   - The matrix stress contribution to the nodal forces is scaled directly by $\eta$:
     $$\boldsymbol{\sigma}_{elem} = \eta \boldsymbol{\sigma}_{matrix}$$
   - The effective mass of the matrix in layer 1 is scaled by $\eta = 10^{-6}$.
   - Consequently, the matrix in layer 1 contributes virtually zero load-bearing capacity and near-zero inertia from the very start of the simulation. Layer 1 behaves as an empty cavity with only 1D fiber trusses spanning it.
4. **Localization of Fracture Energy**:
   - In `VUEL_material.for` (lines 720-745), the characteristic crack band length $L$ is regularized as:
     $$L = (\eta V_0)^{1/3}$$
   - When $\eta = 10^{-6}$, $L$ collapses by a factor of $(10^{-6})^{1/3} = 10^{-2}$ ($100\times$ smaller).
   - The plastic displacement at failure $u_f^p = \frac{2 G_f}{\sigma_{y0}}$ corresponds to an equivalent failure plastic strain:
     $$\varepsilon_f^p = \frac{u_f^p}{L} = \frac{2 G_f}{\sigma_{y0} L}$$
   - A $100\times$ smaller $L$ means the critical strain $\varepsilon_f^p$ required to dissipate fracture energy $G_f$ is scaled $100\times$ higher, creating an artificial numerical stiffness artifact during the softening regime.
   - Meanwhile, outer layers 0 and 2 carry 100% of the matrix load without any fiber reinforcement, meaning that bending stresses will induce matrix microcracking in the outer skins while the center core remains decoupled.

### Recommendation
For high-fidelity VUEL simulations with $N_t = 3$, volume fractions should either be smoothed across adjacent thickness layers (e.g. projecting fiber volume onto layers 0 and 2 based on fiber diameter $d = 0.632\text{ mm} > 0.423\text{ mm}$), or the native material model (`--host-mode native`) should be preferred until the VUEL formulation incorporates non-local volume fraction averaging.
