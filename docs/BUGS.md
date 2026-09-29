# Bugs and discrepancies

Commit under test: `9176486` (branch `mesher-v0.1`). All repro commands run with `C:\Users\salas\anaconda3\python.exe` (3.13.9) from the repo root unless noted; `dist/embmesh.exe` repro commands use the same arguments through the exe. Evidence paths are under `verification/evidence/` (relative to repo root).

## Summary (sorted by severity)

| ID | Severity | Component | Title |
|---|---|---|---|
| BUG-001 | blocker | parser | `*Element`/`*Node` continuation lines are parsed as a new element/node, corrupting connectivity |
| BUG-002 | blocker | writers (beam) | Single global beam-section `n1` is reused for every fiber; it is parallel to the axis of every other (alternating) layer |
| BUG-003 | blocker | model/parser | Instance transform applies rotation before translation instead of after, misplacing any instance that has both |
| BUG-004 | blocker | fibers | Thickness-axis selection (SVD) is unstable for near-cubic hosts: crashes (`OverflowError`/`ValueError`) or silently picks the wrong axis |
| BUG-006 | **blocker** | writers | Entire generated fiber block (`*Node`/`*Element`/section/material/`*Embedded Element`) is appended after `*End Assembly`; confirmed against real Abaqus 2024 (ROAR datacheck) that `output.inp` is rejected outright whenever the source deck already has a complete assembly |
| BUG-005 | major | symmetry | Any single-DOF `*Boundary` on a planar node set is treated as a symmetry plane, including non-zero prescribed velocity/displacement BCs |
| BUG-007 | major | fibers | Layer count is off by one at exact pitch/thickness boundaries (floating-point fencepost) |
| BUG-008 | major | parser | `*Include, input=...` never reads the included file; node/element data in included files is silently dropped |
| BUG-009 | major | fibers | Fiber cylinders can protrude outside the plate envelope for non-square-in-plane thin plates |
| BUG-010 | minor | writers | Fiber node/element ID offset is hard-coded at 100000: collides (`KeyError`, `ValueError`) with real decks that already use IDs ≥100000, or when re-meshing an already-fibered deck |
| BUG-011 | minor | fiber-volume CSV | CSV has no instance/part column, so labels collide across multiple instances of the same part |
| BUG-012 | minor | CLI/parser | Nonexistent input deck exits 0 with no error and silently produces an empty listing |
| BUG-013 | minor | CLI | `--diameter` accepts 0 (crash with raw `OverflowError` traceback) and negative values (accepted silently, rc=0, produces 0 fibers with no warning) |
| BUG-014 | cosmetic | CLI/exe | User-facing errors (`HexOnlyError`, bad `--instance`, bad `--diameter`) print raw Python tracebacks instead of a clean message; exit codes are always 1 regardless of cause |
| BUG-015 | cosmetic | fiber material | Generated fiber material is a fixed placeholder (`*Elastic 1., 0.3`, no density) with no CLI/API option to set it, and no warning that it must be hand-edited before running Abaqus |
| BUG-016 | major | vumat | `VUMAT_tension_only.for` compiles and links but Abaqus/Explicit refuses to run it on T3D2/B31 (`zero or negative initial dilatational modulus`); confirmed against real Abaqus 2024 |

---

### BUG-001 — element/node continuation lines misparsed
- Severity: blocker
- Component: `embmesh/parser.py` (`parse_deck`)
- Commit: `9176486`
- Repro:
  ```
  python -c "from embmesh.parser import parse_deck; d=parse_deck('verification/evidence/work/t11_c20.inp'); print(len(d.parts['P'].elements), [len(e.connectivity) for e in d.parts['P'].elements.values()])"
  ```
  Deck: `verification/evidence/work/t11_c20.inp` (one `C3D20R` element, connectivity wrapped onto a second line, standard Abaqus 16-value-per-line convention).
- Expected: 1 element with 20-node connectivity.
- Actual: 2 "elements" — label 1 with a truncated 15-entry connectivity is overwritten, and the continuation line `16,17,18,19,20` is read as a new element with label 16 and 4-node connectivity.
- Evidence: `verification/evidence/T1_parser_guard.log` (`T1.1h`), `verification/evidence/T1_parser_guard.json`.
- Suspected cause: `parse_deck` has no continuation-line handling; every non-keyword line is parsed independently as `label, data...` with no state carried from the previous line, and no detection of the trailing-comma continuation convention.
- Proposed fix (not applied): buffer element/node data lines under a keyword until a line has no trailing comma (or reaches an expected field count for `*Element`/`*Node`), then parse the concatenated fields.

