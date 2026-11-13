# T-051: early steel-ball inversion in bt1/bt2

## What the local data establish

`analyze_inversion.py` read all 12 local bt1/bt2 viewer NPZ files (150 frames each, 0–approximately 12 µs) and their neighboring extract JSON files. Inversion means the minimum of the eight **C3D8R corner scaled Jacobians is ≤0**, computed from the stored nodal positions. This is a geometric diagnostic, not Abaqus's integration-point failure criterion. The viewer files have **no ball element STATUS**, stress, damage, or contact forces; the extract JSON has only *aggregate* ball deletion counts at approximately 0.30 µs spacing. Thus the data do **not** establish that an individual hex inverted before it was deleted. Initial coordinates and lengths below are in the assembly frame; the ball center is (0,0,11) mm and nose z≈1.475 mm. First-event intervals bracket consecutive *viewer* frames.

| Run | Speed (m/s) | First inversion (µs, interval] | First sampled inverted hexes | First deletion (µs, interval] | Deleted at first STATUS sample | Inverted hexes at last frame / total |
|---|---:|---:|---:|---:|---:|---:|
| b1 beams | 1000 | (1.854, 1.936] | 4 | (1.204, 1.505] | 27 | 650/17000 = 3.82% |
| b2 O-grid | 1000 | (2.186, 2.290] | 6 | (1.356, 1.641] | 11 | 681/17248 = 3.95% |
| b3 O-grid + beams | 1000 | (2.105, 2.234] | 4 | (1.405, 1.897] | 24 | 643/17248 = 3.73% |
| b4 D4 fix | 1000 | (1.777, 1.853] | 1 | (1.505, 1.800] | 25 | 603/17000 = 3.55% |
| b5 steel A | 1000 | (1.853, 1.936] | 5 | (1.505, 1.800] | 82 | 636/17000 = 3.74% |
| b6 316L | 1000 | (1.612, 1.697] | 1 | (1.501, 1.802] | 83 | 610/17000 = 3.59% |
| c1 beams + D4 | 1000 | (1.777, 1.853] | 1 | (1.505, 1.800] | 25 | 558/17000 = 3.28% |
| c1 beams + D4 | 500 | (4.506, 4.588] | 1 | (3.000, 3.302] | 4 | 257/17000 = 1.51% |
| c2 truss + D4 + maxdeg .8 | 1000 | (1.777, 1.853] | 1 | (1.505, 1.800] | 25 | 607/17000 = 3.57% |
| c2 truss + D4 + maxdeg .8 | 500 | (3.785, 3.868] | 2 | (3.000, 3.302] | 4 | 285/17000 = 1.68% |
| c3 beams + D4 + maxdeg .8 | 1000 | (1.777, 1.853] | 1 | (1.505, 1.800] | 25 | 557/17000 = 3.28% |
| c3 beams + D4 + maxdeg .8 | 500 | (4.588, 4.671] | 1 | (3.000, 3.302] | 4 | 259/17000 = 1.52% |

Except b6, the **first sampled geometric inversion follows the first sampled ball deletion**. For b6 the intervals overlap, so even global ordering is unresolved. This contradicts a general claim that visible inversion must precede all deletion; it does not determine order **within the same element**. Deleted elements retain nodal coordinates in the viewer, so some inverted geometry may belong to already dead elements.

### Which elements and where

All first observed inversions are **hexes with four nodes on the original ball contact surface**, at the nose/off-axis annulus (initial centroid z≈1.715–1.831 mm, about 0.24–0.36 mm above the tip). For b1, four initial centroids are (x,y,z)=(0.902,0.325,1.730), (0.920,0.267,1.730), (1.490,0.536,1.803), (1.520,0.442,1.803) mm; radial distance from center is 9.32–9.33 mm versus the 9.525 mm sphere radius. **None touches a symmetry-plane node.** b4 and all 1000 m/s c-decks first show the hex centered at (0.954,0.090,1.730) mm; it likewise has no exact symmetry-plane node. The first b2 O-grid inversion is six **outer-shell, nose-surface** hexes (x,y≈0.26–1.32 mm, z≈1.715–1.831 mm); four touch a symmetry plane, but two do not. Thus symmetry constraints are not necessary for onset. The O-grid inner core is not the first region. This diagnostic is defined only for hexes: the old ball's 1,500 C3D6R wedges have not been checked for their own integration-point Jacobians and could fail earlier.

