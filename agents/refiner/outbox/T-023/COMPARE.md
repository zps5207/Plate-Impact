# T-023: curved 10-ply deck versus v500

Units are metres, seconds, kg, Pa. `curved_10ply_d096.inp` is the generated deck. The reference is `Flat-nodecontact/v500/output.inp` (read only). Fiber diameter here is **0.96 mm**, with area **7.23822947387088e-7 m²**. The baseline's 1.0 mm diameter cannot fit a centered fiber at the curved plate edge: the maximum allowed diameter is 1 mm × cos(11.46944°) = about 0.98003 mm.

| Quantity | v500 baseline | Curved 10-ply |
|---|---:|---:|
| Plate active hosts | 24,000 VU1; plus 24,000 C3D8R ghost | 24,000 native C3D8R |
| Plate nodes | 27,401 | 27,401 shared-interface nodes |
| Ball nodes / elements | 3,642 / 3,312 | 3,642 / 3,312 |
| Fiber nodes / T3D2 segments | 14,192 / 13,864 | 25,770 / 25,260 |
| Fiber runs | 328 inferred from nodes minus segments | 510 (51 per ply) |
| Fiber length | 13.08663334 m | 19.89030110 m |
| Fiber volume, length × section area | 1.02782178e-5 m³ | 1.43970564e-5 m³ |
| Minimum fiber segment | 0.933193 mm | 0.0285507 mm |
| Segment length / c, c = sqrt(2e11/981) = 14,278.43 m/s | 65.36 ns | 2.000 ns |

The segment/c estimates are only fiber wave transit estimates, not Abaqus stable increments. The new minimum is 32.7 times smaller. The 5%-of-local-edge criterion passes all segments after 320 near-crossing vertices were merged, but the absolute minimum of 28.55 µm remains below the brief's approximately 0.1 mm time-step concern. There are **zero** segments below 5% of their assigned local edge; the minimum ratio is 0.0501327. No isolated segment was dropped.

Per-ply T3D2 segment counts, plies 1–10: **2529, 2523, 2529, 2523, 2529, 2523, 2529, 2523, 2529, 2523**. Each ply has 51 continuous fiber runs. Ply 1 is 0° along part X, ply 2 is 90° along part Z, alternating thereafter. The union elsets `EMBMESH_FIBERS_T0` and `EMBMESH_FIBERS_T90` are retained. Each `FIBERS_PLY_k` is embedded into assembly host elset `PLY_k`.

## Geometry and containment

The one-element source has 2,400 top quads. Rebuilding its bottom from the top gives an exact (0, -0.01, 0) translation. Original top/bottom projected mismatch: maximum 76.4195 µm, mean 4.53093 µm, 95th percentile 15.9928 µm; these are respectively 0.08131, 0.004821, and 0.01702 of the 0.939854 mm median in-plane edge. `make_one_element_deck.py` exposes `--face-congruence-tolerance` (default 0.1 mm) and reports these values.

The generated 10-ply host uses one node plane per interface. Its `Outside`, `X`, and `Y` sets have 891, 561, and 561 nodes, respectively, on the outer rim, part X=0, and part Z=0. The plate instance transform and Ball instance are preserved. The alternate `--duplicate-interface-nodes` flag exists in `build_deck.py` and `stack_and_fibers.py`; it was not used for this deliverable.

Check of **the written deck coordinates** sampled endpoints and 25%, midpoint, and 75% positions on all 25,260 segments: 126,300 samples, **0 outside their assigned ply**. Minimum analytic normal clearance was 0.489116 mm against d/2 = 0.480 mm. Minimum endpoint distance to the projected outline was 0.480 mm. This is centerline containment and analytic normal clearance, not a full swept-cylinder interference check on every faceted interface.

## Non-geometry deck differences

The Ball part, its section assignments, Fiber/Matrix/Mild Steel material blocks, `General` friction/hard-contact law, the three boundary lines (`Outside ENCASTRE`, `X XSYMM`, `Y YSYMM`), ball velocity (`Ball-1.Ball, 3, -500.`), `Step-1` explicit duration (7e-05 s), and bulk viscosity (0.06, 1.2) are copied from v500. The baseline contact inclusions (`Surf-1`/`Surf-2` pairs and `EMBMESH_PLATE_NODES`/`EMBMESH_BALL_SURF`) are retained. The plate face surface changes with the new mesh: source top is S1 and exterior lateral faces S3–S6. Ball surface `Surf-2` is preserved.

Every non-geometry change from the v500 input is deliberate:

1. Active VU1 and overlaid ghost C3D8R plate sections become 10 native C3D8R `Matrix` sections. The ghost material, VUEL diagnostics sets, 336,000-line VUEL solution initialization, and VUEL/ghost element output requests are omitted. Consequently this is a native-host comparison, and the plate constitutive/failure implementation differs from v500 beyond the curvature and fiber placement.
2. Baseline T3D2 Fiber section area `7.85398163397448e-7 m²` becomes `7.23822947387088e-7 m²`. Baseline global T0/T90 embedding becomes 10 per-ply `*Embedded Element` blocks; global direction union elsets remain.
3. Fiber-node to ball-node contact is added with `EMBMESH_FIBER_ALL_NODES`, `EMBMESH_FIBER_NODES`, and `EMBMESH_BALL_SURF`. The plate-node auto thickness changes from baseline `0.000488992080759272` to `0.0005` m because the native host median edge is 1 mm; fiber-node auto thickness is `0.000449784870849705` m. The existing general contact interaction is reused.
4. Output requests for VUEL and ghost element state are removed; restart and standard field/history output requests are retained. No cohesive interaction or ghost host is present.

The baseline also has 24,000 ghost elements and their related data that this deck cannot reproduce under the native C3D8R constraint. Thus the run can compare impact response but cannot isolate curvature and fiber placement as the only causes of any difference.

## Self-consistency and reproduction

`check.py` found 3 parts; 61 set declarations; 5 surfaces; 10 embedded blocks; 10 Plate, 2 fiber, and 2 Ball section declarations; no duplicate labels/names, missing element nodes, missing set members, or unresolved surface/embedding references. Counts are in `checks.json`. Abaqus `datacheck`, input acceptance, and a ROAR run were unavailable and have not been verified.

Run from `agents/refiner`:

```powershell
python -B outbox/T-023/make_one_element_deck.py inbox/T-022/Flatv2_curved.inp outbox/T-023/Flatv2_curved_1el.inp
python -B outbox/T-023/build_deck.py outbox/T-023/Flatv2_curved_1el.inp "../../Flat-nodecontact/v500/output.inp" outbox/T-023/curved_10ply_d096.inp
python -B outbox/T-023/check.py outbox/T-023/curved_10ply_d096.inp outbox/T-023/Flatv2_curved_1el.inp outbox/T-023/checks.json
python -B outbox/T-023/compare_stats.py "../../Flat-nodecontact/v500/output.inp" outbox/T-023/baseline_stats.json
```
