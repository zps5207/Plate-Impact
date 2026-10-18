# T-038 handoff

Apply only `embmesh/cli.py`, `embmesh/plywise.py`, `embmesh/plywise_vuel.py`, and `tests/test_plywise_vuel.py` to the project. `run_overlay.py` runs these files against the existing project without editing it. The generated decks and private input are smoke-test artifacts.

The implementation converts the shared ply Part once through the unchanged solid converter, remaps each later ply's assembly element surface sets to ghosts, emits per-instance SVAR107 and diagnostic sets, embeds each fiber instance in its ply's ghost set, and propagates planar X/Y symmetry to fiber instance node sets. Each distinct angle's volume fractions are computed once in the ply frame.

| Deck | VU1 hosts | Ghosts | Fibers per ply | Ball contact nodes: plate / fibers | Symmetry fiber nodes per ply |
| --- | ---: | ---: | ---: | ---: | ---: |
| `Flatv2_8ply/output.inp` | 19,200 | 19,200 | 40 | 39,856 / 12,432 | X=0, Y=0 |
| `concave_8ply/output.inp` | 19,200 | 19,200 | 40 | 39,856 / 12,488 | X=0, Y=0 |
| `plate1hex_4ply/output.inp` | 9,600 | 9,600 | 40 | none | none |

The small real input is a private copy of `Meshing/plate1hex_curved_ball.inp`. Its existing Fiber material was retained. I added `*Plastic` (2e6 at 0 strain; 3e6 at 0.1 strain), `*Damage Initiation, criterion=DUCTILE` (0.25), and `*Damage Evolution, type=DISPLACEMENT` (0.001) to Matrix, and moved that Matrix block after the existing Cohesion interaction so the unchanged converter reads Matrix's own damage data. It inferred failure strain 0.25. The small run has 2,400 hosts per ply and per-ply fraction max 0.6752 (0°) versus 0.7501 (90°).

Ghost scale is `1e-4`; expected combined host/ghost mass ratio is `1.0001`. For Flatv2, per-host fraction min/max/mean is 0 / 1.38936 / 0.496158 for 0° and 0 / 1.46035 / 0.496141 for 90°. For concave it is 0 / 1.34989 / 0.498824 for 0° and 0 / 1.50065 / 0.498840 for 90°. Each 0° Flatv2 ply has 17 cells with fraction >=1 and each 90° ply has 21; concave counts are 17 and 19. The VUEL floors the remaining matrix fraction at `1e-6` in these cells. The requested 0.001 m fiber diameter is also 0.8 times the 0.00125 m ply thickness and triggers a layout warning. These are physical modeling concerns for the requested smoke-test parameters, not deck-generation errors.

No generated fiber node fell exactly on the X/Y planes, so the real-deck symmetry node counts are zero. A focused test exercises nonzero assembly X-plane symmetry on two fiber instances. The source sets are assembly-level; the implementation writes assembly `*Nset, instance=Fibers-Ply-k` and matching `*Boundary` blocks.

Checks: generated decks reparse (17 instances per virgin deck, 9 in the small deck); eight SVAR107 and eight ghost embedding blocks per virgin deck; two focused new tests pass; solid converter tests pass unchanged; 107 tests pass when excluding `tests/test_plywise_cohesive_material.py` and `tests/test_collapse.py`, whose collection code forces project-module imports and masks the outbox overlay. The unfiltered suite reported 119 passed, one skipped, two failed for that import collision. Abaqus/ROAR datacheck and 500 m/s dynamics were not run.
