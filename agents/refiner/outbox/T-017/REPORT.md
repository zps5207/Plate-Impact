# T-017: v500 fiber-to-ball contact

## Reproduction

Run from the project root. `source_v500.inp` in this folder is `Meshing/Flatv2.inp` with its sole ball initial velocity changed from `-1000.` to `-500.` m/s. The NC summary reports initial ball speeds of 100, 200, 300, 400, and 500 m/s; the v500 deck explicitly has `Ball-1.Ball, 3, -500.`. Applying the same source velocity edit for the other four speeds is an inference, since their generated decks and historical CLI transcripts were not saved locally. The commands below are reconstructed from T-011's generation settings and verified against the exported v500 deck.

To recreate the supplied source copy: read `Meshing/Flatv2.inp` as bytes, replace its one occurrence of `Ball-1.Ball, 3, -1000.` with `Ball-1.Ball, 3, -500.`, and save it as `source_v500.inp`. The source itself is included so the commands below can be run directly.

Baseline command:

```bash
python -m embmesh.cli visualize agents/refiner/outbox/T-017/source_v500.inp --instance Plate-1 --diameter 0.001 --gap 0.0002 --host-mode vuel-ghost --vuel-eps-fail 0.113800332690901 --ghost-ductile-failure-strain 1e-6 --plate-node-contact --ball-instance Ball-1 --output agents/refiner/outbox/T-017/baseline_gen
```

Fiber-contact command (one added flag):

```bash
python -m embmesh.cli visualize agents/refiner/outbox/T-017/source_v500.inp --instance Plate-1 --diameter 0.001 --gap 0.0002 --host-mode vuel-ghost --vuel-eps-fail 0.113800332690901 --ghost-ductile-failure-strain 1e-6 --plate-node-contact --fiber-node-contact --ball-instance Ball-1 --output agents/refiner/outbox/T-017/fiber_gen
```

The CLI produces `output.inp` in each output folder. On Windows it writes CRLF; the checked-in v500 reference has LF. `finalize_decks.py` normalizes line endings, proves the baseline byte identical to `verification/roar/t_nc/v500/v500_deck.inp`, and coalesces the duplicate thickness keyword described below:

```bash
python agents/refiner/outbox/T-017/finalize_decks.py agents/refiner/outbox/T-017/baseline_gen/output.inp agents/refiner/outbox/T-017/fiber_gen/output.inp verification/roar/t_nc/v500/v500_deck.inp agents/refiner/outbox/T-017
```

The baseline/reference unified diff is empty. `fiber_contact.diff` is the full unified diff: it adds only the 14,192-node fiber set and its node surface, the fiber/ball contact inclusion, and the fiber thickness data line. The existing plate and native Surf-1/Surf-2 contact remain intact. No Vf values or VUEL settings change.

The freshly regenerated baseline, after CRLF-to-LF normalization, matched the reference byte for byte (14,331,211 bytes; SHA-256 `01af49f6188a6be2a43013288e6f7984b3e747f707fd4cba91c9722923d6f1dd`). The finalized fiber deck is 14,444,068 bytes (SHA-256 `bc6530d029e098e6324a830694f432d10ff8de38117b14e7a5acc523ba917123`). A structural comparison found zero removed lines and exactly 892 added lines: 887 fiber-node label lines, one set header, one surface header, one surface data line, one inclusion pair, and one thickness data line. It found one `*Contact` and one thickness keyword in the final deck.

## Thickness and mechanics

`auto` computes plate thickness as half the median of all twelve edges of each selected host hex: `0.000488992080759272` m. Fiber thickness is half the smaller of that host median edge and the median generated fiber segment length. The segment median is `0.0009428123964848826` m, so fiber thickness is `0.000471406198242441` m. For a 1 mm diameter fiber this is close to its 0.5 mm radius and is a reasonable *initial contact envelope*, but no Abaqus run has established that it produces the intended force or effective radius. The contact thickness is a numerical surface property; it does not alter the fiber's section or Vf.

