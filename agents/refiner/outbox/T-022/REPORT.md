# T-022: real curved quarter-disc mesh

## Coordinate and source-geometry decision

All generation and checks use **Plate part coordinates**: X and Z are the projected in-plane axes, Y is thickness, and the stack points in negative Y. The original `Plate-1` instance rotation and Ball part/instance are retained in the reduced deck.

The supplied ten-layer source is not an exact translation stack despite the brief's description. Its 2,491 outer-face nodes on each side differ in projected XZ coordinates: nearest opposite-face projection mismatch is 76.42 µm maximum, 16.00 µm at the 95th percentile. `make_one_element_deck.py` therefore takes the real top-face quads and replaces the bottom with a copy translated by `(0,-0.01,0)` m. This is a documented geometry change. The resulting 2,400 C3D8R hexes have 4,982 nodes; the maximum stack-vector deviation after writing and reading the deck is `4.41e-16` m, and the minimum center Jacobian is `2.10e-10` m³. Ball data is copied unchanged.

## Generation

`stack_and_fibers.py` makes N translated plies with **duplicated interface nodes**. Its compressed array output includes named `PLY_1..PLY_N` element ranges and per-fiber polyline points and segment-to-host IDs. Fibers alternate 0° (along part X) and 90° (along part Z), at pitch `d`, on each ply's centered mid-surface. The scanline algorithm clips every projected line against every convex C-mesh quad, joins touching intervals into runs, and gives separate fibers to disjoint runs. Every emitted run is trimmed until both ends have at least `d/2` projected distance from the actual outer outline. The first ply's VTK is written for N=3, 6, and 10; N=3 also has top and side PNGs.

The supplied input has a quarter-disc footprint, so the tested scanlines yielded one connected run per line. Multi-run handling exists in the code but was not exercised by this fixture. No Abaqus impact analysis was run.

## Checks

From node spacing, `theta_edge=11.46823°`. From the four corners and center of each bilinear top face, `theta_bilinear=11.46944°`, hence `cos(theta_max)=0.9800309`. The diameter limits for N=3, 6, 10 are 3.26677, 1.63338, and 0.980031 mm. All reported normal clearances use the analytic sphere that generated the warped top surface, evaluated at vertices and five points per segment. The FE surface is bilinear, and the maximum measured vertical polyline-to-bilinear-midface deviation is 0.33 µm; a full swept-cylinder distance to every faceted interface was not computed.

| N | d (mm) | fibers | vertices / mids outside own ply | max vertical chord deviation / d | min normal clearance vs d/2 (mm) | min endpoint outline clearance (mm) | shortest segment (µm) | segments < 5% edge, before → after snap | ply-1 volume fraction min / max / mean | check time / peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3.20 | 45 | 0 / 0 | 0.000099 | 1.63445 vs 1.600 | 1.600 | 5.06 | 29 → 3 | 0 / 4.223 / 0.680 | 19.3 s / 86.7 MB |
| 3 | 3.30 | 42 | 0 / 0 | 0.000100 | 1.63458 vs 1.650 | 1.650 | 2.54 | 25 → 0 | 0 / 6.148 / 0.696 | 17.6 s / 42.7 MB |
| 6 | 1.60 | 186 | 0 / 0 | 0.000203 | 0.81629 vs 0.800 | 0.800 | 0.0153 | 108 → 24 | 0 / 2.142 / 0.719 | 47.8 s / 43.9 MB |
| 6 | 1.65 | 180 | 0 / 0 | 0.000194 | 0.81635 vs 0.825 | 0.825 | 2.66 | 105 → 18 | 0 / 2.553 / 0.741 | 45.8 s / 43.9 MB |
| 10 | 0.96 | 510 | 0 / 0 | 0.000339 | 0.48912 vs 0.480 | 0.480 | 0.159 | 320 → 20 | 0 / 1.454 / 0.734 | 97.3 s / 45.7 MB |
| 10 | 0.99 | 500 | 0 / 0 | 0.000328 | 0.48912 vs 0.495 | 0.495 | 0.393 | 305 → 0 | 0 / 1.534 / 0.757 | 95.2 s / 45.8 MB |

All five sampled interior points per segment also passed `inverse_hex` in their assigned own-ply host; maximum sampled outside-host penetration was `0/d` for every case. The 5% snap test removed short-intersection vertices and rechecked new segment midpoints; all remained in one of their crossed own-ply hosts, but 3, 24, and 20 short segments remain for the N=3, 6, and 10 below-limit cases. The shortest unsnapped 1.60 mm-pitch segment is only 15.3 nm. This is a real time-step risk.

The per-host volume fractions come from `fiber_volume_rows` for ply 1. Values over 1 are **not physically valid local fiber fractions**: the routine assigns the full fiber cross-section to each host traversed by the centerline, while `d` is comparable to or larger than the in-plane cell size. A cross-section-aware volume calculation or larger cells/smaller fiber diameter is needed before using those values as material volume fractions. This is why no optional ROAR smoke deck is submitted.

The detJ corner/center ratio spans `0.47575..0.99967`; the `1/cos(theta)` skew indicator spans `1.000004..1.020376`. This measures shape variation within a hex as well as surface slope; the low detJ ratio comes from irregular projected quads.

## Reproduce

From `agents/refiner`:

```powershell
python -B outbox/T-022/make_one_element_deck.py inbox/T-022/Flatv2_curved.inp outbox/T-022/Flatv2_curved_1el.inp
python -B outbox/T-022/stack_and_fibers.py outbox/T-022/Flatv2_curved_1el.inp --plies 3 --diameter 0.0032 --output outbox/T-022/N3_below
python -B outbox/T-022/stack_and_fibers.py outbox/T-022/Flatv2_curved_1el.inp --plies 6 --diameter 0.0016 --output outbox/T-022/N6_below
python -B outbox/T-022/stack_and_fibers.py outbox/T-022/Flatv2_curved_1el.inp --plies 10 --diameter 0.00096 --output outbox/T-022/N10_below
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 3 --diameter 0.0032 --output outbox/T-022/N3_below --preview
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 3 --diameter 0.0033 --output outbox/T-022/N3_above
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 6 --diameter 0.0016 --output outbox/T-022/N6_below
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 6 --diameter 0.00165 --output outbox/T-022/N6_above
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 10 --diameter 0.00096 --output outbox/T-022/N10_below
python -B outbox/T-022/check.py outbox/T-022/Flatv2_curved_1el.inp --plies 10 --diameter 0.00099 --output outbox/T-022/N10_above
```

The measured peak RSS is per check process, sampled every 50 ms. The maximum was 86.7 MB, well under the 4 GB limit. The six reported checks were run in concurrent processes, so their wall times include CPU contention; peak combined memory was not measured. The reduced-deck command took about 1.0 s, and each stack generator command took under 1 s in this workspace.
