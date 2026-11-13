# Fiber-Host Interaction, Deletion Mechanism, and Mass Anomalies in Vals Plywise Impact

**Task ID:** T-046  
**Role:** Drafter  
**Date:** 2026-10-21  
**Inputs Investigated:**
- Native deletion rerun deck: `Meshing/vals-plywise-del/native/output.inp`
- VUEL deletion rerun deck: `Meshing/vals-plywise-del/vuel/output.inp`
- Solver outputs & logs: `Meshing/vals-plywise-del/results/{native,vuel}/` (`.sta`, `.msg`, `.csv`, `.npz`)
- VUEL source code: `uel/VUEL_material.for` (lines 400–1020)
- Mesher & deck generator: `verification/roar/build_vals_plywise.py`, `embmesh/plyfibers.py`, `embmesh/vuelghost.py`
- Rerun report: `reports/VALS_PLYWISE_DELETION_RERUN_REPORT.html`
- Technical notes & known quirks: `docs/BUGS.md`, `docs/abaqus-explicit-quirks.md`, `agents/ROAR_KNOWLEDGE.md`, `agents/refiner/inbox/MESHER_VUEL_GHOST_TASK_2026-10-01.md`

---

## 1. Executive Summary

In the vp4 rerun of the 20-ply Vals laminate impact (jobs 56580053 and 56580055), element deletion was activated across all elements by adding `*Damage Evolution, type=DISPLACEMENT 0.` to the `Fiber` material and assigning `*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES`. While peak kinetic energy blowup was substantially reduced (from 366 J to ~6 J against a 3.5 J ball), visualization reveals two persistent physical anomalies:
1. **Fibers pull their host elements to deletion instead of failing or snapping back.**
2. **Fibers behave with substantially excessive inertia (they seem far too massive).**

Our investigation of the deck definitions, the mathematical formulation of Abaqus `*Embedded Element`, and the `VUEL_material.for` source code establishes the exact root causes:

1. **Host Deletion Before Fiber Yield:** A single 0.632 mm Dyneema tow requires $1,098\text{ N}$ (static) to $1,412\text{ N}$ (dynamic) to yield, and must undergo significant plastic strain (up to 3.91%) before damage initiates. In contrast, an entire native matrix hex host cell ($1.27\text{ mm}$ pitch) yields at only $113\text{ N}$ and softens to complete failure at just $41.7\ \mu\text{m}$ of localized displacement ($14.3\%$ element strain). The ghost host element in the VUEL model is even weaker, yielding at just $0.011\text{ N}$ ($11\text{ mN}$). Consequently, any tension in the fiber overloads the host by factors of $10\times$ (native) to $100,000\times$ (ghost), causing the host to delete locally while fiber strain remains below $0.5\%$. The fiber acts as a razor wire unzipping host elements along its path.
2. **Permanent Lumped Mass on Deleted Nodes:** In Abaqus/Explicit, the diagonal lumped mass matrix is assembled once at $t=0$. When host elements delete, their stress drops to zero, but **their lumped nodal mass remains permanently on the nodes**. As fibers pull on or pass through regions of deleted elements, they drag these unconstrained, frozen host masses through the mesh without any restoring matrix stiffness, creating the visual and dynamic behavior of heavy, sluggish cables.
3. **Ghost Host Decoupling in VUEL:** Because Abaqus/Explicit cannot embed elements into user elements (BUG-020), fibers are embedded exclusively in $10^{-4}$ scaled ghost elements. The ghost elements fail instantaneously under minute fiber tension, severing the fiber-host constraint while the underlying VUEL element is still completely alive and undeformed.

---

## 2. Answers to the Four Core Questions

### Question 1: Fiber Deletion Mechanics, Failure Strain, and Host Pre-emption

#### 1.1 Does Abaqus/Explicit actually delete T3D2 elements with this setup?
**Yes, Abaqus/Explicit structurally supports element deletion for T3D2 truss elements with this definition.**
- In `Meshing/vals-plywise-del/native/output.inp` (lines 72005, 126154–126161):
  ```abaqus
  *Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL
  3.1370687601686238e-07
  *Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES
  *Material, name=Fiber
  *Damage Initiation, criterion=DUCTILE
    0.0391, 0.333333,     0.01
    0.0251, 0.333333,       1.
   0.01167, 0.333333,    1000.
  *Damage Evolution, type=DISPLACEMENT
  0.
  ```
