\# Embedded Element Mesher v0.1: Goal Specification



Read this whole file before acting. It is the contract for the `/goal` run.



\## 1. Objective



Build a Python package (`embmesh`) plus CLI that:



1\. Parses an Abaqus `.inp` file and reads every part (nodes, elements, sets, geometry) and every instance (part reference, translation/rotation).

2\. Lets me select any instance (optionally an element set within it) to be filled with embedded fibers.

3\. Generates fiber elements and writes an Abaqus deck that uses the native `\*EMBEDDED ELEMENT` constraint.

4\. Lets me toggle the fiber element type: Abaqus native truss (T3D2) or native beam (B31).

5\. Computes, for every host hex element, the fiber volume it contains and writes it in a file the companion user element (UEL/VUEL) can read.

6\. Supports flat cylindrical (disc) plates and curved plates.



Context: the embedded-element approach double counts volume where a fiber sits inside a host element. A companion user element corrects the host element mass/stiffness using the fiber volume. This mesher supplies that per-element fiber volume. The mesher does not implement the correction itself.



\## 2. Environment, permissions, rules



\- Write only inside `C:\\Users\\salas\\OneDrive - The Pennsylvania State University\\Plate Impact` (the working directory).

\- Read only `C:\\Users\\salas\\OneDrive - The Pennsylvania State University\\Embedded Elements` for context (UEL source, reference code, constitution/instruction files). Never write, rename, delete, or run any git command there (`git status` can rewrite the index). Record the sha256 of every file you read there at the start and confirm they are unchanged at the end.

\- Git: work locally only. The working directory is a git repo with a GitHub remote, but you must not run any git command that writes (`add`, `commit`, `push`, `checkout`, `branch`, `reset`, etc.). Read-only git commands such as `git status` and `git diff` are fine inside the working directory only. Never store credentials or keys. I will review, commit, and push when you finish.

\- At the end of every checkpoint, append to `docs/PROGRESS.md` the list of files created or changed since the last checkpoint and a suggested commit message, so I can commit manually at any point.

\- Do not try to run Abaqus locally. Jobs run on ROAR through SLURM in `/storage/home/zps5207/scratch`; I submit them. You produce decks and `sbatch` templates only, with clearly marked `TODO` placeholders for module/license lines you cannot verify.

\- Python 3.11+, `numpy`, `scipy`, `pytest`; keep dependencies minimal; `pyproject.toml`. Fortran only for the VUMAT.

\- Keep `docs/PROGRESS.md` current: current checkpoint, what was verified (with commands), what remains, blockers. If a session ends early, the next one must be able to resume from it.

\- Ambiguity rule: pick the simplest conservative reading, log it in `docs/DECISIONS.md`, and continue. Stop only for the conditions in section 8.

\- Model units are whatever the input deck uses. Never convert units; warn if inputs look inconsistent.



\## 3. Repo layout (create)



```

embmesh/  parser/  model.py  selection.py  geometry/  layup/  fibers.py  volume.py  writers/  cli.py

uel/      (copied user element + PROVENANCE.md)

vumat/    (tension-only elastic-brittle VUMAT, tests, sbatch template)

tests/    examples/  docs/  README.md  .gitignore

```



Update the existing `.gitignore` so it excludes `\*.odb \*.sim \*.lck \*.023 \*.msg \*.dat(abaqus) \_\_pycache\_\_ outputs/`. Note in `docs/DECISIONS.md` that this folder is OneDrive-synced and that `.git` inside OneDrive can corrupt; recommend excluding `.git` from sync.



\## 4. Functional requirements



\### 4.1 Parser

\- Case-insensitive keywords, comments, continuation lines, `\*Include`, `\*Part/\*End Part`, `\*Node`, `\*Element` (with `type`, `elset`), `\*Nset`/`\*Elset` (including `generate`, `internal`), `\*Surface`, `\*Assembly`, `\*Instance` (translation and rotation data lines), `\*Solid Section`, `\*Material`.

\- Unsupported keywords are preserved verbatim and passed through untouched in the output deck.

\- `embmesh list model.inp` prints per part/instance: node count, element types and counts, bounding box, total volume, sets, surfaces.

\- Instance transforms must be applied correctly (rotation about axis a to b by angle, then translation). Test them.



\### 4.2 Selection and hex-only rule

\- CLI and Python API: select instance(s) by name, optionally an element set.

