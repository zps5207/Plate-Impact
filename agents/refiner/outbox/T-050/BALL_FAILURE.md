# T-050: steel ball failure in vp5 and vp6

## Finding

The most likely cause is a concentrated, numerically extreme hard-contact load on the finely meshed ball nose, followed by progressive deformation of its off-axis shell. The ball is paired simultaneously with the host element surface and fiber nodes whose assigned contact thickness is 0.618 mm. The available `CPRESS` output proves that the ball receives very large localized contact pressure, but **does not identify which of those two partners supplies each force**. The role of the thick fiber-node surface is the leading testable hypothesis, not a demonstrated sole cause.

All positions below are undeformed assembly coordinates. The ball is a quarter sphere centered at approximately (0, 0, 11) mm, radius 9.525 mm, with its nose at z = 1.475 mm. Times are since step start. `ball_vp5.npz` samples 85/1001 frames; `ball_vp6.npz` samples 87/939 frames. An event is bracketed by neighboring sampled frames, not timed to an individual increment.

## vp5: first deletion and sequence

At 0.8433 µs, all 18,500 elements are alive. At **1.6823 µs, 75 are dead**. Thus first deletion occurred in (0.8433, 1.6823] µs. These are concentric nose rings, **r ≈ 0.43–1.58 mm**, z ≈ 1.69–1.80 mm, rather than the equator or outer rim. Examples: label 16901 at (0.0497, 1.5823, 1.8030) mm; 16221 at (0.1490, 1.5761, 1.8030); 16951 at (0.0301, 0.9576, 1.7299); 16271 at (0.0902, 0.9539, 1.7299). These 75 go within one output interval; their order within it is unavailable.

| Time (µs) | Deleted ball elements |
|---:|---:|
| 0.843 | 0 |
| 1.682 | 75 |
| 2.521 | 212 |
| 3.360 | 305 |
| 4.201 | 383 |
| 5.041 | 450 |
| 8.402 | 740 |
| 16.801 | 1,443 |
| 25.202 | 2,116 |
| 33.602 | 2,720 |
| 42.002 | 3,103 |
| 70.000 | 3,161 (17.1%) |

`analyze_ball.py` prints the sampled count at every subsequent change. At 2.521 µs an additional 137 elements have died; at 3.360 µs, 93 more. The first sampled center-Jacobian volume ratio below 0.1 occurs at 2.521 µs (minimum 0.0296, labels 9471, 8111, 18372, 8791, 18362). This is already after deletion starts.

## vp6: distortion, including the fatal four

With ball deletion disabled, the first sampled center-Jacobian volume ratio below 0.1 is **6.1643 µs**, minimum **0.0669** in nose-cap elements 18292, 18402, 18302, 18342, 18282 (r ≈ 2.66 mm, z ≈ 1.97 mm). This is a geometric distortion flag, not Abaqus's exact excessive-distortion criterion. Later the outer ball stretches into long elements. Abaqus named elements **509, 475, 502, 479** at the 65.64 µs exception. Their original centroids and diagnostics are:

| Element | Original centroid (mm) | First sampled edge ratio >10 (µs) | Edge ratio at 65.451 µs | Mises at 65.643 µs (GPa) | PEEQ at 65.643 µs |
|---:|---|---:|---:|---:|---:|
| 475 | (8.169, 0.257, 8.077) | 33.881 | 17.2 | 0.972 | 4.295 |
| 479 | (9.009, 0.283, 9.008) | 19.250 | 64.6 | 0.915 | 3.134 |
| 502 | (8.467, 0.266, 9.138) | 23.872 | 51.2 | 0.819 | 2.609 |
| 509 | (7.667, 0.241, 8.246) | not reached | 7.29 | 0.814 | 2.693 |

