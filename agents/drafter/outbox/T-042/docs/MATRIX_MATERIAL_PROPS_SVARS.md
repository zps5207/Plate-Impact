# Matrix Material Model: Props, SVARS, Constitutive Equations & Energy Layout

## 1. Overview and Architecture

`uel/VUEL_material.for` is an extension of `uel/VUEL_failure.for` (Total Lagrangian 8-node hexahedral user element) implementing:
- Isotropic linear elasticity in Green-Lagrange strain $E$ and 2nd Piola-Kirchhoff stress $S$.
- Rate-dependent J2 (von Mises) plasticity with associative radial return and zero hardening ($H_{mod} = 0$).
- Rate-dependent tabular ductile damage onset on equivalent plastic strain ($PEEQ$).
- Energy-based linear softening ($G_f$-governed fracture displacement $\bar{u}_f = 2 G_f / \sigma_{y0}$).
- Gauss-point damage $D \in [0, 1]$ scaling the PK2 stress tensor by $(1 - D)$.
- Volume-fraction-consistent characteristic length $L = V_{0,eff}^{1/3} = ((1 - V_f) V_{0,geom})^{1/3}$.
- Complete separation and tracking of plastic dissipation ($ALLPD$) and damage dissipation ($ALLDMD$).
- Backward-compatible execution of legacy elastic and Stage 1-5 models via `props(14) = MAT_MODEL`.

---

## 2. Properties Layout (`props`)

The element takes up to 39 properties (`nprops = 39`) on the `*UEL Property` definition:

| Prop Index | Symbol | Units | Description |
|---|---|---|---|
| **Legacy Props (1-13)** | | | |
| `props(1)` | $E$ | Pa | Young's modulus (intact matrix: 700.0e6) |
| `props(2)` | $\nu$ | - | Poisson's ratio (intact matrix: 0.45) |
| `props(3)` | $\rho$ | kg/m$^3$ | Mass density (intact matrix: 980.0) |
| `props(4)` | $\beta$ | s | Rayleigh damping coefficient (typical: 0.0) |
| `props(5)` | $b_1$ | - | Linear bulk viscosity coefficient (typical: 0.06, or 0.0 for pure constitutive verif) |
| `props(6)` | $b_2$ | - | Quadratic bulk viscosity coefficient (typical: 1.2, or 0.0 for pure constitutive verif) |
| `props(7)` | $\varepsilon_{fail}$ | - | Legacy normal engineering strain failure trigger (set 10.0 to disable) |
| `props(8)` | $\sigma_{y0,old}$ | Pa | Legacy Stage 1 yield stress (ignored when `MAT_MODEL=1`) |
| `props(9)` | $H_{mod,old}$ | Pa | Legacy Stage 1 hardening modulus (ignored when `MAT_MODEL=1`) |
| `props(10)` | $IPLAST$ | - | Legacy plasticity switch (0=elastic, 1=Stage 1; ignored when `MAT_MODEL=1`) |
| `props(11)` | $JAC_{fail}$ | - | Legacy min det(F) collapse threshold (set 0.0 to disable) |
| `props(12)` | $t_{degrade}$ | s | Legacy post-failure linear time ramp (ignored when `MAT_MODEL=1`) |
| `props(13)` | $r_{bulk}$ | - | Legacy compression-only residual bulk fraction (ignored when `MAT_MODEL=1`) |
| **New Ductile Damage Props (14-39)** | | | |
| `props(14)` | $MAT\_MODEL$ | - | Model selector: `0.0` = legacy model, `1.0` = ductile damage rate model |
| `props(15)` | $RATE\_MODE$ | - | Strain rate measure: `0.0` = plastic strain rate $\dot{\varepsilon}_{p,eq}$ (default); `1.0` = total equivalent strain rate $\sqrt{\frac{2}{3}\dot{E}':\dot{E}'}$ |
| `props(16)` | $G_f$ | J/m$^2$ | Matrix fracture energy per unit area (matrix: 1460.0 J/m$^2$) |
| `props(17)` | $RESSTIFF$ | - | Residual stiffness fraction at $D=1.0$ (default: 0.0) |
| `props(18)` | $NYTAB$ | - | Number of points in yield stress table ($1 \le NYTAB \le 5$, matrix: 1) |
| `props(19)` | $NETAB$ | - | Number of points in fracture strain table ($1 \le NETAB \le 5$, matrix: 1) |
| **Yield Stress Table (pairs 1..5)** | | | |
| `props(20), props(21)` | $\dot{\varepsilon}_{y,1}, \sigma_{y,1}$ | s$^{-1}$, Pa | Rate point 1 (matrix: 0.01 s$^{-1}$, 70.0e6 Pa) |
| `props(22), props(23)` | $\dot{\varepsilon}_{y,2}, \sigma_{y,2}$ | s$^{-1}$, Pa | Rate point 2 (unused slots set to 0.0) |
| `props(24), props(25)` | $\dot{\varepsilon}_{y,3}, \sigma_{y,3}$ | s$^{-1}$, Pa | Rate point 3 |
| `props(26), props(27)` | $\dot{\varepsilon}_{y,4}, \sigma_{y,4}$ | s$^{-1}$, Pa | Rate point 4 |
| `props(28), props(29)` | $\dot{\varepsilon}_{y,5}, \sigma_{y,5}$ | s$^{-1}$, Pa | Rate point 5 |
| **Fracture Strain Table (pairs 1..5)** | | | |
| `props(30), props(31)` | $\dot{\varepsilon}_{f,1}, \varepsilon_{f,1}$ | s$^{-1}$, - | Rate point 1 (matrix: 0.01 s$^{-1}$, 0.10) |
| `props(32), props(33)` | $\dot{\varepsilon}_{f,2}, \varepsilon_{f,2}$ | s$^{-1}$, - | Rate point 2 |
| `props(34), props(35)` | $\dot{\varepsilon}_{f,3}, \varepsilon_{f,3}$ | s$^{-1}$, - | Rate point 3 |
| `props(36), props(37)` | $\dot{\varepsilon}_{f,4}, \varepsilon_{f,4}$ | s$^{-1}$, - | Rate point 4 |
| `props(38), props(39)` | $\dot{\varepsilon}_{f,5}, \varepsilon_{f,5}$ | s$^{-1}$, - | Rate point 5 |

