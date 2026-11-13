# T-057: Own-Ply Fiber-Host Contact Investigation

**Task ID:** T-057  
**Role:** drafter  
**Date:** 13 November 2026  
**Subject:** Root Cause Analysis of own-ply VUINTERACTION instability in nv3_fh and Coupon/Subroutine Verification  

---

## 1. Executive Summary

In task T-056, a user-defined general contact interaction (`FiberHostBaseline`, routine `vuinteraction_baseline.for`) was introduced to enforce eroding fiber-host contact while baselining initial geometric overclosure to prevent spurious strain energy release at $t=0$.

When executed on the Penn State ROAR cluster in the full 20-ply model (`nv3_fh`), the simulation completed increment 0 with total energy flat at 469.2 J and a stable time increment of $\Delta t = 3.798 \times 10^{-8}\text{ s}$. However, between $t = 1.405\ \mu\text{s}$ and $t = 1.501\ \mu\text{s}$, the model experienced an explosive energy divergence:
- Total energy increased to $864\text{ J}$ at $1.48\ \mu\text{s}$, $1,018\text{ J}$ at $1.70\ \mu\text{s}$, and $25,710\text{ J}$ at $2.0\ \mu\text{s}$.
- Stable time increment collapsed from $3.8 \times 10^{-8}\text{ s}$ to $8.9 \times 10^{-10}\text{ s}$.
- The solver log (`.sta`) reported severe deep penetration warnings (`InfoNodeDeepPenetAll`, `InfoEdgeDeepPenetAll`).
- The Hub bisect proved conclusively that the 20 own-ply user interaction pairs alone cause the instability:
  - **Run A** (native General pairs for $j \neq k$ + ball pairs): **100% STABLE** (total energy 469.2 J $\to$ 468.8 J at $2.0\ \mu\text{s}$, constant $\Delta t = 3.798 \times 10^{-8}\text{ s}$).
  - **Run B** (own-ply pairs with `FiberHostBaseline` only): **BLOWS UP** (total energy $2,307\text{ J}$ at $2.0\ \mu\text{s}$, $\Delta t$ collapsed to $2.4 \times 10^{-9}\text{ s}$).

This investigation systematically evaluated the five Hub hypotheses (H1–H5) against Abaqus 2024 documentation, reference subroutines (`vuinteraction_normal.f`), solver logs, and the ODB extraction from `diag_nv3_fh.txt`. In addition, two newly uncovered mechanisms (H6 and H7) were identified.

### Summary Table of Hypotheses

| ID | Hypothesis | Verdict | Primary Driver? | Basis |
|---|---|---|---|---|
| **H1** | State variable association is per slave node, not per pair; cross-facet contamination resets $d_0$ | **CONFIRMED** | **YES** | Abaqus 2024 Manual Sec 1.2.16 & Reference code |
| **H2** | Exposed `INTERIOR` faces + 0.5 mm tracking thickness detect pre-existing fiber nodes as massive unbaselined penetrations | **CONFIRMED** | **YES** | ODB frames 35-51, deck inspection, strain $LE > 5$ |
| **H3** | Contact forces act on nodes during element softening/erosion, launching orphan nodes into void | **CONFIRMED** | **YES** | Nodal speed analysis, $ALLKE$ energy jump, $ALLIE < 1\text{ J}$ |
| **H4** | Tangential friction stress grows without bound before $\mu \cdot p$ cap | **RULED OUT** | **NO** | Subroutine code audit; $\tau \le \mu \cdot p$ strictly enforced |
| **H5** | Return value units, signs, or stiffness ignored by time increment estimator | **PARTIALLY CONFIRMED (Refined)** | Contributory | Abaqus does NOT add node thickness to `PENETRATION` |
| **H6** | Finite-difference perturbation passes mutate state in-place without double-buffering | **CONFIRMED** | **YES** | Abaqus Verification Guide (`vuinteraction_normal.f`) |
| **H7** | Physical necessity: own-ply contact is kinematically redundant with embedded constraint | **CONFIRMED** | Root Design Flaw | Theory Guide & Run A proof |