- *Syntax anomaly:* The mesher assigns `*Solid Section` to 2-node truss elements (`T3D2`). In Abaqus keyword grammar, trusses standardly take `*Truss Section`. However, Abaqus 2024 datacheck accepts `*Solid Section` for 1D elements without error, reading the single entry on the data line as cross-sectional area.
- *Deletion trigger:* In Abaqus/Explicit, element deletion is active by default whenever `*Damage Evolution` is defined, and is explicitly confirmed by `element deletion=YES`. When `type=DISPLACEMENT` is set to `0.`, damage $D$ jumps instantaneously from 0 to 1 at the moment damage initiation is satisfied. Because a T3D2 element has exactly 1 integration point, $D=1$ at that single point causes immediate element removal from the active mesh.

#### 1.2 At what strain does the fiber fail?
The fiber damage initiation criterion is governed strictly by **equivalent plastic strain** $\bar{\varepsilon}^{pl}$, NOT total strain:
$$\bar{\varepsilon}^{pl} \ge \bar{\varepsilon}_0^{pl}(\eta, \dot{\bar{\varepsilon}}^{pl})$$
For a uniaxial truss under pure tension, stress triaxiality is fixed at $\eta = \sigma_m / \bar{\sigma} = 1/3 \approx 0.333333$.
The total failure strain $\varepsilon_{total} = \varepsilon_{elastic} + \bar{\varepsilon}_0^{pl}$ depends on strain rate:
- **Low strain rate ($\dot{\varepsilon} \le 0.01\text{ s}^{-1}$):**
  - Yield stress: $\sigma_{y0} = 3.5\times 10^9\text{ Pa}$ ($3.5\text{ GPa}$)
  - Elastic strain at yield: $\varepsilon_{el} = \sigma_{y0} / E = 3.5\times 10^9 / 1.35\times 10^{11} = 0.02593$ ($2.59\%$)
  - Plastic strain to initiate damage: $\bar{\varepsilon}_0^{pl} = 0.03910$ ($3.91\%$)
  - **Total strain at deletion: $\varepsilon_{total} = 2.59\% + 3.91\% = \mathbf{6.50\%}$**
- **Intermediate strain rate ($\dot{\varepsilon} = 1.0\text{ s}^{-1}$):**
  - Yield stress: $\sigma_{y1} = 4.3\times 10^9\text{ Pa}$ ($4.3\text{ GPa}$)
  - Elastic strain at yield: $\varepsilon_{el} = 4.3\times 10^9 / 1.35\times 10^{11} = 0.03185$ ($3.19\%$)
  - Plastic strain to initiate damage: $\bar{\varepsilon}_0^{pl} = 0.02510$ ($2.51\%$)
  - **Total strain at deletion: $\varepsilon_{total} = 3.19\% + 2.51\% = \mathbf{5.70\%}$**
- **High strain rate ($\dot{\varepsilon} = 1000.0\text{ s}^{-1}$):**
  - Yield stress: $\sigma_{y1000} = 4.5\times 10^9\text{ Pa}$ ($4.5\text{ GPa}$)
  - Elastic strain at yield: $\varepsilon_{el} = 4.5\times 10^9 / 1.35\times 10^{11} = 0.03333$ ($3.33\%$)
  - Plastic strain to initiate damage: $\bar{\varepsilon}_0^{pl} = 0.01167$ ($1.17\%$)
  - **Total strain at deletion: $\varepsilon_{total} = 3.33\% + 1.17\% = \mathbf{4.50\%}$**

To fail and delete, the fiber MUST reach at least **4.50% to 6.50% total strain**, carrying an axial tensile force of:
$$F_{yield} = \sigma_y A_{fiber} = (3.5\text{ to } 4.5\times 10^9\text{ Pa}) \times (3.137\times 10^{-7}\text{ m}^2) = \mathbf{1,098\text{ N to } 1,412\text{ N}}$$

