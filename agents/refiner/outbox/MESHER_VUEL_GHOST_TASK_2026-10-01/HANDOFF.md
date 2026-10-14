# Stage 6 VUEL + ghost-host mesher handoff

Apply these source changes to the project:

- `embmesh/vuelghost.py` (new)
- `embmesh/generate.py`
- `embmesh/cli.py`
- `uel/VUEL_failure.for`
- `tests/test_vuelghost.py` (new)

The Flat.inp-scale handoff deck and evidence are in `Flat-vuel-ghost/`:

- `output.inp` — 24,000 VU1 real hosts plus 24,000 node-identical C3D8R ghosts
- `fiber_volume.csv` — source values routed to SVAR107
- `report.json` — mesher metadata, inferred VUEL properties, and expected mass ratio
- `static_verification.json` — scale-aware structural checks
- `fibers.vtk` / `host_fibers.vtk` — unchanged layup geometry/visualization

Use `uel/VUEL_failure.for` as the user subroutine. Do not use or change the
production-only `uel/VUEL.for`.

The exact generation command was equivalent to:

```text
python -m embmesh.cli visualize Meshing/Flat.inp --instance Plate-1 \
  --diameter 0.001 --gap 0.001 --output Flat-vuel-ghost \
  --host-mode vuel-ghost
```

The original Flat-embmesh fiber VTK and the generated fiber VTK have the same
SHA-256 (`3e2ebf2e5a570355ef656bb1308c123b86fa541a3c6075b408b5a891f635d601`).

Default VUEL properties inferred from the source Matrix material are:

```text
E=5.08e6, nu=0.4, rho=980, beta=0, b1=0.06, b2=1.2,
EPS_FAIL=5.06, SIGY0=611000, HMOD=44500, IPLAST=1,
JAC_FAIL=0.05, DEGRADE_TIME=0, COMP_RESIDUAL_BULK_FRAC=0
```

The ghost clones Matrix's ductile initiation/evolution law and scales density,
elastic modulus, and every plastic stress by `1e-4`; strain coordinates and
Poisson's ratio remain unchanged. This preserves `sqrt(E/rho)` and all native
yield/hardening strains. Its section controls explicitly enable element
deletion.

ROAR/Abaqus remains the required final gate. In particular, measure VU1 failure
from SVAR49 and ghost deletion from STATUS, then tune `--vuel-eps-fail`,
`--vuel-jac-fail`, and (if a ramp is wanted) `--vuel-degrade-time` until their
times differ by at most one explicit increment. Also run the mass, energy/NaN,
and post-host-death fiber-velocity checks from the brief. No Abaqus executable
was available locally, so those claims are deliberately not marked verified.