\- Accepted host types: 8-node hex family (C3D8, C3D8R, C3D8I and reduced/hybrid variants) and 20-node hex (C3D20, C3D20R, geometry only). Anything else in the selected region raises `HexOnlyError` listing offending types and counts. No output is written in that case.

\- Check for degenerate/inverted hex (non-positive Jacobian) and report the labels.



\### 4.3 Fiber inputs (config file, YAML or JSON, plus CLI overrides)

\- `fiber\_diameter` d (required), `gap` g (default 0; applies in-plane and between layers; optional separate `gap\_inplane`, `gap\_layer`; g < 0 is an error).

\- With g = 0: fibers touch neighbours in-plane and the layer below (layer pitch = d + g).

\- Fiber material inputs: E, density, and failure stress/strain for the VUMAT pairing.

\- `fiber\_element\_length` (default: at most the smallest host characteristic length), reference in-plane direction vector for the 0 direction, first-layer offset from the surface (default d/2 + g/2), end inset (default 0).

\- `fiber\_type`: `truss` | `beam`.

&#x20; - truss: `T3D2`, `\*Solid Section` with area = pi d^2 / 4.

&#x20; - beam: `B31`, `\*Beam Section` circular with radius d/2 and a valid `n1` direction per element (perpendicular to the fiber axis; on curved plates derived from the director field).

\- Verify against your knowledge of Abaqus/Explicit that these types and section keywords are supported. Log any uncertainty in `docs/DECISIONS.md` and in the sample deck comments.



\### 4.4 Layup: interpretation

"90-90" is taken as alternating 0/90 orthogonal cross-ply layers. Even layers along direction t0, odd layers along t90. Log this in `DECISIONS.md`.



\### 4.5 Flat cylindrical (disc) plates

\- Detect the thickness axis (PCA/inertia of the selected nodes) unless given; layers stack along it.

\- Layers alternate 0/90 in the plane with reference direction from config. Fibers are chords clipped to the part outline (centerline stays inside the hosts).

\- Layer count from thickness / pitch; report leftover thickness.



\### 4.6 Curved plates

1\. User names the front and back surfaces (`\*Surface` names or element-face sets). Auto-detection is best-effort only, behind a flag.

2\. Triangulate both surfaces; compute smoothed inward-pointing unit normals.

3\. For any interior point x: closest-point projection onto each surface (KD-tree plus refinement) gives n\_f(x) and n\_b(x); director field D(x) = normalize(n\_f(x) + n\_b(x)) (the arithmetic average). Error if |n\_f + n\_b| is near zero.

4\. Layer reference surfaces: march from the front surface along D by ODE integration (RK4), one layer per pitch, keeping fibers orthogonal to D. Report where the number of layers varies across the plate.

5\. In each layer: t0 = normalize(r - (r.D)D), t90 = D x t0, with r the reference vector. Warn where r is nearly parallel to D and use a documented fallback.

6\. Fibers are streamlines of t0 (even layers) or t90 (odd layers), seeded at lateral pitch and integrated with RK4, pruned/re-seeded to hold spacing. On doubly curved surfaces spacing cannot be held exactly: report min/max/mean spacing and warn above 10%.

7\. Sample each fiber polyline at `fiber\_element\_length`.

8\. Write the math in `docs/THEORY.md`.



\### 4.7 Embedded constraint and output deck

\- Original deck content is preserved; add fiber nodes, fiber elements, fiber element sets, sections, materials, and `\*Embedded Element, host elset=<host set>` referencing the fiber set. Include the tolerance parameters as config options.

\- Verify the keyword syntax carefully; flag any doubt.

\- Element/node labels start after the current maxima with a configurable offset; detect collisions.

\- Every embedded node must be located in a host element (isoparametric inverse mapping with Newton, robust on curved/skewed hexes). Nodes outside all hosts are reported and trimmed.

\- The output deck must re-parse with your own parser (round trip).



\### 4.8 Fiber volume per host element

\- Clip every fiber segment against every host hex it passes through (use an acceleration structure). Volume\_e = sum(length inside e) x pi d^2 / 4.

\- Per host element output: label, host volume, fiber volume, fiber volume fraction, and fiber length along t0 and t90 (or global x/y/z; document which).

\- Write a plain-text file in the format the UEL reads. Inspect the UEL in the Embedded Elements folder first to determine how it ingests data (file read in `UEXTERNALDB`, element properties, or common block). Document the interface in `docs/INTERFACE.md`. If the UEL has no ingestion route, do not change its formulation; write a default CSV and document the required interface.

