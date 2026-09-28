# Embedded Element Mesher v0.1 Progress

## Current checkpoint

Checkpoint 1 (recon) is paused by the section 8 **no Git remote** stop condition.

## Verified

- Read the complete goal specification from `GOAL_SPEC.md` (the checkout does not yet contain `docs/GOAL_SPEC.md`; the supplied specification is at repository root).
- `git remote -v` produced no output: no remote is configured, so a required push cannot be performed.
- Creating the required branch/commit also failed because Git could not create `.git/HEAD.lock` or `.git/index.lock` (`Permission denied`) in the managed read-only `.git` directory; the checkout remains on `master` with no commits.
- External context was read read-only from `C:\Users\salas\OneDrive - The Pennsylvania State University\Embedded Elements`.
- UEL source inspected: `VUEL.for` is a native Abaqus/Explicit VUEL entry point for an 8-node hex user element. It receives material properties through `props`; it has no file-reading or `UEXTERNALDB` ingestion path for fiber-volume data. A future mesher should therefore emit a documented default CSV interface without modifying the UEL numerics.
- External files read and starting SHA-256 hashes:
  - `AGENTS.md`: `7D1F28486A7C80A07359CEF09C9E3A4383E436D829C09AD1D2A6B05F6DE7DDC5`
  - `VUEL.for`: `C32F3FB241C38C93EB32751967FBAAC520B953CB17A628923A3468B88A8C1E93`
  - `PROJECT.md`: `6632030A7E12AF69BB9171F60CAE438F9D3C8EAC5D2B943F789CD00421EB792D`
  - `HANDOFF.md`: `4D2188D5590E7DCC20E98FBC0162F6CFAEC6088BF5E68A1A5573A83FBC64C581`

## Commands and output

```text
git remote -v
(no output)
```

```text
git switch -c mesher-v0.1
error: cannot lock ref 'HEAD': Unable to create '.../.git/HEAD.lock': Permission denied
git commit ...
fatal: Unable to create '.../.git/index.lock': Permission denied
```

```text
Get-FileHash -Algorithm SHA256 <external file>
AGENTS.md   7D1F28486A7C80A07359CEF09C9E3A4383E436D829C09AD1D2A6B05F6DE7DDC5
VUEL.for   C32F3FB241C38C93EB32751967FBAAC520B953CB17A628923A3468B88A8C1E93
PROJECT.md 6632030A7E12AF69BB9171F60CAE438F9D3C8EAC5D2B943F789CD00421EB792D
HANDOFF.md 4D2188D5590E7DCC20E98FBC0162F6CFAEC6088BF5E68A1A5573A83FBC64C581
```

## Blocker / resume action

Per section 8, work is paused until the user configures a Git remote and grants this checkout writable Git metadata (or provides a writable clone). Once available, rerun `git remote -v`, create/use branch `mesher-v0.1`, commit this recon checkpoint, and push before proceeding to checkpoint 2.

### Recheck (2026-09-28 continuation)

The blocker persists: `git remote -v` still produces no output, `git branch --show-current` remains `master`, and `git status` reports no commits. The required `docs/GOAL_SPEC.md` path is also absent; the supplied specification remains at repository-root `GOAL_SPEC.md`.

### Third blocker audit (2026-09-28)

Live recheck again returned no remote, branch `master`, and `No commits yet`; the working tree contains only untracked specification/docs files. Earlier `git switch -c mesher-v0.1` and `git commit` attempts failed with permission denied creating `.git/HEAD.lock` and `.git/index.lock`. The same no-remote/unwritable-Git condition has now recurred for three consecutive goal turns.

## Remaining

All implementation checkpoints and acceptance checks remain.

## Local continuation (Git writes intentionally disabled)

The revised run permits local-only work and explicitly forbids Git write commands. Checkpoint 1 recon artifacts now include `pyproject.toml`, `.gitignore`, package/docs stubs, and a canonical `docs/GOAL_SPEC.md` copy. Checkpoint 2 implementation is in progress: parser/model, transforms, selection, hex-only validation, inverse mapping, clipping, layup, VUMAT reference, CLI, and initial tests are present.

### Checkpoint 2 verification

Command:

```text
& 'C:\Users\salas\anaconda3\python.exe' -m pytest -q
.....                                                                    [100%]
5 passed in 2.70s
```

The first run exposed a floating-point exact-equality assertion in the test (`0.9999999999999999` versus `1`); it was corrected to `numpy.isclose`. Remaining parser edge cases, fixture generators, curved layup, volume acceleration, deck round-trip, and acceptance checks remain.

## Checkpoints completed locally (no Git writes)

### Checkpoint 2 — parser/model, selection, geometry

Implemented `embmesh.model`, `parser`, `selection`, `geometry`, fixtures, and tests. The parser handles case-insensitive part/assembly nodes/elements, node and element sets (including `generate`), surfaces, instance translation and axis-angle rotation, and preserves original deck lines for output. Hex-only selection rejects unsupported types with `HexOnlyError`; Newton inverse mapping and segment clipping are covered by tests.

### Checkpoints 3–5 — layup, fibers, volume, deck writers

Implemented flat plate layer generation with `pitch=d+gap` and alternating t0/t90 layers, per-host clipped volume rows, CSV/report/legacy VTK writers, native `T3D2`/`B31` toggles, circular truss/beam sections, beam n1 construction, embedded constraint output, and round-trip parsing. The flat unit-host fixture with `d=.25, gap=0` reports volume fraction `0.7853981633974483` (π/4).

### Checkpoint 6 — curved utilities

Implemented radial director, concentric-shell layer radii, spacing statistics, and a deterministic shell fiber fixture with tests. Full surface triangulation/RK4 refinement remains a documented extension.

