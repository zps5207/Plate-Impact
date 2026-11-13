# T-025 curved stacked fiber resampling

The curved reference-face crossings now define a geometric path. Each run is resampled into `max(1, round(L / target_length))` truss segments, where `L` is the path's 3D arc length and `target_length` is the cube root of median host volume, matching `flat_disc_fibers`. The path endpoints remain fixed. No short-segment merge remains. A small station correction makes the straight T3D2 chords equal to within `1e-9` relative while keeping every node on the path. Exact equal arc intervals and exact equal chords conflict at path bends; the largest arc-interval departure is `2.6148e-6` relative.

| Measure | Curved stacked | Flatv2 stacked = flat | v500 baseline |
|---|---:|---:|---:|
| Fiber runs | 490 | 450 | 328 |
| T3D2 segments | 20,120 | 18,711 | 13,864 |
| Total written centerline length, m | 19.07327637 | 17.67573881 | 13.08663334 |
| Length × circular area, m³ | 1.49801162e-5 | 1.38824928e-5 | 1.02782178e-5 |
| Shortest written segment, µm | **934.039** | **918.118** | **933.193** |
| Longest written segment, µm | 969.395 | 1,006.076 | — |
| Layer count | 10 | 9 | — |

The shortest curved segment is 1.73% longer than the flat run's and 0.091% longer than v500's. There are zero curved runs with `L < target_length / 2`. The curved target is 947.924 µm. Curved written segment length / target has min/median/max **0.985353 / 0.999893 / 1.022651**. Maximum within-fiber straight-segment spread is `8.11e-11` relative before writing and `2.23e-10` after deck coordinate rounding. `theta_max` is 11.46944°, with 1.99691% maximum neighboring-layer overlap fraction.

The independent written-deck audit found **0 outside** among 20,610 nodes, 20,120 segment midpoints, and 100,600 samples at five interior positions per segment in world coordinates. Maximum measured outside distance is **0 µm = 0 d** at the `point_in_hex` tolerance of `1e-8` in element coordinates. The `EMBFIB-1` instance has no transform. Every node is accepted by a host search. This is a sampled centerline test, not a full swept-cylinder containment proof.

The Flatv2 `stacked` and `flat` written `output.inp` files are byte-identical (SHA-256 `25DDF011AF77A6691539C22D68502708CFD0E348A3246CC226226BF44134977B`). The unchanged Flatv2 input thickness rounds just below 10 mm and produces nine layers; the rebuilt curved host produces ten. The 7.9065% difference in written length-times-area volume combines layer count, footprint, and curvature, so it is not a curvature-only effect.

| CLI run | Wall time, s | Peak process-tree RSS, bytes |
|---|---:|---:|
| Curved stacked | 261.812 | 218,243,072 |
| Flatv2 stacked | 345.797 | 208,367,616 |
| Flatv2 flat | 340.172 | 211,968,000 |

All heavy CLI runs were sequential. Each used diameter 0.001 m, `--plate-node-contact --fiber-node-contact --ball-instance Ball-1 --preview`. The [curved preview](curved_stacked/preview.html), written deck, report, VTK, CSV, logs, and RSS records are in this folder. The full current suite against the T-025 overlay passed: **144 passed, 3 skipped** (`full_tests.log`). No Abaqus or ROAR run was made.

## Reproduce

From `agents/refiner`:

```powershell
python -B outbox/T-025/run_cli.py outbox/T-024/curved_hostonly.inp stacked outbox/T-025/curved_stacked
python -B outbox/T-025/run_cli.py "../../Meshing/Flatv2.inp" stacked outbox/T-025/flat_stacked
python -B outbox/T-025/run_cli.py "../../Meshing/Flatv2.inp" flat outbox/T-025/flat_plain
python -B outbox/T-025/check_written.py outbox/T-025/curved_stacked/output.inp outbox/T-025/curved_written_check.json
python -B outbox/T-025/compare_runs.py outbox/T-025/curved_stacked outbox/T-025/flat_stacked outbox/T-025/flat_plain "../../Flat-nodecontact/v500/output.inp" outbox/T-025/comparison.json
```

From the project root, with `PYTHONPATH` set to `agents/refiner/outbox/T-025`, run `python -P -B -m pytest tests agents/refiner/outbox/T-025/tests/test_stacked.py -q --import-mode=importlib -p no:cacheprovider --basetemp agents/refiner/outbox/T-025/pytest_final_log`.
