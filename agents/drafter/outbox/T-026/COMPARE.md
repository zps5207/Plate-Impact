# T-026 Layup Comparison & Audit

All lengths are in metres unless otherwise stated. All CLI runs were executed sequentially using `--diameter 0.001 --plate-node-contact --fiber-node-contact --ball-instance Ball-1 --preview` on 24,000 native C3D8R hosts (Plate-1). The interactive curved preview is at [`agents/refiner/outbox/T-025/curved_stacked/preview.html`](file:///C:/Users/salas/OneDrive%20-%20The%20Pennsylvania%20State%20University/Plate%20Impact/agents/refiner/outbox/T-025/curved_stacked/preview.html).

## Summary Table

| Metric | Curved `stacked` (T-025/T-026) | Original Flatv2 `stacked` | Original Flatv2 `flat` | v500 baseline |
|---|---:|---:|---:|---:|
| Hosts (Plate-1) | 24,000 | 24,000 | 24,000 | 24,000 (+ 24,000 ghosts) |
| Fiber runs (count) | 490 | 450 | 450 | 328 |
| Fiber nodes | 20,610 | 19,161 | 19,161 | 14,192 |
| T3D2 segments | 20,120 | 18,711 | 18,711 | 13,864 |
| Total written fiber length (m) | 19.073276 | 17.675739 | 17.675739 | 13.086633 |
| Fiber volume ($L \times \frac{\pi d^2}{4}$) (m³) | 1.498012e-5 | 1.388249e-5 | 1.388249e-5 | 1.027822e-5 |
| Layers | 10 | 9 | 9 | Not independently established |
| Target segment length (m) | 9.479235e-4 | 9.446847e-4 | 9.446847e-4 | 9.428124e-4 (median) |
| Shortest written segment (m) | 9.340392e-4 (934.0 μm) | 9.181176e-4 (918.1 μm) | 9.181176e-4 (918.1 μm) | 9.331931e-4 (933.2 μm) |
| Median written segment (m) | 9.478221e-4 (947.8 μm) | 9.439638e-4 (944.0 μm) | 9.439638e-4 (944.0 μm) | 9.428124e-4 (942.8 μm) |
| Longest written segment (m) | 9.693952e-4 (969.4 μm) | 1.006076e-3 (1006.1 μm) | 1.006076e-3 (1006.1 μm) | 9.677382e-4 (967.7 μm) |
| Segment length / target (min) | 0.985353 | 0.971877 | 0.971877 | 0.9898 |
| Segment length / target (median) | 0.999893 | 0.999237 | 0.999237 | 1.0000 |
| Segment length / target (max) | 1.022651 | 1.064986 | 1.064986 | 1.0264 |
| Short runs ($L < L_{\text{target}}/2$) | 0 | 0 | 0 | 0 |
| Per-fiber segment spread ($\frac{\max - \min}{\text{median}}$) | 2.22e-10 | 1.60e-10 | 1.60e-10 | 0.0 (exact linspace) |
| Surface inclination $\theta_{\text{max}}$ | 11.469° | 0.0° | 0.0° | 0.0° |
| Maximum layer overlap fraction | 1.9969% | 0.0% | 0.0% | 0.0% |
| Ball-node contact lines | 4 | 4 | 4 | 3 |
| Contact plate nodes | 27,401 | 27,401 | 27,401 | ~27,401 |
| Contact fiber nodes | 20,610 | 19,161 | 19,161 | 14,192 |
| Plate contact half-thickness (m) | 4.993097e-4 | 4.889921e-4 | 4.889921e-4 | 4.889921e-4 |
| Fiber contact half-thickness (m) | 4.739111e-4 | 4.719819e-4 | 4.719819e-4 | 4.714062e-4 |
| World-frame vertices outside host | 0 / 20,610 | 0 / 19,161 | 0 / 19,161 | 0 / 14,192 |
| World-frame 5-point interior samples outside | 0 / 100,600 | 0 / 93,555 | 0 / 93,555 | 0 |
| CLI execution wall time (s) | 261.81 s | 227.69 s | 225.09 s | N/A |
| Peak process-tree RSS | 208.1 MiB | 202.4 MiB | 201.5 MiB | N/A |

## Key Differences and Analysis

### 1. Elimination of Short Segments via Even Resampling
- **T-024 vs T-025/T-026**: In T-024, placing vertices at every host edge crossing produced segments as short as **33.8 μm** (0.0338 mm), despite heuristic merging. In T-025/T-026, even arc-length resampling with equal-chord relaxation brings the shortest segment to **934.0 μm** (0.934 mm).
- **Comparison to Flat and Baseline**: The shortest curved segment (934.0 μm) is now directly comparable to the flat run (918.1 μm) and the v500 baseline (933.2 μm). All segments lie tightly between 98.5% and 102.3% of the target mesh cell length (~948 μm).
- **Truss Segment Count**: By spacing segments evenly at $L_{\text{target}}$ rather than at every mesh facet boundary, the total segment count dropped from 24,115 (in T-024) to 20,120 (in T-025/T-026). This 16.6% reduction substantially reduces model size and improves explicit time-step stability without compromising geometry or containment.

### 2. Exact Flat Equivalence
- Comparing `flat_stacked` and `flat_plain` byte-for-byte confirms:
  - `output.inp`: **Byte-for-byte identical** (True)
  - `fibers.vtk`: **Byte-for-byte identical** (True)
  - `fiber_volume.csv`: **Byte-for-byte identical** (True)
  - `host_fibers.vtk`: **Byte-for-byte identical** (True)
- The only differences between the two output directories are in `report.json` (where `flat_stacked` includes additional curvature metadata fields) and `preview.html` (which varies only in a dynamically generated Plotly DIV ID).

### 3. Layer Count and Volume Scaling
- The curved translation-stack deck has an exact thickness of 0.010 m (10 mm), producing exactly **10 layers** under the standard $d=0.001$ m rule.
- The original Flatv2 deck has a thickness of 0.00999999982 m, producing **9 layers**.
- Total written fiber volume on the curved deck is $1.498012 \times 10^{-5}\text{ m}^3$, which is 7.91% higher than Flatv2 ($1.388249 \times 10^{-5}\text{ m}^3$). This difference arises from the 10th layer and slight 3D arclength lengthening over the 11.47° dish curvature.

### 4. World-Frame Host Containment
- Comprehensive world-coordinate geometric audits of the written Abaqus decks:
  - Curved deck: 0 of 20,610 vertices outside; 0 of 100,600 interior segment samples outside (tested at 1/6, 2/6, 3/6, 4/6, 5/6 along every segment). Maximum outside distance is 0.0 μm.
  - Flat deck: 0 of 19,161 vertices outside; 0 of 93,555 interior segment samples outside. Maximum outside distance is 0.0 μm.
- Both decks have identity instance transformations for `EMBFIB-1`, correctly matching the world assembly frame.