*Note on Abaqus Keyword Formatting:*
Abaqus/Explicit requires at most 8 values per data line under `*UEL Property`. The 39 props are emitted as 4 lines of 8 values and 1 line of 7 values.

---

## 3. State Variables Layout (`svars`)

The element allocates 159 state variables (`nsvars = 159`):

### 3.1 Legacy & Base State (svars 1 to 107)
- `svars(1:48)`: 2nd Piola-Kirchhoff stress components at Gauss points 1 to 8 (6 per GP: $S_{11}, S_{22}, S_{33}, S_{12}, S_{13}, S_{23}$).
- `svars(49)`: Element failure flag: `0.0` = intact, `1.0` = dead/eroded.
- `svars(50:105)`: Plastic strain state at Gauss points 1 to 8 (7 per GP: $E_{p,11}, E_{p,22}, E_{p,33}, 2E_{p,12}, 2E_{p,13}, 2E_{p,23}$, and accumulated $PEEQ$).
- `svars(106)`: Element damage variable $D_{elem} = \max_k(D_k) \in [0, 1]$.
- `svars(107)`: Fiber volume fraction $V_f$ initialized via `*Initial Conditions, TYPE=SOLUTION`. Effective matrix volume scaling $\eta = \max(1 - V_f, 10^{-6})$.

### 3.2 Per-Gauss-Point Ductile Damage Variables (svars 108 to 155)
For each Gauss point $k \in \{1, \dots, 8\}$, variables occupy offset $base = 107 + (k - 1) \times 6$:
- `svars(base + 1)`: $PEEQ_k$ (accumulated equivalent plastic strain).
- `svars(base + 2)`: $PEEQ_{onset,k}$ (equivalent plastic strain at damage onset, frozen during softening).
- `svars(base + 3)`: $D_k$ (Gauss point damage fraction $\in [0, 1]$).
- `svars(base + 4)`: $\sigma_{y0,k}$ (yield stress at damage onset, frozen during softening).
- `svars(base + 5)`: $\dot{\varepsilon}_{onset,k}$ (effective strain rate at damage onset, frozen during softening).
- `svars(base + 6)`: $STATUS_k$ (GP lifecycle flag: `0.0` = elastic, `1.0` = plastic pre-damage, `2.0` = softening, `3.0` = failed $D=1$).

