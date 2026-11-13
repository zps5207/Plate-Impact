# Analysis of Hex Element Inversion Mechanisms & Numerical Remedies in Abaqus/Explicit

**Task ID:** T-052  
**Role:** Drafter (agy)  
**Date:** October 27, 2026  
**Deliverable:** `agents/drafter/outbox/T-052/INVERSION_FIXES.md`  
**Target Cluster:** Penn State ROAR (ICDS), Abaqus/Explicit 2024  

---

## 1. Executive Summary & Physics of 1000 m/s Impact

In the native 20-ply Valerie plate impact model and the subsequent `bt1` and `bt2` test series, a mild steel quarter-ball (radius $R = 9.525$ mm, initial mass $0.00709$ kg, initial kinetic energy $E_0 \approx 3.55$ kJ) impacts a carbon-fiber/epoxy laminate at $v_0 = 1000$ m/s ($Mach \approx 2.9$ in air, $\approx 0.17$ relative to the steel dilatational sound speed $c_d = 5900$ m/s). 

Across all 12 $\mu$s runs in `bt1` and `bt2`:
- Element deletion begins between **$t \approx 1.5$ and $1.8$ $\mu$s** (in `vp5`, 75 elements were deleted by $1.68$ $\mu$s).
- By $12$ $\mu$s, approximately **$4.0\%\text{--}4.9\%$ of the ball elements (728 to 913 elements)** are deleted.
- Geometric corner Jacobian analysis (`reports/bt2_inversion.json` via `ball_inversion.py`) indicates that **$1.5\%\text{--}3.9\%$ of the ball C3D8R hexes possess a non-positive corner Jacobian** by $12$ $\mu$s.
- Neither changing fibers from truss to beam (`c1`), nor fixing the Johnson-Cook rate sensitivity ($D_4 = +0.002$ in `b4`), nor changing matrix degradation ($0.8$ in `c2`/`c3`), nor adopting an O-grid ball (`b2`) stopped this erosion or inversion.

### Critical Finding: Deconstructing the "Elements Invert Before They Delete" Hypothesis

The prevailing hypothesis going into this task was: *"the user believes elements invert and blow up before they delete."* 

An exhaustive chronological audit of `reports/bt2_inversion.json` directly contradicts this assumption:

| Simulation Deck | First Deletion Time ($t_{del}$) | Ball Inversion at $1.75$ $\mu$s | First Inversion Time ($t_{inv}$) | Inverted Fraction at $12$ $\mu$s | Deleted Fraction at $12$ $\mu$s |
|---|---:|---:|---:|---:|---:|
| **vp5 baseline** (1000 m/s) | $\le 1.68$ $\mu$s (75 dead) | **0.0000** | $2.10$ $\mu$s (0.25%) | 3.94% | 4.93% (913 / 18,500) |
| **b4_d4fix** (1000 m/s) | $\le 1.77$ $\mu$s | **0.0000** | $1.85$ $\mu$s (0.006%) | 3.55% | 4.54% (840 / 18,500) |
| **c1_beam_d4** (1000 m/s) | $\le 1.77$ $\mu$s | **0.0000** | $1.85$ $\mu$s (0.006%) | 3.28% | 3.93% (728 / 18,500) |
| **c2_truss_d4_md80** (1000 m/s) | $\le 1.77$ $\mu$s | **0.0000** | $1.85$ $\mu$s (0.006%) | 3.57% | 4.24% (784 / 18,500) |
| **c1_beam_d4_v500** (500 m/s) | $\approx 3.3$ $\mu$s | **0.0000** | $4.58$ $\mu$s (0.006%) | 1.51% | 1.86% (344 / 18,500) |