These four are **off-axis, near the quarter-ball's y = 0 symmetry face and radial outer surface**, not the initially failing nose rings. Their last finite sampled volume ratios are approximately 0.917, 1.008, 1.041, 1.068 respectively: stretching/shear, rather than simple volume collapse, is evident. Some nodal displacements in the special final frame are NaN, so geometric measurements there are unreliable. The actual failing increment is between the 65.451 and 65.643 µs sampled frames, or inside the final special frame; output does not resolve it further.

## Contact and steel response

At vp5 first deletion (1.682 µs), the extraction reports **0 loaded ball nodes, 24,768 loaded host nodes, 0 loaded fiber nodes**; the global top pressure is 0.426 GPa on PLY-19 node 9. This host pressure may include ply-to-ply cohesive contact, so it is not proof that PLY-19 is the ball's counterface. At 2.521 µs, the counts are 5 / 26,084 / 0 and the peak is **213.4 GPa on BALL-1 node 7455**. At 3.360 µs it reaches **852.5 GPa on BALL-1 node 19015**, with only one ball node reported loaded. The pressure spike follows the first deletion in sampled time; it cannot be established as the immediate initiator. At vp5 end, the counts are 1 / 5,713 / 0 and peak 0.249 GPa on a PLY node.

At vp6 6.164 µs, the counts are 27 / 25,208 / 1 and peak **251.3 GPa on BALL-1**. At 65.451 µs they are 40 / 5,836 / 0, peak 11.27 GPa on BALL-1; at the special 65.643 µs frame, 36 / 5,891 / 0, peak **28.37 GPa** on BALL-1 node 640. For the four fatal elements' own nodes, the maximum at 65.451 µs is 10.5–11.3 GPa; at 24.64 µs element 475's nodes reach 30.9 GPa. The last global maximum node 640 is near the nose in the original mesh, not one of the four fatal elements. The top-60 table gives pressure on a reporting node and its instance, **not contact partner identity or force contribution**. The small reported fiber count, including zero late in both jobs, does not prove zero fiber force on a node-based contact surface.

The reference steel yield is 0.304 GPa. Thus vp6's terminal **contact pressure** is ~93× that number (vp5's sampled 213 and 852 GPa are ~702× and ~2,800×), but hydrostatic contact pressure is not equivalent stress and must not be interpreted as a yield ratio. The four vp6 elements' Mises stresses are 0.814–0.972 GPa. The deck's Johnson–Cook flow strength is `304.33 MPa + 422.007 MPa × PEEQ^0.345`, multiplied by rate and temperature factors; at PEEQ 2.61–4.30 its quasistatic, room-temperature value is about **0.89–1.00 GPa**. Their measured Mises levels are of that order. Actual rate and temperature are absent, so exact strength cannot be calculated.

For vp5's first 75 deleted elements, the preceding 0.843 µs frame has PEEQ = 0 throughout and maximum Mises only 0.000199 GPa; at 1.682 µs the deleted elements' reported PEEQ and stress are zero. The JC damage condition was crossed **between sampled frames**; these values do not measure its crossing state. The deck's initiation constants are D1=0.1152, D2=1.0116, D3=-1.7684, D4=-0.05279, D5=0.5262, reference rate 0.0001/s, 293–1800 K. The zero-triaxiality, room-temperature reference-rate failure strain would be D1+D2=**1.1268**. At triaxiality 1/3 it would be approximately **0.677** before rate dependence. Negative D4 lowers this illustrative threshold with increasing rate. Stress triaxiality, integration-point strain rate, temperature, and damage variable are missing, so the actual threshold and accumulated JC damage of the first failed elements cannot be computed. Extract `TRIAX`, `PEEQR`, `TEMP`, `JCCRT` (or the available JC damage criterion output), and integration-point `PEEQ`/`S` for BALL-1 labels 16901, 16221, 16951, 16271 in the first ~2 µs, including every frame or a tighter increment interval.

## Mesh scale and energy