### 3.3 Element-Level Summary Variables (svars 156 to 159)
- `svars(156)`: $D_{max} = \max_{k=1..8} D_k$ (peak Gauss-point damage).
- `svars(157)`: $D_{avg} = \frac{1}{8}\sum_{k=1}^8 D_k$ (mean Gauss-point damage).
- `svars(158)`: $ELEM\_STATUS$ (`0.0` = intact, `1.0` = partially softened, `2.0` = fully failed).
- `svars(159)`: $W_{dmd,elem}$ (accumulated damage dissipation energy for this element [J]).

---

## 4. Constitutive Equations & Damage Evolution

### 4.1 Total Lagrangian Elastic-Plastic Formulation
Green-Lagrange strain tensor $E = \frac{1}{2}(F^T F - I)$ in engineering Voigt order $[E_{11}, E_{22}, E_{33}, 2E_{12}, 2E_{13}, 2E_{23}]$.
1. Elastic trial state:
   $$E_e^{trial} = E - E_p^{old}$$
   $$S^{trial} = K \text{tr}(E_e^{trial}) I + 2\mu \text{dev}(E_e^{trial})$$
   $$\sigma_{vm}^{trial} = \sqrt{\frac{3}{2} S'_{trial} : S'_{trial}}$$

2. Rate-dependent yield stress $\sigma_y(\dot{\varepsilon})$:
   Interpolated linearly in $\log_{10}(\text{rate})$ from the props table:
   $$u = \frac{\log_{10}(r) - \log_{10}(r_i)}{\log_{10}(r_{i+1}) - \log_{10}(r_i)}$$
   $$\sigma_y = \sigma_{y,i} + u (\sigma_{y,i+1} - \sigma_{y,i})$$
   Clamped to end values outside $[r_1, r_{N}]$; floor $r_{min} = 10^{-12}\text{ s}^{-1}$.

3. Radial return (associative, no hardening):
   If $\sigma_{vm}^{trial} > \sigma_y$:
   $$\Delta \gamma = \frac{\sigma_{vm}^{trial} - \sigma_y}{3\mu}$$
   $$PEEQ^{new} = PEEQ^{old} + \Delta \gamma$$
   $$\Delta E_p = \Delta \gamma \frac{3}{2\sigma_{vm}^{trial}} S'_{trial}$$
   $$S_{undamaged} = p^{trial} I + \frac{\sigma_y}{\sigma_{vm}^{trial}} S'_{trial}$$

### 4.2 Damage Initiation & Softening
1. Onset criterion:
   Initiates at GP $k$ when $PEEQ_k \ge \varepsilon_f(\dot{\varepsilon})$.
   At initiation, $\sigma_{y0} = \sigma_y$ and $\dot{\varepsilon}_{onset} = \dot{\varepsilon}$ are recorded and frozen.

2. Characteristic length $L$:
   $$L = (V_{0,eff})^{1/3} = (\eta V_{0,geom})^{1/3}$$
   *Justification:* The fracture energy $G_f$ is defined per unit area of matrix crack. In an element with embedded fibers ($V_f > 0$), the physical volume of host matrix is scaled by $\eta = 1 - V_f$. Using the effective reference volume ensures mesh objectivity and consistent energy dissipation per unit crack area.

3. Failure displacement and softening:
   $$\bar{u}_f = \frac{2 G_f}{\sigma_{y0}}$$
   $$\bar{u} = L (PEEQ - PEEQ_{onset})$$
   $$D = \min\left(1.0, \max\left(D^{old}, \frac{\bar{u}}{\bar{u}_f}\right)\right)$$

4. Stress scaling:
   $$S = (1 - D) S_{undamaged}$$
   When $D = 1.0$, $S = 0$ (or $RESSTIFF \times S_{undamaged}$ if specified).

