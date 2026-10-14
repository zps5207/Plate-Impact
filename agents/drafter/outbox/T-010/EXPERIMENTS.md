# T-010: ROAR Validation Experiments

This document specifies four self-contained, concrete ROAR experiments designed to validate the contact workarounds and eliminate ball penetration through the plate. Each experiment includes the exact input deck modification, execution command, ODB extraction script, and explicit quantitative confirmation/rejection criteria.

---

## EXPERIMENT 1 (EXP-01): Whole-Ghost Surface with Penalty Stiffness Scaling (Recipe #1)

### Purpose
Validate Workaround 1 (Recipe #1): Determine whether expanding the plate contact surface to all ghost elements (`EMBMESH_GHOST_HOST`) and scaling the general contact penalty stiffness by $10^4$ eliminates ball penetration and stops the ball, without changing material physics or Fortran code.

### Deck Modifications to `evidence/Flatv2_user.inp` / `evidence/flat_v2_output.inp`
1. In the Assembly section, redefine `Surf-1` from the boundary elsets to the full ghost element set:
   ```abaqus
   *Surface, type=ELEMENT, name=Surf-1
   Plate-1.EMBMESH_GHOST_HOST,
   ```
2. In the Step interaction section under `*Contact, op=NEW`, add the penalty stiffness scale factor:
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
3. Add history output for contact forces and projectile kinematics:
   ```abaqus
   *Output, history, time interval=1.0e-7
   *Contact Output
   CFORCE, CAREA
   *Node Output, nset=Ball-1.Ball
   V3, U3
   ```

### Execution on ROAR
```bash
# Save modified deck as Flatv2_EXP01.inp
abaqus job=Flatv2_EXP01 input=Flatv2_EXP01.inp user=VUEL_failure.for cpus=8 mp_mode=threads interactive
```

### ODB Extraction Script (`extract_exp01.py`)
```python
import sys
from odbAccess import openOdb

odb = openOdb("Flatv2_EXP01.odb")
step = odb.steps["Step-1"]

# 1. Projectile Velocity History
ball_nset = odb.rootAssembly.instances["BALL-1"].nodeSets["BALL"]
v3_history = []
for frame in step.frames:
    v3_field = frame.fieldOutputs["V"]
    v3_vals = [val.data[2] for val in v3_field.getSubset(region=ball_nset).values]
    avg_v3 = sum(v3_vals) / len(v3_vals) if v3_vals else 0.0
    v3_history.append((frame.frameValue, avg_v3))

# 2. Energy Summary
ke = step.historyRegions["Assembly ASSEMBLY"].historyOutputs["ALLKE"].data
ie = step.historyRegions["Assembly ASSEMBLY"].historyOutputs["ALLIE"].data
c_energy = step.historyRegions["Assembly ASSEMBLY"].historyOutputs.get("ALLVD", None)

print("Final Frame Time: %e" % step.frames[-1].frameValue)
print("Initial Ball V3: %f m/s, Final Ball V3: %f m/s" % (v3_history[0][1], v3_history[-1][1]))
print("Initial ALLKE: %f J, Final ALLKE: %f J" % (ke[0][1], ke[-1][1]))
print("Final ALLIE: %f J" % (ie[-1][1]))
```

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):**
  - Final ball velocity drops significantly below $900\text{ m/s}$ (energy absorbed by plate $> 20\%$, corresponding to $\Delta ALLKE > 800\text{ J}$).
  - Maximum number of ball nodes inside live ghost bounding boxes drops from $490$ to $< 10$.
  - Ghost deletion occurs progressively as the ball pushes into the plate rather than leaving untouched islands.
- **REJECTED (FAIL):**
  - Ball retains $> 980\text{ m/s}$ and energy absorption remains $\approx 1\%$.

---

## EXPERIMENT 2 (EXP-02): Node-Based Plate Contact Surface with Assigned Thickness (Recipe #2 / User Idea)

### Purpose
Directly test the User's proposal: Determine whether a node-based contact surface (`*Surface, type=NODE`) representing plate nodes can effectively transmit contact forces to the ball using the real nodal mass, and evaluate the severity of inter-nodal punch-through and point singularities.

### Deck Modifications
1. In the Assembly section, define the node-based surface covering all plate nodes:
   ```abaqus
   *Surface, type=NODE, name=Surf-Plate-Nodes
   Plate-1.PLATE,
   ```
2. In the Step interaction section under `*Contact, op=NEW`, include `Surf-Plate-Nodes` and assign a finite contact thickness of $0.5\text{ mm}$ (half the element edge):
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

### Execution on ROAR
```bash
# Save modified deck as Flatv2_EXP02.inp
abaqus job=Flatv2_EXP02 input=Flatv2_EXP02.inp user=VUEL_failure.for cpus=8 mp_mode=threads interactive
```