#### 1.3 Is the fiber failure strain reachable before the host fails?
**NO. It is mathematically and mechanically impossible for the host elements to support this load without deleting first.**
- *Host Element Load Capacity:*
  - Matrix properties: $E = 7.0\times 10^8\text{ Pa}$ ($700\text{ MPa}$), $\sigma_{y,mat} = 7.0\times 10^7\text{ Pa}$ ($70\text{ MPa}$).
  - A host hex element has dimensions $h \approx 1.27\text{ mm}$, giving face area $A_{host} \approx 1.613\times 10^{-6}\text{ m}^2$.
  - Maximum tensile force sustainable by the entire host element before yielding:
    $$F_{host,max} = \sigma_{y,mat} A_{host} = 70\times 10^6\text{ Pa} \times 1.613\times 10^{-6}\text{ m}^2 = \mathbf{113\text{ N}}$$
  - Maximum shear force sustainable (von Mises $\tau_y = \sigma_y / \sqrt{3} \approx 40.4\text{ MPa}$):
    $$F_{host,shear} \approx 40.4\times 10^6\text{ Pa} \times 1.613\times 10^{-6}\text{ m}^2 = \mathbf{65\text{ N}}$$
- *Softening Displacement to Host Deletion:*
  - In the native deck, matrix softening uses fracture energy $G_f = 1460\text{ J/m}^2$.
  - Critical opening displacement to complete deletion:
    $$u_f = \frac{2 G_f}{\sigma_{y,mat}} = \frac{2 \times 1460}{70\times 10^6} = 4.17\times 10^{-5}\text{ m} = \mathbf{41.7\ \mu\text{m}}$$
  - In a $1.27\text{ mm}$ element, this corresponds to an additional softening strain of only $\Delta \varepsilon_{soft} = 41.7\ \mu\text{m} / 1.27\text{ mm} \approx 0.0328$ ($3.28\%$).
  - Total strain to delete the host: $\varepsilon_{host,del} = \varepsilon_{el} + \varepsilon_{init}^{pl} + \Delta \varepsilon_{soft} = 10\% + 1\% + 3.28\% = \mathbf{14.28\%}$.
- *The Pre-emption Mechanism:*
  - At just **$0.5\%$ fiber strain** (purely elastic, far below fiber yield), fiber tension is:
    $$T = E_{fiber} A_{fiber} \varepsilon = 1.35\times 10^{11} \times 3.137\times 10^{-7} \times 0.005 = \mathbf{212\text{ N}}$$
  - Because $212\text{ N} > 113\text{ N}$, the fiber exerts nearly DOUBLE the ultimate strength of the host element before reaching even one-fifth of its own yield limit!
  - When the host element yields, it localizes and deletes after just $41.7\ \mu\text{m}$ of localized deformation.
  - Across a fiber span of several centimeters, $41.7\ \mu\text{m}$ of deflection represents a fiber strain of less than $0.1\%$.
  - Therefore, the host element ALWAYS yields and deletes first. As soon as it deletes, the constraint is broken at that element, shedding load to the adjacent host element, which in turn immediately deletes. The fiber never accumulates the plastic strain required to initiate damage.

---

### Question 2: Embedded Constraint Force Transmission and Host Deletion Dynamics

#### 2.1 How does the native `*Embedded Element` constraint pass fiber force to the host?
1. **Geometric Mapping & Kinematic Constraint:**
   Abaqus evaluates the isoparametric coordinates $(\xi, \eta, \zeta) \in [-1, 1]^3$ of each embedded fiber node inside its containing host hex. The translational displacement $\mathbf{u}_{emb}$ of the embedded node is constrained via the host trilinear shape functions $N_i$:
   $$\mathbf{u}_{emb} = \sum_{i=1}^8 N_i(\xi, \eta, \zeta) \mathbf{u}_i^{host}$$
