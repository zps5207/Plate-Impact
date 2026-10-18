# T-024 smoke test measurements

All lengths use metres. All three CLI runs used `--diameter 0.001 --plate-node-contact --fiber-node-contact --ball-instance Ball-1 --preview` on 24,000 native C3D8R hosts. Each output deck has `EMBMESH_HOST`, `EMBMESH_FIBERS_T0/T90`, one embedded block, and plate-node plus fiber-node ball contact. The curved preview is [`curved_stacked/preview.html`](curved_stacked/preview.html).

| Measure | Curved `stacked` | Original Flatv2 `stacked` = `flat` | v500 baseline |
|---|---:|---:|---:|
| Hosts | 24,000 | 24,000 | 24,000 real plus 24,000 ghosts |
| Fiber runs | 490 | 450 | 328 |
| T3D2 segments | 24,115 | 18,711 | 13,864 |
| Total written fiber length | 19.07329948 | 17.67573881 | 13.08663334 |
| Fiber volume from written length x area | 1.49801344e-5 | 1.38824928e-5 | 1.02782178e-5 |
| Layers | 10 | 9 | Not independently established |
| Shortest written segment | 3.381776e-5 | 9.181176e-4 | 9.331931e-4 |
| CLI wall time | 293.25 s | 337.61 s | Not run |
| Peak process-tree RSS | 204.9 MiB | 202.2 MiB | Not run |

The flat `stacked` and `flat` output decks are byte-for-byte identical. The `flat` run took 338.83 s and peaked at 203.9 MiB. The curved written deck has 0 of 24,605 fiber vertices and 0 of 24,115 segment midpoints outside a host in world coordinates. The flat written deck also has zero outside. The curved deck's section area is 7.85398163397448e-7 m², matching v500's 1 mm diameter.

The host-only deck's Ball part matches v500 byte for byte (6,975 lines). Its contiguous Fiber/Matrix/Mild Steel material, BC, and initial velocity block also matches byte for byte (63 lines). Both step headers specify `*Dynamic, Explicit`, `7e-05` s, and bulk viscosity `0.06, 1.2`; the velocity remains `-500` m/s. The mesher appended contact to the existing interaction named `General`.

Curved slope is 11.46944 degrees and the maximum adjacent-layer normal overlap fraction is 1.99691%. Stack vector in world coordinates is `(0, 0, 0.01)` m. The maximum face translation mismatch is 4.34e-18 m against a 1.04e-4 m tolerance. The host-only deck has 24,000 elements, 27,401 nodes, and exactly the same world bounding box as its T-023 one-element source. Its Plate-1 `Outside`, `X`, and `Y` sets cover 891 rim nodes, 561 x=0 nodes, and 561 y=0 nodes respectively. The original Flatv2 deck's assembly sets are generated from a separately meshed flat host and their label counts need not coincide with this rebuilt mesh.

The curved fiber volume is 7.9067% higher than the original flat CLI volume from written lengths. The aggregate centerline volume fraction from `fiber_volume.csv` is 0.762981 curved versus 0.706967 flat. This difference combines curvature, the rebuilt reference footprint, and **one extra layer**; it cannot be interpreted as a curvature-only volume effect. The original Flatv2 thickness in world coordinates is 0.009999999820000003 m, so the unchanged `_layer_positions` fencepost rule produces nine 1 mm layers. The exactly rebuilt curved host is 0.01 m and produces ten. Satisfying both exact flat output equivalence and ten layers on that rounded Flatv2 input would require changing the existing flat layup behavior.

The per-host length-times-area volume estimate reports fractions above 1 in 1,550 curved hosts and 1,166 flat hosts; curved maximum is 1.876. That estimate assigns a full circular cross section to every clipped centerline length, including tiny boundary hosts and accepted overlaps. `--precise-volume` remains available but was not run on the full 24,000-host case. The section area and geometric centerline containment are checked independently of this per-host estimate.

The first curved CLI attempt without `--ball-instance` completed volume and visualization but stopped at contact with the documented CLI error. The successful runs supplied `--ball-instance Ball-1`, the source deck's actual ball instance. All three successful runs were sequential. Abaqus datacheck, ROAR impact, true swept-cylinder clearance, and solver stability were not tested.
