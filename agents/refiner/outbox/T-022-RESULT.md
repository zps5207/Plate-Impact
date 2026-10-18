task_id: T-022
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-022/make_one_element_deck.py
  - outbox/T-022/Flatv2_curved_1el.inp
  - outbox/T-022/Flatv2_curved_1el.json
  - outbox/T-022/stack_and_fibers.py
  - outbox/T-022/check.py
  - outbox/T-022/REPORT.md
  - outbox/T-022/N3_below/stack_fibers.npz
  - outbox/T-022/N3_below/fibers_ply1.vtk
  - outbox/T-022/N3_below/fibers_top.png
  - outbox/T-022/N3_below/fibers_side.png
  - outbox/T-022/N3_below/checks.json
  - outbox/T-022/N3_above/checks.json
  - outbox/T-022/N6_below/stack_fibers.npz
  - outbox/T-022/N6_below/fibers_ply1.vtk
  - outbox/T-022/N6_below/checks.json
  - outbox/T-022/N6_above/checks.json
  - outbox/T-022/N10_below/stack_fibers.npz
  - outbox/T-022/N10_below/fibers_ply1.vtk
  - outbox/T-022/N10_below/checks.json
  - outbox/T-022/N10_above/checks.json
  - outbox/T-022-RESULT.md
summary: |
  Built a 2,400-hex, one-element-thick version of the real curved quarter-disc Plate and generated N=3, 6, 10 translation stacks with 0/90 centered fibers. All tested fiber vertices, midpoints, and five sampled interior points per segment lie in their assigned ply hosts. Diameters just below h*cos(theta_max) pass the normal-clearance check; those just above fail. The source outer faces are not exact translates: their nearest projected-node mismatch reaches 76.42 µm, so the reduced deck uses the real top face and a translated bottom face. Coordinates and checks use the Plate PART frame (X,Z projection; -Y stack); the original Ball and instance transformations are retained.
checks_run: |
  Stack deviation after deck read: 4.41e-16 m. theta_max: 11.46944° (edges 11.46823°, bilinear corners/center 11.46944°). detJ min/max ratio: 0.47575/0.99967; skew 1/cos(theta) min/max: 1.000004/1.020376. Maximum sampled outside-host penetration: 0/d in all cases. Minimum endpoint outline clearance: d/2 in all cases. The table's V/M column is the count outside own ply, with total vertices/midpoints in parentheses. Clearance is minimum normal distance vs d/2, in mm. VF is ply-1 min/max/mean from fiber_volume_rows. Times and peak RSS are per check process.

  | N | d mm | N_max | fibers | V/M outside (totals) | chord/d; outside/d | clearance mm | segments <5% edge before→after snap | VF min/max/mean | time; peak RSS |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | 3 | 3.20 | 3 | 45 | 0/0 (2166/2121) | 0.000099; 0 | 1.63445 vs 1.600 PASS | 29→3 | 0/4.223/0.680 | 19.3 s; 86.7 MB |
  | 3 | 3.30 | 2 | 42 | 0/0 (2079/2037) | 0.000100; 0 | 1.63458 vs 1.650 FAIL | 25→0 | 0/6.148/0.696 | 17.6 s; 42.7 MB |
  | 6 | 1.60 | 6 | 186 | 0/0 (9246/9060) | 0.000203; 0 | 0.81629 vs 0.800 PASS | 108→24 | 0/2.142/0.719 | 47.8 s; 43.9 MB |
  | 6 | 1.65 | 5 | 180 | 0/0 (8952/8772) | 0.000194; 0 | 0.81635 vs 0.825 FAIL | 105→18 | 0/2.553/0.741 | 45.8 s; 43.9 MB |
  | 10 | 0.96 | 10 | 510 | 0/0 (26090/25580) | 0.000339; 0 | 0.48912 vs 0.480 PASS | 320→20 | 0/1.454/0.734 | 97.3 s; 45.7 MB |
  | 10 | 0.99 | 9 | 500 | 0/0 (25450/24950) | 0.000328; 0 | 0.48912 vs 0.495 FAIL | 305→0 | 0/1.534/0.757 | 95.2 s; 45.8 MB |

  All post-snap midpoints stayed inside a crossed host of their own ply. Full statistics, shortest segment lengths, plots, and interpretation are in REPORT.md. The reduced deck parses as 4,982 nodes/2,400 hosts with positive center Jacobians. The generated stack arrays have 7,200/14,400/24,000 hosts for N=3/6/10 and named PLY_1..PLY_N element ranges. Ball-part text was checked byte-for-byte up to the Plate part boundary.

  Reproduce from agents/refiner:
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
not_verified: |
  Abaqus input processing, embedding acceptance, and any ROAR impact run; a full swept-cylinder clearance calculation against faceted ply interfaces (normal distances use the generating analytic sphere); true cross-section-aware per-host fiber volume fractions; peak combined memory when checks ran concurrently; scanline multi-run behavior on a nonconvex footprint. The optional N=3 Abaqus smoke deck was not delivered because the length-based local volume-fraction check exceeded 1. Snap checks covered new segment midpoints, not every point along each snapped segment.
suggestions: |
  Resolve the source top/bottom geometry discrepancy before treating this as a faithful Flatv2 replacement. Use cross-section-aware volume accounting or smaller d/larger in-plane cells, and address remaining tiny segments before a ROAR smoke run. Then verify the native embedded-fiber deck in Abaqus/Explicit.
concerns: |
  The supplied source is not exactly stackable; the reduced deck's bottom face was reconstructed. The existing centerline-based fiber_volume_rows gives per-host values as high as 4.223, 2.142, and 1.454 for the below-limit cases. Snapping at 5% still leaves 3, 24, and 20 short segments. These are material/model-quality limitations despite passing centerline containment.
denied_actions: none