### Checkpoint 7 — UEL/interface/reporting

Copied `VUEL.for` to `uel/` without numerical edits; `uel/PROVENANCE.md` records the source hash. `docs/INTERFACE.md` documents the absence of a UEL file-ingestion route and the default CSV interface. `report.json` and legacy ASCII VTK are emitted by `mesh_flat`.

### Checkpoint 8 — VUMAT

Added the pure-Python tension-only elastic-brittle update rule, tests for tension/compression/failure, sample input decks, and an SLURM template with TODO site placeholders. The Fortran file is intentionally marked TODO for the Abaqus-version-specific full VUMAT signature and has not been run locally.

## Acceptance command outputs (current)

```text
& 'C:\Users\salas\anaconda3\python.exe' -m pytest -q
..........                                                               [100%]
10 passed in 2.77s
```

```text
& 'C:\Users\salas\anaconda3\python.exe' -m embmesh.cli list examples/flat_disc.inp
part DISC: nodes=8 elements=1 types={'C3D8': 1} bbox=[0.0, 0.0, 0.0]..[1.0, 1.0, 1.0] sets=['HOST'] surfaces=[]
instance DISC-1: part=DISC translation=[0.0, 0.0, 0.0] rotation_angle=0
```

```text
mesh_flat('examples/flat_disc.inp','DISC-1',.25,'outputs/flat')
fiber count: 16
host row: (1, 0.9999999999999999, 0.7853981633974483, 0.7853981633974484, 8.0, 8.0)
round-trip parts: 1
```

```text
UEL hash check
uel_copy=C32F3FB241C38C93EB32751967FBAAC520B953CB17A628923A3468B88A8C1E93
external=C32F3FB241C38C93EB32751967FBAAC520B953CB17A628923A3468B88A8C1E93
MATCH
```

Known verification boundary: Abaqus itself is not run locally by specification; native keyword/VUMAT execution remains for the user's ROAR environment. Python-side curved triangulation/director/RK4 utilities, include handling, bbox-pruned clipping, and collision checks are implemented.

### Latest verification

```text
& 'C:\Users\salas\anaconda3\python.exe' -m pytest -q
..........                                                               [100%]
10 passed in 3.06s
```

```text
embmesh list examples/multi_instance.inp
part P: nodes=8 elements=1 types={'C3D8': 1} bbox=[0.0, 0.0, 0.0]..[1.0, 1.0, 1.0] sets=[] surfaces=[]
instance A: part=P translation=[0.0, 0.0, 0.0] rotation_angle=0
instance B: part=P translation=[1.0, 0.0, 0.0] rotation_angle=90

embmesh list examples/wedge.inp
part BAD: nodes=4 elements=1 types={'C3D4': 1} bbox=[0.0, 0.0, 0.0]..[1.0, 1.0, 1.0] sets=['HOST'] surfaces=[]
instance BAD-1: part=BAD translation=[0.0, 0.0, 0.0] rotation_angle=0

curved shell: radii [2.1, 2.3, 2.5, 2.7, 2.9], spacing {'min': 1.0, 'max': 1.0, 'mean': 1.0}
```

```text
Final acceptance smoke command
flat relative volume error 0.0
flat fraction 0.7853981633974484
roundtrip fibers 16
wedge HexOnlyError unsupported host element types: C3D4 (1) writes False
truss True False True False
beam False True False True
curved radii [2.1, 2.3, 2.5, 2.7, 2.9] radial True
volume csv True
```

## Current checkpoint

Checkpoint 9 local implementation and acceptance audit complete. All required artifacts are present and all no-Abaqus Python acceptance checks pass. No Git write commands were run in this revised local-only run. Human review is required before committing/pushing.

## Windows executable

Built with PyInstaller 6.22.3 on Windows 11 using Anaconda Python 3.13:

```text
python -m PyInstaller --noconfirm --clean --onefile --name embmesh embmesh_entry.py
Build complete! The results are available in ...\dist
dist\embmesh.exe size: 172,821,170 bytes

dist\embmesh.exe list examples\flat_disc.inp
part DISC: nodes=8 elements=1 types={'C3D8': 1} bbox=[0.0, 0.0, 0.0]..[1.0, 1.0, 1.0] sets=['HOST'] surfaces=[]
instance DISC-1: part=DISC translation=[0.0, 0.0, 0.0] rotation_angle=0
```

## Visualization and symmetry continuation

Added `embmesh visualize` and the matching executable command. It imports the selected part instance, generates fibers, writes a patched `output.inp`, combined `host_fibers.vtk` (host wireframe plus fiber lines and host volume-fraction cell scalar), `fiber_volume.csv`, and `report.json`; Python environments can add `--preview` for `preview.png`.

Symmetry propagation scans source `*Boundary` records for single translational DOFs on planar node sets. Fiber nodes within the configured tolerance of the inferred X/Y/Z plane are appended to the same `*Nset` in the patched deck. The symmetry mapping and propagated labels are recorded in `report.json`.

```text
dist\embmesh.exe visualize examples\symmetry.inp --instance Q-1 --diameter .25 --output outputs\exe-visual
patched deck: outputs\exe-visual/output.inp
host/fiber VTK: outputs\exe-visual/host_fibers.vtk
fibers: 16; host elements: 1
```

The inspected `uel/VUEL.for` still cannot consume per-element volume correction IDs: it has no file input, `UEXTERNALDB`, common block, or element-ID property table. The app therefore emits the per-element CSV and explicitly documents the integration gap in `docs/INTERFACE.md`; applying correction requires a companion UEL/VUEL adapter or preprocessing step.
