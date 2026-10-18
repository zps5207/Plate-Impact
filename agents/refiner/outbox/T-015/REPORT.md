# T-015: v500 host fiber volume fraction audit

## Verdict

**The 821 `Vf >= 1` values are a volume-assignment bug in the data fed to the VUEL, not evidence that fibers physically fill more than their host cells. High confidence for the sampled elements; the exact corrected distribution over all 24,000 cells has not been computed.** The default mesher credits a host with the **entire circular cross-section** of each fiber whenever the centerline passes through it. A fiber diameter of 1 mm is similar to or larger than the in-plane width of the smaller v500 host cells. Much of that fiber disk belongs to neighboring cells, so the centerline approximation can assign more fiber volume to a cell than its geometric volume. `docs/INTERFACE.md` already describes this limitation and the optional cross-section-aware estimator, but `generate.py` currently writes the approximate `rows` values to SVAR107 even when `--precise-volume` is requested.

No duplicate T3D2 node-pair segments were found. The most extreme sampled cells contain only **one continuous strand**, represented by one or two adjacent T3D2 segments. The eight fiber planes are 1.2 mm apart; their 1 mm-diameter cylinders have 0.2 mm interlayer clearance. T0 and T90 occupy alternating planes. This is inconsistent with a T0/T90 double-count or an obvious physical overlap. The deck's truss section area is `7.85398163397448e-7 m² = pi*(0.001 m)^2/4`, so a metres-versus-millimetres error is also ruled out for these values.

The consequence is material: `uel/VUEL_failure.for` uses `ETA_VF=max(1-SVAR107,1e-6)` to scale matrix mass and integration volume. Every one of these 821 elements receives effectively zero matrix contribution. The Hub's solver-log mass example for element 402 is consistent with this, but I did not independently inspect that solver log.

## How the deck value is computed

`embmesh/generate.py` calls `fiber_volume_rows` in `embmesh/volume.py`, passes `row[3]` to `fractions`, then `embmesh/vuelghost.py::_initial_solution_lines` writes that fraction to the 107th solution value for each `Plate-1.<label>`. `embmesh/writers.py` writes the same approximate rows to `fiber_volume.csv`; `embmesh/hostvtk.py` only visualizes the supplied fractions. The formula is

`Vf(e) = [pi*d²/4 * sum_f sum_s length(segment_s clipped to host_e)] / volume(host_e)`, with `d = 0.001 m` and `A = 7.85398163397448e-7 m²` in this deck. `hex_volume` uses 2×2×2 quadrature. `clip_segment_hex` finds the interval of the segment's **centerline** in each host, so a crossing strand's length is split among hosts by its centerline intersections. The entire area is assigned to each clipped interval. Both T0 and T90 fiber objects enter the same summation (`l0+l90`), although the deck's T0/T90 fibers lie in alternating z planes. The code does not de-duplicate geometrically overlapping fibers or take a union of their volumes; this layup's duplicate node-pair count is zero.

`embmesh/volume.py::fiber_volume_rows_precise` instead samples the circular disk across the hex at stations along the segment and is available through `--precise-volume`. It writes a separate CSV, but the current `generate.py` still uses the approximate `rows` for SVAR107. The precise estimator is numerical, not an exact solid-geometry Boolean union.

## Deck distribution and location

Parsed `verification/roar/t_nc/v500/v500_deck.inp` directly. Plate-1's assembly transform was applied to host nodes before comparing them with EMBFIB coordinates. Values are in metres. Counts sum to 24,000.

| Vf interval | Cells |
|---|---:|
| 0 | 7,521 |
| (0, 0.1) | 392 |
| [0.1, 0.25) | 747 |
| [0.25, 0.5) | 1,211 |
| [0.5, 0.75) | 1,236 |
| [0.75, 1) | 12,072 |
| [1, 1.25) | 712 |
| [1.25, 1.5) | 98 |
| [1.5, 2) | 8 |
| [2, 2.5) | 3 |

There are 16,479 positive values; the maximum is 2.27296179210333. All 821 crowded cells have in-plane radius `sqrt(x²+y²)` between 41.11 and 49.70 mm. None occurs inside 40 mm, including the impact region near the origin. There are 414 in the 40–45 mm annulus and 407 in the 45–50 mm annulus. The crowded cell centers range over x = 16.98–43.59 mm, y = 20.52–44.83 mm, and z = −9.5 to −1.5 mm. Thus they are **near the circular outer edge**, with some on the plate's top/bottom host layers, rather than concentrated at the impact point or the straight x/y symmetry edges. Their median host volume is `5.76e-10 m³`, compared with `8.43e-10 m³` over all hosts; the smallest crowded host is `1.93e-10 m³`. Smaller edge cells are especially vulnerable to the full-disk assignment.