**Key Physical Observations:**
1. **Strict Temporal Sequence ($t_{del} < t_{inv}$):** In *every single run*, initial element deletion occurs **prior to any detectable corner Jacobian inversion**. At $t = 1.68\text{--}1.75$ $\mu$s, when dozens of nose elements have already been deleted, the inversion fraction is strictly **0.000%**.
2. **Post-Deletion Ghost Tracking Artifact:** In `ball_inversion.py`, the corner Jacobian metric `min_sj(pos[i][conn])` is evaluated over the fixed array `ball_conn_C3D8R` for all initial element labels **without filtering by element `STATUS`**. When an element deletes in Abaqus/Explicit, its internal stress is removed, but its nodes remain active as unconstrained point masses. As the plate drives past the crater, these orphan nodes tumble and drift apart. The geometric corner Jacobian calculated on the connectivity of an *already deleted element* inevitably turns negative.
3. **Loss of Geometric Support for Adjacent Intact Elements:** When an element abruptly vanishes ($u_f = 0$), the resisting face traction $\boldsymbol{\sigma} \cdot \mathbf{n}$ vanishes in a single time step ($< 1$ ns). The shared nodes on surviving neighbor elements are subjected to unconstrained external impact forces and intense tensile rarefaction waves, driving them into inverted configurations.
4. **Hourglassing and Distortion Under Sustained Strain:** In `vp6` (where element deletion was disabled entirely), elements did not invert at $1.8$ $\mu$s, but instead survived until $t = 65.6$ $\mu$s, accumulating extreme plastic strain ($\text{PEEQ} > 4.0$) and edge ratios $> 10\text{--}60$ until flank elements inverted and triggered a floating-point crash.

Thus, hex inversion is driven by **three coupled pathologies**:
- **Artifactual inversion:** Post-deletion geometric collapse of orphan nodes belonging to deleted elements.
- **Dynamic shock inversion:** Instantaneous traction release from abrupt element deletion causing shock reflection and nodal punch-through in surviving neighbors.
- **Constitutive/Kinematic inversion:** Lack of distortion control and suboptimal hourglass formulations allowing C3D8R zero-energy modes to collapse under extreme compressive and shear loads.

---

## 2. Comprehensive Analysis of Candidate Inversion Mechanisms

### Mechanism 1: Reduced-Integration Hourglassing (Zero-Energy Modes in C3D8R)

#### Mechanical & Mathematical Description
The standard first-order hexahedral element in Abaqus/Explicit is the 8-node brick with reduced integration (**C3D8R**), utilizing a single integration point at its centroid ($\xi = \eta = \zeta = 0$). An 8-node hexahedron possesses 24 degrees of freedom:
- 6 rigid-body modes (3 translations, 3 rotations).
- 6 physical uniform strain modes (3 direct strains, 3 engineering shear strains).
- **12 non-physical zero-energy hourglass modes** (orthogonal vectors that produce zero strain at the element centroid, $\boldsymbol{\varepsilon}_{hg}(\mathbf{0}) = \mathbf{0}$).

Under severe dynamic impact ($1000$ m/s), high-frequency spatial shock waves excite these zero-energy modes. The default hourglass control formulation in Abaqus/Explicit for solid elements is **`HOURGLASS=RELAX STIFFNESS`**, which applies an integral viscoelastic formulation based on Flanagan and Belytschko. Under high plastic flow, the relaxed stiffness can lose effective resistance against steady hourglass mode accumulation. While the volume at the centroid remains positive ($\det \mathbf{J}_c > 0$), element corners displace in opposing zigzag directions, collapsing the corner Jacobian matrix $\mathbf{J}_v = \partial \mathbf{x} / \partial \boldsymbol{\xi}$ at the vertices:
$$\det \mathbf{J}_v = (\mathbf{x}_{1} - \mathbf{x}_v) \cdot \left[ (\mathbf{x}_2 - \mathbf{x}_v) \times (\mathbf{x}_3 - \mathbf{x}_v) \right] \le 0$$
This produces a non-convex, inverted corner shape without any constitutive warning from the centroid integration point.

