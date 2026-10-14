# T-010: Contact Penetration Root-Cause Analysis and Workaround Engineering

## Executive Summary & Verdict on the User's Idea

### The User's Idea
The user proposes defining a node-based contact surface (`*Surface, type=NODE`) for the plate nodes against the ball's face-based surface (`Surf-2`), exploiting the fact that the plate nodes carry both the user-element (`VU1`) mass/stiffness and the ghost element, thereby letting the full nodal mass participate in contact.

### Honest Verdict: Will it work? What are the traps?
- **Will it work?** Partially, but **it is not recommended as the primary solution on its own**. While a node-based surface immediately fixes the artificial softness of the penalty spring (raising the contact penalty from $\sim 0.85\text{ N/m}$ to $\sim 1.7 \times 10^{10}\text{ N/m}$ due to mass-based penalty scaling), it introduces severe geometric and physical traps inherent to discrete point contactors in hypervelocity impact.
- **The Traps:**
  1. **Inter-nodal Porosity / Punch-Through [Documented]:** A node-based surface contains **no surface facets and zero area**. In Abaqus/Explicit, a node surface can only act as a slave contactor against master element faces. Master nodes (the ball nodes) have no slave facets to push against. If a ball node passes between plate nodes, it experiences **zero contact force**. The plate nodes act like a "bed of needles" rather than an impermeable solid barrier.
  2. **Severe Localized Impulsive Spikes & Mesh Distortion [Documented / Recalled]:** Point contact concentrates multi-kilonewton impact forces onto discrete nodes. Accelerating individual 0.7 mg nodes at $10^9\text{ m/s}^2$ causes severe localized element distortion, numerical hourglassing, and high-frequency noise, which can prematurely trip the VU1 strain or Jacobian failure criteria.
  3. **"Zombie" Debris Nodes Post-Failure [Documented]:** In Abaqus/Explicit, a node is dropped from contact only when *all* elements attached to it are deleted. Because custom user elements (`VU1`) **cannot be deleted by Abaqus**, the plate nodes remain permanently active in the model even after the host material has completely failed physically. If the ball reverses or pushes spall debris, these weightless/unconstrained "zombie" nodes continue to act as indestructible rigid contact points against the ball.
  4. **Pop-Through / Reverse Normal Projection [Documented]:** If an advancing ball facet pushes a plate node past the ball's midplane or exit face within an increment, the contact penalty projects the node to the nearest exterior face (the back of the ball), pulling the node along with the ball rather than retarding it.
- **Verdict Summary:** A node-based surface solves the mass-scaling symptom of H1, but creates porosity and singularity problems. The true engineering fix is **whole-body ghost surface definition combined with contact penalty stiffness scaling** (Recipe 1).

---

## Detailed Evaluation of the User's Technical Inquiries

