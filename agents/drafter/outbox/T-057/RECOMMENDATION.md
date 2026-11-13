# Recommendation: Own-Ply Fiber-Host Contact Strategy (T-057)

**Task ID:** T-057  
**Role:** drafter  
**Target:** Plate Impact Project (nv3 model on ROAR)  
**Date:** 13 November 2026  

---

## 1. Executive Recommendation

**DROP own-ply fiber-host contact in production.**  
Adopt the **Run A** contact architecture across all production runs:
1. Retain native `General` contact for all inter-ply pairs (fibers in ply $k$ vs host in ply $j$ for $j \neq k$).
2. Retain native `General` contact for all projectile pairs (fibers and host vs ball).
3. **Omit all 20 own-ply fiber-host contact pairs** (`EMBMESH_FIBER_NODES_PLY_k` vs `EMBMESH_HOST_PLY_k`), removing the need for user interaction `FiberHostBaseline`.

If own-ply contact is ever required for specialized localized studies, deploy the newly drafted `vuinteraction_baseline_v2.for` (which introduces increment-parity double-buffering and a 20 MPa pressure cap), but do **not** use own-ply contact in the full 20-ply impact model.

---

## 2. Technical Justification

### A. Physical Redundancy While Intact
Fibers are kinematically embedded in their host matrix elements via `*EMBEDDED ELEMENT`. The host displacement field strictly constrains the translational degrees of freedom of the fiber nodes. Defining surface contact between an embedded truss and its enclosing host volume is physically redundant and creates conflicting kinematic over-constraints.

### B. Ill-Posed Mechanics upon Matrix Erosion
When host elements degrade and delete under high-velocity impact:
- Interior element boundaries are exposed as active contact facets (`INTERIOR` option).
- Because fibers are embedded inside the ply, they inevitably sit directly behind newly exposed interior facets within the tracking zone.
- Abaqus General Contact evaluates these pre-existing interior fiber nodes as deep penetrations ($0.2\text{–}0.4\text{ mm}$).
- Since in-plane transverse fiber slip is less than $0.1\text{ mm}$, genuine own-ply contact after erosion provides negligible physical load transfer, while introducing catastrophic numerical hazards (artificial 40–80 MPa impulses on degrading nodes).

### C. Empirical Proof from Cluster Bisect (ROAR)
The ROAR bisect results provide decisive, unimpeachable evidence:
- **Run A (Native inter-ply contact only, NO own-ply pairs):**
  - Completed $2.0\ \mu\text{s}$ with total energy virtually constant ($469.2\text{ J} \to 468.8\text{ J}$).
  - Stable time increment remained rock-solid at $\Delta t = 3.798 \times 10^{-8}\text{ s}$ across all 53 increments.
  - Zero deep penetration warnings, zero orphan node runaway, zero energy divergence.
- **Run B (Own-ply pairs with FiberHostBaseline only):**
  - Blew up immediately following top-ply element deletions ($ETOTAL$ jumped from $469\text{ J}$ to $2,307\text{ J}$ at $2.0\ \mu\text{s}$).
  - Stable time increment collapsed by an order of magnitude ($\Delta t \to 2.4 \times 10^{-9}\text{ s}$).

---

## 3. Physical Replacement Strategy

When own-ply fiber-host contact is dropped:

1. **Inter-Ply Contact ($j \neq k$):**
   Fibers in ply $k$ interact natively with host elements in adjacent plies ($k-1, k+1$, etc.) via standard Abaqus General Contact. Because the geometric clearance from mid-ply fiber nodes to adjacent ply surfaces is $+0.319\text{ mm}$ (clear by $319\ \mu\text{m}$), native penalty contact operates cleanly without initial overclosure or baseline ratcheting.

2. **Projectile Contact:**
   Fibers interact natively with the steel ball via `EMBMESH_FIBER_NODES` vs `EMBMESH_BALL_SURF`.

3. **Behavior of Freed Fibers:**
   When a host element erodes, its embedded constraint is released. The freed fiber truss continues to carry axial tension across the cavity and transfers load through its surviving embedded anchors in adjacent host elements. This accurately captures tensile membrane bridging and fiber pull-out mechanics without spurious contact shocks.

---

## 4. Hub Execution Sequence (ROAR)

The Hub should execute the following sequence on ROAR in `/scratch/zps5207/ctv/`:

### Step 1: Cluster Validation of Mechanisms (Coupons)
Run the two minimal diagnostic coupons with `vuint_bigforce.for` to verify H1 and H2/H3:
```bash
# Coupon A: Boundary sliding cross-talk (H1)
abaqus job=coupon_h1_sliding input=coupon_h1_sliding.inp user=vuint_bigforce.for double=both interactive

# Coupon B: Interior face erosion shock (H2/H3)
abaqus job=coupon_h2_erosion input=coupon_h2_erosion.inp user=vuint_bigforce.for double=both interactive
```
*Expected:* Coupon A shows `BIG` force spike when crossing the facet interface; Coupon B shows `BIG` force spike immediately upon element deletion at $t \approx 1\ \mu\text{s}$.

### Step 2: Verification of Fixed Subroutine (v2) on Coupons
Run both coupons with `VUEL_material_plus_vuinteraction_v2.for`:
```bash
abaqus job=coupon_h1_v2 input=coupon_h1_sliding.inp user=VUEL_material_plus_vuinteraction_v2.for double=both interactive
abaqus job=coupon_h2_v2 input=coupon_h2_erosion.inp user=VUEL_material_plus_vuinteraction_v2.for double=both interactive
```
*Expected:* Contact forces remain strictly bounded by the 20 MPa crushing cap; $\Delta t$ remains stable; zero kinetic energy explosion.

### Step 3: Production Model Execution (Run A Architecture)
Generate production deck with own-ply contact omitted:
```bash
# In Meshing/newvals-fiberhost-tt3/ or via mesher CLI:
# Use --fiber-host-contact interply_only (or Run A filter)
sbatch --job-name=nv3_fhA --nodes=1 --ntasks=24 --time=04:00:00 \
  --wrap="abaqus job=nv3_fhA input=nv3_fhA.inp user=uel/VUEL_material.for double=both cpus=24 -interactive"
```
*Expected:* 100% stable 2.0 $\mu$s solve with flat total energy ($ETOTAL \approx 469\text{ J}$) and nominal time increment $\Delta t \approx 3.8 \times 10^{-8}\text{ s}$.
