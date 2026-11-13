# T-048: ODB-verified T-046 tests versus vp4

## Scope and method

I independently checked the five T-046 input decks, their `.sta/.msg/.dat` and Slurm stdout files, and the five Abaqus ODB JSON extracts returned in `agents/refiner/inbox/T-048-odb/`. The extracts contain `STATUS`, `LE`, `PEEQ`, `S`, nodal `U/V/RF` (and `A` for test 5), plus global energy histories for each frame. Vector values were serialized as NumPy-style strings by the extractor; I parsed them numerically. All five runs completed with solver exit code 0. The ODB fields distinguish host/ghost labels 1–9, embedded fiber labels 101–103, and free protruding fiber label 102 in tests 2–3 or 104 in test 4. Each event time below is the **first output frame** with `STATUS=0`; the actual increment occurred after the immediately preceding output frame, roughly 1 µs earlier.

## Element deletion evidence

| Test | First `STATUS=0` frame (previous live frame) | Status at end, 100 µs | Last live / first dead fiber state |
|---|---|---|---|
| 1, lone truss | Fiber 1: **48.137 µs** (47.056 µs) | Fiber dead | `LE11` 0.043531 → 0.045177; `PEEQ` 0.010198 → 0.011609; `S11` 4.50 GPa → 0. |
| 2, native host + fiber | **Free fiber 102: 38.071 µs** (37.015 µs) | Host 1 **live**; embedded fiber 101 **live**; free 102 dead | Free `LE11` 0.039357 → 0.045156; `PEEQ` 0.006023 → 0.011540; `S11` 4.50 GPa → 0. |
| 3, ghost host + fiber | **Free fiber 102: 39.019 µs** (38.030 µs) | Ghost 1 **live**; embedded fiber 101 **live**; free 102 dead | Free `LE11` 0.040984 → 0.045148; `PEEQ` 0.007650 → 0.011454; `S11` 4.50 GPa → 0. |
| 4, 3 × 3 native block + fiber | **Free fiber 104: 32.070 µs** (31.006 µs) | All nine hosts **live**; all three embedded fibers 101–103 **live**; free 104 dead | Free `LE11` 0.039799 → 0.046116; `PEEQ` 0.006465 → 0.011528; `S11` 4.50 GPa → 0. |
| 5, lone host | Host 1: **14.562 µs** (13.057 µs) | Host dead | Host `LE11` 0.207642 → 0.232389; `S11` 107.3 MPa → 0. |

All named elements have STATUS in every exported frame; the conclusions do not rely on disappearance from an output field. In test 4, **none** of hosts 1–9 fails, so there is no center-row sequence to map. Tests 2–4 provide the opposite outcome to the proposed host-first scenario: the directly pulled, protruding `FIB_FREE` segment fails while every host and embedded fiber stays active. The existing decks therefore do **not** reproduce vp4 host deletion.

Test 1 confirms the T3D2 plus `*Solid Section` and zero-displacement damage-evolution combination can delete a fiber. Its first dead frame stores `LE11=0.045177` (4.52% logarithmic strain, about 4.62% engineering strain) and `PEEQ=0.011609`, close to the 0.01167 high-rate plastic-damage input. The smooth-step imposed engineering extension was 4.56% at the last live frame and 4.72% at the first dead frame. The frozen first-dead `LE` is a useful deletion-state reading, but the exact increment of STATUS change was not exported. The data support a fast-ramp failure near the **4.5% high-rate estimate**, not a universal 6.5% threshold.

## Host loads and ghost behavior

At the free-fiber deletion frame in test 2, host 1 and embedded fiber 101 both have `STATUS=1`; the embedded fiber is in compression (`S11≈−0.754 GPa`). In test 3, ghost 1 and embedded fiber 101 are live; the embedded fiber carries `S11≈+1.303 GPa`, while the ghost has only about `1.24 kPa` axial stress. All remain live through 100 µs. In test 4, the three embedded fibers remain live at free-fiber failure, with stresses of about `+1.358`, `−0.978`, and `+0.374 GPa`; all nine hosts remain live throughout. This demonstrates why comparing the **entire axial tow force** with a **single host face yield force** cannot establish the load actually delivered to one host: constraint force depends on how tension changes along the embedded tow and on the boundary conditions. Test 3 contains a ghost C3D8R, but **no VUEL element**, so it cannot test ghost-before-VUEL deletion.

The global energy transients are real solver outputs, not position-derived proxies. `ALLKE` peaks at about 0.0177 J (test 2), 0.0145 J (test 3), and 0.0592 J (test 4), near free-fiber failure. They show the controlled setups have release transients; they do not establish the source of vp4's energy gain. Test 4 finishes with `ALLKE≈0.00222 J` while all hosts and embedded fibers remain active.

## Test-5 mass question