### BUG-002 — beam section n1 reused across alternating layers
- Severity: blocker
- Component: `embmesh/writers.py` (`append_fibers_to_deck`, beam branch)
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli visualize <flat plate deck> --instance PLATE-1 --diameter 0.25 --fiber-type beam --output out
  ```
  e.g. `verification/evidence/work/t15_beam_out_*/output.inp`.
- Expected: a beam-section normal (`n1`) that is not parallel to any fiber's axis (Abaqus requires `n1` non-parallel to the beam axis for every element using that section, or a per-orientation section).
- Actual: `n1` is computed once from `fibers[0]`'s axis only (`embmesh/writers.py`: `axis=... fibers[0].points...`) and reused for the single shared `*Beam Section`. With the default 0/90 alternating layup, half the fibers (the ones in the same direction as `fibers[0]`) have `n1` exactly parallel to their own axis.
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.5 beam: n1 perpendicular to EVERY beam axis`) — 8 of 16 fibers found parallel.
- Suspected cause: single global section instead of per-direction (or per-element) beam sections/orientations.
- Proposed fix (not applied): emit one `*Beam Section` (or `*Beam General Section` + `*Orientation`) per fiber direction actually present (t0/t90, and any curved layup directions), each with its own valid `n1`.

### BUG-003 — instance transform order (rotation before translation)
- Severity: blocker
- Component: `embmesh/model.py` (`Instance.transform`)
- Commit: `9176486`
- Repro:
  ```
  python - <<'PY'
  from embmesh.parser import parse_deck
  d = parse_deck('verification/evidence/work/t11_a.inp')  # translation "10,0,0" then rotation "0,0,0,0,0,1,90"
  print(d.instance_nodes('I')[2])
  PY
  ```