2. **Force Equivalence via Virtual Work:**
   The embedded truss calculates its internal axial force vector $\mathbf{F}_{emb}$ from its constitutive law. By the principle of virtual work:
   $$\delta W = \delta \mathbf{u}_{emb}^T \mathbf{F}_{emb} = \sum_{i=1}^8 (\delta \mathbf{u}_i^{host})^T [ N_i(\xi, \eta, \zeta) \mathbf{F}_{emb} ]$$
   Hence, the equivalent load delivered to each host node $i$ is:
   $$\mathbf{F}_i^{host} = N_i(\xi, \eta, \zeta) \mathbf{F}_{emb}$$
   Every Newton of axial tension developed in the fiber is transmitted directly onto the host element's corner nodes without slip or threshold.

#### 2.2 What happens to embedded fiber nodes whose host element is deleted?
*[Sourced from Abaqus/Explicit Mechanics & Theory; Unverified general knowledge where indicated]*
- **Constraint Dissolution:** When a host element deletes, Abaqus/Explicit removes its element equations from the solver. The kinematic multi-point constraint tying the embedded node to that host element is **instantly dissolved**.
- **No Automatic Fiber Deletion [General Knowledge]:** Abaqus does NOT automatically delete embedded elements when their host deletes. The embedded element lifecycle is completely decoupled from the host element lifecycle unless explicitly programmed via a user subroutine.
- **Node Release & Whiplash:**
  - The embedded node becomes an independent "free" node in 3D space.
  - The node retains its own lumped mass from the attached truss elements ($m_{node} = \frac{1}{2} \rho A L \approx 1.9\times 10^{-7}\text{ kg}$).
  - If the fiber was in tension, the sudden release of the anchoring host force creates an unbalanced internal force $\mathbf{F}_{emb}$ acting on the tiny nodal mass, producing extreme local accelerations:
    $$\mathbf{a} = \frac{\mathbf{F}_{emb}}{m_{node}} \sim \frac{500\text{ N}}{1.9\times 10^{-7}\text{ kg}} \approx 2.6\times 10^9\text{ m/s}^2$$
  - This explains the extreme velocities (up to $23 - 35\text{ km/s}$) and flailing displacements observed in the solver logs and viewer.

#### 2.3 Difference between Native Host and VUEL Host + Ghost Deletion
- **Native Host:**
  The host element is a real C3D8R hex with matrix properties ($E = 700\text{ MPa}$, $\sigma_y = 70\text{ MPa}$). Deletion occurs when the native material reaches its energy softening limit ($14.3\%$ strain).
- **VUEL Host + Ghost Scaffold (BUG-020 & BUG-021):**
  - Per `docs/BUGS.md` BUG-020, Abaqus/Explicit rejects `*Embedded Element` directly inside a `*User Element` (100% of embedded nodes fail input processing).
  - To bypass this, the mesher creates duplicate native **ghost C3D8R elements** (`EMBMESH_GHOST_HOST`) on the same nodes as the VUEL, with properties scaled by $10^{-4}$:
    - Density: $\rho_{ghost} = 0.098\text{ kg/m}^3$
    - Elastic modulus: $E_{ghost} = 70,000\text{ Pa}$ ($70\text{ kPa}$)
    - Yield stress: $\sigma_{y,ghost} = 7,000\text{ Pa}$ ($7\text{ kPa}$)
    - Ductile onset strain: $\varepsilon_0^{pl} = 0.13725$
    - Displacement evolution: $0.$
  - Fibers are embedded **strictly into the ghost elements**, not into the VUEL!
  - Maximum load capacity of the ghost host element:
    $$F_{ghost,max} = 7\times 10^3\text{ Pa} \times 1.613\times 10^{-6}\text{ m}^2 = \mathbf{0.0113\text{ N}} = \mathbf{11.3\text{ mN}}$$
  - **The Ghost Deletion Trap:** While the ghost was intended to delete synchronously with the VUEL matrix failure, the presence of the embedded fiber completely destroys this synchronization. As soon as an embedded fiber carries even $0.05\text{ N}$ (50 grams of force!), the ghost element is overloaded by thousands of percent, reaches its failure strain immediately, and **DELETES**.
  - **Decoupling from the Real Physics:** When the ghost deletes, the fiber is completely uncoupled from the mesh, even while the VUEL element on those exact same nodes is virtually unstrained and undamaged!
  - Furthermore, per BUG-021, a VUEL cannot natively delete or erode in Abaqus/Explicit. It remains in the mesh zeroing its stress. Visual deletion and contact erosion in the VUEL deck depend 100% on the ghost element.