The `.sta` file gives initial total mass `9.8e-7 kg`, matching a 1 mm cube at `980 kg/m^3`. ODB STATUS verifies host 1 is dead by 14.562 us and its stress becomes zero. The prescribed X displacement continues accelerating nodes 2, 3, 6, and 7 until about 20 us. At each returned frame from 14.562 through 19.849 us, each of these nodes has `RF1/A1 = 1.2250002e-7 to 1.2250003e-7 kg` (for example, node 2 at 14.562 us: `RF1 = -0.49784082 N`, `A1 = -4,064,005.8 m/s^2`). That ratio equals `9.8e-7 / 8 kg`, the cube's original lumped mass per node. The matching ratio at all four pulled nodes and five post-deletion frames **demonstrates that this test retains the deleted host's nodal inertial mass** while the prescribed motion accelerates them. My earlier conclusion that the test could not resolve mass retention was wrong; I had looked only at the zero kinetic energy after the ramp ended. The result does not measure the dynamical importance of retained mass in vp4 or whether another deletion configuration handles mass identically.

## Reconciliation with vp4 (T-045)

T-045 measured first host deaths at 1.75 µs native and 2.10 µs VUEL. The local viewer geometry first exceeded **1.0462 stretch**, comparable to test 1's observed engineering failure strain, at 7.35 µs native (52 hosts already dead) and 6.65 µs VUEL (43 hosts already dead). This strengthens the conclusion that **early vp4 host deaths precede large exported fiber stretch** even with the corrected high-rate threshold. It remains a geometry-only comparison; the vp4 export lacks fiber STATUS, local stress, and subframe event timing. It cannot say which late, wildly stretched fiber segments were active or whether live fiber force caused later host damage. Only 188/517 native and 214/612 VUEL host deaths had a previously hot fiber node within one element size under T-045's definition. The controlled tests show fiber-first failure is possible in these boundary conditions; they neither reproduce nor disprove a different local vp4 host-first mechanism.

The mass accounting from T-045 remains: about 78.70 g of modeled fiber in each vp4 deck; native retains 200.02 g full matrix host for 278.72 g total, while VUEL's volume-fraction correction yields 122.10 g host and 200.80 g total. Test 3's initial mass, `4.61718×10⁻⁷ kg`, equals `4.6162×10⁻⁷ kg` for 1.5 mm of fiber plus `9.8×10⁻¹¹ kg` for the ghost. Test 5 establishes retained nodal inertia after host deletion in its constrained cube; it does not establish that this retained host mass makes vp4 fibers appear heavy. Similar vp4 motion in corrected VUEL and mass-inflated native models still argues against native double counting as the sole cause. T-045's finite-difference position-based kinetic-energy estimates are not solver KE and must not be used to diagnose inertia.

## Remaining hypotheses, ranked by current evidence

1. **Unresolved active versus deleted fiber geometry and local constraints in vp4.** T-045 saw extreme stretch in fewer than 0.1% of segments, but exported fiber positions without STATUS. Test 1 proves this truss formulation can delete; tests 2–4 show a dead free fiber retains reported geometry/strain in subsequent ODB frames. The actual vp4 fiber STATUS and stress near host deaths remain the decisive missing data.
2. **Contact, local matrix damage, and possibly embedded-fiber force transfer near the impact.** First host deaths and most later deaths do not have a preceding hot fiber by T-045's measure. Test 2–4 do not show host failure despite live embedded fibers; this weakens any universal tow-unzipping explanation but does not exclude local vp4 fiber loads. Paired host/fiber STATUS, stress, damage, and contact histories are needed.
3. **Ghost scaffold constraint behavior in VUEL.** Test 3's ghost remains live, directly contradicting the proposed inevitable rapid ghost deletion in this setup. The actual vp4 ghost and VUEL state relationship is still unmeasured, and this test has no VUEL.
4. **Mass and energy effects.** Native initial double counting is verified by deck accounting; VUEL largely corrects it. Test 5 verifies retained nodal inertia after host deletion in its constrained cube. Its dynamical role in vp4 remains unverified. The energy transients in small tests caution against attributing vp4 motion solely to mass.

## Corrections to `FIBER_HOST_MECHANISM.md`

- Its claims that hosts **always** fail before fibers and that the force comparison makes host-first failure mathematically inevitable are **contradicted by tests 2–4**. All hosts survive to the end; the pulled free fiber fails first. The simplistic force-capacity comparison cannot substitute for local constraint-force and stress histories.
- Its test-plan claim of sequential host unzipping in the 3 × 3 block is **contradicted**: all nine hosts remain live for the full run.
- Its prediction of immediate ghost failure under minute fiber tension is **contradicted in test 3**: the ghost remains live. The deck has no VUEL, so ghost-versus-VUEL decoupling was never tested.
- Its 6.50% fiber deletion figure applies to the low-rate material estimate, not this fast-ramp run. The ODB confirms deletion near 4.52% logarithmic / 4.62% engineering strain in test 1, consistent with the high-rate branch.
- Its test-5 retained-mass conclusion is **supported for this cube** by the post-deletion `RF1/A1` ratio, even though the ODB has no direct MASS field. Extrapolation to vp4 dynamics remains unverified.
- Its proposed heavy-orphan-node and surviving-fiber explanations for vp4 remain **hypotheses**. The five small tests do not verify them in the impact model.

No new solves or ROAR submissions were performed for this reconciliation. The existing five ODB extracts resolved the element-deletion question; test 5 also resolves retained nodal inertia for its own deleted host. Its effect in vp4 remains open.