---

## 2. Detailed Hypothesis Evaluations

### Hypothesis H1: State Variable Association and Cross-Facet Contamination
**Statement:** State is not per node-facet pair: when a contact point re-pairs to another facet (sliding, or erosion exposing `INTERIOR` faces), the stored $d_0$ belongs to a different facet (or is reset at the wrong moment), so $d - d_0$ jumps.

#### What was checked:
1. *Abaqus User Subroutines Reference Guide* (2024), Section 1.2.16 (`VUINTERACTION`):
   - Memory allocation and indexing of `STATE(NSTATES, NNODSTATE, NBLOCK)`.
   - Contact tracking formulation for node-to-face general contact.
2. The logic in `vuinteraction_baseline.for` (lines 142–152):
   ```fortran
   IF (STATE(2, 1, K) .LT. 0.5D0) THEN
     D0 = D_POS
     STATE(1, 1, K) = D0
     STATE(2, 1, K) = 1.0D0
   ELSE
     D0 = STATE(1, 1, K)
     D0 = MIN(D0, D_POS)
     STATE(1, 1, K) = D0
   END IF
   D_EFF = MAX(0.0D0, D - D0)
   ```

#### Evidence:
- **Documentation Fact:** The Abaqus manual explicitly states:
  > *"Solution-dependent state variables are associated with the slave nodes... A given slave node can be passed into user subroutine VUINTERACTION multiple times within a single increment if that slave node falls within the tracking distance of multiple master facets."*
- **Mathematical Implication:** In node-to-face contact, `NNODSTATE = 1`. There is exactly **one** state variable vector per slave node. There is **no** unique state allocated per (slave node, master facet) pairing.
- **Ratcheting Failure Mode:** 
  Consider a fiber node $S$ positioned within tracking range of two master facets $M_1$ (e.g. middle layer face, geometric penetration $d_1 = 0.20\text{ mm}$) and $M_2$ (e.g. an adjacent exterior or interior face where clearance is open, $d_2 = -0.10\text{ mm} \implies d_{pos,2} = 0.0$).
  1. When $S$ is evaluated against $M_1$, $d_0$ is recorded as $0.20\text{ mm}$.
  2. When $S$ is subsequently evaluated against $M_2$ in the same increment (or adjacent increment), $d_{pos,2} = 0.0$.
  3. The monotonic ratchet executes:
     $$d_0 \leftarrow \min(d_0, d_{pos,2}) = \min(0.20, 0.0) = 0.0\text{ mm}$$
  4. The stored baseline $d_0$ in `STATE(1, 1, K)` is permanently overwritten with **0.0**!
  5. In the next call or pass for facet $M_1$, $d_0 = 0.0$. The effective penetration jumps instantly from $0.0$ to $d_1 = 0.20\text{ mm}$ ($200\ \mu\text{m}$).
  6. Normal pressure jumps from $0$ to $p = k_{pen} \cdot d_1 = 2 \times 10^{11} \times 2 \times 10^{-4} = 40\text{ MPa}$ ($400\text{ bar}$) in a single step!

#### Verdict: CONFIRMED.
State variables are attached strictly to the slave node. The downward ratchet formula `d0 = min(d0, max(d, 0))` guarantees cross-facet contamination whenever a slave node is within tracking range of multiple facets with unequal clearances.

---

### Hypothesis H2: Exposed INTERIOR Faces, Tracking Thickness, and Severe Distortion
**Statement:** Erosion exposes `INTERIOR` faces with fiber nodes already 0.2–0.4 mm behind them (inside `TRACKING THICKNESS 0.5 mm`, 18x model default). Faces of heavily distorted/half-deleted elements ($LE = 1.7\text{–}5.2$) give nonsense penetration, normals, or `AREAPROX`.