The [Abaqus surface-property guide](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEITNRefMap/simaitn-c-surfacepropassign.htm) expressly permits nonzero thickness on a node surface in Explicit general contact and says each `PROPERTY` should have at most one assignment keyword per step, with repeated data lines. The current `embmesh/contact.py` emits a second `*Surface Property Assignment, property=THICKNESS` when the fiber flag extends the existing plate-contact block. The supplied ready deck places the fiber data line under the existing keyword. A source fix is needed before using the unprocessed CLI fiber output directly. Suggested change in `_augment_step_contact` (replace the final insertion of `thickness_lines` when `prop is not None`):

```diff
-        insert_at = _block_data_end(lines, prop, end_step)
-        lines[insert_at:insert_at] = thickness_lines
+        thickness = next((i for i in range(contact + 1, end_step)
+                          if lines[i].lstrip().startswith('*') and
+                          not lines[i].lstrip().startswith('**') and
+                          _keyword(lines[i]) == ('surface property assignment', {'property': 'THICKNESS'})), None)
+        if thickness is not None:
+            insert_at = _block_data_end(lines, thickness, end_step)
+            lines[insert_at:insert_at] = [line for surface, value in thicknesses
+                                           if value is not None and value > 0
+                                           for line in [f'{surface}, {value:.15g}']]
+        else:
+            insert_at = _block_data_end(lines, prop, end_step)
+            lines[insert_at:insert_at] = thickness_lines
```

The proposed source diff is unapplied and should be accompanied by a test that checks a single thickness keyword when the plate and fiber flags are enabled together.

The [Abaqus constraint guide](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEITNRefMap/simaitn-c-expcontactconstraints.htm) says general contact uses penalty enforcement; it also warns that contact on a DOF governed by an embedded-element constraint can take precedence over that constraint. This is a real modeling risk for the fiber nodes. The fiber nodes are close to host nodes in the impact zone, so both surfaces can act on the ball and could change contact force or cause redundant loading; that outcome is an inference, not a measured fact. The same guide gives a nominal 1% stable-increment reduction for node-surface penalty contact in its default case, but the effect for this model is unknown. T-011 tests establish CLI wiring, sets and keyword placement; they do not establish Abaqus acceptance or physical response. Datacheck, then compare penetration, ball velocity, force/energy histories, embedded-constraint warnings, and stable increments against v500.

## ROAR launch recipe

`run_v500_fiber_contact.sbatch` mirrors `verification/roar/run_variant.sbatch` and uses one node, one CPU, 16 GB, and the `run_v500_fiber_contact_%j.out` naming pattern. The Hub can stage `v500_fiber_contact.inp` as `output.inp`, the current `uel/VUEL_failure.for`, and the script in a new directory such as `/storage/home/zps5207/scratch/ctv/nc/v500_fiber_contact/`. Do not overwrite `ctv/nc/v500/`. From that new directory, the Hub can submit `MODE=datacheck sbatch run_v500_fiber_contact.sbatch`, inspect `v500_fiber_contact_check.dat` and stdout, then submit `sbatch run_v500_fiber_contact.sbatch` after approval. No ROAR action was taken here.

## Local checks

- `python -m pytest tests/test_contact.py tests/test_contact_cli.py -q -p no:cacheprovider --basetemp agents/refiner/outbox/T-017/pytest_tmp`: 10 passed.
- `python -m pytest tests -q -p no:cacheprovider --basetemp agents/refiner/outbox/T-017/pytest_all`: 56 passed.
- Baseline regenerated and compared byte for byte after line-ending normalization; contact diff inspected for other changes.
- No Abaqus datacheck or solver execution was available locally. The Abaqus documentation linked above is version 2025; ROAR is documented as Abaqus 2024, so its exact parser behavior remains to be checked by datacheck.