- Expected (Abaqus convention: instance is translated, then rotated about the given axis, both expressed in the assembly/global frame — hand calc): node 2 = `(1,0,0)` → translate `(11,0,0)` → rotate 90° about Z through the origin → `(0,11,0)`.
- Actual: mesher returns `(10,1,0)` — it rotates the untranslated part-local point first, then adds the translation, i.e. rotate-then-translate.
- Evidence: `verification/evidence/T1_parser_guard.log` (`T1.1a`), deck at `verification/evidence/work/t11_a.inp`.
- Suspected cause: `Instance.transform` rotates `p` (the original, untranslated coordinates) and only adds `self.translation` afterward, instead of translating first and rotating about the (translated-frame) axis point.
- Proposed fix (not applied): apply translation to `p` first, then rotate about `rotation_origin` (which for a post-translation rotation is already expressed in the target/global frame per the deck).
- Note: this only produces a visible discrepancy when an instance has *both* nonzero translation and nonzero rotation (`examples/multi_instance.inp`'s instance `B` has both, on a rotation line that is also listed *before* the translation line, an ordering the parser tolerates but Abaqus itself would not accept — see report §2).

### BUG-004 — thickness-axis selection unstable for near-cubic hosts
- Severity: blocker
- Component: `embmesh/fibers.py` (`flat_disc_fibers`, SVD-based `thickness_axis` default)
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli visualize <0.5x2x2 plate> --instance PLATE-1 --diameter 0.1 --output out
  ```
  (`verification/evidence/work/t14_thickX.inp`, an ordinary axis-aligned hex block, thin in X.)
- Expected: fibers layered along the thin (X) axis, same behavior as the equivalent Y-thin and Z-thin cases (which do work — `verification/evidence/work/t14_thickY_out_*`).
- Actual: `ValueError: arange: cannot compute length` (crash) for the X-thin case; for a perfect cube (`t14_cube`, 1×1×1) the SVD tie-break is unpredictable and produced layering along the wrong/an inconsistent axis across runs (11/11/9 levels per axis, none of them the clean `floor(1/d)` expected on any single axis).
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.4 t14_thickX`, `T1.4 t14_cube`).
- Suspected cause: the default `thickness_axis` is the smallest-singular-vector direction from an SVD of the node cloud, which is numerically degenerate for near-cubic aspect ratios; no fallback or the auto-detected axis is fed into a downstream `np.arange` that receives a negative/`inf` step for some axis orderings.
- Proposed fix (not applied): require the user to pass an explicit `thickness_axis` for non-clearly-thin geometries (i.e. don't silently guess when the smallest two singular values are close), and validate the derived `pitch`/span before building the `arange`.

### BUG-005 — arbitrary single-DOF BCs misidentified as symmetry
- Severity: major
- Component: `embmesh/symmetry.py` (`boundary_symmetry_sets`)
- Commit: `9176486`
- Repro: deck with `*Boundary, type=VELOCITY` prescribing a non-zero velocity (`XSYM, 1, 1, 5.0`) on a planar node set, then `embmesh visualize`.
  Evidence deck: `verification/evidence/work/t17_*` (variant "prescribed velocity") — see `verification/evidence/T1_bc_curved_iface.log`.
- Expected: only genuine zero-value symmetry constraints (`*Boundary` with no amplitude/value, or explicit `XSYMM`/`YSYMM`/`ZSYMM`) are propagated to fiber nodes.
- Actual: the code only checks that the DOF is 1/2/3 and that `first==last`, ignoring both the `type=` option and any prescribed value on the data line; a non-zero prescribed velocity plane is treated exactly like a symmetry plane and its fiber nodes are merged into that same `*Nset` in the output deck.
- Evidence: `verification/evidence/T1_bc_curved_iface.log` (`T1.7 prescribed velocity ... fiber nodes must not silently inherit`).
- Suspected cause: `boundary_symmetry_sets` reads only `vals[0]` (set name) and `vals[1:3]` (DOF range) from each `*Boundary` data line, never inspecting the keyword's `type=` option or a possible magnitude in `vals[3]`.
- Proposed fix (not applied): require magnitude-free `*Boundary` records (no third value, or explicit `0`) and the default (`type=DISPLACEMENT`, not `VELOCITY`/`ACCELERATION`) before treating a set as a symmetry plane; also recognize the `XSYMM`/`YSYMM`/`ZSYMM` shorthand and instance-qualified set names (`PLATE-1.XSYM`), both currently silently ignored (see report §3, T1.7).

### BUG-006 — the ENTIRE fiber block is appended after `*End Assembly`; `output.inp` is not valid Abaqus input at all
- Severity: **blocker** (upgraded from "major" after direct confirmation against a real Abaqus 2024 datacheck on ROAR, job 55889996/55890011, 2026-09-28 — see below)
- Component: `embmesh/writers.py` (`append_fibers_to_deck`)
- Commit: `9176486`
- Repro (local, static): any deck with a recognized symmetry BC, e.g. `verification/evidence/work/t17_place_out_*/output.inp` — propagated `*Nset` appears after `*End Assembly`.
- Repro (Abaqus, dynamic — the stronger finding): mesh a flat plate deck that already has a complete `*Assembly ... *End Assembly` block (the normal case for any deck a user would actually submit), unmodified:
  ```
  python -m embmesh.cli visualize <deck-with-assembly-and-step> --instance PLATE-1 --diameter 0.25 --output out
  module load anaconda/2023.09 abaqus intel
  abaqus job=check input=out/output.inp datacheck interactive
  ```
  Evidence deck: `verification/roar/t2/flat_truss_asis.inp` (produced by `verification/make_t2.py`'s `_asis` variant, which is the mesher's own `output.inp` with nothing moved or edited).
- Expected: Abaqus datacheck accepts the deck (or reports a genuine modeling issue, not a keyword-placement error).
- Actual: Abaqus 2024 rejects it outright:
  ```
  ***ERROR: in keyword *NODE, file "flat_truss_asis.inp", line 157: The keyword
             is misplaced. It can be suboption for the following
             keyword(s)/level(s): assembly, instance, part
  THE PROGRAM HAS DISCOVERED     1 FATAL ERRORS
  ```
  i.e. the mesher's entire appended block — `*Node`, `*Element`, `*Solid Section`/`*Beam Section`, `*Material`, `*Embedded Element`, and any propagated symmetry `*Nset` — sits at the top/model level (after the original deck's `*End Assembly`, and after `*End Step` if the source deck already had a step), which Abaqus does not accept for `*Node` (or anything nested under it). **The mesher's native, unmodified `output.inp` cannot be read by Abaqus when the source deck already contains a complete assembly** (and, per the goal spec, also cannot when the source has a step — the common real-world case).