### ODB Extraction Script (`extract_exp02.py`)
```python
import sys
from odbAccess import openOdb

odb = openOdb("Flatv2_EXP02.odb")
step = odb.steps["Step-1"]

# Check peak contact pressure on plate nodes
max_cp = 0.0
frames_with_contact = 0
for frame in step.frames:
    if "CPRESS" in frame.fieldOutputs:
        cp_field = frame.fieldOutputs["CPRESS"]
        vals = [v.data for v in cp_field.values if v.data > 0.0]
        if vals:
            frames_with_contact += 1
            max_cp = max(max_cp, max(vals))

ke = step.historyRegions["Assembly ASSEMBLY"].historyOutputs["ALLKE"].data
print("Frames with active CPRESS: %d / %d" % (frames_with_contact, len(step.frames)))
print("Maximum recorded CPRESS: %e Pa" % max_cp)
print("Initial KE: %f J, Final KE: %f J" % (ke[0][1], ke[-1][1]))
```

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):**
  - Plate nodes develop sustained contact ($CPRESS > 0$ across $> 200$ frames instead of 1-frame spikes).
  - Ball velocity drops below $950\text{ m/s}$.
  - No fatal mesh distortion occurs at the contact boundary.
- **REJECTED (FAIL):**
  - Severe numerical chatter causes time step collapse ($\Delta t < 10^{-11}\text{ s}$) or abortion.
  - Ball passes through the gaps between nodes without significant velocity loss ($V_{final} > 980\text{ m/s}$).

---

## EXPERIMENT 3 (EXP-03): Ghost Scale Physics Variant ($\alpha = 0.01$)

### Purpose
Test the physics-scaling hypothesis: Increase native ghost material scaling by a factor of 100 (from $10^{-4}$ to $10^{-2}$, yielding $E_{ghost} = 50.8\text{ kPa}$), keeping the whole-ghost surface definition, to measure how much contact stiffness increases naturally while quantifying the energy dissipation absorbed by the ghost.

### Mesher Command
```bash
python embmesh/vuelghost.py evidence/Flatv2_user.inp Flatv2_EXP03.inp \
    --ghost-scale 0.01 \
    --vuel-eps-fail 0.1138 \
    --vuel-jac-fail 0.05
```

### Execution on ROAR
```bash
abaqus job=Flatv2_EXP03 input=Flatv2_EXP03.inp user=VUEL_failure.for cpus=8 mp_mode=threads interactive
```

### ODB Extraction Script (`extract_exp03.py`)
```python
import sys
from odbAccess import openOdb

odb = openOdb("Flatv2_EXP03.odb")
step = odb.steps["Step-1"]
ke = step.historyRegions["Assembly ASSEMBLY"].historyOutputs["ALLKE"].data
ie = step.historyRegions["Assembly ASSEMBLY"].historyOutputs["ALLIE"].data
pd = step.historyRegions["Assembly ASSEMBLY"].historyOutputs.get("ALLPD", None)

print("Initial KE: %f J, Final KE: %f J (Loss: %.2f J)" % (ke[0][1], ke[-1][1], ke[0][1] - ke[-1][1]))
print("Internal Energy ALLIE: %f J" % ie[-1][1])
if pd:
    print("Plastic Dissipation ALLPD: %f J" % pd.data[-1][1])
```

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):**
  - Ball velocity drops measurably more than in Flat_v2 ($\Delta KE > 300\text{ J}$ vs $79\text{ J}$).
  - Confirms that element penalty stiffness was artificially choking contact forces in Flat_v2.
- **REJECTED (FAIL):**
  - $10^{-2}$ scaling is still too soft to stop the ball, indicating that higher scale factors ($10^4$ or $10^5$) are required.

---

## EXPERIMENT 4 (EXP-04): Single-Hex Reduced Calibration Deck (5-Second Smoke Test)

### Purpose
Provide a lightweight, 5-second sanity test on ROAR to calibrate contact penalty stiffness directly before submitting a 33-minute full plate job.

### Model Setup
- **Target:** A single $1\text{ mm} \times 1\text{ mm} \times 1\text{ mm}$ C3D8R ghost + VU1 pair encastre at the base ($z = -1\text{ mm}$).
- **Impactor:** A rigid steel block ($1\text{ mm} \times 1\text{ mm} \times 0.5\text{ mm}$) traveling at $1000\text{ m/s}$ in $-z$.
- **Variants Tested:**
  1. Default ghost ($10^{-4}$ scale, `HARD` contact).
  2. Recipe 1 ghost ($10^{-4}$ scale + `SCALE FACTOR 10000.0`).
  3. Recipe 2 node-based contact.

### Execution on ROAR
```bash
abaqus job=SingleHex_Calib input=SingleHex_Calib.inp user=VUEL_failure.for interactive
```

### ODB Extraction
Extract penetration depth vs contact force curve:
$$F_c(t) = -m_{impactor} \cdot a_z(t)$$
$$k_{effective} = \frac{\Delta F_c}{\Delta \delta}$$

### Confirmation & Rejection Criteria
- **CONFIRMED (PASS):**
  - Variant 1 penetrates $> 0.5\text{ mm}$ with $F_c < 1\text{ N}$ (reproducing Flat_v2 softness).
  - Variant 2 stops or deflects the impactor with $F_c > 1000\text{ N}$ and penetration $< 0.05\text{ mm}$ before element yield.
