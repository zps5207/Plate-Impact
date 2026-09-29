# Verification Goal (Claude Code)

Read this whole file before acting. It is the contract for this `/goal` run.

## 1. Objective

Independently verify the current state of the embedded-element toolchain in this directory and deliver:

1. `docs/VERIFICATION_REPORT.md`: the current status of the app, with evidence.
2. `docs/BUGS.md`: every bug or discrepancy found, in the format in section 5.

Do not fix the mesher. Find, reproduce, document, and propose fixes. The purpose is an honest status report, so a failing test is a useful result, not a problem to hide.

## 2. Scope

In scope: the embedded-element mesher (CLI and Python API), the Windows exe INP patcher, the visualization tool, the boundary-condition passing methods, the tension-only elastic-brittle VUMAT, and the fiber-volume file interface to the user element.

Out of scope for verification: the volume redundancy correction inside the VUEL. It is not implemented yet. It is handled by the separate parallel track in section 7. Verification runs use the plain Abaqus embedded element with NO correction, and those uncorrected results become the baseline the correction is later judged against.

## 3. Rules

- Local writes: only `verification/` and `docs/` in `C:\Users\salas\OneDrive - The Pennsylvania State University\Plate Impact`. Treat the mesher source, `uel/`, and `vumat/` as read-only during verification.
- `C:\Users\salas\OneDrive - The Pennsylvania State University\Embedded Elements` is read-only context. Never write there.
- ROAR: work only under `/storage/home/zps5207/scratch/plate_impact_verif/` (create it). Inspect existing job scripts in scratch (read-only) to learn the module and license lines. If you cannot determine them with confidence, stop and ask me.
- Job limits (adjust only if I say so): walltime at most 30 minutes per job, at most 5 jobs queued or running at once, modest core counts, `scancel` only jobs you submitted in this run, never delete anything outside your subdirectory. Log every job ID, script, and outcome in `docs/PROGRESS_VERIF.md`.
- Independence: write your own checks from scratch in `verification/`. Use the tools as a black box through their CLI and output files where possible; do not reuse Codex's tests as evidence. Read Codex's tests and `docs/PROGRESS.md` only to compare its claims against what you find.
- Git: no git write commands. Read-only git commands are fine. List every file you created at the end and ask me to review, commit, and push.
- Keep raw evidence (logs, `.dat`/`.msg`/`.sta` excerpts, command output, plots) in `verification/evidence/` and reference it from the report.
- Do not stop at the first bug. Continue with the remaining independent tests. Mark a test `blocked` (with the reason) rather than skipping it silently.
- Keep `docs/PROGRESS_VERIF.md` current (current test, results so far, blockers) so a resumed session can continue.

## 4. Test plan

Mark every test `pass`, `fail`, or `blocked`, with evidence.

### T0. Audit
- Run `pytest` and record results.
- Build a claims table: each acceptance claim in `docs/PROGRESS.md` against what you observed.
- Exe patcher: runs on a clean environment (no Python), same output as the Python CLI (compare hashes), handles paths with spaces and OneDrive paths, sensible exit codes and error messages, `--help` accurate.

### T1. Local geometry and data checks
1. Parser: round-trip a real deck; compare node, element, and set counts and instance transforms (rotation and translation) with a hand-checked case.
2. Hex-only guard: wedge, tet, and shell each raise the error and write no output.
3. Fiber volume, independent of the mesher's clipper: Monte Carlo or voxel sampling of fiber cylinders in host hexes. Pass: total equals total fiber length x pi d^2 / 4 within 1e-6 relative; bulk volume fraction about pi/4 within 2%.
4. Layup: minimum centerline distance at least d at zero gap; layer count equals thickness divided by pitch; 0/90 alternation; curved plates (cylindrical shell, concentric spherical shell, varying-thickness plate): director field and fiber orthogonality; near-parallel reference vector; label collisions.
5. Truss and beam toggle: correct section keywords (T3D2 with area, B31 with radius and `n1`).
6. Visualization tool: read its exported file back and compare counts and volumes to the data; render checks that fibers stay inside the plate and layers alternate.
7. Boundary condition passing: diff generated keywords against a hand-written reference deck; check node set membership, amplitudes, and units.
8. Fiber-volume file: parse it against `docs/INTERFACE.md` and against the ingestion code in the UEL source; check label mapping (part vs assembly labels) and totals.