- Evidence: `verification/roar/t2_datacheck_flat_truss_asis.dat` excerpt (job 55889996, ROAR, captured 2026-09-28) — full `.dat`/`.stdout` saved under `verification/evidence/roar_t2_round1/`; SLURM job log in `docs/PROGRESS_VERIF.md`.
- Suspected cause: `append_fibers_to_deck` always appends its whole block to the end of the original deck's text, rather than inserting it before `*End Assembly` (and, further, `*Solid Section`/`*Beam Section` are never valid directly under `*Assembly` either — see the follow-on finding below).
- Follow-on finding (still confirmed against Abaqus, after moving the block before `*End Assembly`): a `*Solid Section`/`*Beam Section` for elements added directly inside `*Assembly ... *End Assembly` (not inside any `*Instance`) is *also* rejected —
  ```
  ***ERROR: in keyword *SOLIDSECTION, file "...", line 230: The keyword
             is misplaced. It can be suboption for the following
             keyword(s)/level(s): instance, part
  ```
  — so simply relocating the block earlier in the file is not sufficient; the fiber `*Node`/`*Element`/section trio must be nested inside its own orphan-mesh `*Instance` (an `*Instance` block with no `part=`) for the section assignment to be legal, with `*Embedded Element` referencing the resulting elset with an instance-qualified name (e.g. `EMBFIB-1.EMBMESH_FIBERS`). This full fix was verified to be syntactically necessary by iterating against real Abaqus datacheck error messages during this run.
- Proposed fix (not applied): in `append_fibers_to_deck`, wrap the generated `*Node`/`*Element` and their `*Solid Section`/`*Beam Section` in a new orphan-mesh `*Instance, name=<fiber-instance>` (no `part=`) block, insert that block — plus an instance-qualified `*Embedded Element` and any propagated symmetry `*Nset` merged into the existing set — immediately before the original deck's `*End Assembly` line; keep `*Material` definitions at model level (outside `*Assembly`, where they already validly sit).

### BUG-007 — layer count off-by-one at exact pitch boundaries
- Severity: major
- Component: `embmesh/fibers.py` (`flat_disc_fibers`)
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli visualize <1x1x1 plate> --instance PLATE-1 --diameter 0.1 --output out   # thickness/pitch = 10 exactly
  ```
  (`verification/evidence/work/t14_c.inp`, also reproduced with thickness 1.2, pitch 0.2 → 6 expected in `t14_f.inp`.)
- Expected: `floor(thickness/pitch)` layers when the ratio is an exact integer (10 for d=0.1 on a unit-thickness plate; 6 for d=0.2 on a 1.2-thick plate).
- Actual: 9 layers and 5 layers respectively — one fewer than the closed-form count.
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.4 t14_c`, `T1.4 t14_f`).
- Suspected cause: `n=max(1,int(np.floor((hi-lo)/pitch))+1)` combined with the per-layer skip test `if z>hi-diameter/2: continue` is fencepost-sensitive to floating-point noise in `hi-lo` and `k*pitch`; at an exact boundary the last valid layer's `z` can end up a few ULP above `hi-d/2` and gets dropped.
- Proposed fix (not applied): compute the layer count from a tolerant closed form (e.g. `round((hi-lo)/pitch - 1e-9)`) instead of a float `floor`+conditional-skip loop, or add an explicit epsilon to the skip test.

### BUG-008 — `*Include` never reads the included file
- Severity: major
- Component: `embmesh/parser.py` (`parse_deck`)
- Commit: `9176486`
- Repro:
  ```
  python -c "from embmesh.parser import parse_deck; d=parse_deck('verification/evidence/work/t11_inc.inp'); print(len(d.parts['P'].nodes))"
  ```
  (`t11_inc.inp` has `*Part... *Include, input=inc_nodes.inp ... *Element...`, and `inc_nodes.inp` defines 8 nodes.)
