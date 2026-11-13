# T-045: fiber motion, host deletion, and mass in vp4

## Scope and reproducibility

`analyze_fiber_host.py` reads the two vp4 viewer NPZ files, the two energy CSVs, and the VUEL input deck. Run it from this folder with `python analyze_fiber_host.py <project-root>`. Outputs are `*_frames.csv` (200 frames), `*_deaths.csv` (one row per first observed host death), `*_ply_direction.csv` (one row per ply and direction per frame), and `*_summary.json`. Coordinates, density, mass, and energy calculations use SI units. The energy CSVs are in mJ, converted to J here. Viewer frames are spaced about 0.35 µs apart, so event order within one interval cannot be resolved.

## Direct measurements

| Measure | VUEL host | Native host |
|---|---:|---:|
| Host elements first observed dead | 612 / 80,500 (0.760%) | 517 / 80,500 (0.642%) |
| First host death | 2.10 µs | 1.75 µs |
| First segment above estimated 1.065 failure stretch | 6.65 µs | 7.70 µs |
| Maximum segment stretch in exported geometry | 538.3× | 350.6× |
| Maximum fraction above 1.1× | 0.0788% (~163 segments) | 0.0812% (~168 segments) |
| Maximum fiber node displacement | 664 mm | 429 mm |
| Peak ALLKE | 5.789 J | 6.128 J |

The first host death precedes any exported fiber stretch above the estimated failure strain by 4.55 µs (VUEL) or 5.95 µs (native). Thus fiber tensile failure cannot explain the **first** host deaths. It does not establish the order of later local events. The >100× stretch is confined to a tiny subset; at peak, the 99th percentile stays below 1.003 and the 99.9th below 1.009. At the final frame, about 163 (VUEL) or 167 (native) segments exceed 2× their initial length. Their continued geometric presence does **not** show they remain active: the viewer export has no fiber STATUS, and Abaqus can retain coordinates of deleted elements.

The highly stretched fibers concentrate in the later plies. The maximum count above 1.1× is in ply 19, x direction: 57 VUEL and 38 native segments. The largest individual stretch is in ply 17, x direction. The fibers alternate x on odd plies and y on even plies; the per-frame CSV gives the counts, maximum stretch, displacement, and speed for every ply. These ply labels derive from initial z and the nominal 1.27 mm ply pitch.

## Spatial and temporal association

For each transition from host STATUS 1 to 0, the script uses the element center and fiber-node coordinates in the immediately preceding frame. A `hot` node is attached to a segment stretched above 1.1× then, or moved faster than 1,000 m/s during the preceding frame interval. One element size means the cube root of that host element's reference volume (median 1.23 mm).

| Proximity at first observed host deletion | VUEL | Native |
|---|---:|---:|
| Any fiber node within one element size | 612/612 (100%) | 517/517 (100%) |
| Hot fiber node within one element size | 214/612 (35.0%) | 188/517 (36.4%) |
| No hot fiber within two element sizes | 138/612 (22.5%) | 130/517 (25.1%) |

The `any fiber` result is not causal evidence: the embedded fibers are dense throughout the laminate. The hot-fiber counter-check is more discriminating, but still correlational. Many host deaths occur near the ball without a nearby hot fiber by this definition. VUEL has 42 host deaths before any segment anywhere exceeds 1.065×; native has 52. Deletion coordinates and distances are in `*_deaths.csv`. A causal comparison needs paired ODB fiber STATUS and host STATUS at finer time resolution and local force/stress histories.

## Mass and kinetic energy

Fiber length from the T3D2 reference geometry is about 255.7 m. With area 3.137e-7 m² and density 981 kg/m³, the deck assigns **78.70 g** of fiber mass. Both host reference meshes contain 80,500 bricks and have geometric matrix mass **200.02 g** at 980 kg/m³. The native deck keeps all 200.02 g and adds the fibers, totaling **278.72 g**: an extra **39.3%** relative to the full matrix host. The VUEL deck's SVAR107 values give a volume-weighted effective host mass of **122.10 g**, because `VUEL_material.for` uses `ELEMASS = DENS * (1 - FIBER_VOL_FRAC) * ELVOL_GEOM`. Its host plus fibers total **200.80 g**, only 0.78 g above the uncorrected matrix mass. The unweighted mean SVAR107 is 0.3895; the calculation uses each element's actual volume and SVAR107, not that mean. The deck geometric mass agrees with the viewer geometry within 0.01 mg.