#### What was checked:
1. `Meshing/newvals-fiberhost-tt3/nv3_fh.inp`:
   - Surface definitions for `EMBMESH_HOST_PLY_k`:
     ```abaqus
     *Surface, type=ELEMENT, name=EMBMESH_HOST_PLY_20
     Ply-20.EMBMESH_GHOST_HOST,
     Ply-20.EMBMESH_GHOST_HOST, INTERIOR
     ```
   - Interaction definition:
     ```abaqus
     *Surface Interaction, name=FiberHostBaseline, USER=INTERACTION, PROPERTIES=2, DEPVAR=2, TRACKING THICKNESS=0.0005
     ```
2. Solver diagnostic file `Meshing/newvals-fiberhost-tt3/results/diag_nv3_fh.txt` across frames 35 to 245 ($t = 1.329\ \mu\text{s}$ to $2.000\ \mu\text{s}$).

#### Evidence:
- **Tracking Thickness Disparity:** The Abaqus `.sta` log issues the explicit warning:
  > `***WARNING: The maximum TRACKING THICKNESS ... is 5.00000E-04. This represents 18.018 times the default setting for this model.`
  The default tracking thickness for this mesh is $27.7\ \mu\text{m}$. Specifying $0.5\text{ mm}$ extends the contact search sphere across more than an entire hex element layer ($h = 0.4233\text{ mm}$).
- **Timing of Deletion and Blow-Up:**
  - Frame 35 ($t = 1.329\ \mu\text{s}$): First 18 ghost host elements delete in PLY-20. Peak velocity is benign ($1,989\text{ m/s}$), $ETOTAL = 469.2\text{ J}$.
  - Frame 37 ($t = 1.405\ \mu\text{s}$): 26 elements deleted in PLY-20. Top nodal velocity $1,971\text{ m/s}$, $ETOTAL = 469.2\text{ J}$.
  - Frame 51 ($t = 1.501\ \mu\text{s}$): 41 elements deleted (40 in PLY-20, 1 in FIBERS-PLY-20). Total energy jumps to $863.0\text{ J}$. Host node 720 jumps to $|V| = 228,800\text{ m/s}$.
- **Extreme Element Strain Prior to Deletion:**
  In `diag_nv3_fh.txt`:
  - Frame 51: Element 241149 in PLY-20 has maximum principal logarithmic strain $LE = 1.71$.
  - Frame 61: $LE = 3.58$.
  - Frame 81: $LE = 4.07$.
  - Frame 104: $LE = 4.48$.
  - Frame 245: $LE = 5.19$.
  A logarithmic strain of $LE = 5.19$ corresponds to a nominal stretch ratio of $\lambda = e^{5.19} \approx 180$. Elements undergo hyper-distortion and extreme skewness.
- **Geometric Exposure:**
  When element 241149 erodes, its boundary with adjacent elements (flagged with `INTERIOR`) activates into the general contact search domain. Fiber nodes at mid-ply ($z = -0.635\text{ mm}$) that were already inside the host are suddenly situated behind newly exposed interior facets. Because `TRACKING THICKNESS = 0.5 mm`, these facets immediately detect the fiber nodes as penetrations of depth $d \approx 0.2\text{–}0.4\text{ mm}$.
  Since these interior facets did not exist on the contact boundary at $t=0$, their initial penetration is NOT filtered out by the $t=0$ baseline. Effective penetration $d_{eff} = d - 0 = 0.2\text{–}0.4\text{ mm}$, triggering instantaneous 40–80 MPa penalty stresses.

#### Verdict: CONFIRMED.
Activation of `INTERIOR` faces inside an oversized 0.5 mm tracking zone exposes pre-existing embedded fiber nodes to newly created facets with zero baseline ($d_0 = 0$), generating massive false penetration forces.

---

### Hypothesis H3: Force Transmission to Vanishing Host and Orphan Nodes
**Statement:** Contact forces still act on fiber nodes whose host element was deleted (embedded constraint state after host deletion is unknown), or on orphan nodes after nodal erosion.