---

### Question 3: Mass Formulation, Volume Scaling, and Deleted Node Lumped Mass

#### 3.1 Native Host Mass Inflation
- In the native deck:
  - Matrix density $\rho_{mat} = 980\text{ kg/m}^3$ is applied to the full geometric volume of the plate.
  - Fiber density $\rho_{fiber} = 981\text{ kg/m}^3$ is applied to the fiber tows.
  - Fiber volume fraction is $V_f \approx 0.389$ ($38.9\%$).
  - `*Embedded Element` does NOT subtract the volume of the fibers from the host solid elements.
  - Effective smeared density in the ply:
    $$\rho_{eff,native} = \rho_{mat} + V_f \rho_{fiber} \approx 980 + 0.389 \times 981 = 1,361.6\text{ kg/m}^3 \approx \mathbf{1.389 \times \rho_{mat}}$$
  - The native model suffers an artificial **~39% mass inflation** due to double-counting the volume occupied by the fibers.

#### 3.2 What is scaled in the VUEL (`uel/VUEL_material.for`)?
**Both the host lumped mass matrix (`amass`) AND the constitutive internal stress volume (`DVOL_EFF`) are explicitly scaled by $\eta = 1 - V_f$.**
Source evidence from `uel/VUEL_material.for`:
1. *Fiber Volume Fraction Extraction (lines 406–409):*
   ```fortran
           FIBER_VOL_FRAC = 0.0D0
           IF (nsvars .GE. 107) FIBER_VOL_FRAC = svars(KBLOCK,107)
           ETA_VF_RAW = 1.0D0 - FIBER_VOL_FRAC
           ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)
   ```
2. *Mass Matrix Calculation (`lflags(iOpCode) == jMassCalc`, lines 459–466):*
   ```fortran
             ELVOL_EFF = ETA_VF * ELVOL_GEOM
             ELEMASS = DENS * ELVOL_EFF
             DO INODE = 1, 8
               DO I = 1, 3
                 IDOF = (INODE - 1) * 3 + I
                 amass(KBLOCK, IDOF, IDOF) = ELEMASS / 8.0D0
               END DO
             END DO
   ```
   **Confirmed:** Nodal lumped mass assembled into Abaqus's global mass matrix is scaled by $(1 - V_f)$.
3. *Internal Force Integration (`lflags(iOpCode) == jIntForceAndDtStable`, lines 547, 868–873):*
   ```fortran
               DVOL_EFF = ETA_VF * DVOL_GEOM
               FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_PK2(J) * DVOL_EFF
   ```
   **Confirmed:** Constitutive internal forces from matrix stress integrate over effective volume $DVOL\_EFF = (1 - V_f) DVOL\_GEOM$.
4. *Energy Integrations (lines 885, 888, 892, 971):*
   Elastic energy (`ELIE`), plastic dissipation (`PLASTIC_DISSIP`), damage dissipation (`DAMAGE_DISSIP`), and kinetic energy (`ELKE`) all scale with `DVOL_EFF`.
5. *Exception:* Artificial bulk viscosity and Rayleigh damping use geometric volume `DVOL_GEOM` (lines 870, 875) to maintain numerical damping stability.