#### Abaqus Remedies & Exact Keywords
1. **Enhanced Assumed Strain (EAS) Hourglass Formulation:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_ENHANCED, hourglass=ENHANCED, element deletion=YES
   *Solid Section, elset=BALL_ELEMS, material=Steel, controls=CTRL_BALL_ENHANCED
   ```
   *Formulation:* Based on Puso (2000), `HOURGLASS=ENHANCED` constructs an enhanced assumed strain field. The hourglass resistance is derived directly from the physical tangent stiffness of the material rather than an arbitrary numerical penalty parameter. It provides strict resistance to hourglassing without locking or artificial energy growth.
2. **Viscous Hourglass Control for High-Rate Shock:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_VISCOUS, hourglass=VISCOUS, element deletion=YES
   *Solid Section, elset=BALL_ELEMS, material=Steel, controls=CTRL_BALL_VISCOUS
   ```
   *Formulation:* Generates artificial damping forces directly proportional to nodal hourglass velocities ($F_{hg} = -c_{hg} \dot{q}_{hg}$). As recommended in the Abaqus theory manual for high-velocity impact, blast, and shock waves, viscous damping specifically attenuates transient high-frequency oscillations before they accumulate into geometric distortion.
3. **Elastic Stiffness Hourglass Control:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_STIFF, hourglass=STIFFNESS, element deletion=YES
   ```
   *Formulation:* Pure elastic stiffness ($F_{hg} = -k_{hg} q_{hg}$) without viscoelastic relaxation.

---

### Mechanism 2: Lack of Distortion Control (Absence of Non-Linear Restoring Penalty)

#### Mechanical & Mathematical Description
In Abaqus/Explicit, standard continuum elements do not automatically prevent nodes from punching through opposite faces unless **distortion control** is explicitly activated. When an element is subjected to intense uniaxial compression or localized contact indentation:
- The characteristic thickness $L_e$ rapidly compresses toward zero.
- If the equivalent plastic strain is below the initiation threshold ($\text{PEEQ} < \varepsilon_D^{pl}$), the element continues to deform.
- Without a restoring constraint, a node can pass through the plane formed by its opposing face nodes, turning the element inside-out ($\det \mathbf{J} < 0$).
- In the baseline Valerie model (`output.inp`), the section control card is:
  ```abaqus
  *Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES
  ```
  **No distortion control was specified.** By default, `DISTORTION CONTROL=NO` for solid elements in Abaqus/Explicit!

#### Abaqus Remedies & Exact Keywords
```abaqus
*Section Controls, name=CTRL_BALL_DISTORT, element deletion=YES, distortion control=YES, length ratio=0.1
*Solid Section, elset=BALL_ELEMS, material=Steel, controls=CTRL_BALL_DISTORT
```
*Parameter Details:*
- `DISTORTION CONTROL=YES`: Activates a nonlinear penalty constraint that monitors the ratio of the element's current characteristic thickness to its initial characteristic length:
  $$r = \frac{L_{min}(t)}{L_0}$$
- `LENGTH RATIO = 0.1` (default 0.1, adjustable between 0.05 and 0.2): When $r$ falls below the specified threshold, Abaqus applies an internal nonlinear restoring force that acts like a progressive virtual spring resisting further collapse and strictly preventing corner inversion.

---

### Mechanism 3: Loss of Geometric Support After Neighbour Deletion (Rarefaction Waves & Ghost Tracking)

#### Mechanical & Mathematical Description
When Johnson-Cook damage criteria are satisfied in an element, `*DAMAGE EVOLUTION, TYPE=DISPLACEMENT` with value `0.` triggers instantaneous element deletion.
1. **Dynamic Traction Shock:** Before deletion, the element exerted an internal traction $\mathbf{t} = \boldsymbol{\sigma} \cdot \mathbf{n} \approx 1\text{--}2$ GPa across its boundary faces. When it vanishes within $\Delta t < 1$ ns, this traction instantaneously drops to zero. This step-function unloading sends an intense tensile rarefaction wave back into adjacent elements, inducing high-rate tensile and shear distortion.
2. **Unbalanced Boundary Nodes:** The nodes shared between the deleted element and surviving neighbors are now fully exposed on the exterior boundary. They receive external contact pressure without internal structural backing, causing them to be violently driven inward.
3. **The "Ghost Connectivity" Tracking Metric:** In `ball_inversion.py`, node positions of dead elements continue to be evaluated against `ball_conn_C3D8R`. Once deleted, orphan nodes have zero internal stiffness. Under inertia and contact interaction, they drift into unphysical spatial configurations, yielding negative corner Jacobians for elements that have already been deleted from the solver!

#### Abaqus Remedies & Exact Keywords
1. **Displacement/Energy-Based Progressive Softening:**
   Replace abrupt instantaneous failure with progressive post-initiation softening:
   ```abaqus
   *Damage Evolution, type=DISPLACEMENT, softening=LINEAR
    1.0e-5
   ```
   *Effect:* Decays stress from peak strength to zero over a finite nodal displacement ($u_f = 10\ \mu$m, representing thousands of explicit increments), eliminating the acoustic shock wave and smoothly transferring boundary loads to surviving elements.
2. **Maximum Degradation Clamping:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_MAXDEG, element deletion=YES, max degradation=0.85
   ```
   *Effect:* Clamps maximum damage at $D = 0.85$, retaining residual stiffness and damping to prevent unconstrained nodal blow-up.