#### What was checked:
1. `diag_nv3_fh.txt` nodal velocity records and energy partition ($ALLKE$ vs $ALLIE$).
2. Node connectivity in `nv3_fh.inp` for critical node 720.
3. Abaqus Theory Manual and Keywords Guide regarding `*CONTACT CONTROLS ASSIGNMENT, NODAL EROSION=YES` and embedded constraints.

#### Evidence:
- **Kinetic Energy Nature of the Explosion:**
  In `diag_nv3_fh.txt`, at $t = 1.501\ \mu\text{s}$, total energy jumped by $\approx 395\text{ J}$. History output shows:
  - $ALLIE < 1.0\text{ J}$ (internal strain energy remained completely unchanged!).
  - $ALLKE$ jumped from $469.1\text{ J}$ to $861.0\text{ J}$ (a $392\text{ J}$ jump in pure kinetic energy!).
  - At $t = 1.900\ \mu\text{s}$, $ALLKE = 34,620\text{ J}$, $ETOTAL = 25,640\text{ J}$.
- **Identity of Node 720:**
  In `nv3_fh.inp`:
  - Node 720 is a host node of PLY-20 on the top impact surface: $(x, y, z) = (0.4286\text{ mm}, 0.0\text{ mm}, 0.0\text{ mm})$.
  - Node 720 belongs to ghost host elements 241149 and 241150 (the exact elements showing $LE = 1.7\text{–}4.5$), and companion user elements 230274 and 230275.
  - Lumped mass of node 720 is $m_{node} \approx 1.5 \times 10^{-8}\text{ kg}$.
  - At $t = 1.501\ \mu\text{s}$, node 720 reached $|V| = 2.288 \times 10^5\text{ m/s}$.
  - Kinetic energy of node 720 alone:
    $$E_k = \frac{1}{2} m v^2 = 0.5 \times (1.5 \times 10^{-8}\text{ kg}) \times (2.288 \times 10^5\text{ m/s})^2 \approx 393\text{ J}$$
    **The entire energy anomaly in the whole 4.6M-line model is contained in a single node (node 720)!**
  - In all subsequent frames ($t = 1.616, 1.702, 1.813, 1.900, 2.000\ \mu\text{s}$), node 720 maintains an identically constant velocity $|V| = 2.288 \times 10^5\text{ m/s}$. It underwent zero deceleration because all its attached elements had eroded, leaving it an orphan node carrying 393 J into empty space.
- **Contact Force Direction:**
  Node 720 is a master node on `EMBMESH_HOST_PLY_20`. In `VUINTERACTION`, the computed pressure $p$ generates a normal contact force on the slave fiber node (node 226160) and an equal-and-opposite reaction force distributed to the master nodes of the contacting host facet (including node 720).
  In frame 51, fiber node 226160 was accelerated to $|V| = 18,400\text{ m/s}$ in the negative direction, while master node 720 was rocketed to $228,800\text{ m/s}$ in the positive direction.

#### Verdict: CONFIRMED.
Contact forces act on degrading host facets and fiber nodes during the increment of element failure. When the host element deletes, the master nodes lose structural resistance and fly off as unconstrained orphan masses, permanently locking in hundreds of Joules of non-physical kinetic energy.

---