Thus fibers are not excessively heavy in the VUEL **mass bookkeeping**. The native configuration has a substantial double-counted volume/mass. That cannot by itself explain the similar large displacements in both runs, nor the rise from initial ALLKE 3.546 J to peaks of 5.789/6.128 J.

The CSVs contain finite-difference kinetic-energy *proxies* using reference lumped masses, fiber positions, and host positions. Their peaks are 341/216 J for fiber nodes and 3,270/2,327 J for geometric host nodes (VUEL/native), far above ODB ALLKE. Even at ~5.6 µs, before major motion, the host proxy is 8.6/33.6 J against ALLKE ~3.5/3.7 J. The proxies therefore **must not be interpreted as solver kinetic energy or added mass**. They likely include motion of nodes associated with deleted/distorted elements, and VUEL host proxy also uses uncorrected mass. The export lacks actual nodal V, per-element alive mass, and fiber STATUS, so trustworthy fiber-versus-host kinetic-energy partition is not available locally.

## Ranked explanations and decisive checks

1. **Detached/deleted fiber or host geometry keeps moving in the viewer.** Supports: extreme stretch affects <0.1% of segments; position-derived KE exceeds solver ALLKE by orders of magnitude; deleting elements need not remove their plotted nodes. Against: fiber STATUS is absent, so this is not confirmed. Query fiber and host `STATUS` for the same labels and frames; overlay the high-stretch segments and host death locations with live/dead state, plus `S11`, `PEEQ`, and `DUCTCRT` for fiber T3D2 elements.
2. **The embedded constraint transfers large fiber tension to comparatively weak matrix hosts.** Supports: E=135 GPa versus 0.7 GPa matrix, fiber yield 3.5 GPa versus matrix 70 MPa; 1.04 elastic stretch would imply ~1.69 kN per segment at this area, capped/reduced by plasticity and damage. Some host deaths are near hot fibers. Against: only ~35–36% of deaths have a hot node within one element size; first host deaths precede large fiber stretch. Query live fiber axial `S11`, `PEEQ`, `DUCTCRT`, and STATUS next to each dying host and its stress/damage state (`S`, `PEEQ`/damage variables, STATUS) immediately before death. Evaluate whether force rises before host damage.
3. **Native double counting of matrix and fiber mass.** Supports: +78.7 g (+39.3%) beyond full matrix mass. Against: VUEL corrects nearly all of it, yet shows comparable pathology. Query actual nodal/element masses or initial mass summary on both ODBs, then recompute KE from ODB `V` and alive mass; check mass scaling history if used.
4. **Contact, distortion, or deletion-related energy creation.** Supports: ALLKE exceeds the initial 3.546 J in both runs and host-node motion is extreme. Against: the local exports do not isolate energy source. Query `ALLKE`, `ALLIE`, `ALLVD`, `ALLWK`, `ETOTAL`, contact work/energy histories if present, and element-level energy/damage/contact fields available in each ODB, resolved around the first rise.

For ROAR read-only extraction, first list available step/frame field and history output keys. Then extract fiber `STATUS`, `S11`, `PEEQ`, `DUCTCRT`, nodal `V`, and any mass/element-energy quantities actually present at the first-death times and at 10, 20, 40, 70 µs. The current NPZ exporter writes `STATUS` **only for host elements** and writes positions for fibers; it cannot settle whether highly stretched fibers are carrying tension or have failed. No ROAR ODB extraction or new solve was performed in this task because an authenticated SSH agent socket was not available in the session. No `sbatch` was submitted.