### T2. Abaqus datacheck on ROAR
Datacheck flat and curved decks, truss and beam. Pass: no unconstrained embedded nodes, embedded node weight factors sum to 1 (within 1e-6), element types accepted in Explicit, no unexpected warnings. Record embedded node counts and any tolerance sensitivity.

### T3. Mechanics in Abaqus/Explicit on ROAR (uncorrected)
- Single host element with fibers: uniaxial along and across fibers, shear, compression, hydrostatic. Compare with rule-of-mixtures analytics.
- Measure the redundancy error versus fiber fraction (stiffness, mass, energy). These numbers are the baseline for the VUEL correction; report them in a table.
- Mass check: model mass versus matrix mass x (1 - phi) plus fiber mass, and versus the uncorrected mass.
- Energy balance (ALLIE and related) closes within a few percent.
- VUMAT: tension to failure, compression clamp, element deletion; T3D2 and B31.
- Cantilever beam case.
- Sensitivity: fiber element length versus host size, host refinement, embedded tolerances, fibers on host faces, stable time increment versus the mesher's estimate.
- If time allows: a small 1-D through-thickness wave test versus effective properties.

## 5. Bug format (`docs/BUGS.md`)

For each bug: ID (BUG-001...), title, severity (blocker, major, minor, cosmetic), component, commit or version, exact repro command, expected, actual, evidence path, suspected cause, proposed fix (not applied). Sort by severity in a summary table at the top.

## 6. Report structure (`docs/VERIFICATION_REPORT.md`)

1. Executive summary: overall verdict and the three biggest issues.
2. Feature status matrix: each feature marked Working, Partial, Broken, or Untested, with one line of evidence.
3. Test results table (ID, description, method, pass criterion, result, evidence).
4. Baseline redundancy data (T3) as tables.
5. Bug summary (link to `docs/BUGS.md`).
6. Coverage gaps and limitations.
7. Recommended next steps, ordered.
8. Reproducibility: versions, commit hash, environment, job IDs, how to rerun each test.

## 7. Parallel track: VUEL volume redundancy correction (delegate)

The VUEL cannot yet accept the fiber-volume correction. Work on it in parallel with verification, but keep the tracks separate.

- Delegate the code to Codex through whatever delegation mechanism exists (check `docs/DELEGATION.md` and `tools/run-worker.sh` in the Embedded Elements folder, if present, or an installed Codex plugin). If none works, prepare a self-contained brief for me to hand to Codex, and say so.
- Codex works locally only, in a new directory `vuel_correction/` in this repo. It must not touch the mesher source, `verification/`, `uel/`, or `vumat/`, and cannot run Abaqus.
- Codex deliverables: `docs/VUEL_CORRECTION_DESIGN.md` (formulation, how the per-element fiber volume fraction is read from the mesher's file, how host internal force and mass are corrected, edge cases, cases where the fiber fraction is high) and the modified VUEL source. Reference material is read-only in Embedded Elements (the reference code and the published energy-based redundancy study).
- You (Claude Code) own everything touching ROAR: compile Codex's VUEL, run single-element and cantilever cases, and compare corrected versus the uncorrected baseline from T3 and versus analytics. Feed failures back to Codex. Write the status in `docs/VUEL_CORRECTION_STATUS.md`, separate from the verification report.
- Start this track after T0 is complete. Never let it block or contaminate verification; verification stays uncorrected.

## 8. Done and stop conditions

Done when every test in section 4 is marked pass, fail, or blocked with evidence, both deliverables are complete per sections 5 and 6, and you have listed all files created and asked me to review, commit, and push.

Pause and report if: SLURM or module details cannot be determined; SSH fails; a required write outside the allowed locations is needed; or jobs consistently fail for a reason you cannot diagnose after three distinct attempts.