3. **Element Deletion Disabled (`ELEMENT DELETION=NO`):**
   ```abaqus
   *Section Controls, name=CTRL_BALL_NODEL, element deletion=NO
   ```
   *Effect:* Completely eliminates orphan nodes; keeps all elements in the active solver mesh.

---

### Mechanism 4: Contact-Node Intrusion (Oversized Fiber Node Needle Punching)

#### Mechanical & Mathematical Description
In the baseline model:
- The ball nose is discretized with fine C3D8R hexes having edge lengths down to $L_e \approx 0.17$ mm (minimum edge $0.039$ mm).
- The fiber reinforcement is modeled using 1D discrete elements (T3D2 truss) whose nodes are collected into `EMBMESH_FIBER_NODES` with an assigned contact thickness:
  ```abaqus
  *Surface Property Assignment, property=THICKNESS
  EMBMESH_FIBER_NODES, 0.000617973861320424
  ```
- **The geometric mismatch:** The assigned contact sphere diameter ($0.618$ mm) is **$3.7\times$ larger than the smallest ball element edge ($0.17$ mm)**.
- Each fiber node acts as a point-mass, rigid spherical punch ($E_{fiber} = 72$ GPa vs steel yield $0.304$ GPa). When impacting at 1000 m/s, contact penalty forces are concentrated entirely onto isolated nodal points. As documented in T-050, this creates artificial contact pressure spikes of **213 to 852 GPa**.
- A concentrated point force of this magnitude punches an individual surface node through the rear face of a ball hex within a few increments, inverting the corner Jacobian before volumetric plastic strain can even develop at the Gauss point!

#### Abaqus Remedies & Exact Keywords
1. **Continuous Element-Based Beam Contact Surface:**
   ```abaqus
   *Element, type=B31, elset=FIBERS
   *Beam Section, elset=FIBERS, material=Fiber, section=CIRC, controls=EMBMESH_DELETE_ALL
    0.000316
    0., 0., -1.
   *Surface, type=ELEMENT, name=EMBMESH_FIBER_SURF
   FIBERS,
   ```
   *Effect:* Replaces point-node contact spheres with a continuous cylindrical contact tube, distributing contact pressure evenly along element faces.
2. **Reduced Fiber Contact Thickness:**
   ```abaqus
   *Surface Property Assignment, property=THICKNESS
   EMBMESH_FIBER_NODES, 0.000050
   ```
   *Effect:* Reduces contact thickness from $0.618$ mm to $0.050$ mm ($50\ \mu$m), eliminating the $3.7\times$ oversized rigid punch.
3. **Contact Penalty Scaling:**
   ```abaqus
   *Contact Controls Assignment, type=SCALE PENALTY
    , , 0.1
   ```
   *Effect:* Softens the contact spring stiffness by $10\times$, attenuating dynamic contact force spikes.

---

### Mechanism 5: Very Large Strain Rate & Shock Mismatch in Abrupt-Fail Damage

