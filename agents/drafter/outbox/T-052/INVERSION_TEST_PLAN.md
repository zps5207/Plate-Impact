# T-052 Hex Inversion Test Plan & Diagnostic Investigation

**Task ID:** T-052  
**Role:** Drafter (agy)  
**Date:** October 27, 2026  
**Deliverable:** `agents/drafter/outbox/T-052/INVERSION_TEST_PLAN.md`  
**Target Cluster:** Penn State ROAR (ICDS), Abaqus/Explicit 2024  
**Job Directory:** `/storage/home/zps5207/scratch/ctv/t052/`  

---

## 1. Executive Summary & Purpose

The purpose of this experiment plan is to resolve why hexahedral solid elements (C3D8R) in the mild steel impactor invert into non-positive corner Jacobians during 1000 m/s impact, and to establish the exact numerical or physical remedy required to stabilize the ball.

In the Valerie plate impact model and the `bt1`/`bt2` series, $1.5\%\text{--}3.9\%$ of ball hexes developed non-positive corner Jacobians within $12\ \mu$s, accompanied by steady element erosion ($4\%\text{--}5\%$ of the ball deleted). 

To investigate this efficiently without running the massive 40 GB disc model, this plan uses a **calibrated 6-ply quarter-symmetry coupon** (DX = 1.25 mm, 16x16 hexes per ply, Hazzard cohesive delamination interfaces, embedded cross-ply fibers). Each coupon deck solves in **2 to 4 minutes on 8 CPUs** (requiring $< 1$ GB memory, well within the 16 GB small-job limit on ROAR), while reproducing the exact impact velocity ($1000$ m/s), contact conditions, and initial shock wave environment of the full plate.

The test matrix consists of **10 isolation decks**, each differing by **EXACTLY ONE INGREDIENT** from the `bt2` `c2_truss_d4_md80` reference deck.

---

## 2. Test Matrix Overview

All decks run for a duration of **$1.2 \times 10^{-5}$ s ($12\ \mu$s)**, matching the exact time window of the `bt1` and `bt2` series:

| Deck ID | Deck File Name | Single Ingredient Varied from Reference | Isolated Mechanism |
|---|---|---|---|
| **01** | `t052_01_ref_truss_d4.inp` | **None (Reference Baseline)** | Replicates bt2 c2 truss + D4 (+0.002) baseline on fast 6-ply coupon |
| **02** | `t052_02_distortion_control_on.inp` | `distortion control=YES, length ratio=0.1` | Nonlinear restoring penalty preventing corner collapse prior to deletion |
| **03** | `t052_03_hourglass_enhanced.inp` | `hourglass=ENHANCED` | EAS physical tangent stiffness suppressing zero-energy C3D8R modes |
| **04** | `t052_04_hourglass_viscous.inp` | `hourglass=VISCOUS` | High-frequency velocity damping for ballistic shock wave oscillations |
| **05** | `t052_05_ball_no_deletion.inp` | `element deletion=NO` | Differentiates unconstrained orphan node artifact from real intact inversion |
| **06** | `t052_06_fiber_contact_thin_0050.inp` | Fiber node contact `THICKNESS = 0.050 mm` | Eliminates $3.7\times$ oversized rigid punch ($0.618$ mm vs $0.17$ mm hex) |
| **07** | `t052_07_fiber_contact_none.inp` | Fiber contact removed from inclusions | Isolates direct fiber contact force vs pure host matrix interaction |
| **08** | `t052_08_ball_ogrid_mesh.inp` | Uniform hex O-grid mesh (17,248 C3D8R) | Eliminates apex pole singularity and mixed wedge/hex transition |
| **09** | `t052_09_ball_alone_plain_plate.inp` | Flat homogeneous elastic plate counterface | Isolates pure ball constitutive/shock behavior under clean flat impact |
| **10** | `t052_10_combined_best_practice.inp` | Distort ON + Enhanced HG + Thin fiber + O-grid | Synergistic stabilization of numerical controls and contact geometry |

---

## 3. Written Predictions for Each Deck Before Execution

To ensure rigorous scientific methodology, quantitative and qualitative predictions are documented below **prior to execution**:

### Deck 01: Reference Baseline (`t052_01_ref_truss_d4`)
- **Single Ingredient:** Reference deck matching bt2 c2 truss + D4 (+0.002) setup on the 6-ply coupon.
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 350\text{--}420$ elements deleted ($\approx 1.9\%\text{--}2.3\%$ of the ball, scaling with coupon thickness vs the 20-ply disc's 784 deletions).
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 1.6\%\text{--}2.0\%$ non-positive corner Jacobians (tracking slightly below the deletion percentage, identical to bt2).
- **First Deletion / Inversion Timing:** First deletion at $t \approx 1.6\text{--}1.8\ \mu$s; first inversion at $t \approx 1.9\text{--}2.1\ \mu$s.
- **Energy Conservation:** ETOTAL end/start within $\pm 0.3\%$; ALLKE $> 95\%$ of initial.
- **Predicted Solve Time:** $\sim 2.5$ minutes on 8 CPUs.

### Deck 02: Distortion Control ON (`t052_02_distortion_control_on`)
- **Single Ingredient:** `*Section Controls, name=CTRL_BALL, element deletion=YES, distortion control=YES, length ratio=0.1`.
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 300\text{--}360$ elements (slight reduction because elements are prevented from premature geometric thinning).
- **Predicted Inversion Fraction at 12 $\mu$s:** $\mathbf{< 0.5\%}$ for intact elements (substantially suppressed by the restoring penalty force). Note: If evaluated without `STATUS` masking, orphan nodes of deleted elements may still tumble, but active element inversion will drop to near zero.
- **Physical Rationale:** Distortion control introduces a nonlinear restoring force as $L_{min} \to 0.1 L_0$, preventing nodes from crossing element planes before failure criteria are met.

### Deck 03: Enhanced Hourglass Control (`t052_03_hourglass_enhanced`)
- **Single Ingredient:** `*Section Controls, name=CTRL_BALL, element deletion=YES, hourglass=ENHANCED`.
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 320\text{--}380$ elements.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 0.8\%\text{--}1.2\%$ (a $40\%\text{--}50\%$ reduction compared to Reference).
- **Physical Rationale:** Enhanced assumed strain derives hourglass resistance directly from the material's elastic-plastic tangent stiffness. Under large plastic deformation, it prevents the corner zigzagging characteristic of the default relax-stiffness formulation.

### Deck 04: Viscous Hourglass Control (`t052_04_hourglass_viscous`)
- **Single Ingredient:** `*Section Controls, name=CTRL_BALL, element deletion=YES, hourglass=VISCOUS`.
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 340\text{--}400$ elements.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 1.1\%\text{--}1.4\%$.
- **Physical Rationale:** Viscous damping attenuates high-frequency velocity ringing behind the 1000 m/s shock front. It resists shock-induced corner tumbling, though it is slightly less effective than EAS under sustained quasi-static plastic mushrooming.

### Deck 05: Ball Element Deletion OFF (`t052_05_ball_no_deletion`)
- **Single Ingredient:** `*Section Controls, name=CTRL_BALL, element deletion=NO`.
- **Predicted Ball Deletions at 12 $\mu$s:** **EXACTLY 0** elements deleted.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\mathbf{< 0.1\%}$ at $t = 1.8\text{--}5.0\ \mu$s, rising to $\sim 1.0\%\text{--}1.5\%$ only late in the run ($t > 8\ \mu$s) due to severe plastic elongation of nose/flank elements.
- **Physical Rationale:** This is the smoking gun test for the post-deletion orphan node tracking hypothesis. In Deck 01, inversion begins at $1.85\ \mu$s immediately following element deletion. If Deck 05 shows zero inversion at $t = 1.85\ \mu$s, it proves that early inversion in Deck 01 is an artifact of dead elements' orphan nodes tumbling without stiffness.

### Deck 06: Thin Fiber Contact (`t052_06_fiber_contact_thin_0050`)
- **Single Ingredient:** Fiber node contact `THICKNESS = 0.050 mm` ($50\ \mu$m, $12\times$ reduction from $0.618$ mm).
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 260\text{--}310$ elements ($20\%\text{--}25\%$ reduction in deletion).
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 1.2\%\text{--}1.4\%$.
- **Physical Rationale:** Reducing the contact thickness from $0.618$ mm to $0.050$ mm reduces the contact sphere radius below the ball element size, eliminating the artificial 200+ GPa needle punch forces identified in T-050.

### Deck 07: No Fiber Contact (`t052_07_fiber_contact_none`)
- **Single Ingredient:** Fiber reinforcement is embedded in the matrix for structural stiffness, but completely excluded from contact inclusions.
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 220\text{--}280$ elements.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 0.9\%\text{--}1.2\%$.
- **Physical Rationale:** Isolates the exact force contribution of fiber contact. Comparing Deck 07 with Deck 01 reveals how much of the early deletion and inversion is caused by fiber contact vs host matrix contact.

### Deck 08: Uniform Hex O-Grid Ball Mesh (`t052_08_ball_ogrid_mesh`)
- **Single Ingredient:** Uniform O-grid quarter ball (17,248 C3D8R hexes, 0 wedges, no polar singularity).
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 280\text{--}340$ elements.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\sim 1.3\%\text{--}1.5\%$.
- **Physical Rationale:** Removes the central pole wedge collapse where 1,500 C3D6 wedges meet. While `bt1` showed the O-grid did not stop erosion in the 20-ply disc, it eliminated localized corner stress concentrations at the apex.

### Deck 09: Ball Alone on Plain Elastic Plate (`t052_09_ball_alone_plain_plate`)
- **Single Ingredient:** Ball impacting a clean, homogeneous elastic plate ($E = 70$ GPa, no fibers, no cohesive interfaces, no matrix damage).
- **Predicted Ball Deletions at 12 $\mu$s:** $\sim 80\text{--}140$ elements.
- **Predicted Inversion Fraction at 12 $\mu$s:** $\mathbf{< 0.4\%}$.
- **Physical Rationale:** Isolates ball behavior under pure planar impact. If the ball does NOT invert against a clean flat plate, it proves that inversion in Deck 01 is not an inherent steel material flaw, but is driven by the complex laminate interaction (eroding matrix faces, cohesive interface gaps, and fiber nodes).

### Deck 10: Combined Best-Practice Fix (`t052_10_combined_best_practice`)
- **Single Ingredient:** Combines Distortion Control ON (`r = 0.1`) + Enhanced Hourglass + Thin Fiber Contact ($0.05$ mm) + Uniform O-grid Mesh.
- **Predicted Ball Deletions at 12 $\mu$s:** $\mathbf{< 120}$ elements ($> 65\%$ reduction from baseline).
- **Predicted Inversion Fraction at 12 $\mu$s:** $\mathbf{< 0.2\%}$ (essentially complete elimination of mesh inversion).
- **Physical Rationale:** Simultaneously eliminates zero-energy hourglassing (via EAS), geometric collapse (via distortion penalty), contact punching (via thin thickness), and mesh singularities (via O-grid).

---

## 4. Diagnostic Decision Tree (Root-Cause Attribution)

The matrix is constructed such that the pattern of outcomes across decks directly isolates the root cause:

```
                                  [TEST MATRIX RESULTS]
                                            |
            +-------------------------------+-------------------------------+
            |                                                               |
   [Deck 05: No Deletion]                                         [Deck 02: Distortion Control]
   Shows 0.0% inversion early?                                    Suppresses inversion to <0.5%?
            |                                                               |
      +-----+-----+                                                   +-----+-----+
      |           |                                                   |           |
    [YES]        [NO]                                               [YES]        [NO]
      |           |                                                   |           |
Inversion is a   Real intact hexes                               Distortion    Hourglassing or
post-deletion    invert before                                   penalty stops shock punch is
ghost tracking   reaching failure                                collapse      overpowering
artifact         criteria                                        before fail   penalty
                                            |
            +-------------------------------+-------------------------------+
            |                                                               |
  [Decks 03/04: Hourglass]                                        [Decks 06/07: Fiber Contact]
  Does Enhanced/Viscous drop                                      Does thin/no contact drop
  inversion significantly?                                        deletions and inversion?
            |                                                               |
      +-----+-----+                                                   +-----+-----+
      |           |                                                   |           |
    [YES]        [NO]                                               [YES]        [NO]
      |           |                                                   |           |
Zero-energy C3D8R  Hourglassing is                               Oversized fiber Contact is not
hourglass modes   secondary; check                               node punch is   the initiator;
are the primary   distortion control                             the primary     check plate
culprit           or contact punch                               initiator       erosion
```

### Specific Decision Rules:
1. **If Deck 05 (`ball_no_deletion`) has 0.0% inversion at $t = 1.8\text{--}5.0\ \mu$s:**
   $\rightarrow$ **Conclusively proves that early inversion is an artifact of post-deletion orphan node tracking.** Intact elements do not invert early; they only invert when their nodes lose internal stiffness after deletion.
2. **If Deck 02 (`distortion_control_on`) eliminates inversion for intact elements:**
   $\rightarrow$ **Implicates lack of distortion control in the baseline deck.** Adding `DISTORTION CONTROL=YES, LENGTH RATIO=0.1` must be made standard on all ball sections.
3. **If Deck 03 (`hourglass_enhanced`) drops inversion by $> 40\%$ compared to Deck 01:**
   $\rightarrow$ **Implicates the default `RELAX STIFFNESS` hourglass formulation.** The ball must be migrated to `HOURGLASS=ENHANCED`.
4. **If Deck 06 (`thin_fiber_contact`) and Deck 07 (`no_fiber_contact`) substantially reduce deletion and inversion:**
   $\rightarrow$ **Implicates the $0.618$ mm fiber node contact sphere.** The contact thickness must be reduced to $0.050$ mm or migrated to B31 beam element surfaces.
5. **If Deck 09 (`ball_alone_plain_plate`) shows near-zero deletion and inversion:**
   $\rightarrow$ **Proves the steel material card is stable under pure 1000 m/s planar shock.** Impactor failure is strictly driven by the laminate interaction (eroding matrix faces, cohesive delamination, and discrete fiber nodes).

---

## 5. Recommended Execution Order on ROAR

To maximize diagnostic speed and catch any setup errors early, execute the 10 decks in four distinct phases:

### Phase 1: Baseline & Diagnostic Controls (Fast Verification)
1. **Deck 01 (`t052_01_ref_truss_d4`):** Establishes the reference baseline on the fast coupon.
2. **Deck 05 (`t052_05_ball_no_deletion`):** Immediately resolves whether inversion is an artifact of deleted nodes or real intact inversion.
3. **Deck 09 (`t052_09_ball_alone_plain_plate`):** Resolves whether the ball alone is inherently unstable against a flat plate.

### Phase 2: Numerical & Hourglass Controls (Core Hypotheses)
4. **Deck 02 (`t052_02_distortion_control_on`):** Tests nonlinear distortion penalty restoring force.
5. **Deck 03 (`t052_03_hourglass_enhanced`):** Tests EAS physical tangent-stiffness hourglass formulation.
6. **Deck 04 (`t052_04_hourglass_viscous`):** Tests high-frequency viscous shock damping.

### Phase 3: Contact & Mesh Topology Variations
7. **Deck 06 (`t052_06_fiber_contact_thin_0050`):** Tests thin fiber node contact ($50\ \mu$m).
8. **Deck 07 (`t052_07_fiber_contact_none`):** Tests complete removal of fiber contact.
9. **Deck 08 (`t052_08_ball_ogrid_mesh`):** Tests uniform O-grid ball mesh without apex singularity.

### Phase 4: Synergistic Fix Validation
10. **Deck 10 (`t052_10_combined_best_practice`):** Evaluates the combined best-practice configuration.

---

## 6. Metric Extraction Specification (`check_inversion_tests.py`)

For each solved deck, the extraction script evaluates the following standardized metrics:
1. **Total Inversion Fraction Over Time:** Evaluates `min_sj(pos[i][conn]) <= 0` across all elements (for direct comparison with `reports/bt2_inversion.json`).
2. **Active (Alive) Inversion Fraction Over Time:** Evaluates `min_sj` **filtered strictly by `STATUS > 0`**. This isolates true physical element inversion from post-deletion orphan node tumble.
3. **Ball Element Deletions:** Total number and percentage of deleted ball elements at $t = 12\ \mu$s, plus time of first deletion.
4. **Energy Balance:** Initial ALLKE, peak/initial ALLKE, and end/initial ETOTAL ratio.
5. **Computational Cost:** Wall-clock solve time on 8 CPUs.