- Expected: 8 nodes read from the included file.
- Actual: 0 nodes (the include is never applied; the part ends up with elements referencing nonexistent nodes).
- Evidence: `verification/evidence/T1_parser_guard.log` (`T1.1j`).
- Suspected cause: the include-handling branch (`if section == "include": inc = base_dir / vals[0] ...`) only runs when a *data line* follows the `*Include` keyword, but `*Include` carries its target filename in the `input=` option on the keyword line itself and has no data line beneath it; the branch is therefore dead code for every real `*Include` usage.
- Proposed fix (not applied): read the file from `opts.get("input")` at the point the `*Include` keyword line itself is parsed, and splice its lines into `lines` immediately (as the code already does once triggered), rather than waiting for a data line.

### BUG-009 — fiber cylinders can protrude outside the plate for non-square thin plates
- Severity: major
- Component: `embmesh/fibers.py` (`flat_disc_fibers`)
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli visualize <1.1x1.1x0.7 plate> --instance PLATE-1 --diameter 0.4 --output out
  ```
  (`verification/evidence/work/t14_e.inp`.)
- Expected: every fiber cylinder's centerline stays at least `d/2` inside every plate face (as verified for the square-in-plane cases `t14_a`,`t14_b`,`t14_c`,`t14_d`,`t14_f`).
- Actual: max protrusion beyond a face = 0.1 (with `d/2=0.2`), i.e. a fiber row extends 0.1 units past the plate boundary.
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.4 t14_e fiber cylinders inside plate envelope`).
- Suspected cause: `flat_disc_fibers` derives `t0,t1` from an SVD-estimated thickness axis and a fixed in-plane `reference=(1,0,0)`; for a plate whose true edges aren't aligned with the `(1,0,0)`-derived `t0`/`t1` frame (nearly-square but not exactly, aspect ratio 1.1:1.1:0.7), the per-row span (`lo2,hi2`) computed by projecting the full point cloud onto `d` does not equal the actual footprint of that particular row along `perp`, so end fibers overshoot.
- Proposed fix (not applied): compute each fiber's span from the actual host-element cross-section at its row position, not from the global bounding-box projection along a single fixed direction.
- **Corroborated against real Abaqus 2024 (ROAR, jobs 55890832–55891147, 2026-09-28):** face-exact (`d`=gap=0.5 on a 0.5-pitch host), a non-rectangular (elements-removed) plate, a skewed/sheared mesh, and a refined mesh (`sens_refine_n3`) all produced the real, independently-confirming Abaqus error
  ```
  ***ERROR: NODE <n> INSTANCE EMBFIB-1 ON AN EMBEDDED ELEMENT DOES NOT LIE IN
             ANY HOST ELEMENT. CHECK COORDINATES, EXTERIOR TOLERANCE AND ABSOLUTE
             EXTERIOR TOLERANCE PARAMETERS, AND THE HOST ELEMENT SET DEFINITION.
  ```
  even with the `*Embedded Element` exterior tolerance widened to `absolute exterior tolerance=0.5` and `fractional exterior tolerance=0.3` (`verification/roar/t2/skew_tol0p5.inp`, `skew_tolfrac0p3.inp`) — ruling out "just needs a bigger tolerance" as the fix. This is strong, independent (real-solver) evidence that the mesher's own point-in-host test (used for `report.json`'s `embedded_endpoints_inside` count) does not always agree with Abaqus's own point-location algorithm, beyond the T1.4-detected pure Python envelope-overshoot case. Evidence: `verification/evidence/roar/face_reloc.dat`, `verification/roar/t2/t2_55891146.out` (via `docs/PROGRESS_VERIF.md`).