#### Mechanical & Mathematical Description
Under $1000$ m/s impact, the initial plastic strain rate reaches:
$$\dot{\varepsilon}^{pl} \approx \frac{v_0}{L_e} \approx \frac{1000\text{ m/s}}{1.7 \times 10^{-4}\text{ m}} \approx 5.8 \times 10^6\text{ s}^{-1}$$
In the original baseline deck, the Johnson-Cook damage card had $D_4 = -0.05279$ and $\dot{\varepsilon}_0 = 10^{-4}$ s$^{-1}$. At $\dot{\varepsilon} \approx 5.8 \times 10^6$ s$^{-1}$:
$$1 + D_4 \ln\left(\frac{\dot{\varepsilon}^{pl}}{\dot{\varepsilon}_0}\right) = 1 - 0.05279 \times \ln(5.8 \times 10^{10}) = 1 - 1.308 = -0.308$$
The failure strain became **negative**, causing instantaneous element deletion at $\text{PEEQ} = 0.000$. While changing $D_4$ to $+0.002$ in `b4` restored a positive failure strain ($1 + 0.002 \times 24.78 = 1.050$), the abrupt displacement evolution ($u_f = 0$) still caused elements to delete instantaneously upon reaching initiation, triggering the rarefaction shock waves and orphan node tumble described in Mechanism 3.

#### Abaqus Remedies & Exact Keywords
```abaqus
*Damage Initiation, criterion=JOHNSON COOK
 0.1152, 1.0116, -1.7684, 0.002, 0.5262, 1800., 293., 0.0001
*Damage Evolution, type=DISPLACEMENT, softening=LINEAR
 5.0e-5
```

---

### Mechanism 6: Kinematic Formulation & Objective Stress Integration (Kinematic Split & Second-Order Accuracy)

#### Mechanical & Mathematical Description
In Abaqus/Explicit, the default kinematic split for C3D8R is `KINEMATIC SPLIT=AVERAGE STRAIN`.
- Under large rotations and high shear rates, first-order central difference time integration of the Jaumann rate of Cauchy stress can accumulate artificial shear energy or volumetric locking.
- In rotating or highly sheared impactor zones, the element can shear into a rhomboid or self-intersecting configuration.

#### Abaqus Remedies & Exact Keywords
1. **Orthogonal Kinematic Split:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_ORTHO, kinematic split=ORTHOGONAL, element deletion=YES
   ```
   *Effect:* Calculates the strain increment using Flanagan-Belytschko orthogonal projection, preventing spurious volume strain and shear locking.
2. **Second-Order Accurate Kinematics:**
   ```abaqus
   *Section Controls, name=CTRL_BALL_2ND, second order accuracy=YES, element deletion=YES
   ```
   *Effect:* Integrates the rate of deformation tensor with second-order time accuracy, preserving rotational objectivity over large deformation paths. (Note: In Abaqus/Explicit, activating second-order accuracy automatically defaults the kinematic split to average strain).

---

### Mechanism 7: Element Conversion to SPH Particles (`ELEMENT CONVERSION=YES`)

#### Mechanical & Mathematical Description
In hypervelocity impact and severe penetration mechanics, continuum Lagrangian finite element meshes inevitably break down because the physical shear deformation exceeds the geometric capability of a hexahedral topology. Rather than deleting elements (which destroys mass, momentum, and impactor kinetic energy) or allowing distorted hexes to invert and abort the solver, Abaqus/Explicit provides **automatic element-to-particle conversion (SPH)**.
- When an individual C3D8R hex reaches a designated deformation threshold, Abaqus automatically replaces the element with a cluster of Smoothed Particle Hydrodynamics particles (**PC3D**).
- The generated SPH particles inherit the parent element's mass, momentum, velocity, stress state, and constitutive damage variables.
- Because SPH particles are meshless (governed by kernel interpolation rather than corner connectivity), **Jacobian inversion is eliminated by definition** while impactor mass and volume are 100% conserved!

#### Abaqus Remedies & Exact Keywords
```abaqus
*Section Controls, name=CTRL_BALL_SPH, element conversion=YES, conversion criterion=STRAIN
 0.6
