# T-008: Next Experiments on ROAR to Separate and Confirm Hypotheses

This document specifies four self-contained experiments (ODB queries and small deck variants) for the Hub to execute on ROAR. Each experiment defines the exact script or input modification, what to extract, and explicit criteria confirming or rejecting the corresponding hypothesis.

---

## EXPERIMENT 1 (EXP-01): ODB Query — Cross-Referencing Far-Field Deletions with Fiber Trajectories

### Hypothesis Tested
**Explanation 3 (Fiber Shear Metric Inversion):** Confirms that ghosts deleted far from the crater ($r > 20\text{ mm}$) despite intact `VU1` elements were driven by shear traction transmitted from embedded fibers under tension.

### Exact Request for the Hub to Run on ROAR
Run the following script against the existing `flat_v2.odb`:
```python
# Save as query_fiber_deletions.py and run via: abaqus python query_fiber_deletions.py
import math
from odbAccess import openOdb

odb = openOdb("flat_v2.odb")
root = odb.rootAssembly
plate = root.instances["PLATE-1"]
fibers = root.instances["EMBFIB-1"]
last_frame = odb.steps["Step-1"].frames[-1]

status_field = last_frame.fieldOutputs["STATUS"]
# Find all deleted ghost elements (label > 24000, STATUS == 0)
deleted_ghosts = []
for val in status_field.values:
    if val.elementLabel > 24000 and val.data == 0.0:
        deleted_ghosts.append(val.elementLabel)

# Fiber y-coordinates (fibers run along X and Y axes)
# Plate dimensions: quarter model X >= 0, Y >= 0
far_deleted_coords = []
for label in deleted_ghosts:
    host_elem = plate.elements[label - 24000]
    # compute centroid
    nodes = [plate.nodes[n - 1].coordinates for n in host_elem.connectivity]
    xc = sum(pt[0] for pt in nodes) / 8.0
    yc = sum(pt[1] for pt in nodes) / 8.0
    zc = sum(pt[2] for pt in nodes) / 8.0
    r = math.sqrt(xc**2 + yc**2)
    if r > 0.020:  # r > 20 mm
        far_deleted_coords.append((label, xc, yc, zc, r))

print("Total far-field deleted ghosts (r > 20 mm): %d" % len(far_deleted_coords))

# Check alignment: along fiber lines, either xc or yc is localized near fiber spacing
# Output first 20 coordinates
for item in far_deleted_coords[:20]:
    print("Ghost %d: r=%.2f mm, (x=%.4f, y=%.4f, z=%.4f)" % (item[0], item[4]*1000, item[1], item[2], item[3]))
```

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):** $> 85\%$ of far-field deleted ghosts lie along narrow bands aligned with fiber axes (0° and 90°), with peak strain concentrated in shear components ($\text{LE}_{13}, \text{LE}_{23}$).
- **REJECTED (FAIL):** Deleted ghosts are distributed uniformly or randomly across the far field, indicating boundary reflection or numerical noise rather than fiber traction.

---

## EXPERIMENT 2 (EXP-02): Deck Variant — Calibrated Ghost Yield Threshold for 1D Confined Strain

### Hypothesis Tested
**Explanation 2 (Confined Compression Strain Gap):** In 1D uniaxial strain, the ghost yield strain is $\epsilon_y = \frac{\sigma_{y0}}{2G} = 16.84\%$, whereas the `VU1` threshold is $\text{EPS\_FAIL} = 11.38\%$. Lowering the ghost yield stress from $61.1\text{ Pa}$ to $41.3\text{ Pa}$ makes $\epsilon_y = \frac{41.3}{362.86} = 0.1138$, synchronizing J2 yield with the VU1 threshold under confined compression.

### Exact Request for the Hub to Run on ROAR
1. Modify `flat_v2_output.inp` lines 451807–451809:
   ```abaqus
   *Plastic, extrapolation=LINEAR
   41.3, 0
   50.0, 2
   ```
2. Submit job:
   ```bash
   abaqus job=Flatv2_TunedYield input=Flatv2_TunedYield.inp user=VUEL_failure.for cpus=8 mp_mode=threads interactive
   ```
3. Run extraction:
   Check whether the 11 criterion-mismatch hosts near the axis (Hosts 29392, 30952, 30993, 31114, 38716, 38757, 39116, 39196, 39317, 39357, 39397) delete.

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):** All 11 mismatch ghosts delete when their Mises stress exceeds $41.3\text{ Pa}$, eliminating the criterion mismatch without altering the VU1 Fortran code.
- **REJECTED (FAIL):** The 11 ghosts still survive, indicating an unmodeled kinematic constraint or integration point disparity.

---

## EXPERIMENT 3 (EXP-03): Smoke Test — Single Embedded Fiber Pull Submodel

### Hypothesis Tested
**Explanation 3 in Isolation:** Validates that tension in embedded `T3D2` fibers causes ghost deletion via shear while leaving `VU1` normal engineering stretch far below `EPS_FAIL`.

### Exact Request for the Hub to Run on ROAR
Run a 10-second single-fiber strip submodel:
- 10 host hexes along the X-axis ($10\text{ mm} \times 1\text{ mm} \times 1\text{ mm}$) with 1 embedded truss fiber along the centerline.
- One end fixed; opposite fiber node pulled in tension by $0.2\text{ mm}$ over $1.0 \times 10^{-5}\text{ s}$.
- Execution command:
  ```bash
  abaqus job=SingleFiber_Pull input=SingleFiber_Pull.inp user=VUEL_failure.for interactive
  ```

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):** Ghost elements adjacent to the fiber delete as their shear strain reaches $\gamma \ge 19.4\%$ ($\text{PEEQ} \ge 10^{-6}$), while the `VU1` user elements remain active ($\text{ENG} \approx 1.9\% < 11.38\%$).
- **REJECTED (FAIL):** Ghost and VU1 delete simultaneously, or neither deletes.

---

## EXPERIMENT 4 (EXP-04): Deck Variant — Extended Step Time (7.0e-5 s to 1.2e-4 s)

### Hypothesis Tested
**Explanation 1 & 4 (Elastic Freezing vs. Delayed Loading):** Proves whether the surviving 58 islands are permanently frozen below yield or simply lagging due to wave transit time.

### Exact Request for the Hub to Run on ROAR
1. Modify `flat_v2_output.inp` step duration:
   Change step time from `7.0e-5` to `1.2e-4`.
2. Submit job:
   ```bash
   abaqus job=Flatv2_LongStep input=Flatv2_LongStep.inp user=VUEL_failure.for cpus=8 mp_mode=threads interactive
   ```
3. Extract final status and Mises history of the 58 islands from $7.0 \times 10^{-5}\text{ s}$ to $1.2 \times 10^{-4}\text{ s}$.

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):** The 58 islands remain alive throughout the extended window, with Mises stress decaying toward zero after the stress wave leaves the plate, proving that island survival is a permanent static equilibrium rather than a temporal lag.
- **REJECTED (FAIL):** Islands delete during the extended interval ($t > 7.0 \times 10^{-5}\text{ s}$), indicating that they were merely slow to yield.