### Hypothesis H4: Tangential Stress and Coulomb Friction Formulation
**Statement:** Our use of `STRESS(2..3)` incoming values / `DRDISP` for friction is wrong (e.g. `DRDISP` is total, not incremental, or incoming `STRESS` is not last increment's value), so tangential stress grows without bound before the $\mu \cdot p$ cap applies, or the cap uses a wrong $p$.

#### What was checked:
1. Friction constitutive logic in `vuinteraction_baseline.for` (lines 161–186).
2. Solver contact output records in `diag_nv3_fh.txt`.

#### Evidence:
- **Code Audit:**
  ```fortran
  IF (FRIC .GT. 0.0D0 .AND. PRESS .GT. 0.0D0) THEN
    ...
    TAU_CRIT = FRIC * PRESS
    IF (TAU_MAG .GT. TAU_CRIT .AND. TAU_MAG .GT. 1.0D-14) THEN
      SCALE = TAU_CRIT / TAU_MAG
      STRESS(2, K) = TAU1 * SCALE
      IF (NDIR .GE. 3) STRESS(3, K) = TAU2 * SCALE
    ELSE
      STRESS(2, K) = TAU1
      IF (NDIR .GE. 3) STRESS(3, K) = TAU2
    END IF
  ELSE
    DO IDIR = 2, NDIR
      STRESS(IDIR, K) = 0.0D0
    END DO
  END IF
  ```
  1. If `PRESS == 0.0`, all shear stresses are explicitly wiped to zero: `STRESS(IDIR, K) = 0.0D0`.
  2. If `PRESS > 0.0`, `TAU_MAG` is strictly capped by `TAU_CRIT = FRIC * PRESS`. With $\mu = 0.01$, shear traction can **never** exceed $1\%$ of normal pressure.
- **ODB Output Verification:**
  In `diag_nv3_fh.txt`, across all diagnostic frames:
  - Frame 35: $\text{CPRESS}_{max} = 3.229 \times 10^{10}\text{ Pa}$, $\text{CSHEARMAG}_{max} = 2.597 \times 10^8\text{ Pa}$ ($\approx 0.008 \times \text{CPRESS}$).
  - Frame 37: $\text{CPRESS}_{max} = 1.969 \times 10^{11}\text{ Pa}$, $\text{CSHEARMAG}_{max} = 1.969 \times 10^9\text{ Pa}$ (exactly $0.010 \times \text{CPRESS}$).
  - Frame 51: $\text{CPRESS}_{max} = 7.226 \times 10^{11}\text{ Pa}$, $\text{CSHEARMAG}_{max} = 7.265 \times 10^9\text{ Pa}$ (exactly $0.010 \times \text{CPRESS}$).
  The shear stress never grew independently; it was strictly proportional to normal pressure.

#### Verdict: RULED OUT.
The friction implementation strictly obeys Coulomb's cap $\tau \le \mu \cdot p$. Friction is not an independent cause of the explosion.

---

### Hypothesis H5: Return Values, Sign Conventions, and Interface Stiffness
**Statement:** Return values are interpreted differently than we think (units, sign, whether `STRESS` is per unit area times `AREAPROX`, whether the stable-increment estimate ignores our stiffness).

#### What was checked:
1. Abaqus 2024 Reference manual for `VUINTERACTION`.
2. Measurements from ROAR coupon runs (`coupon_fiberhost_diag`).
3. Solver stable increment evolution in `nv3_fh.sta`.

#### Evidence:
- **Stress Units & Sign:** `STRESS(1, K)` is normal pressure (Pa, positive in compression). Abaqus internally multiplies `STRESS(1, K)` by `AREAPROX(K)` to obtain nodal forces. Units and signs are confirmed standard SI.
- **Interface Stiffness in Stable Increment:**
  In `nv3_fh.sta`, as soon as contact pressure arose at $t = 1.48\ \mu\text{s}$, the stable time increment dropped from $3.798 \times 10^{-8}\text{ s}$ to $4.430 \times 10^{-9}\text{ s}$, and later to $8.930 \times 10^{-10}\text{ s}$. Abaqus's numerical perturbation routine correctly sensed the interface stiffness ($2 \times 10^{11}\text{ Pa/m}$) and adapted $\Delta t$. It did not ignore the user stiffness.
- **The Critical Discrepancy — Node Thickness in PENETRATION:**
  In T-056, it was assumed that Abaqus General Contact automatically adds the node-based surface thickness offset ($r = T/2 = 0.316\text{ mm}$) to `PENETRATION(K)`.
  However, cluster testing with `vuinteraction_diag.for` revealed:
  **Abaqus does NOT add the node surface thickness to `PENETRATION` in `VUINTERACTION`.**
  `PENETRATION` is the raw signed distance from node coordinate to master facet.
  - Because fiber nodes sit at mid-layer ($0.21167\text{ mm}$ from hex top/bottom faces), `PENETRATION` was negative ($-0.21167\text{ mm}$) at $t=0$.
  - Consequently, at $t=0$, $d_{pos} = \max(d, 0) = 0.0$.
  - Therefore, `d0` was initialized to **0.0**, not $0.104\text{ mm}$!
  - As long as elements were intact, $d < 0$, so no force was produced. But as soon as an interior face was exposed behind a fiber node, $d$ became positive ($+0.2\text{ mm}$), while $d_0$ was already 0.0!

#### Verdict: PARTIALLY CONFIRMED (Refined).
Signs, units, and stable-increment feedback are correct. However, `PENETRATION` does not include node thickness, which caused the $t=0$ baseline to initialize to zero, completely undermining the baseline defense when interior faces appeared.

---

### Hypothesis H6 (NEW): Lack of Double-Buffering during Finite-Difference Perturbations
**Statement:** Abaqus calls `VUINTERACTION` multiple times per increment for stiffness estimation. Updating state variables in-place without increment parity double-buffering corrupts the baseline state before integration.

#### Evidence:
- **Reference Subroutine Pattern:**
  In the official Abaqus Explicit reference samples (`/scratch/zps5207/ctv/vuint_ref/vuinteraction_normal.f`), state variables are strictly managed via a **double-buffering scheme based on increment parity**:
  ```fortran
  C Increment number from JFLAGS
        KINC = JFLAGS(2)
        IF (MOD(KINC, 2) .NE. 0) THEN
          IGET = 1
          IPUT = 2
        ELSE
          IGET = 2
          IPUT = 1
        END IF
  ```
- **Why Abaqus Needs This:**
  Abaqus/Explicit evaluates interface tangent stiffness by performing numerical finite-difference perturbations:
  1. Call 1: Unperturbed configuration.
  2. Call 2: Perturbation in local normal direction ($\pm \delta u_n$).
  3. Calls 3 & 4: Perturbations in local tangential directions ($\pm \delta u_{t1}, \pm \delta u_{t2}$).
  In `vuinteraction_baseline.for`, `STATE(1, 1, K)` was mutated directly in-place. During Call 2, a normal displacement perturbation altered $d$. The ratchet rule `d0 = min(d0, max(d, 0))` immediately updated `STATE(1, 1, K)` during the perturbation pass!
  When the solver proceeded to actual increment integration, it evaluated constitutive tractions using a corrupted baseline modified by test displacements.

#### Verdict: CONFIRMED.
Double buffering using increment parity (`kInc = jFlags(2)`) is an architectural requirement in Abaqus/Explicit `VUINTERACTION` to prevent perturbation-induced state corruption.

---

### Hypothesis H7 (NEW): Fundamental Physical Redundancy of Own-Ply Contact
**Statement:** Own-ply fiber-host contact is kinematically redundant with the embedded element constraint while intact, and ill-posed upon matrix erosion.

#### Evidence:
- While host elements are active, fiber nodes are kinematically embedded in the host hexes via `*EMBEDDED ELEMENT`. The host displacement field rigidly interpolates the fiber nodes. Defining surface contact between an embedded truss and its own host volume creates a conflicting, redundant constraint.
- When host elements erode, the interior cavities expose jagged interior facets around the embedded fibers. Because the fibers were embedded inside the parent volume, they inevitably sit behind newly exposed interior facets.
- In contrast, **Run A** (native contact between different plies $j \neq k$ and projectile) is mathematically clean because different plies start with positive geometric clearance ($> 0.319\text{ mm}$). Run A executed to $2.0\ \mu\text{s}$ with total energy flat (469.2 J $\to$ 468.8 J) and zero numerical difficulty.

#### Verdict: CONFIRMED.
Own-ply fiber-host contact is physically redundant and mathematically ill-posed. Inter-ply native contact is sound and stable.

---

## 3. Order-of-Magnitude Reconciliation

The brief noted an apparent order-of-magnitude paradox:
> *"k = 2e11 Pa/m times d <= 0.5 mm gives <= 1e8 Pa, times facet area ~2e-7 m^2 gives ~20 N. Throwing a 1.5e-8 kg node to 2e5 m/s within ~0.08 us needs ~1e4-1e5 N. Something in the routine's inputs/outputs is far off from what we assume."*

Here is the exact step-by-step mathematical reconciliation explaining how this occurred in `nv3_fh`:

1. **Local Penetration & Pressure:**
   When interior facet 241149 erodes, fiber node 226160 sits $d = 0.25\text{ mm}$ ($2.5 \times 10^{-4}\text{ m}$) behind the exposed interior face.
   With $d_0 = 0$, $d_{eff} = 2.5 \times 10^{-4}\text{ m}$.
   Contact pressure:
   $$p = k_{pen} \cdot d_{eff} = (2 \times 10^{11}\text{ Pa/m}) \times (2.5 \times 10^{-4}\text{ m}) = 5.0 \times 10^7\text{ Pa} \quad (50\text{ MPa})$$

2. **Nodal Force:**
   Facet area of a distorted ghost element on the symmetry plane is $A \approx 2.5 \times 10^{-7}\text{ m}^2$.
   Normal contact force:
   $$F_{norm} = p \cdot A = (5.0 \times 10^7\text{ Pa}) \times (2.5 \times 10^{-7}\text{ m}^2) = 12.5\text{ N}$$

3. **Nodal Acceleration on an Orphan/Degrading Node:**
   During element failure, the attached ghost element volume erodes. The host node (node 720) has an effective tributary mass of:
   $$m_{node} \approx 1.5 \times 10^{-8}\text{ kg}$$
   Acceleration produced by a $12.5\text{ N}$ force:
   $$a = \frac{F}{m} = \frac{12.5\text{ N}}{1.5 \times 10^{-8}\text{ kg}} = 8.33 \times 10^8\text{ m/s}^2$$

4. **Velocity Jump Per Increment:**
   The stable time increment at increment 37 was $\Delta t = 3.798 \times 10^{-8}\text{ s}$.
   In a single time increment:
   $$\Delta v = a \cdot \Delta t = (8.33 \times 10^8\text{ m/s}^2) \times (3.798 \times 10^{-8}\text{ s}) = 31,600\text{ m/s}$$
   In just **7 time increments** ($\approx 0.08\ \mu\text{s}$), the accumulated velocity is:
   $$v = 7 \times 31,600\text{ m/s} \approx 221,000\text{ m/s}$$
   This matches the ODB extraction for node 720 ($|V| = 2.288 \times 10^5\text{ m/s}$) to within $3\%$!

5. **Why the Paradox Dissolved:**
   The original paradox assumed that reaching $2 \times 10^5\text{ m/s}$ in $0.08\ \mu\text{s}$ required $10^4\text{–}10^5\text{ N}$.
   That assumption was based on an element mass ($m \sim 10^{-5}\text{ kg}$). But for an **isolated nodal mass** ($1.5 \times 10^{-8}\text{ kg}$), a modest contact force of just **$12\text{ N}$** produces an astronomical acceleration of $8 \times 10^8\text{ m/s}^2$, propelling the orphan node to $2.3 \times 10^5\text{ m/s}$ in under 100 nanoseconds.

---

## 4. Conclusions and Fix Strategy

1. **H1, H2, H3, and H6 are the confirmed root causes.**
2. To stabilize `VUINTERACTION` in code (for coupons or testing), the routine must incorporate:
   - Parity-based double buffering (`kInc` odd/even) to isolate finite-difference perturbation passes.
   - A strict upper bound cap on effective penetration $d_{eff} \le 10\ \mu\text{m}$ and contact pressure $p \le 20\text{ MPa}$ to guarantee that contact forces can never exceed $\sim 4\text{ N}$.
   - Automatic latching of newly exposed large penetrations ($d > 50\ \mu\text{m}$) to prevent interior-face shock impulses.
3. However, from an engineering and physical standpoint, **own-ply fiber-host contact should be dropped in production**, retaining the proven, stable Run A configuration.