\- Also emit a `report.json` (totals, counts, min/max volume fraction, spacing stats, estimated stable time increment of the fiber elements from E, density, and length) and a legacy ASCII `.vtk` of fibers and host fraction for ParaView.



\### 4.9 Copy the user element

\- Locate the UEL/VUEL source in Embedded Elements, copy it to `uel/`, and write `uel/PROVENANCE.md` (source path, sha256, date, upstream repo commit if discernible, license of any third-party code).

\- Do not edit the copy's numerics. For verification decks, use a compressible neo-Hookean host material by default with a simple elastic-plastic option, as placeholders only.



\### 4.10 VUMAT (fiber material)

\- `vumat/`: a tension-only, elastic-brittle VUMAT for the truss and beam fibers. Stress increments are elastic; compressive stress is clamped to zero (no compression capacity); when tensile stress reaches the failure value the stress goes to zero and the element is deleted through the state-variable delete flag.

\- Props: E, failure stress (or strain), plus density via `\*Density`.

\- Verify Abaqus/Explicit VUMAT support for T3D2 and B31 in your knowledge and log uncertainty.

\- Provide a pure-Python reference of the update rule with pytest tests (tension to failure, compression, cyclic), single-element sample decks (tension, compression, failure), and an `sbatch` template with `TODO` placeholders.



\## 5. Tests and fixtures (no Abaqus required)

Write generators for: (a) flat disc hex mesh, (b) concentric spherical-cap/cylindrical-shell hex plate, (c) a deck with a wedge or tet element to trigger `HexOnlyError`, (d) multi-instance deck with rotations/translations.



\## 6. Additional requirements

\- Deterministic output; run configs saved beside outputs.

\- Vectorized/KD-tree/spatial-hash code; target at least 1e6 fiber elements without quadratic scaling.

\- Warn when fiber element length is much smaller than host size (time step penalty) or much larger (poor constraint resolution).

\- Warn on multiple instances sharing a host element set name.

\- Logging with a `--verbose` flag; clear error messages.

\- Optional: GitHub Actions workflow running `pytest`.



\## 7. Acceptance checks (all must pass; list each with the command and its output in `docs/PROGRESS.md`)

1\. `pytest` passes; tests cover parser, transforms, hex-only error, point location, clipping, layup, writers, VUMAT reference.

2\. `embmesh list` prints correct summaries for all fixtures.

3\. Flat disc, g = 0, truss: sum of per-element fiber volume equals total clipped fiber length x pi d^2 / 4 within 1e-6 relative; bulk fiber volume fraction of the interior is approximately pi/4 (about 0.785) within 2%.

4\. Curved concentric shell: layer surfaces stay within 1% of their expected radius; director field is radial within tolerance; spacing stats reported.

5\. Wedge/tet in the selected instance raises `HexOnlyError` and writes nothing.

6\. Same geometry produces valid T3D2 and B31 decks; section keywords and `n1` vectors correct.

7\. Output deck round-trips through the parser; every embedded node is inside a host with reported tolerance.

8\. Fiber volume file produced and consistent with the UEL ingestion path (or default CSV plus documented gap).

9\. `uel/` copy present with matching hash in `PROVENANCE.md`; sha256 of files read in Embedded Elements unchanged.

10\. VUMAT reference tests pass; sample decks and `sbatch` template present.

11\. README, INTERFACE.md, DECISIONS.md, THEORY.md, PROGRESS.md present; the final message lists every created or changed file, a suggested commit message, and asks me to review, commit, and push.



\## 8. Stop and report conditions

Pause and write the blocker in `docs/PROGRESS.md` if: the UEL is missing or its interface cannot be determined; Abaqus keyword syntax cannot be resolved with confidence and it blocks progress; the same test fails after three distinct fix attempts; a required write outside the working directory is needed; or the token budget is nearly used (log first).



\## 9. Checkpoints (in order)

1\. Recon: read Embedded Elements context, record hashes, inspect UEL, create repo skeleton and docs stubs.

2\. Parser and model with fixtures and tests.

3\. Selection, hex-only check, point location, clipping.

4\. Flat disc layup, fibers, embedded deck, volume output, tests.

5\. Truss/beam toggle.

6\. Curved plate director field and layup, tests.

7\. UEL copy, interface docs, VTK and report.

8\. VUMAT, reference tests, sample decks.

9\. Docs, CI, final acceptance run, final report asking me to commit and push.

