# Reproducing Diagnostic Coupons for Own-Ply VUINTERACTION (T-057)

This directory contains two minimal, high-speed reproducing coupon models designed to execute in under 10 seconds on 1 CPU. Each deck isolates a specific physical and numerical failure mechanism identified in the T-057 investigation.

---

## 1. Coupon A: Fiber Sliding Across Facet Boundaries (`coupon_h1_sliding.inp`)

### Mechanism Isolated
Tests **Hypothesis H1** (State variable cross-talk and cross-facet baseline resetting).
- Evaluates whether solution-dependent state variables (`STATE`) are attached to the slave node or the proximity pair.
- Determines whether a fiber node with an initial overclosure ($d = 50\ \mu\text{m}$) retains its baselined zero-force state as it slides across the boundary between two adjacent master facets, or whether proximity evaluation against adjacent facets causes cross-talk, wipes $d_0 \to 0$, and unleashes sudden penalty forces.

### Deck Details
- **Mesh:** 
  - Host: Two adjacent C3D8R hex elements ($1.0\text{ mm} \times 1.0\text{ mm} \times 0.5\text{ mm}$ each) sharing a vertical interface at $X = 1.0\text{ mm}$. Top surface at $Z = 0.0$.
  - Fiber: 2-node T3D2 truss at $Z = -0.05\text{ mm}$ (embedded $50\ \mu\text{m}$ below the top master surface, giving initial kinematic overclosure $d = +50\ \mu\text{m}$).
- **Kinematics:** Base of host is fixed. Fiber nodes are given a constant horizontal sliding velocity $v_x = 50.0\text{ m/s}$. The leading fiber node crosses the facet boundary at $X = 1.0\text{ mm}$ at $t = 12.0\ \mu\text{s}$.
- **Contact:** Node-based slave surface against element-based master surface, using `FiberHostBaseline` with `TRACKING THICKNESS = 0.0005 m`.

### Execution Command (ROAR)
```bash
abaqus job=coupon_h1_sliding input=coupon_h1_sliding.inp user=verification/roar/fiberhost_t056/vuint_bigforce.for double=both interactive
```

### What to Look for in the Log (`vuint_big.txt` and `.sta`)
1. **At $t = 0$ ($0 \le t < 12\ \mu\text{s}$):**
   - Check initialization in `vuint_big.txt`: Node 2 should register initial overclosure $d \approx 5.0 \times 10^{-5}\text{ m}$. Baseline routine sets $d_0 = 50\ \mu\text{m}$.
   - Effective penetration $d_{eff} = d - d_0 = 0.0$. Total energy $ETOTAL$ should remain completely flat.
2. **At $t \approx 12\ \mu\text{s}$ (Boundary Crossing):**
   - Watch for `BIG` rows in `vuint_big.txt`.
   - When Node 2 approaches $X = 1.0\text{ mm}$, both Element 1 and Element 2 facets enter the proximity block.
   - Look at columns `mst1..4`, `d`, `d0`, and `press`.

### Expected Outcomes per Hypothesis
- **Under H1 (Confirmed):** Because state is stored per slave node, proximity evaluation against the second facet or side face resets $d_0 \to 0$. In the subsequent pass, $d_{eff}$ jumps from 0 to $50\ \mu\text{m}$. Logger emits a `BIG` line with $p \approx 10\text{ MPa}$ ($1.0 \times 10^7\text{ Pa}$), triggering an artificial contact force spike and kinetic energy disturbance at the facet interface.
- **Under Null Hypothesis (State is per-pair):** If Abaqus maintained independent state per master facet, Node 2 would smoothly transition across $X = 1.0\text{ mm}$, initializing $d_{0,2} = 50\ \mu\text{m}$ on Facet 2 without disturbing Facet 1, maintaining zero contact force and perfectly flat $ETOTAL$ throughout.

---