## Geometry reconstruction for sampled cells

The analysis script reads Plate VU1 connectivity, Plate nodes, EMBFIB T3D2 connectivity and nodes, applies the Plate-1 instance transform, clips every candidate segment to each selected hex, and recomputes `A*sum(length)/Vhost`. It reproduces SVAR107 to approximately 3e-10 absolute or better for these samples. The last column is the **numerical** swept-cylinder/hex estimate with 21 axial stations, for corroboration only. The centerline clip uses the same geometry routine as production, so the first reconstruction checks deck consistency and arithmetic, not an independent clipping algorithm.

| Host | Host volume (m³) | In-host strand lengths (m) | Deck Vf | Recomputed Vf | Cross-section-aware estimate |
|---:|---:|---|---:|---:|---:|
| 402 | 5.938644e-10 | 0.000829875 (one T90 segment) | 1.097526545 | 1.097526545 | 0.504 |
| 1161 | 2.167386e-10 | 0.000058992 + 0.000568255 (two joined T90 segments) | 2.272961792 | 2.272961792 | 0.712 |
| 13998 | 2.089488e-10 | 0.000050952 + 0.000541056 (two joined T0 segments) | 2.225244955 | 2.225244955 | 0.542 |
| 11591 | 2.219377e-10 | 0.000102061 + 0.000492804 (two joined T90 segments) | 2.105122257 | 2.105122257 | 0.932 |

For example, element 402 has `Vf = (0.000829874612 m)*(7.853981634e-7 m²)/(5.938644484e-10 m³) = 1.097526545`. Element 1161 has `Vf = (0.000058992153 + 0.000568254735)*A/(2.167385987e-10) = 2.272961792`. The two segments of 1161 share a node; they are one strand split for meshing, not two crossing fibers.

## Proposed change (not applied)

Regenerate v500 from the original source deck after making the VUEL path use the existing cross-section-aware estimator. Add an explicit matrix-fraction floor, here illustrated as 10%, and record how many values were capped. That floor is a **modeling choice** to review against the intended matrix content; it avoids the current `1e-6` numerical remnant but cannot correct a bad layup or substitute for the more accurate geometric estimate. Any unexpected precise `Vf >= 1` should trigger geometry review before a solver run.

```diff
diff --git a/embmesh/generate.py b/embmesh/generate.py
@@
-    if precise_volume:
+    if precise_volume or host_mode == "vuel-ghost":
@@
-    fractions = {row[0]: row[3] for row in rows}
+    volume_rows = precise_rows if host_mode == "vuel-ghost" else rows
+    raw_fractions = {row[0]: row[3] for row in volume_rows}
+    fractions = (raw_fractions if host_mode != "vuel-ghost" else
+                 {label: min(max(vf, 0.0), 0.9)
+                  for label, vf in raw_fractions.items()})
@@
     report_kw.update(host_meta)
+    if host_mode == "vuel-ghost":
+        report_kw.update(vuel_fraction_source="cross_section_weighted",
+                         vuel_fraction_raw_max=max(raw_fractions.values(), default=0.0),
+                         vuel_fraction_capped_count=sum(vf > 0.9 for vf in raw_fractions.values()))
```

Also make the CLI print `fiber_volume_precise.csv` for VUEL mode, since the patch writes it automatically. As a quicker **stopgap for an already generated approximate deck**, clamp SVAR107 to 0.9 before rerunning; this prevents effectively zero host mass but leaves potentially large local volume errors. Neither proposal was run through Abaqus here.

## Provenance and limits

Command: `python outbox/T-015/analyze_v500.py`. It verified the deck's counts, section area, positions, segment uniqueness, selected reconstructed values, and four numerical cross-section-aware samples. Source inspection covered `embmesh/generate.py`, `volume.py`, `geometry.py`, `fibers.py`, `writers.py`, `hostvtk.py`, `vuelghost.py`, `cli.py`, and `uel/VUEL_failure.for`. No v500 `fiber_volume.csv` or original mesher settings/CLI record was found locally, so I analyzed the exact run deck rather than regenerating it. Full 24,000-cell precise volumes, global physical overlap testing, the solver log, Abaqus reruns, and the proposed patch's behavior remain unverified.