*Solid Section, elset=BALL_ELEMS, material=Steel, controls=CTRL_BALL_SPH
```
*Parameters:*
- `ELEMENT CONVERSION=YES`: Enables conversion of C3D8R, C3D6, and C3D4 elements to PC3D particles.
- `CONVERSION CRITERION=STRAIN`: Specifies conversion when the maximum principal strain reaches the designated threshold (e.g. $\varepsilon_{max} = 0.6$). Alternative criteria include `STRESS` or `TIME`.

---

### Mechanism 8: Arbitrary Lagrangian-Eulerian (ALE) Adaptive Meshing

#### Mechanical & Mathematical Description
ALE adaptive meshing decouples the motion of the spatial mesh from the motion of the underlying material.
- In each explicit increment (or specified sweep interval), the interior nodes of the ball are repositioned using volume or Laplacian smoothing to optimize aspect ratios and maintain element convexity.
- The material state (stress, PEEQ, damage) is advected through the reorganized grid.

#### Abaqus Remedies & Exact Keywords
```abaqus
*Step, name=Impact, nlgeom=YES
*Dynamic, Explicit
, 1.2e-5
*Adaptive Mesh, elset=BALL_C3D8R, controls=ALE_CTRL
*Adaptive Mesh Controls, name=ALE_CTRL, meshing predictor=CURRENT, smoothing objective=UNIFORM
 10, 3, 0.5
```
*Parameters:*
- Placed inside the `*STEP` definition.
- `10, 3, 0.5`: Number of mesh sweeps (10), frequency in increments (every 3 increments), and weighting factor.

---

### Mechanism 9: Bulk Viscosity & Shock Wave Dispersion

#### Mechanical & Mathematical Description
The stable explicit time increment is governed by the CFL condition:
$$\Delta t \le \frac{L_{min}}{c_d} = \frac{L_{min}}{\sqrt{\frac{E(1-\nu)}{\rho(1+\nu)(1-2\nu)}}}$$
For the smallest ball element ($L_e \approx 0.039$ mm), $\Delta t_{stable} \approx 6.6$ ns. In ballistic shock waves, if the compressive shock front is narrower than the element width, the front face moves faster than stress can propagate to the back face, flattening the element to zero volume within a single increment. Abaqus applies bulk viscosity to introduce volumetric damping:
$$p_{bv} = b_1 \rho c_d L_e | \dot{\varepsilon}_{vol} | + b_2 \rho L_e^2 (\dot{\varepsilon}_{vol})^2$$
- $b_1$ (linear bulk viscosity, default $0.06$) damps high-frequency ringing.
- $b_2$ (quadratic bulk viscosity, default $1.2$) smears the shock front over 2 to 3 elements to prevent shock-induced inversion.

#### Abaqus Remedies & Exact Keywords
```abaqus
*Bulk Viscosity
 0.12, 2.4