The ball has 17,000 C3D8R bricks and 1,500 C3D6R wedges. Initial true edge-length quantiles across their connectivity are **0.039, 0.178, 0.376, 0.593, 0.622, 0.729 mm** at 0, 10, 50, 90, 99, 100%. The median edge is 0.61× the assigned 0.618 mm fiber-node contact thickness and 0.30× the approximately 1.27 mm ply thickness. Thus the ball mesh is **fine relative to the nominal contact thickness**, not obviously too coarse. The very short 0.039 mm edges and mixed wedge/brick nose topology may be sensitive to localized node contact; mesh convergence and surface discretization have not been established.

Using the 7850 kg/m³ deck density, initial element geometry and assigned 1000 m/s ball speed, the first 75 deleted elements contain approximately **3.96 J of initial kinetic energy**, all 3,161 ultimately deleted elements **771 J** (about 22% of the ball's initial ~3.52 kJ), and vp6's four fatal elements **2.48 J** in total. These are initial per-element mass × speed²/2 estimates, **not kinetic energy at deletion or distortion**; the extract has displacement but no velocity or per-element energy. Actual kinetic energy there requires BALL-1 nodal `V` and a documented element mass/lumped-mass allocation (or per-element kinetic energy output) at the relevant frames. The project brief calls the initial energy “3.55 J” and ODB energies “mJ”, but the SI geometry, density, speed, and `vp5_extract2.json` initial `ALLKE=3546.13` are mutually consistent with **~3.55 kJ / 3546 J**. This thousandfold unit-label discrepancy should be reconciled before energy is used in a decision.

## Alternative explanations and next tests

| Candidate | Evidence for | Evidence against / uncertainty |
|---|---|
| Thick fiber-node ball contact | Assigned 0.618 mm thickness exceeds median ball edge; hard contact and few reporting ball nodes coincide with extreme pressures; ball/fiber pair is explicitly included. | The `CPRESS` extraction does not identify pairs; reported fiber pressure counts are zero at first deletion and late vp6. Fiber force is unmeasured. |
| Host element ball contact | Ball/host pair is included; host pressures rise at onset; removing eroded host faces made vp5 energy behave much better than vp4. | Host loaded counts include cohesive ply contact; top host pressure cannot be tied to the ball. |
| Ball mesh geometry | Nose starts eroding in a coherent ring; 0.039 mm minimum edges and mixed wedge/brick topology could focus force; vp6 outer elements become slender. | Median mesh is already finer than contact thickness; no refinement comparison exists. |
| JC rate/temperature or deletion controls | Negative D4 may reduce ductility at high rates; zero-displacement damage evolution deletes immediately once initiated. | Actual rate, temperature and damage variable are absent; removing JC prevents deletion but still yields vp6 distortion, so JC deletion is not the sole cause. |
| Retained mass on deleted nodes | Mass retention was independently confirmed by T-046 and can affect later spikes and energy. | It cannot explain the **first** deletion, which precedes retained deleted-node mass; no isolated run tests its later contribution. |

Ranked test-deck changes, each compared at early pressure/deletion onset and energy history:

1. **Remove only `EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF` contact**, leaving ball/host contact and materials intact. If nose deletion/pressure spikes disappear, fiber-node contact is implicated.
2. **Run the complementary fiber-only ball-contact deck** (remove only the host/ball inclusion), with existing cohesive ply interactions. This separates the two sources instead of relying on `CPRESS` instance counts.
3. **Refine the ball's nose and near-symmetry-face surface mesh while preserving diameter, mass, material, and contact definitions.** Compare onset and maximum pressure with the baseline to assess mesh sensitivity.

Contact-pair force histories (`CFN`/appropriate Abaqus pair force output, including per-pair `CPRESS`/`CSTATUS` if available), per-contact-surface tractions, and dense early frames are needed to establish **against what** each first-failing element is loaded. The provided extraction cannot assign a ball node's pressure to fiber versus host, nor compute exact at-failure steel damage or kinetic energy.