## 2. Coupon B: Interior Face Exposure upon Element Deletion (`coupon_h2_erosion.inp`)

### Mechanism Isolated
Tests **Hypotheses H2 and H3** (Newly exposed `INTERIOR` faces with pre-existing interior fiber nodes, and contact force transfer to degrading/orphan nodes).
- Evaluates what happens when a host element containing an embedded fiber node is deleted mid-run, exposing an interior boundary facet within the 0.5 mm tracking zone.
- Determines whether the newly exposed interior face treats the existing fiber node as an un-baselined deep penetration, causing contact force explosion and time-step collapse.

### Deck Details
- **Mesh:** 
  - Host: Column of 2 stacked C3D8R hex elements ($1.0\text{ mm} \times 1.0\text{ mm} \times 1.0\text{ mm}$ each).
    - Element 1 (bottom, $Z \in [0, 1\text{ mm}]$): Surviving elastic host.
    - Element 2 (top, $Z \in [1, 2\text{ mm}]$): Sacrificial host with ductile damage ($\epsilon_f = 0.005$, displacement at failure = 0).
  - The interface between Element 1 and Element 2 is an **`INTERIOR`** facet at $Z = 1.0\text{ mm}$.
  - Fiber: T3D2 truss embedded inside Element 2 at $Z = 1.2\text{ mm}$ (positioned $0.2\text{ mm}$ above the interior interface).
- **Kinematics:** Base of Element 1 is fixed. Top of Element 2 is pulled upward at $v_z = 20.0\text{ m/s}$. Element 2 reaches failure strain $\epsilon = 0.005$ and erodes at $t \approx 1.0\ \mu\text{s}$.
- **Contact:** Host surface defined with `Host.ALL_HOST_ELEMS, INTERIOR`. Tracking thickness = $0.0005\text{ m}$.

### Execution Command (ROAR)
```bash
abaqus job=coupon_h2_erosion input=coupon_h2_erosion.inp user=verification/roar/fiberhost_t056/vuint_bigforce.for double=both interactive
```

### What to Look for in the Log (`vuint_big.txt`, `.sta`, and history output)
1. **For $t < 1.0\ \mu\text{s}$ (Pre-Deletion):**
   - Element 2 is intact (`STATUS = 1.0`). Fiber node is at $Z = 1.2\text{ mm}$.
   - Proximity to exterior faces has negative penetration (open gap), so $d_0$ initializes to 0.0. Contact pressure is zero.
2. **At $t \approx 1.0\ \mu\text{s}$ (Erosion Event):**
   - Element 2 erodes (`STATUS \to 0`).
   - The interior face at $Z = 1.0\text{ mm}$ becomes an active master contact face.
   - The fiber node is situated at $Z \approx 1.2\text{ mm}$. With fiber radius $r = 0.316\text{ mm}$, the distance $0.20\text{ mm} < 0.316\text{ mm}$.
   - General Contact detects penetration $d \approx +116\ \mu\text{m}$.
   - In `vuint_big.txt`, check whether a `BIG` line fires immediately upon deletion.
   - In `coupon_h2_erosion.sta`, observe whether stable time increment $\Delta t$ collapses.

### Expected Outcomes per Hypothesis
- **Under H2/H3 (Confirmed):** Because the interior face was not active at $t=0$, its penetration was never baselined ($d_0 = 0.0$). The routine computes $d_{eff} = 116\ \mu\text{m}$, producing $p = 2 \times 10^{11} \times 1.16 \times 10^{-4} \approx 23.2\text{ MPa}$. The force propels the freed fiber node and top nodes of Element 1 into high velocities, causing an energy divergence and time-step collapse.
- **Under Null Hypothesis (Interior faces benign):** If exposed interior faces handled embedded nodes without spurious penetration, $d_{eff}$ would remain zero, contact forces would stay bounded, and $\Delta t$ would remain near $7 \times 10^{-8}\text{ s}$.
