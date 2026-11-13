# Design Document: Odd-Count Through-Thickness Subdivision ($N_t \in \{1, 3, 5, \dots\}$)

**Task**: T-053  
**Author**: drafter  
**Target Module**: `embmesh` (`embmesh/plywise.py`, `embmesh/cli.py`, `embmesh/plyfibers.py`, `embmesh/plywise_contact.py`)  

---

## 1. Mathematical and Topological Formulation

### 1.1 Objective & Background
In the baseline plate meshing pipeline, each composite ply ($t_{ply} = 1.27\text{ mm}$ for Valerie's 20-ply plate impact deck `Vals.inp`) was represented by exactly one layer of C3D8R hexahedral elements. However, Valerie's published study (*"A numerical investigation into the ballistic impact response of composite plates"*, Section 3.2, p. 118) utilizes **three elements through the thickness of each individual ply** (totaling $20 \times 3 = 60$ element layers through the laminate thickness, corresponding to $177{,}600$ matrix elements).

To enable direct comparison and fidelity matching with Valerie's model while preserving the full suite of automation tools developed in `embmesh` (fiber embedded generation, cohesive interfaces, eroding ball contact, and VUEL ghost conversion), this document specifies the topological subdivision scheme for odd through-thickness layer counts $N_t \in \{1, 3, 5, \dots\}$.

---

### 1.2 Topology & Subdivision Geometry

Consider a single conforming hexahedral layer representing a ply part. Let:
- $\mathbf{s}_{full} \in \mathbb{R}^3$ be the median through-thickness vector of the plate.
- $N_{plies}$ be the number of plies in the laminate ($N_{plies} = 20$).
- $\mathbf{s}_{ply} = \frac{\mathbf{s}_{full}}{N_{plies}}$ be the step translation vector of one ply.
- $N_t \in \{1, 3, 5, \dots\}$ be the odd through-thickness subdivision factor.
- $\mathbf{s}_{elem} = \frac{\mathbf{s}_{ply}}{N_t}$ be the step translation vector of one subdivided element layer.

#### Node Subdivision & Numbering
Let column $c$ be defined by its bottom node $b \in \mathcal{N}_{bot}$ and its corresponding top node $t = \text{bottom\_to\_top}[b] \in \mathcal{N}_{top}$. Subdividing column $c$ into $N_t$ equal layers generates $N_t + 1$ node levels:
- **Level $0$** (exterior bottom face):
  $$\mathbf{x}_{c, 0} = \mathbf{x}_b, \quad \text{Node ID} = b$$
- **Level $N_t$** (exterior top face):
  $$\mathbf{x}_{c, N_t} = \mathbf{x}_b + \mathbf{s}_{ply}, \quad \text{Node ID} = t$$
- **Intermediate Levels $l \in \{1, \dots, N_t - 1\}$**:
  $$\mathbf{x}_{c, l} = \mathbf{x}_b + \frac{l}{N_t}\mathbf{s}_{ply}, \quad \text{Node ID} = b + l \cdot N_{stride}$$

To guarantee that node IDs never collide with any existing node in the part mesh across any level $l \in [1, N_t - 1]$, the node stride is chosen as the smallest power of 10 strictly greater than the maximum node ID:
$$N_{stride} = 10^{\max(4, \, \lceil \log_{10}(N_{max} + 1) \rceil)}$$
For `Vals.inp` with $N_{max} = 10{,}086$, $N_{stride} = 100{,}000$.

#### Element Subdivision & Connectivity
Each original element $e \in \mathcal{E}_{orig}$ is subdivided into $N_t$ elements along thickness, indexed by layer $m \in \{0, \dots, N_t - 1\}$:
$$\text{Element ID} = e + m \cdot E_{stride}, \quad E_{stride} = 10^{\max(4, \, \lceil \log_{10}(E_{max} + 1) \rceil)}$$
Let the 8-node local connectivity of original element $e$ be $\mathbf{C} = (n_0, n_1, \dots, n_7)$. Through `oriented_faces(pts, direction)`, we obtain:
- `bottom_face`, `top_face` $\in \{S1, \dots, S6\}$
- `local_pairs`: a list of 4 tuples $(\text{loc\_b}_k, \text{loc\_t}_k)$ where $\text{loc\_b}_k \in \{0, \dots, 7\}$ is the index in $\mathbf{C}$ on the bottom face, and $\text{loc\_t}_k \in \{0, \dots, 7\}$ is the matching index on the top face.

For layer $m \in \{0, \dots, N_t - 1\}$, the connectivity $\mathbf{C}^{(m)}$ is formed by replacing local nodes:
- At position $\text{loc\_b}_k$:
  $$\mathbf{C}^{(m)}[\text{loc\_b}_k] = \begin{cases} b_k & \text{if } m = 0 \\ b_k + m \cdot N_{stride} & \text{if } m > 0 \end{cases}$$
- At position $\text{loc\_t}_k$:
  $$\mathbf{C}^{(m)}[\text{loc\_t}_k] = \begin{cases} t_k & \text{if } m + 1 = N_t \\ b_k + (m + 1) \cdot N_{stride} & \text{if } m + 1 < N_t \end{cases}$$

#### Determinant of the Jacobian
Because every bottom node remains in its exact corresponding local bottom position and every top node remains in its matching local top position, element node ordering and cyclic orientation are strictly preserved.
Let $\mathbf{J}_{orig}(\xi, \eta, \zeta)$ be the Jacobian matrix of the original single-ply element, and $\mathbf{J}^{(m)}(\xi, \eta, \zeta)$ be the Jacobian matrix of the subdivided element in layer $m$. Since the geometry is uniformly scaled along the thickness parametric coordinate $\zeta$ by factor $1 / N_t$:
$$\det\left(\mathbf{J}^{(m)}\right) = \frac{1}{N_t} \det\left(\mathbf{J}_{orig}\right) > 0$$
Hence, no element inversion or negative Jacobian is possible.

---

## 2. Detailed Technical Aspects (a) through (e)

### (a) Fibers: Mid-Plane Placement & Diameter Validation
- **Mid-Plane Geometry**:
  In a ply with thickness $\mathbf{s}_{ply}$, the unidirectional fiber bed resides on the ply mid-plane:
  $$\mathbf{x}_{mid} = \mathbf{x}_{bot} + 0.5 \cdot \mathbf{s}_{ply}$$
  For any odd integer $N_t = 2k + 1$ (with $k \in \mathbb{N}$), the center layer index is:
  $$m_{mid} = \frac{N_t - 1}{2} = k$$
  The layer $m_{mid}$ spans through thickness from:
  $$\zeta_{bot, mid} = \frac{k}{2k + 1} = 0.5 - \frac{1}{2(2k + 1)}$$
  to:
  $$\zeta_{top, mid} = \frac{k + 1}{2k + 1} = 0.5 + \frac{1}{2(2k + 1)}$$
  The midpoint of layer $m_{mid}$ is:
  $$\frac{\zeta_{bot, mid} + \zeta_{top, mid}}{2} = \frac{2k + 1}{2(2k + 1)} = 0.5$$
  Therefore, the ply mid-plane coincides **identically** with the geometric mid-plane of the center element layer $m_{mid}$.
- **Host Element Filtering**:
  When passing elements to `ply_fibers(...)`, only the middle-layer elements:
  $$\mathcal{E}_{mid} = \left\{ e + m_{mid} \cdot E_{stride} \;\middle|\; e \in \mathcal{E}_{orig} \right\}$$
  are passed as host candidates. Every fiber segment centroid and node is therefore bounded strictly within layer $m_{mid}$.
- **Diameter vs Thickness Check**:
  In `embmesh/plyfibers.py`, the mesher verifies that fiber diameter $d$ does not exceed host thickness. For $N_t = 3$, the subdivided element thickness is:
  $$t_{elem} = \frac{1.27\text{ mm}}{3} \approx 0.4233\text{ mm}$$
  While Valerie's fiber diameter is $d = 0.632\text{ mm}$. If checked against the subdivided element thickness, $0.632\text{ mm} > 0.4233\text{ mm}$, which would falsely trigger `ValueError: fiber diameter exceeds ply thickness`.
  To resolve this, `ply_fibers(...)` now accepts `ply_thickness: float | None = None`. When provided, the geometric check tests $d \le t_{ply} = 1.27\text{ mm}$, which correctly succeeds ($0.632\text{ mm} \le 1.27\text{ mm}$).

---

### (b) Cohesive Surfaces Between Plies
- **Surface Isolation**:
  Abaqus surface-based cohesive behavior governs interlaminar separation between adjacent plies (e.g. `Ply-1_top` interacting with `Ply-2_bottom`).
  Internal matrix layers within a subdivided ply must share nodes and undergo standard continuum deformation without interlaminar cohesive traction-separation laws.
- **Top and Bottom Facet Assignment**:
  - `PLY_BOTTOM` consists exclusively of bottom faces of layer $m = 0$ elements:
    $$\text{PLY\_BOTTOM} = \left\{ (e, \text{bottom\_face}) \;\middle|\; e \in \mathcal{E}_{orig} \right\}$$
  - `PLY_TOP` consists exclusively of top faces of layer $m = N_t - 1$ elements:
    $$\text{PLY\_TOP} = \left\{ (e + (N_t - 1)E_{stride}, \text{top\_face}) \;\middle|\; e \in \mathcal{E}_{orig} \right\}$$
  - All intermediate faces (at levels $l = 1, \dots, N_t - 1$) share common nodes across adjacent layers $m$ and $m + 1$. No cohesive contact surfaces are defined on internal faces.

---

### (c) Ball Contact: Impact Surface & Node Tracking
- **Surface Facet Matching (`Surf-1`)**:
  In `Vals.inp`, the original impact surface `Surf-1` is an element-based surface defined on the impacted face of `Plate-1`.
  In `embmesh/plywise_contact.py`, `add_plywise_ball_contact` maps `Surf-1` facets to the exterior surface of `Ply-1`.
  With element ID stride $E_{stride}$, the facet matching routine was updated using modular arithmetic:
  $$e_{col} = e \pmod{E_{stride}}$$
  This ensures that whether `Surf-1` was defined on the bottom or top surface, it attaches strictly to the exterior faces of layer 0 (for bottom impact) or layer $N_t - 1$ (for top impact).
- **Node-Based Contact**:
  When `--plate-node-contact` is active, all nodes in `Ply-1` (including all through-thickness intermediate nodes) are included in the contact node set `EMBMESH_PLATE_CONTACT_NODES`, ensuring continuous contact coverage during indentation.

---

### (d) VUEL Volume-Fraction & Softening Implications
In `verification/roar/build_vals_plywise.py`, the user material option `--host-mode vuel-ghost` with subroutine `uel/VUEL_material.for` is supported.
- **Volume Fraction Distribution**:
  Because the fiber layer is hosted strictly in the center layer $m = m_{mid}$:
  - Outer layers ($m \ne m_{mid}$): Fiber volume is zero ($V_f = 0$). Remaining matrix volume fraction is $\eta = 1 - V_f = 1.0$.
  - Center layer ($m = m_{mid}$): Contains all fiber segments across the ply. The host element volume is $V_{elem} = \frac{1}{N_t} V_{ply}$. Thus, the local fiber volume fraction is scaled by $N_t$:
    $$V_{f, mid} \approx N_t \cdot V_{f, ply} \approx 3 \times 0.39 = 1.17$$
- **Matrix Constitutive Response in `VUEL_material.for`**:
  - In `VUEL_material.for` (lines 420-460), the matrix volume fraction is computed as:
    $$\eta = \max(1.0 - V_f, \, 10^{-6})$$
  - When $V_f \ge 1.0$, $\eta$ is floored at $10^{-6}$.
  - The elemental mass and stress contributions of the matrix in the center layer scale directly with $\eta$. With $\eta = 10^{-6}$, the center-layer matrix contributes virtually zero stiffness and zero inertial mass; the center layer behaves almost purely as an embedded fiber truss/beam cage.
  - In lines 720-750 of `VUEL_material.for`, the characteristic element length used for fracture energy regularization is:
    $$L = (\eta V_0)^{1/3}$$
    When $\eta = 10^{-6}$, $L$ collapses by a factor of $(10^{-6})^{1/3} = 10^{-2}$ ($100\times$ reduction). This severely reduces the plastic displacement at failure:
    $$u_f^p = \frac{2 G_f}{\sigma_{y0}}$$
    causing the matrix in the center layer to degrade rapidly upon yielding, while the outer layers ($V_f = 0, \eta = 1$) preserve full matrix stiffness, strength, and ductile softening.

---

### (e) Symmetry & Boundary Sets
- **Intermediate Node Propagation**:
  Boundary conditions in `Vals.inp` constrain symmetric and clamped edges (e.g. `fix` ENCASTRE, `X` XSYMM, `Y` YSYMM).
  In the original single-layer mesh, a column $c$ on a boundary had both bottom node $b \in \mathcal{S}_{bc}$ and top node $t \in \mathcal{S}_{bc}$.
  When subdividing into $N_t$ layers, the physical boundary condition applies to the **entire continuous through-thickness edge**.
  The mesher inspects all part-level and assembly-level node sets:
  $$\text{If } b \in \mathcal{S}_{bc} \text{ and } t \in \mathcal{S}_{bc} \implies b + l \cdot N_{stride} \in \mathcal{S}_{bc} \quad \forall l \in \{1, \dots, N_t - 1\}$$
- **Fiber Boundary Snapping**:
  In `embmesh/plywise_vuel.py` (`_finish_boundary_fibers`), fiber end nodes are projected to the perimeter boundary quad faces. Because the quad faces of subdivided elements have intermediate nodes that are now present in the host boundary sets, fiber end nodes are correctly recognized as belonging to symmetry planes `X` and `Y`, receiving proper symmetry boundary constraints.

---

## 3. Backward Compatibility & Verification
- For default `--through-thickness 1`, the mesher branches to the original single-element algorithm, guaranteeing byte-identical output to the legacy mesher.
- Unit tests in `tests/test_plywise_through_thickness.py` verify regression, invalid count rejection (even numbers and non-positive integers raise `EmbmeshError` and exit code 5), node/element count formulas, fiber containment, and surface isolation.