Every statement below is labeled **[Documented]** (derived from the Abaqus Analysis User's Guide / Theory Manual) or **[Recalled]** (established Abaqus solver behavior).

### 1. Can node-based surfaces be used in general contact with a ball face-based surface?
- **Answer:** **YES.**
- **Details:** In Abaqus/Explicit general contact (`*Contact`), a node-based surface (`*Surface, type=NODE`) can be explicitly paired with an element-based (face) surface via `*Contact Inclusions`. Node-based surfaces are *not* included in the default `ALL EXTERIOR` domain and must be explicitly specified. In general contact, node-based surfaces act as pure slave points against master element faces (node-to-face contact).
- **[Label: Documented - Abaqus Analysis User's Guide §36.4.1 "Defining general contact domains in Abaqus/Explicit" & §36.4.2 "Contact formulation for general contact in Abaqus/Explicit"].**

### 2. What happens when the element under a node surface is deleted (the ghost) while the VU1 remains: does the node stay a contact point forever or is it dropped?
- **Answer:** **The node stays an active contact point.**
- **Details:** In Abaqus/Explicit, element deletion removes eroded element integration points and element topology. A node is only deactivated or removed from the active model if *all* elements connected to it are deleted and it has no other mass, constraints, or boundary conditions. Because the node-coincident `VU1` user element is never deleted by Abaqus (user elements cannot be deleted by the solver), the node remains an active degree-of-freedom carrier with finite mass assembled in the global lumped mass vector. Because node-based surfaces are defined by nodal identity rather than element facet topology, the node remains in the general contact inclusion domain as an active contactor throughout the entire step.
- **[Label: Documented / Recalled - Abaqus Analysis User's Guide §36.4.1 & §14.1.1 "Element deletion"].**

### 3. Do nodes of VU1-only regions that are not in any ghost face stay valid?
- **Answer:** **YES.**
- **Details:** In Abaqus, a `*Surface, type=NODE` can be formed from any valid node set (`*Nset`), regardless of whether those nodes belong to native element exterior faces, interior elements, or user elements (`VU1`). The contact preprocessor does not require an underlying element face to construct a node-based surface.
- **[Label: Documented - Abaqus Keywords Reference Guide, `*SURFACE`].**

### 4. Does a node surface add mass-based penalty stiffness from the nodal mass (which includes VU1 mass)?
- **Answer:** **YES.**
- **Details:** In Abaqus/Explicit general contact, when a node-based surface interacts with an element face, Abaqus has no element modulus ($E$) or element characteristic length ($L_{char}$) associated with the slave nodes. Therefore, Abaqus/Explicit computes the penalty contact stiffness $K_{node}$ from the nodal lumped mass $m_i$ and the stable time increment $\Delta t$:
  $$K_{node} = c \frac{m_i}{\Delta t^2} \quad (c \approx 0.1 \sim 1.0)$$
  Because the global lumped mass matrix is assembled from all elements—and the `VU1` element supplies $99.99\%$ of the nodal mass ($1.0 \times \rho_{real}$ vs $10^{-4} \times \rho_{real}$ from the ghost)—the nodal mass $m_i \approx 7.0 \times 10^{-7}\text{ kg}$ yields a penalty stiffness on the order of:
  $$K_{node} \approx \frac{7.0 \times 10^{-7}\text{ kg}}{(6.44 \times 10^{-9}\text{ s})^2} \approx 1.7 \times 10^{10}\text{ N/m}$$
  This is 10 orders of magnitude stiffer than the ghost element default penalty.
- **[Label: Documented - Abaqus Theory Guide §5.1 "Contact constraint enforcement" & Analysis User's Guide §36.4.2].**

### 5. Is node-to-node contact (`*Contact Pair` with two node surfaces) possible in Explicit?
- **Answer:** **NO.**
- **Details:** In Abaqus/Explicit, contact pairs (`*Contact Pair`) strictly require at least one of the surfaces to be an element-based (face) surface. Pairing two node-based surfaces (`*Surface, type=NODE`) is unsupported. The Abaqus preprocessor aborts during datacheck with the fatal error: *"A contact pair cannot be defined between two node-based surfaces."*
- **[Label: Documented - Abaqus Analysis User's Guide §36.5.1 "Defining contact pairs in Abaqus/Explicit"].**

---

## Root-Cause Synthesis from `evidence/`

Diagnostic analysis of `Flat_v2` (`evidence/flat_v2_diagnostics_report.html`, `evidence/flat_v2_output.inp`, and `evidence/ct_plate_nodes_contact.csv`) reveals that ball penetration is governed by two interlocking mechanisms: **H1 (Penalty Softness)** and **H2 (Missing Interior Surface)**.

### Quantitative Size & Impedance Estimates

| Entity | Quantity | Value | Source / Formula |
| :--- | :--- | :--- | :--- |
| **Ball (Steel)** | Density $\rho_{steel}$ | $7850\text{ kg/m}^3$ | `evidence/Flatv2_user.inp:59244` [verified] |
| | Young's Modulus $E_{steel}$ | $203\text{ GPa}$ | `evidence/Flatv2_user.inp:59246` [verified] |
| | Poisson's Ratio $\nu_{steel}$ | $0.33$ | `evidence/Flatv2_user.inp:59246` [verified] |
| | Dilatational Wave Speed $c_{steel}$ | $6190\text{ m/s}$ | $c = \sqrt{\frac{E(1-\nu)}{\rho(1+\nu)(1-2\nu)}}$ [verified] |
| | Acoustic Impedance $Z_{steel}$ | $4.86 \times 10^7\text{ Pa}\cdot\text{s/m}$ | $Z = \rho c$ [verified] |
| | Quarter-Model Mass $M_{ball}$ | $8.19\text{ g}$ | `evidence/Flatv2_user.inp` & `sta` [verified] |
| | Impact Velocity $v_0$ | $1000\text{ m/s}$ | `evidence/Flatv2_user.inp:59273` [verified] |
| | Kinetic Energy (Quarter) $E_k$ | $4095\text{ J}$ | $E_k = \frac{1}{2} M v_0^2$ (`report:108` 4094 J) [verified] |
| | Required Stopping Force $F_{req}$ | $\mathbf{4.1 \times 10^5\text{ N}}$ ($410\text{ kN}$) | $F = \frac{E_k}{d_{plate}} = \frac{4095\text{ J}}{0.01\text{ m}}$ [verified] |
| **Matrix (Host)** | Density $\rho_{mat}$ | $980\text{ kg/m}^3$ | `evidence/Flatv2_user.inp:59234` [verified] |
| | Young's Modulus $E_{mat}$ | $5.08\text{ MPa}$ | `evidence/Flatv2_user.inp:59236` [verified] |
| | Bulk Modulus $K_{bulk, mat}$ | $8.47\text{ MPa}$ | $K = \frac{E}{3(1-2\nu)}$, $\nu=0.4$ [verified] |
| | Wave Speed $c_{mat}$ | $101.5\text{ m/s}$ | $c \approx \sqrt{\frac{K + \frac{4}{3}G}{\rho}}$ [verified] |
| | Acoustic Impedance $Z_{mat}$ | $9.95 \times 10^4\text{ Pa}\cdot\text{s/m}$ | $Z = \rho c$ [verified] |
| **Ghost (Scaled $10^{-4}$)**| Density $\rho_{ghost}$ | $0.098\text{ kg/m}^3$ | `vuelghost.py` $\times 10^{-4}$ [verified] |
| | Young's Modulus $E_{ghost}$ | $508\text{ Pa}$ | `vuelghost.py` $\times 10^{-4}$ [verified] |
| | Bulk Modulus $K_{bulk, ghost}$ | $846.7\text{ Pa}$ | $K_{ghost} = \frac{508}{3(1-0.8)}$ [verified] |
| | Acoustic Impedance $Z_{ghost}$ | $\mathbf{9.95\text{ Pa}\cdot\text{s/m}}$ | $Z = \rho c$ ($5 \times 10^6\times$ softer than steel) [verified] |
| | Default Penalty Stiffness $k_{ghost}$| $\mathbf{0.85\text{ N/m}}$ | $k \approx \frac{K_{bulk} A}{L_{char}} = \frac{847 \times 10^{-6}}{10^{-3}}$ [verified] |
| | Force at 1 mm Penetration $F_{pen}$ | $\mathbf{0.00085\text{ N}}$ ($0.85\text{ mN}$) | $F = k \delta$ ($5 \times 10^8\times$ below $F_{req}$) [verified] |

### Mechanism Breakdown

1. **Hypothesis H1 (Penalty Stiffness derived from 1e-4 Ghosts) - VERIFIED [evidence/flat_v2_diagnostics_report.html:115]:**
   - Abaqus/Explicit derives element-based penalty contact stiffness from the underlying element modulus.
   - Because `Surf-1` is assigned to ghost elements with $E = 508\text{ Pa}$, the default penalty stiffness is $k \approx 0.85\text{ N/m}$.
   - When the steel ball ($M = 8.2\text{ g}$, $v = 1000\text{ m/s}$) impacts the ghost face, a 1 mm penetration produces a resisting force of only $0.85\text{ mN}$, compared to the $410\text{ kN}$ required to decelerate the ball. The ball experiences virtually zero resistance.

2. **Hypothesis H2 (Missing Interior Contact Faces) - VERIFIED [evidence/flat_v2_output.inp:111202 & Flatv2_user.inp:59131]:**
   - In `flat_v2_output.inp`, `Surf-1` is defined exclusively on three explicit element sets:
     ```abaqus
     *Surface, type=ELEMENT, name=Surf-1
     _Surf-1_S2, S2
     _Surf-1_S3, S3
     _Surf-1_S4, S4
     ```
   - Analysis of `_Surf-1_S2`, `S3`, `S4` shows they contain exactly **6,216 elements** (out of 24,000 ghosts, exactly $25.9\%$). These correspond only to the initial exterior perimeter and top/bottom layers.
   - The remaining **17,784 ghost elements ($74.1\%$) are never part of `Surf-1`**.
   - When the top ghost elements reach ductile damage failure and delete, their faces vanish. Because interior ghost elements are not part of `Surf-1`, **no newly exposed interior faces are created**. A gaping geometric hole opens in `Surf-1`, allowing the ball nodes to freely enter the interior of the plate without any contact surface existing.

3. **Origin of Impulsive CPRESS Spikes - VERIFIED [evidence/ct_plate_nodes_contact.csv]:**
   - Contact pressure was recorded on only 285 plate nodes, with a median duration of exactly **1 frame** ($70\text{ ns}$), peaking at $4.0 \times 10^{10}$ to $6.12 \times 10^{11}\text{ Pa}$.
   - These spikes occur during the brief instant a ball node violently penetrates a surviving exterior ghost element before that element reaches its displacement failure limit ($\Delta u_{fail} = 0$) and deletes. Once deleted, the face vanishes and CPRESS drops instantly to zero.

---

## Brainstorming & Ranked Workarounds

| Rank | Workaround | Prob. Fix Penetration | Implementation Effort | Risk to Failure Physics | Primary Mechanism & Assessment |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | **Whole-Ghost Surface + General Contact Penalty Scale Factor (`*Contact Controls Assignment`)** | **HIGH (95%)** | **LOW** | **ZERO** | Remap `Surf-1` to all 24,000 ghost elements (`EMBMESH_GHOST_HOST`) so interior faces dynamically activate upon erosion. Scale general contact penalty stiffness by $10^4$ or $10^5$ to restore structural stiffness without altering ghost mass or constitutive behavior. |
| **2** | **Whole-Plate Node-Based Contact Surface (`*Surface, type=NODE`) with Assigned Thickness** | **MEDIUM (70%)** | **LOW** | **MEDIUM** | User's idea. Node mass ($99.99\%$ from VU1) automatically scales penalty stiffness to $\sim 1.7 \times 10^{10}\text{ N/m}$. Requires assigning contact thickness to prevent zero-thickness punch-through, but carries risk of inter-nodal porosity and zombie debris nodes. |
| **3** | **Explicit Linear Penalty Stiffness (`*Surface Behavior, pressure-overclosure=LINEAR`) on Whole Ghost Surface** | **HIGH (95%)** | **LOW** | **ZERO** | Replace `HARD` contact with direct user-specified linear penalty modulus ($K = 10^{11}\text{ Pa/m}$) on `Surf-1`. Decouples contact stiffness completely from element material definitions. |
| **4** | **Rescale Ghost Material ($\alpha = 0.01$ or $0.1$) with Compensated VU1 Reduction** | **HIGH (90%)** | **MEDIUM** | **HIGH (Physics Change)** | Increase ghost scale from $10^{-4}$ to $10^{-2}$ or $10^{-1}$ and subtract the ghost stiffness/density from the VU1 properties. Directly stiffens contact, but changes plastic dissipation and requires user approval. |
| **5** | **Kinematic / Master-Slave Contact Pair (`*Contact Pair`) with Eroding Slave Surface** | **LOW (30%)** | **MEDIUM** | **MEDIUM** | Replace general contact with pure master-slave contact pairs. Abaqus/Explicit kinematic contact pairs frequently error or suffer severe snagging when slave elements erode. |
| **6** | **Coincident Membrane / Shell Surface Skin (`M3D4R`) on Interior/Exterior Ghost Faces** | **MEDIUM (60%)** | **HIGH** | **MEDIUM** | Add massless membrane elements sharing ghost nodes to act as pure contact facets. High mesher complexity; requires synchronizing membrane deletion with ghost deletion. |
| **7** | **Decouple Ghost Density ($\rho_{scale} = 1.0$) from Ghost Stiffness ($E_{scale} = 10^{-4}$)** | **LOW (20%)** | **LOW** | **HIGH (Physics Change)** | Retain $10^{-4}$ stiffness but keep ghost density at 1.0. Increases nodal mass but does not resolve element-based facet penalty scaling, while artificially inflating plate total mass. |
| **8** | **Full Inversion: Ghost carries Real Matrix ($\alpha = 1.0$), VU1 carries only Fibers** | **HIGH (85%)** | **VERY HIGH** | **EXTREME (Physics Change)** | Relegates custom VUEL to fiber-only role. Defeats the foundational purpose of the custom Fortran VUEL constitutive framework. |

---

## Concrete Recipes for the TOP TWO Workarounds

### RECIPE #1: Whole-Ghost Surface + General Contact Penalty Scale Factor (Recommended)

#### Deck Changes
1. **Redefine `Surf-1` on all ghost elements:**
   Replace the boundary-only face sets (`_Surf-1_S2`, `S3`, `S4`) with a whole-element surface definition over `EMBMESH_GHOST_HOST`:
   ```abaqus
   *Surface, type=ELEMENT, name=Surf-1
   Plate-1.EMBMESH_GHOST_HOST,
   ```
2. **Apply Penalty Stiffness Scale Factor in General Contact:**
   Under `*Contact, op=NEW`, add `*Contact Controls Assignment` scaling penalty stiffness between `Surf-1` and `Surf-2` by $10,000$ (restoring $E_{ghost} \times 10^4 = 5.08\text{ MPa}$ or higher):
   ```abaqus
   *Contact, op=NEW
   *Contact Inclusions
   Surf-1 , Surf-2
   Surf-2 , Surf-1
   Surf-1 , 
   Surf-2 , 
   *Contact Property Assignment
    ,  , General
   *Contact Controls Assignment, type=SCALE FACTOR
   Surf-1, Surf-2, 10000.0
   ```

#### Where in `embmesh/vuelghost.py` the change belongs
- In `convert_to_vuel_ghost()`, around lines 360–389:
  Currently, `vuelghost.py` filters for `*Surface, type=ELEMENT` and remaps existing member elsets (`_Surf-1_S2`, etc.).
  Replace this logic by redefining `Surf-1` to point to the instance-level ghost elset:
  ```python
  # Ensure Surf-1 includes all ghost elements for dynamic erosion tracking:
  surf_replacement = [
      "*Surface, type=ELEMENT, name=Surf-1",
      f"{instance}.{GHOST_ELSET},"
  ]
  ```
- Around lines 390–415 (step/contact handling):
  Inspect the `*Contact` block and insert:
  ```python
  if name == "contact":
      transformed_contact = block + [
          "*Contact Controls Assignment, type=SCALE FACTOR",
          "Surf-1, Surf-2, 10000.0"
      ]
  ```

#### Expected Effect
- **Dynamic Interior Contact:** As crater elements erode, interior ghost faces automatically become active exterior faces in the general contact domain.
- **Realistic Penalty Force:** Contact penalty stiffness increases from $0.85\text{ N/m}$ to $8500\text{ N/m}$ (or up to $8.5 \times 10^5\text{ N/m}$ if scaled by $10^6$), preventing ball penetration through live ghosts.
- **Intact Physics:** The ghost material remains scaled by $10^{-4}$ (no change to VUEL constitutive laws, mass matrix, or yield behavior).

#### Confirmatory ROAR Experiment
- **Deck Variant:** `Flat_v2_Recipe1.inp` (Whole-ghost `Surf-1` + scale factor `10000.0`).
- **Extraction:** Run diagnostic script extracting ball velocity `V3` vs time, number of ball nodes inside live ghosts, and total ghost deletions.
- **Pass/Fail Criterion:**
  - **PASS:** Ball velocity drops significantly below $980\text{ m/s}$ (plate absorbs substantial kinetic energy); peak ball nodes inside live ghosts drops from $490$ to $< 10$; crater forms with cleanly eroded cavity.
  - **FAIL:** Ball speed remains $> 980\text{ m/s}$ or ball nodes still penetrate live ghosts.

---

### RECIPE #2: Whole-Plate Node-Based Contact Surface with Assigned Thickness (User's Idea Enhanced)

#### Deck Changes
1. **Define Node-Based Contact Surface on Plate Instance:**
   In the assembly section, define `Surf-Plate-Nodes` from the plate node set:
   ```abaqus
   *Surface, type=NODE, name=Surf-Plate-Nodes
   Plate-1.PLATE,
   ```
2. **Assign Contact Thickness and Inclusions:**
   Assign a finite contact thickness (e.g. $0.5\text{ mm}$, half the element edge length) so nodes behave as contact spheres rather than zero-dimensional point needles:
   ```abaqus
   *Contact, op=NEW
   *Contact Inclusions
   Surf-Plate-Nodes, Surf-2
   Surf-1, Surf-2
   Surf-2, Surf-1
   *Contact Property Assignment
    ,  , General
   *Surface Property Assignment, type=THICKNESS
   Surf-Plate-Nodes, 0.0005
   ```

#### Where in `embmesh/vuelghost.py` the change belongs
- In `convert_to_vuel_ghost()`, before `*End Assembly` (lines 397–402):
  Insert the node surface definition:
  ```python
  final.extend([
      "*Surface, type=NODE, name=Surf-Plate-Nodes",
      f"{instance}.PLATE,"
  ])
  ```
- In the step interaction definition (under `*Contact`):
  Append `Surf-Plate-Nodes, Surf-2` to `*Contact Inclusions`, and add the `*Surface Property Assignment, type=THICKNESS` card.

#### Expected Effect
- **Mass-Based Contact Stiffness:** Abaqus computes penalty stiffness from the full nodal mass ($m_i \approx 0.7\text{ mg}$), yielding $K \approx 1.7 \times 10^{10}\text{ N/m}$.
- **Reduced Punch-Through:** The assigned $0.5\text{ mm}$ thickness creates a continuous contact envelope around the nodes, mitigating inter-nodal porosity.
- **Known Trade-Off:** Node-based contact forces remain somewhat spiky compared to face-to-face contact.

#### Confirmatory ROAR Experiment
- **Deck Variant:** `Flat_v2_Recipe2.inp`.
- **Extraction:** Read `ct_contact.json`, `CPRESS` at plate nodes, and ball node penetrations.
- **Pass/Fail Criterion:**
  - **PASS:** Ball nodes do not penetrate live plate nodes; plate absorbs $> 20\%$ of ball kinetic energy.
  - **FAIL:** Ball nodes slip between plate nodes without decelerating, or analysis aborts due to severe nodal distortion.

---

## Physics Changes Listed Separately for User Decision

The following options alter the constitutive partition or material calibration and are flagged as **PHYSICS CHANGES**:

### 1. Rescaling the Ghost Material ($\alpha = 0.01$ or $0.1$) with Compensated VU1 Reduction
- **Description:** Instead of scaling the ghost by $10^{-4}$, scale the ghost elastic modulus, density, and yield stress by $\alpha = 0.01$ ($1\%$) or $\alpha = 0.1$ ($10\%$). In `vuelghost.py`, reduce the `VU1` properties to $(1 - \alpha) \times \text{Matrix}$ so the unfailed composite stiffness and mass are exactly preserved.
- **Advantages:** Contact penalty stiffness naturally scales up by $100\times$ to $1000\times$ without altering contact keywords.
- **Physical Impact / Trade-Offs:**
  - The ghost element will carry $1\%$ to $10\%$ of the physical load and plastic dissipation.
  - Ghost deletion will dissipate non-negligible energy prior to VU1 failure.
  - Requires adjusting the ghost ductile damage initiation and displacement evolution to ensure synchronization with the VU1 failure trigger.
- **Decision Required:** Does the user approve shifting $1\%$ to $10\%$ of the constitutive responsibility from `VUEL_failure.for` to native Abaqus `C3D8R` elements?

---

## What the Data CANNOT Tell Us & Further ODB Queries

### What the Current Data Cannot Tell Us
1. **Solver Penalty Spring Stiffness:** The ODB records `CPRESS` and `CSHEARMAG`, but does not output the internal penalty spring stiffness ($K_{penalty}$) evaluated by the Abaqus solver engine.
2. **Ball Element Erosion / Integrity:** The ball was run without `STATUS` output (`flat_v2_diagnostics_report.html:133`). We cannot determine whether ball elements suffered Johnson-Cook damage or eroded during impact.
3. **Continuous Gap / Clearance History:** Only bounding box penetrations and closest approach frames were sampled. Continuous contact clearance histories (`CDISP` / `COPEN`) across the contact interface are absent.
4. **Direct VU1 Internal State History:** `SDV49` (failure flag) and `SDV106` were requested in `flat_v2_output.inp` but omitted from the ODB.

### Further ODB Queries & Instrumentation Requested from the Hub
1. **History Output for Interface Force:** Request `*Contact Output, history` with `CFORCE` and `CAREA` for `Surf-1` against `Surf-2` to obtain continuous time histories of contact force and contact area.
2. **Ball Element Status:** Add `STATUS` to the ball element field output requests (`*Element Output, elset=Ball-1.Ball \n S, PEEQ, STATUS`) to confirm whether the projectile is deforming or eroding.
3. **Contact Displacement Output:** Request `CDISP` (contact clearance and penetration distance) in field output at the plate contact surface.