At the last b1 frame (11.990 µs), 529/650 inverted hexes have at least one original surface node, 175 have a nose-surface node, and 162 touch a symmetry plane. At b2's last frame (11.978 µs), the corresponding counts are 498/681, 67, and 230. Inversion spreads away from the first nose annulus; these counts classify *initial* node locations, not the deformed contact state. The initial b1 first-inverting hexes have minimum edge 0.0398–0.0793 mm and initial minimum scaled Jacobian 0.995–0.997. The first b2 hexes have minimum edge 0.494–0.502 mm and initial minimum scaled Jacobian 0.998–0.999. They start well shaped; neither an initially negative Jacobian nor a poor initial corner angle explains the onset.

### Speed, mesh, and energy

For each matched c-deck pair, 500 m/s delays first sampled inversion from 1.85 µs to 3.87–4.67 µs (about 2.1–2.5×) and cuts the 12 µs inverted fraction from 3.28–3.57% to 1.51–1.68% (about 0.46–0.47×). First deletion also shifts from about 1.5–1.8 µs to 3.0–3.3 µs. Because the horizon stays at 12 µs, the fraction difference mixes load magnitude with penetration stage; it is not a speed power law.

b2's O-grid removes wedges and raises the **minimum per-hex edge** from 0.0391 to 0.115 mm overall; its first-inverting edges are about 0.5 mm, versus 0.04–0.08 mm in b1. Yet b2 has 681/17248=3.95% inverted at 12 µs versus b1's 650/17000=3.82%; onset is only about 0.35 µs later. b3 changes fibers as well and ends at 3.73%. Thin original nose edges and wedge topology therefore are **not sufficient explanations**; mesh still affects timing and location. The deck assigns fiber node-contact thickness 0.617974 mm, about 8–16× b1's first-inverting minimum edges and about 1.2× b2's. A nominal contact thickness is not an actual measured penetration distance.

The JSON `ALLKE` starts at **3546 J** for the 1000 m/s original ball and **886.5 J** for its 500 m/s version; b2 starts at 3577 J because its discretized mass differs. These are **3.55 kJ and 0.887 kJ**, consistent with SI density 7850 kg/m³, radius 9.525 mm, and speed. The HTML report's 3.55/0.89 “J” labels and the prior “mJ” interpretation are off by a factor of 1000. `ALLAE` at 12 µs is 0.28–4.95 J across bt1 and 1.16–4.72 J across bt2; that is **global artificial energy**, not a ball-local hourglass diagnosis.

## Ranked mechanisms, with limits

