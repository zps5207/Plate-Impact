# T-056 Test Decks & ROAR Verification Suite

This directory contains test decks, builder scripts, and generator tools for verifying fiber-to-host eroding contact with initial overclosure baseline tracking via `VUINTERACTION`.

---

## Files in this Directory

1. **`make_coupon_fiberhost.py`**:
   Parametric generator that creates the 2-ply coupon test decks.

2. **`coupon_fiberhost.inp`**:
   The primary coupon test deck (identical to `coupon_fiberhost_baseline.inp`), implementing the `VUINTERACTION` baseline tracking scheme.

3. **`coupon_fiberhost_nocontact.inp` (Variant i)**:
   Reference coupon deck with NO fiber-host contact. Cohesive contact between plies remains active.

4. **`coupon_fiberhost_native.inp` (Variant ii)**:
   Coupon deck with standard native penalty contact (`General`) applied to all fiber-host pairs, including own ply. Demonstrates the non-physical energy explosion at $t=0$ caused by embedded initial overclosure ($0.104\text{ mm}$ penetration).

5. **`coupon_fiberhost_baseline.inp` (Variant iii)**:
   Coupon deck with `FiberHostBaseline` (`VUINTERACTION`) applied to own-ply fiber-host contact and native penalty (`General`) applied to adjacent plies. Resolves the energy issue by recording initial overlap at $t=0$ as a baseline ($d_0$) and ratcheting downward monotonically.

6. **`build_newvals_fiberhost_tt3.py`**:
   Production builder script. Reads `Meshing/newvals-interior-tt3/nv3_int.inp`, adds eroding ghost host surfaces with interior faces, per-ply fiber node surfaces, 400 fiber-host inclusion pairs, `FiberHostBaseline` interaction, equivalent truss thickness ($0.000632\text{ m}$), and `*Contact Controls Assignment, nodal erosion=YES`. Writes `Meshing/newvals-fiberhost-tt3/nv3_fh.inp` (2 $\mu\text{s}$ step, 20 field frames).

---

## Physics and Expected Behaviors

### Coupon Model Structure
- **Dimensions**: 2 plies ($1.27\text{ mm}$ thickness each, total $2.54\text{ mm}$), 3 hex layers per ply through-thickness ($0.4233\text{ mm}$ per layer). In-plane: $4 \times 4$ hexes of size $0.632 \times 0.632\text{ mm}$.
- **Matrix / Host**: Dual-element representation matching nv3: `VU1` user elements carrying non-linear elastoplastic matrix damage and failure, overlaid with `C3D8R` ghost host elements (`EMBMESH_GHOST_HOST`) carrying contact surfaces.
- **Fibers**: Mid-ply `T3D2` truss elements embedded in the own-ply ghost hosts via `*Embedded Element`.
- **Loading**: Bottom nodes of Ply 1 fixed ($U_1 = U_2 = U_3 = 0$). One fiber in Ply 1 pulled axially at $v_x = 50\text{ m/s}$ to induce intense shear strain in surrounding matrix hexes, triggering ductile damage and host element deletion.

### Diagnostic Comparison Matrix
| Metric / Check | Variant (i): No Contact | Variant (ii): Native Penalty | Variant (iii): Baseline Subroutine |
| :--- | :--- | :--- | :--- |
| **Initial Energy ($t=0$)** | Normal ($ALLIE \approx 0$, $ALLKE \approx 0$) | **Spurious Blowup** ($ALLIE$ & $ALLKE$ jump immediately due to $0.104\text{ mm}$ spring stretch) | **Normal & Clean** ($d_0 = d \implies P=0$, no energy jump) |
| **Spurious Host Deletion** | None | **Severe** (adjacent hosts delete before mechanical load arrives) | None (hosts delete only under genuine shear deformation) |
| **Freed Fiber Mechanics** | Fiber passes freely through matrix void with no resistance | Spurious forces continue to push on remaining matrix | Monotonic downward ratchet ensures physical contact once fiber leaves initial overclosure zone |
| **Energy Conservation** | $ETOTAL$ conserved | Large non-physical work/contact energy artifact | Clean energy balance ($ALLIE + ALLKE + ALLPD + ALLFD = ETOTAL$) |

---

## Exact ROAR Execution Sequence for the Hub

Execute jobs in the following strict order on ROAR:

### Step 1: Run Coupon Variants (Verification of Mechanics & Subroutine)
First, copy `agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for` to your working directory.

1. **Run Variant (iii) / Baseline Scheme**:
   ```bash
   abaqus job=coupon_fiberhost_baseline input=agents/drafter/outbox/T-056/decks/coupon_fiberhost_baseline.inp user=agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for double=both interactive
   ```
   *Expected Outcome*: Clean startup, stable time increment $\approx 1.5 \times 10^{-9}\text{ s}$, zero initial energy spike at $t=0$, smooth matrix shear failure and fiber pullout.

2. **Run Variant (ii) / Native Penalty (Negative Control)**:
   ```bash
   abaqus job=coupon_fiberhost_native input=agents/drafter/outbox/T-056/decks/coupon_fiberhost_native.inp user=agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for double=both interactive
   ```
   *Expected Outcome*: Demonstrates the energy blowup. Examine `.sta` and `.odb` history curves: immediate spike in $ALLIE$ / $ALLKE$ at $t=0$ and premature host element deletions.

3. **Run Variant (i) / No Contact (Reference Baseline)**:
   ```bash
   abaqus job=coupon_fiberhost_nocontact input=agents/drafter/outbox/T-056/decks/coupon_fiberhost_nocontact.inp user=agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for double=both interactive
   ```
   *Expected Outcome*: Reference baseline curves for shear-induced matrix failure without contact forces.

---

### Step 2: Build the Production Deck `nv3_fh.inp`
Execute the builder script from the repository root:
```bash
python agents/drafter/outbox/T-056/decks/build_newvals_fiberhost_tt3.py
```
*Output*: Generates `Meshing/newvals-fiberhost-tt3/nv3_fh.inp`.

---

### Step 3: Run Datacheck on ROAR
Verify keyword syntax, inclusion table linking, and user interaction initialization:
```bash
abaqus datacheck job=nv3_fh input=Meshing/newvals-fiberhost-tt3/nv3_fh.inp user=agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for double=both cpus=4
```
*Verification Check*:
- Inspect `nv3_fh.log`, `nv3_fh.msg`, and `nv3_fh.sta`.
- Check that `*Contact Controls Assignment, nodal erosion=YES` and `*Surface Interaction, name=FiberHostBaseline` are accepted with `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`.

---

### Step 4: Execute 2 $\mu\text{s}$ Solve on ROAR
Submit the short 2 $\mu\text{s}$ impact solve via Slurm:
```bash
sbatch --job-name=nv3_fh --nodes=1 --ntasks=24 --time=04:00:00 --wrap="abaqus job=nv3_fh input=Meshing/newvals-fiberhost-tt3/nv3_fh.inp user=agents/drafter/outbox/T-056/VUEL_material_plus_vuinteraction.for double=both cpus=24 -interactive"
```
*Verification Checks on Solve*:
- Confirm ball contact occurs at $t \approx 0.97\ \mu\text{s}$.
- Check that before impact ($t < 0.97\ \mu\text{s}$), $ALLKE$ and $ALLIE$ remain flat with zero premature ghost deletions.
- Monitor stable time increment ($dt \approx 1.5 \times 10^{-9}\text{ s}$).