```
*Effect:* Doubles linear and quadratic shock viscosity to suppress ballistic shock inversion.

---

## 3. Comprehensive Verification Matrix for ROAR (Abaqus 2024)

The table below summarizes all candidate remedies, their exact Abaqus/Explicit keywords, verification status on Penn State ROAR (Abaqus/Explicit 2024), and explicit documentation of any uncertainties:

| Remedy Formulation | Exact Abaqus Keyword & Parameter | Purpose / Isolated Mechanism | ROAR Support Status (Abaqus 2024) | Level of Certainty & Notes |
|---|---|---|---|---|
| **Distortion Control** | `*Section Controls, name=..., distortion control=YES, length ratio=0.1` | Prevents corner Jacobian inversion by nonlinear restoring penalty before deletion | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Standard feature for C3D8R in Explicit. |
| **Enhanced Hourglass** | `*Section Controls, name=..., hourglass=ENHANCED` | EAS tangent-stiffness formulation; suppresses C3D8R zero-energy modes under large plastic strain | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Fully supported for linear elastic and Johnson-Cook plasticity. |
| **Viscous Hourglass** | `*Section Controls, name=..., hourglass=VISCOUS` | Velocity-proportional damping; suppresses high-velocity shock ringing | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Traditional recommended setting for blast/shock. |
| **Element Deletion OFF** | `*Section Controls, name=..., element deletion=NO` | Keeps elements in mesh; isolates orphan node tracking artifact from real intact inversion | **Supported & Verified** | **High [Verified in vp6]**. Elements survive until extreme distortion. |
| **Orthogonal Kinematic Split** | `*Section Controls, name=..., kinematic split=ORTHOGONAL` | Centroid strain with orthogonal hourglass shape vectors; reduces shear locking | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Standard option for C3D8R. |
| **Second Order Accuracy** | `*Section Controls, name=..., second order accuracy=YES` | Second-order time integration of deformation rate tensor | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Automatically resets kinematic split to average strain. |
| **Smooth Fiber Contact** | `*Element, type=B31` + `*Surface, type=ELEMENT` | Replaces discrete 1D node contact with continuous element surface | **Supported & Verified** | **High [Verified in bt1/bt2 runs b1 and c1]**. Decks solved cleanly on ROAR. |
| **Thin Fiber Contact** | `*Surface Property Assignment, property=THICKNESS` on node set ($0.050$ mm) | Eliminates 3.7x oversized rigid spherical punch against 0.17 mm hexes | **Supported & Verified** | **High [Verified in T-049 deck 07]**. Valid keyword syntax. |
| **Penalty Scaling** | `*Contact Controls Assignment, type=SCALE PENALTY` (factor $0.1$) | Softens contact spring stiffness to attenuate contact pressure spikes | **Supported & Verified** | **High [Verified in ROAR_KNOWLEDGE.md]**. Valid within `*Contact`. |
| **Progressive Softening** | `*Damage Evolution, type=DISPLACEMENT, softening=LINEAR` ($u_f > 0$) | Eliminates infinite acceleration shock and rarefaction waves from abrupt deletion | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Standard Johnson-Cook evolution. |
| **Max Degradation** | `*Section Controls, name=..., max degradation=0.8` | Clamps maximum damage degradation | **Supported & Verified** | **High [Verified in bt2 c2/c3]**. Valid syntax on `*Section Controls`. |
| **Element to SPH Conversion** | `*Section Controls, name=..., element conversion=YES, conversion criterion=STRAIN` | Replaces severely distorted hexes with PC3D SPH particles, eliminating mesh inversion | **Supported in Explicit 2024** | **Medium-High [Verified in Abaqus 2024 docs, Recalled in this repo]**. Requires general contact domain to include particles; may affect stable time step. |
| **ALE Adaptive Meshing** | `*Adaptive Mesh, elset=BALL_C3D8R` + `*Adaptive Mesh Controls` | Dynamically smooths mesh during explicit simulation to prevent skewing | **Supported in Explicit 2024** | **Medium [Verified in Abaqus 2024 docs, Recalled in this repo]**. In models with interior element deletion, interaction with eroding faces can restrict smoothing sweeps. |
| **Shock Bulk Viscosity** | `*Bulk Viscosity` ($0.12, 2.4$) | Smears steep shock fronts across elements to prevent shock-induced pancake inversion | **Supported & Verified** | **High [Verified from Abaqus 2024 Reference Manual]**. Standard Explicit keyword. |

---

## 4. Key Recommendations for the Test Matrix

Based on the coupled physical mechanisms identified above:
1. **Prioritize Distortion Control and Hourglass Formulations:** The baseline Valerie deck utilized default relax-stiffness hourglassing without distortion control (`DISTORTION CONTROL=NO`). Testing `DISTORTION CONTROL=YES` and `HOURGLASS=ENHANCED` addresses the core numerical susceptibility of C3D8R elements under extreme compression.
2. **Differentiate Active vs. Ghost Inversion:** Deck 05 (`ELEMENT DELETION=NO`) is critical for proving whether elements invert *before* deletion or whether the reported inversion metric is an artifact of unconstrained post-deletion node tracking.
3. **Control Impact Geometry:** Deck 09 (impactor against a homogeneous plain elastic plate) isolates whether the ball inverts purely from flat impact shock and inertia, completely removing laminate and fiber interactions.
4. **Evaluate Combined Numerical Best-Practice:** Deck 10 combines distortion control, enhanced hourglassing, thin contact, and an O-grid mesh to test if synergistic stabilization eliminates both unphysical deletion and inversion.