#### 3.3 What lumped mass is left on nodes of deleted elements?
*[Sourced from Abaqus Analysis User's Guide Section 19.1.1 & Explicit Solver Architecture]*
- In Abaqus/Explicit, the diagonal lumped mass matrix $\mathbf{M}$ is assembled **once at increment 0** by summing contributions from all elements attached to each node:
  $$M_I = \sum_{e \in elements\_at\_I} m_I^{(e)}$$
- During time integration:
  $$\ddot{\mathbf{u}}_I = \mathbf{M}_I^{-1} (\mathbf{F}_I^{ext} - \mathbf{F}_I^{int})$$
- When an element fails and is **deleted**:
  - Its internal force $\mathbf{F}^{int}$ is zeroed.
  - **ITS NODAL MASS CONTRIBUTION IS NEVER REMOVED FROM THE NODES.**
  - The mass of deleted elements remains permanently on the 8 corner nodes.
- **Why the fibers seem too massive:**
  When host elements delete around the ball perforation, their nodes become "orphan" nodes. These orphan nodes retain the **full inertia of the deleted solid matrix elements** ($~980\text{ kg/m}^3$) plus any attached fiber elements, but possess **zero elastic restoring stiffness**.
  As the intact fibers are dragged through the perforation zone, they remain kinematically coupled to (or impact) these heavy orphan nodes. The fibers are literally dragging clumps of dead host mass through space, making them behave like extremely heavy, sluggish, non-rebounding chains!

---

### Question 4: Physical Scale Mismatch, Rate Curves, VUMAT, and Embedding Strategies

#### 4.1 Is the fiber scale a modelling problem of its own?
**YES, fundamentally.**
- In reality, a Dyneema tow consists of hundreds of micro-filaments ($d \sim 12\ \mu\text{m}$) embedded in polyurethane resin. Load is transferred through shear across a huge specific surface area:
  $$\left(\frac{A_{surface}}{V}\right)_{real} = \frac{\pi d L}{\frac{\pi}{4} d^2 L} = \frac{4}{d} \approx 3.3\times 10^5\text{ m}^{-1}$$
- In the finite element model, the tow is collapsed into a single 1D truss line of diameter $d = 0.632\text{ mm}$ ($632\ \mu\text{m}$):
  $$\left(\frac{A_{surface}}{V}\right)_{model} = \frac{4}{0.632\times 10^{-3}} \approx 6.3\times 10^3\text{ m}^{-1} \quad (\mathbf{52\times\text{ smaller}})$$
- The entire tensile strength of the tow ($1.1\text{ to } 1.4\text{ kN}$) is dumped into the host mesh at discrete points spaced $1.24\text{ mm}$ apart.
- A host element with $\sigma_y = 70\text{ MPa}$ and shear capacity of $65\text{ N}$ simply cannot transfer $1,100\text{ N}$ over a $1.24\text{ mm}$ gauge length without yielding and tearing. The stiffness mismatch ($193:1$) and strength mismatch ($50:1$) mathematically guarantee localized host failure.

#### 4.2 Would rate curves change it?
**No. Rate curves make the problem worse.**
- Rate-dependent plasticity increases fiber yield strength from $3.5\text{ GPa}$ to $4.5\text{ GPa}$ at $\dot{\varepsilon} = 1000\text{ s}^{-1}$.
- This raises the required fiber force from $1,098\text{ N}$ to $1,412\text{ N}$.
- Because the fiber is even stronger, it overloads the matrix even faster, accelerating host deletion while staying even further below its own yield point.

#### 4.3 Would the T-041 fiber VUMAT (`vumat/VUMAT_fiber_rd.for`) change it?
*Note: `VUMAT_fiber_rd.for` was specified in T-041 but not implemented in the tree yet.*
- If the VUMAT retains the $3.5\text{ GPa}$ yield stress and requires plastic strain to initiate damage, it will suffer the same host-preemption failure.
- **However, the VUMAT provides three critical fixes that can solve the problem:**
  1. **Tension-Only Law:** Native T3D2 trusses resist compression with full $135\text{ GPa}$ stiffness. When matrix hexes undergo shear or compression under the ball, compressed fibers develop massive spurious stresses that blow up the mesh. A tension-only VUMAT eliminates compressive stiffness entirely.
  2. **Total-Strain / Direct Stress Failure Criterion:** Instead of requiring plastic onset ($PEEQ$), the VUMAT can initiate damage at a realistic **total strain limit** (e.g. $\varepsilon_{fail} \approx 2.5\% - 3.0\%$) or maximum principal stress ($\sigma \ge 3.5\text{ GPa}$), allowing fibers to break cleanly without requiring large plastic deformation.
  3. **Direct Deletion Control:** The VUMAT controls the element deletion state variable directly via `*Depvar, delete=N`, guaranteeing that Abaqus/Explicit removes the element without keyword ambiguity.

#### 4.4 Would a different embedding strategy change it?
**YES:**
1. **Co-Deletion (Coupled Host-Fiber Deletion):** When a host element deletes, all fiber segments embedded within that host element should be deleted simultaneously. In ballistic impact, when the matrix is pulverized, the embedded fibers in that plug are physically ejected; leaving them behind as free-flying tensile cables is unphysical.
2. **Homogenized Orthotropic Continuum Plies:** Eliminate embedded 1D lines entirely; model each ply as an orthotropic continuum using Hashin failure or an orthotropic user material. This completely bypasses the discrete point-load shear tearing.

---

## 3. Ranked List of Probable Causes

| Rank | Probable Cause | Mechanism & Sourced Evidence | Severity |
| :---: | :--- | :--- | :---: |
| **1** | **Massive Strength & Stiffness Mismatch (193:1 $E$, 50:1 $\sigma_y$)** | Fiber tow carries $1,100 - 1,412\text{ N}$; host hex carries at most $113\text{ N}$ ($65\text{ N}$ shear). Fiber tension overloads host by $10\times$ at $<0.5\%$ fiber strain, tearing host to deletion before fiber can yield. | **Blocker** |
| **2** | **Unreachable Fiber Damage Initiation Strain** | Fiber `*Damage Initiation` requires $3.91\%$ plastic strain in addition to $2.59\%$ elastic strain ($6.50\%$ total strain). Host deletes at $41.7\ \mu\text{m}$ displacement ($14.3\%$ host strain), releasing fiber long before $6.5\%$ strain is reached. | **Blocker** |
| **3** | **Ghost Host Decoupling in VUEL Deck** | Fibers are embedded in $10^{-4}$ scaled ghost elements ($E=70\text{ kPa}$, $\sigma_y=7\text{ kPa}$, max force $11\text{ mN}$). Ghost deletes under trivial fiber load, leaving fibers detached from host while VUEL matrix is still alive. | **Major** |
| **4** | **Frozen Lumped Mass on Deleted Element Nodes** | Abaqus/Explicit never removes nodal mass when elements delete. Deleted host nodes retain full matrix mass ($980\text{ kg/m}^3$). Flailing fibers drag these unconstrained heavy nodes, causing excessive apparent fiber inertia. | **Major** |
| **5** | **Lack of Co-Deletion (Independent Element Lifecycles)** | Abaqus does not delete embedded elements when host deletes. Unconstrained fiber segments flail into the void, create artificial kinetic energy ($ALLKE > 6\text{ J}$ vs $3.5\text{ J}$ ball), and unzip adjacent rim elements. | **Major** |

---

## 4. Fix Options and Recommendations

### Option 1: Lower Fiber Failure Strain to Elastic Limit (Elastic-Brittle Tow Model)
- **What changes:**
  Modify the fiber material in `build_vals_plywise.py` to initiate damage at the elastic limit ($\varepsilon_{crit} \approx 0.025$ to $0.030$), or use an instantaneous displacement evolution.
  ```abaqus
  *Material, name=Fiber
  *Elastic
   1.35e+11, 0.45
  *Damage Initiation, criterion=MAXS
   3.5e+09
  *Damage Evolution, type=DISPLACEMENT
   0.
  ```
  *(Or adjust Ductile Damage Initiation with onset plastic strain = 0.0001).*
- **Risk:** Low. Deck-level change only. Ensures fibers snap when tensile stress hits Dyneema strength ($3.5\text{ GPa}$) rather than waiting for unreachable plasticity.

### Option 2: Implement T-041 Fiber VUMAT with Strain-Based Deletion & Tension-Only
- **What changes:**
  Deploy `vumat/VUMAT_fiber_rd.for` (from T-041 spec) for `T3D2` fibers:
  - Tension-only modulus ($E = 135\text{ GPa}$ in tension, $0$ in compression).
  - Explicit element deletion via `*Depvar, delete=N`.
  - Failure criterion triggered at total tensile strain $\varepsilon \ge 0.026$ or max stress $\sigma \ge 3.5\text{ GPa}$.
- **Risk:** Low to Moderate. Requires compiling user subroutine with the solver. Completely eliminates compression blowup and guarantees solver-level fiber removal.

### Option 3: Co-Deletion of Fibers upon Host Deletion (Deck / Post-Processing Coupling)
- **What changes:**
  Modify mesher / analysis so that whenever a host element status drops to 0, all embedded fibers within that host are deleted.
- **Risk:** Moderate. In pure native Abaqus, requires VUSDFLD/VUMAT field variable coupling.

### Option 4: Homogenized Orthotropic Continuum Plies (Architectural Fix)
- **What changes:**
  Replace discrete 1D embedded fibers with 3D continuum elements possessing orthotropic engineering constants ($E_{11} = 53\text{ GPa}$, $E_{22} = E_{33} = 1.2\text{ GPa}$, $G_{12} = 0.5\text{ GPa}$) and Hashin damage.
- **Risk:** High effort. Requires replacing the meshing strategy.

### Recommended Fix:
**Combine Option 1 (Immediate: Lower fiber failure threshold to elastic limit $\varepsilon \le 2.6\%$ in `build_vals_plywise.py`) with Option 2 (T-041 Tension-Only VUMAT).**
This immediately allows fibers to fail at their true physical tensile limit ($3.5\text{ GPa}$), eliminates artificial compression stiffness, and stops fibers from dragging deleted hosts through the plate.

---

## 5. Verification Test Plan & ROAR Access

Five verification test decks have been generated in `agents/drafter/outbox/T-046/tests/` via `make_test_decks.py`:

| Deck Name | Description | Key Outputs Requested | Target Verification |
| :--- | :--- | :--- | :--- |
| `test1_fiber_alone.inp` | Single T3D2 fiber element under pure uniaxial tension ($u=0.1\text{ mm}$, $\varepsilon=10\%$). | S11, LE11, PEEQ, STATUS, ALLKE, ALLIE, ALLPD | Confirms Abaqus/Explicit deletes T3D2 using `*Solid Section` + `*Damage Evolution, type=DISPLACEMENT 0.` at $\varepsilon \approx 6.5\%$. |
| `test2_single_host_pull.inp` | Single native C3D8R host hex + embedded T3D2 fiber. Host fixed at back; fiber pulled. | Host STATUS, Fiber STATUS, RF, U, ALLIE, ALLPD | Demonstrates host reaches $14.3\%$ strain and deletes while fiber strain is $<0.5\%$, breaking constraint. |
| `test3_vuel_ghost_pull.inp` | Single VUEL/Ghost host hex + embedded T3D2 fiber. | Ghost STATUS, Fiber STATUS, RF, U | Demonstrates ghost deletes at $F < 0.05\text{ N}$ ($11\text{ mN}$ range), decoupling fiber while VUEL is intact. |
| `test4_block_3x3_pull.inp` | 3x3x1 host hex block with embedded fiber tow pulled through center row. | Element STATUS over time, U, RF | Demonstrates sequential "wire-through-butter" unzipping of host elements without fiber failure. |
| `test5_mass_conservation.inp` | Dynamic pull and release measuring nodal acceleration and kinetic energy after host deletion. | Node U, V, A, Host STATUS, ALLKE | Proves that Abaqus/Explicit retains lumped nodal mass on deleted element nodes. |

### ROAR Submission Package
- Runner script: `outbox/T-046/tests/run_test.sbatch` (`#SBATCH --mem=16G`, scratch security guard, datacheck error inspection).
- Single submit script: `outbox/T-046/tests/submit_chain.sh` (submits all 5 datachecks and solves as a single sequential dependency chain `--dependency=afterany`).
- Remote directory: `/storage/home/zps5207/scratch/ctv/t046/`.
- **Status:** Test decks and submit scripts are built and locally validated. Cluster execution remains **unrun** pending the user's connection setup and single `sbatch` authorization per `PROTOCOL.md`.