1. **Intense, localized ball-surface loading and progressive nose erosion: strongest geometric evidence.** First inversion sits immediately under original exterior contact nodes in every run; lower speed delays and reduces it. The deck includes both host-element/ball and fiber-node/ball hard contact. Existing `CPRESS` values cannot apportion force between these partners. The 0.618 mm fiber-node thickness is a plausible contributor, **not proven** as the source of the first load.
2. **Loss of element support after nearby deletion: plausible, unmeasured.** Aggregate deletion starts before sampled inversion in 11/12 runs, and the first inverted locations overlap the early nose erosion zone described in T-050. Without per-element STATUS, adjacency and fully orphaned nodes cannot be counted. The chronology supports a hypothesis, not proof of an erosion-to-inversion sequence.
3. **Reduced-integration hourglass/distortion after erosion: plausible, unmeasured.** All observed inverted elements are C3D8R and can geometrically fold; the global `ALLAE` is small relative to initial kinetic energy but does not bound local hourglass motion. There is no ball-local hourglass energy or element mode measure. b2 also uses C3D8R and still inverts.
4. **Material softening and zero-displacement JC damage evolution: relevant to deletion, not isolated as the inversion cause.** b4 corrects JC D4 from -0.05279 to +0.002, and c-decks change fibers/max degradation; none eliminates inversion. The deck still deletes immediately after JC damage initiation. Element-level `JCCRT`, `PEEQ`, rate, and STATUS are needed to say whether first-inverting elements were softened, alive, or already deleted.
5. **Original mesh's short edges / wedge transition: aggravator, not primary cause.** The original minimum edge is 0.039 mm, but the all-hex O-grid's first inversion occurs in initially excellent 0.5 mm outer cells and ends at a comparable fraction. A better mesh may improve a local failure margin but has not removed the mechanism.

These are ranked **hypotheses**, not a unique numerical cause. In particular, no current field separates host contact from fiber contact, or inversion of live elements from retained geometry of deleted elements.

## Ranked next fixes / discrimination tests

1. **Isolate or reduce fiber-node/ball contact thickness** while leaving host/ball contact fixed; separately run a host-only versus fiber-only contact inclusion comparison. This is a **deck-only** contact change and directly tests the leading load hypothesis. Compare first deletion/inversion, contact force by pair, and penetration; a thickness reduction changes contact geometry and must be physically justified.
2. **Enable an appropriate distortion safeguard or earlier distortion-triggered deletion for C3D8R**, subject to the installed Abaqus version's available section controls. This is **deck-only** if supported; it can prevent inverted *live* elements from destabilizing the solution, but it does not explain the initiating load and could increase erosion.
3. **Use enhanced hourglass control for the ball hex section.** This is **deck-only** if supported. A paired run with otherwise identical settings can test whether reduced-integration modes amplify inversion; track ball-local artificial energy or hourglass indicators if obtainable.
4. **Delay/regularize ball damage evolution** using a nonzero physical displacement/energy criterion while keeping the steel flow law fixed. This is **deck-only** and tests whether abrupt deletion causes unsupported surface nodes. A change in inversion by itself would not identify contact origin.
5. **Refine/rework the nose surface and transition cells** only after contact and deletion are isolated. This needs a **new mesh**, not a deck card alone. The b2 comparison argues against simply replacing the original grid as the first fix.

## Missing ODB evidence and supplied extraction

`extract_inversion_odb.py` is a read-only Abaqus Python script for the ROAR bt1/bt2 ODBs. It saves `BALL-1` element labels, types, connectivity, original nodes, **per-element STATUS**, Mises, PEEQ, PEEQR, JCCRT, SDEG, EVF, TEMP, TRIAX when present, nodal ball CPRESS and V, every existing frame through 6 µs, and sparse later frames. Match its node/element labels to the viewer coordinates and compute (a) first inversion and first deletion *of the same label*, (b) number of inverted elements still STATUS=1, (c) inverted elements adjacent to deleted elements, and (d) nodes whose **all** attached elements have STATUS=0. Existing ODB frame cadence still limits the temporal order; a denser rerun may be needed if both events occur between frames. `JCCRT`, PEEQR, or other fields may not be present in existing ODBs because the decks only request preselected fields and contact outputs; the script records available keys and fills missing fields with NaN.

To distinguish **what loads the nose**, request in a new deck pair-resolved ball/host and ball/fiber normal contact forces (and contact status/traction by surface), or perform the contact-isolation decks above. General-contact nodal `CPRESS` alone does not identify the partner. To test hourglass directly, request ball-local artificial/hourglass energy or the supported element diagnostic and correlate it with the first live inversion. No ROAR job or ODB was opened for this deliverable.
