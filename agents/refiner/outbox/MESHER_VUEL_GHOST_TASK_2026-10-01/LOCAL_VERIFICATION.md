# Local verification

- Staged Python suite: `24 passed in 0.49s`.
- Flat.inp generation completed: 125 fibers and 24,000 host elements, matching
  the existing `Meshing/Flat-embmesh` layup.
- `verify_flat_vuel_ghost.py` result: PASS. See
  `Flat-vuel-ghost/static_verification.json`.
- Final deck round-trip parse:
  - Plate: 24,000 `VU1` + 24,000 `C3D8R`
  - EMBFIB: 125 `T3D2`
  - Ball unchanged: 2,992 `C3D8R` + 320 `C3D6`
- NumPy f2py read `uel/VUEL_failure.for` as `format:fix,strict` and emitted all
  six routines to `VUEL_failure.pyf`: `vuel`, `shape8h_tl`,
  `compute_defgrad`, `compute_green_lagrange`, `compute_strainrate_tl`, and
  `build_bl_matrix`.
- VUEL source SHA-256:
  `AD65DD27AE6EACEDBB64DF73FEA90D1F030911846AC067950B744C3CAC3838EF`.
- Flat VUEL+ghost deck SHA-256:
  `CE64E99C6A67FB1D0403904C52622856CAAF0B625E8E92C7F848FFE318DA9D4C`.
- Analytical host mass from the generated per-element volumes is
  `0.01924101825850784`; expected ghost mass is `1.924101825850784e-06`,
  giving total/real ratio `1.0001` exactly to reported precision.

Not locally verifiable: Abaqus input processing/solve completion, deletion-time
agreement, `.sta`/`.msg` NaN and energy checks, measured Abaqus model mass, and
post-death fiber velocities. These require the brief's Claude/ROAR refinement
loop.