### 4.3 Element Failure Latch & Dead Sentinel
- Gauss-point damage operates independently at each GP.
- When **all 8 Gauss points** reach $D_k \ge 1.0 - 10^{-6}$, the element is fully softened and the failure latch trips:
  `svars(49) = 1.0`, `svars(158) = 2.0`.
- *Justification:* Waiting for all Gauss points to reach $D=1$ prevents premature element deactivation under non-uniform stress gradients (bending/shear) where other integration points still retain load-carrying capacity. In single-element affine testing, all 8 Gauss points reach $D=1$ simultaneously.
- Once failed, the element is made numerically inert:
  $\text{rhs} = 0$, and `dtimeStable(KBLOCK) = 1.0D30` (dead sentinel path).

---

## 5. Energy Array Partitioning & Consistency

The VUEL updates the Abaqus element energy array `energy(nblock, 12)`:

| Energy Slot | Parameter | Abaqus Output | Accumulation Rule |
|---|---|---|---|
| Slot 1 | `iElPd` | `ALLPD` | Plastic work before onset: $\Delta W_p = \sigma_y \Delta \gamma \times dV_{eff}$ |
| Slot 3 | `iElIe` | `ALLIE` | Damaged elastic strain energy: $\frac{1}{2} (1 - D_k) S_{undamaged} : E_e \times dV_{eff}$ |
| Slot 5 | `iElDd` | `ALLVD` / `ALLDD` | Damping dissipation: $\beta C : \dot{E} : \dot{E} \times dV_{geom} \Delta t$ |
| Slot 6 | `iElBv` | `ALLBV` | Bulk viscosity dissipation |
| Slot 9 | `iElKe` | `ALLKE` | Kinetic energy: $\frac{1}{2} M_{eff} v^2$ |
| Slot 11 | `iElDmd` | `ALLDMD` | Damage dissipation during softening: $\frac{G_f}{L} \Delta D \times dV_{eff}$ |

### 5.1 Verification of Dissipated Energy
Under monotonic uniaxial tension to complete softening ($D=1$):
- Pre-onset plastic work per unit volume:
  $$W_p = \sigma_y \varepsilon_f = 70\times 10^6 \times 0.10 = 7.0\times 10^6\text{ J/m}^3$$
- Damage softening work per unit volume:
  $$W_{dmd} = \frac{G_f}{L} = \frac{1460}{1.0} = 1460\text{ J/m}^3$$
- Total dissipated energy ($ALLPD + ALLDMD$):
  $$W_{total} = 7,001,460\text{ J/m}^3$$
For a unit cube ($V=1\text{ m}^3$): Total energy = $7.001460\text{ MJ}$.

---

## 6. Stable Time Increment & Embedded Fibers Note for the Hub

In `uel/VUEL_material.for`, the dilatational wave speed is calculated from the intact matrix material constants:
$$c_{matrix} = \sqrt{\frac{\lambda + 2\mu}{\rho}} = \sqrt{\frac{2.6552\times 10^9}{980}} \approx 1646\text{ m/s}$$
$$\Delta t_{elem} = 0.8 \frac{2}{\omega_{max}} (\sqrt{1 + \xi^2} - \xi) \approx 4.8\times 10^{-4}\text{ s}\quad (L = 1\text{ m})$$

### Embedded Fibers Interaction:
- Embedded fibers ($E = 135\text{ GPa}$, $\rho = 981\text{ kg/m}^3$) are modeled as native Abaqus truss (T3D2) or beam (B31) elements.
- Wave speed in the fibers: $c_{fiber} = \sqrt{E/\rho} \approx 11,730\text{ m/s}$.
- Native elements enforce their own stable time increment inside Abaqus/Explicit:
  $$\Delta t_{global} = \min(\Delta t_{VUEL}, \min_{fibers} \Delta t_{fiber})$$
- **The VUEL does NOT need fiber $E$ to compute its own $\Delta t$**, because the host element's internal equations only govern the matrix mass and stiffness. The Abaqus solver automatically enforces the minimum stable time increment across all active elements.
- When the VUEL element fails ($D=1$), `dtimeStable` returns the sentinel `1.0D30`, ensuring that an eroded matrix element never caps the solver increment.