### BUG-010 — hard-coded fiber ID offset collides with real decks / repeat runs
- Severity: minor
- Component: `embmesh/writers.py` (`append_fibers_to_deck`, default `node_offset=100000`), `embmesh/generate.py`, `embmesh/cli.py` (no override option)
- Commit: `9176486`
- Repro A (existing high labels):
  ```
  python -m embmesh.cli visualize <deck with a node labeled 250000> --instance PLATE-1 --diameter 0.25 --output out
  ```
  → `KeyError: 8` (the fiber code silently assumes label 8 still refers to the corner it expects, once node 8 is renumbered to 250000 elsewhere in the same test the offset check doesn't catch the newly-out-of-range label at all in the model itself).
- Repro B (re-mesh an already-fibered deck):
  ```
  python -m embmesh.cli visualize out/output.inp --instance PLATE-1 --diameter 0.25 --output out2
  ```
  → `ValueError: fiber node offset 100000 collides with existing maximum 100031`.
- Expected: either a clear, documented error (for B, this already happens — good) or a `--node-offset`/`--element-offset` CLI option to resolve the collision without editing source.
- Actual: (A) an unrelated `KeyError` from deep inside `fibers.py`; (B) a clear `ValueError`, but no CLI flag to work around it.
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.4 label collision` entries).
- Suspected cause: `node_offset`/`element_offset` are constructor defaults in `writers.append_fibers_to_deck` with no CLI/API pass-through.
- Proposed fix (not applied): expose `--node-offset`/`--element-offset` on the CLI; validate all part-instance node/element labels against the chosen offset before generating fibers and raise the existing `ValueError` early, in `select_elements` rather than after a `KeyError`.

### BUG-011 — fiber-volume CSV has no instance/part identifier
- Severity: minor
- Component: `embmesh/writers.py` (`write_volume_csv`), `embmesh/volume.py`
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli visualize examples/multi_instance.inp --instance B --diameter 0.25 --output out
  head -1 out/fiber_volume.csv
  ```
- Expected: a column identifying which instance (and/or part) each `element_label` belongs to, since `examples/multi_instance.inp` itself demonstrates two instances (`A`,`B`) of the same part `P`, whose elements share label `1`.
- Actual: header is `element_label,host_volume,fiber_volume,volume_fraction,length_t0,length_t90` — no instance/part column.
- Evidence: `verification/evidence/T1_bc_curved_iface.log` (`T1.8 label mapping`).
- Suspected cause: `fiber_volume_rows`/`write_volume_csv` key rows only by the part-local element label.
- Proposed fix (not applied): add an `instance` column (matching the `--instance` argument) to the CSV header and rows.

### BUG-012 — nonexistent deck silently "succeeds"
- Severity: minor
- Component: `embmesh/parser.py` (`parse_deck`), `embmesh/cli.py`
- Commit: `9176486`
- Repro:
  ```
  python -m embmesh.cli list does_not_exist.inp; echo $?
  ```
- Expected: nonzero exit code and an error message naming the missing file.
- Actual: exit code 0, no output at all (an empty `Deck` is silently returned and `list` prints nothing because it has no parts).
- Evidence: `verification/evidence/T1_parser_guard.log` (`T1.1k`).
- Suspected cause: `parse_deck` treats any string argument that doesn't `Path.exists()` as literal deck *text* rather than a bad path (`text = p.read_text() if p.exists() else path_or_text`), so a missing filename is parsed as zero-keyword "deck text" instead of raising `FileNotFoundError`.
- Proposed fix (not applied): raise `FileNotFoundError` when a `str`/`Path` argument looks like a path (contains no newline) but does not exist, rather than falling back to treating it as inline deck text.

### BUG-013 — `--diameter` accepts 0 and negative values
- Severity: minor
- Component: `embmesh/cli.py`, `embmesh/fibers.py`
- Commit: `9176486`
- Repro:
  ```
  dist\embmesh.exe visualize examples\flat_disc.inp --instance DISC-1 --diameter 0 --output out    # crashes
  dist\embmesh.exe visualize examples\flat_disc.inp --instance DISC-1 --diameter -1 --output out   # "succeeds", 0 fibers, rc=0
  ```
- Expected: an explicit, early validation error ("diameter must be positive").
- Actual: `--diameter 0` raises `OverflowError: cannot convert float infinity to integer` from deep inside `flat_disc_fibers` (division by zero in `pitch`); `--diameter -1` runs to completion with `fibers: 0`, exit code 0, and writes all output files as if nothing were wrong.
- Evidence: `verification/evidence/T0_exe_cli.txt` (`## zero diameter`, `## neg diameter`).
- Suspected cause: no input validation in `cli.py`/`mesh_flat` before diameter/gap are used arithmetically.
- Proposed fix (not applied): validate `diameter > 0` and `gap >= 0` in the CLI (mirroring `embmesh/config.py`'s existing checks for the YAML/JSON config path, which already reject negative gap) before calling `mesh_flat`.

### BUG-014 — raw tracebacks and undifferentiated exit codes on user error
- Severity: cosmetic
- Component: `embmesh/cli.py`, `embmesh_entry.py`
- Commit: `9176486`
- Repro: any of the error cases above via `dist\embmesh.exe` (see `verification/evidence/T0_exe_cli.txt`, `T1_parser_guard.log` exe entries).
- Expected: a one-line, user-readable error message and a distinguishing exit code (per the goal's "sensible exit codes and error messages" T0 criterion).
- Actual: full Python/PyInstaller tracebacks to stderr and a flat exit code of 1 for every error type (hex-only guard, bad instance name, degenerate input, etc. are all indistinguishable by exit code).
- Evidence: `verification/evidence/T0_exe_cli.txt`, `verification/evidence/T1_parser_guard.log`.
- Suspected cause: `main()`/`embmesh_entry.py` have no top-level exception handling.
- Proposed fix (not applied): catch `HexOnlyError`, `KeyError` (bad instance/elset), and `ValueError` in `main()`, print a one-line message, and return distinct nonzero codes.

### BUG-016 — VUMAT_tension_only.for cannot be run in Abaqus/Explicit on T3D2/B31 without further work
- Severity: major
- Component: `vumat/VUMAT_tension_only.for`
- Commit: `9176486`
- Repro:
  ```
  module load anaconda/2023.09 abaqus intel
  abaqus job=vumat_tension_truss input=vumat_tension_truss.inp user=VUMAT_tension_only.for interactive
  ```
  (`verification/roar/t3/vumat_tension_truss.inp`, a single T3D2 fiber element with `*User Material, constants=2` referencing this VUMAT.)
- Expected: the analysis proceeds (goal T3: "VUMAT: tension to failure, compression clamp, element deletion; T3D2 and B31").
- Actual: the VUMAT compiles and links cleanly against Abaqus 2024 (Intel Fortran 2021.4.0, no errors), but the analysis input file processor rejects the job before the first increment:
  ```
  ***ERROR: Bad Material definition in element number 100010 instance EMBFIB-1:
            zero or negative initial dilatational modulus caused by bad material
            data. Please check your material input and any initial conditions if
            necessary.
  ```
- Evidence: `verification/evidence/roar/vumat_tension_truss.stdout` (job run on ROAR, 2026-09-28).
- Suspected cause: Abaqus/Explicit's packager probes a user material for an initial stiffness estimate (needed for the automatic stable-time-increment calculation) before the first real increment. A VUMAT supplies no material Jacobian, and this material is legitimately zero-stiffness for part of its response range (tension-only, clamped at zero in compression) — the probe likely lands in a zero-stiffness branch and Abaqus refuses to proceed rather than silently using a zero/negative modulus for the stability estimate.
- Attempted workaround (unsuccessful, reverted): supplying a fixed initial time increment via a keyword named `*Fixed Time Incrementation` — this is not valid Abaqus 2024 syntax (`***ERROR: Unknown keyword "fixedtimeincrementation"`); the correct keyword/option for direct user control of the time increment with a user material was not identified within this session.
- Proposed fix (not applied, needs Abaqus-specific investigation): likely candidates are (a) driving the step with `*Dynamic, Explicit` plus the correct direct-user-control syntax for a fixed increment (distinct from `*Fixed Mass Scaling`, which controls mass not time), (b) adding a nominal small positive stiffness contribution for compression in the VUMAT itself so the probe never sees exactly zero, or (c) providing an explicit `*Initial Conditions` that puts the material in its stiff (tension) branch at time zero. None of these were tried to a working conclusion this session.

### BUG-015 — fiber material is a hard-coded placeholder
- Severity: cosmetic
- Component: `embmesh/writers.py` (`append_fibers_to_deck`)
- Commit: `9176486`
- Repro: inspect any `output.inp`, e.g. `verification/evidence/work/t15_truss_out_*/output.inp`.
- Expected: either a CLI/API option to supply real fiber material properties (E, density, etc.), or a clearly flagged `**TODO`/warning that the emitted `*Material, name=EMBMESH_FIBER` block (`*Elastic 1., 0.3`, no `*Density`) is a placeholder that must be edited before running Abaqus.
- Actual: the placeholder material is emitted silently with no warning printed to the user and no option to override it.
- Evidence: `verification/evidence/T1_volume_layup.log` (`T1.5 truss/beam: fiber material is a placeholder`).
- Suspected cause: hard-coded literal in `append_fibers_to_deck`.
- Proposed fix (not applied): add `--fiber-modulus`/`--fiber-density`/`--fiber-poisson` CLI options (or accept a material block passthrough), and/or print a warning naming the placeholder values on every run.
