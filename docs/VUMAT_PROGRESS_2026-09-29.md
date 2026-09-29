# VUMAT progress report — 2026-09-29

Follow-on to Checkpoint 8 (`docs/PROGRESS.md`) and `docs/BUGS.md` BUG-016. Goal for
this session: split the single tension-only VUMAT pilot into separate truss and
beam VUMATs, both elastic-brittle (E=100 GPa, G=50 GPa), with the truss
discarding shear and the beam suppressing bending and compression; confirm each
runs on Abaqus's native T3D2/B31; confirm the fiber VUMATs interact properly
with the `VUEL` host in a 1-element/4-fiber job; confirm fibers don't load in
compression and the beam doesn't load in bending; write this report. Also
reviewed the local material-point oracle already run against the pilot VUMAT
(`agents/refiner/outbox/vumat_local_validation/`).

**Update, same day, after the human approved a ROAR submission**: both T4
smoke-test variants now run to `THE ANALYSIS HAS COMPLETED SUCCESSFULLY` with
zero errors on real Abaqus 2024 (jobs 55900454 and 55900492). That confirms
the `RESSTIFF` fix for BUG-016 and settles RISK-017 (VUMAT does run on B31 on
this install) — see **ROAR run results** below for the full account,
including two more real, previously-unconfirmed bugs (BUG-018, BUG-019) found
and fixed along the way. The rest of this report below "ROAR run results" is
left as originally written (before any Abaqus run happened) so the record of
what was and wasn't known at each point stays intact; read the update section
first for the current state.

## ROAR run results (2026-09-29, later same session)

The human approved a ROAR submission and supplied a live `SSH_AUTH_SOCK` for
this session's Bash tool, per `~/.ssh` agent-forwarding conventions this
project already uses (see the ROAR access memory). Work happened in the
existing `/storage/home/zps5207/scratch/plate_impact_verif/` workspace,
alongside T2/T3, under a new `t4/` subfolder for decks and job-specific user
files, with `t4.sbatch` mirroring `t3.sbatch`'s pattern.

**Job history** (each `rc` is the `abaqus job=... user=...` process exit code
captured by `t4.sbatch`; `.dat`/`.stdout` paths are under
`run_<deck>/<deck>.{dat,stdout}` in that scratch workspace):

| Job | Decks | Outcome |
|---|---|---|
| 55900407 | vuel_fiber_smoke, c3d8_fiber_smoke | Both rc=1, but not a real result: the decks were copied to the wrong path (`t4.sbatch` expects a `t4/` subfolder; the first `scp` landed the files at the workspace root). Fixed by moving the files into `t4/`. |
| 55900412 | same, after the path fix | Both rc=1. Real Abaqus error this time: `*Beam Section` element 201 "IS CLOSE TO PARALLEL WITH ITS BEAM SECTION AXIS" — traced to BUG-018 (radius+n1 combined on one data line silently drops the given n1). Fixed in `verification/make_t4.py`. |
| 55900454 | same, after the BUG-018 fix | **c3d8_fiber_smoke: rc=0, completed successfully.** vuel_fiber_smoke: rc=1, new error — `*User Element, type=U1` rejected (BUG-019: Explicit user-element type keys must start with `VU`). Fixed. |
| 55900492 | vuel_fiber_smoke only (c3d8 already confirmed) | **rc=0, completed successfully.** |

**What this confirms:**
- **BUG-016's `RESSTIFF` fix works** (for the new split VUMATs): `c3d8_fiber_smoke` — 2 T3D2 `TRUSSFIBER` elements + 2 B31 `BEAMFIBER` elements, both via `VUMAT_fibers_combined.for` — got through Abaqus's packager and the entire Explicit step with no error. The `zero or negative initial dilatational modulus` error that blocked `VUMAT_tension_only.for` (BUG-016) did not recur.
- **RISK-017 is cleared for this Abaqus 2024 install**: a `*User Material` on a B31 beam element was accepted at input-file-processing time and the VUMAT was called and drove the analysis to completion, despite Abaqus's documented VUMAT-element-type list not naming beams. Whichever of "the docs are stricter than the implementation" or "beam has an undocumented allowance" is true, the practical answer for this project is: it works, on this install, with this file's assumed `strainInc` layout (axial, then shear).
- **The VUEL host and the fiber VUMATs interact successfully**: `vuel_fiber_smoke` — the same 4 fibers, but the host is `uel/VUEL.for`'s user element instead of native C3D8 — also completed with zero errors. Coupling is via directly shared corner-node DOFs (no `*Embedded Element`), as planned; Abaqus accepted a `*User Element` and `*User Material`-driven fiber elements sharing nodes in the same analysis with no complaint.

**Two more real, confirmed, previously-unconfirmed bugs were found and fixed
along the way** (full detail in `docs/BUGS.md`):
- **BUG-018**: `*Beam Section, section=CIRC` with `radius, n1x, n1y, n1z` all
  on one data line silently does not use the given `n1` — Abaqus falls back
  to its own automatic default normal, which is degenerate whenever the
  beam's own axis coincides with whichever direction that default prefers.
  This project's own `verification/t1_volume_layup.py` had already raised
  this exact suspicion in a code comment, unconfirmed, months ago; it just
  never surfaced as a hard error in the one beam deck previously run on real
  Abaqus (T3's `single_uniax_along_d0.25_beam`) because that beam's axis
  happened not to coincide with the default direction. **This defect is also
  present in `embmesh/writers.py::append_fibers_to_deck` itself** (the real
  mesher, not just this session's test decks) and was not fixed there — see
  `docs/BUGS.md` BUG-018 for why, and for the fix needed.
- **BUG-019**: Abaqus/Explicit user-element type keys must start with `VU`
  (e.g. `VU1`); `U1` (a convention this session picked from habit, not from
  this project's own `uel/VUEL.for`, which never specifies a deck-side type
  key) is rejected outright. Fixed by renaming to `VU1`.

**What this run does NOT confirm** (still open, honestly):
- The *quantitative* physics of the beam's shear/bending split under a real,
  intentionally-bending load case — this smoke test's minimal boundary
  conditions (see `verification/make_t4.py`) were chosen to get nonzero,
  mixed strain into all 4 fibers structurally, not to isolate and check a
  specific bending mode's suppression numerically against the ODB's stress
  output. The local oracle (`verification/validate_vumat_fibers.py`) already
  checks that at the material-point level; extracting and checking the
  ODB's actual field output from these two completed jobs is a reasonable
  next step but was not done this session.
- Whether `RESSTIFF`'s specific value (`1.0e-4`) is well-chosen for any
  particular real fiber/host stiffness ratio beyond this smoke test's SI
  units and property choices.
- `VUMAT_tension_only.for` itself was not re-tried; BUG-016 stays open for
  that specific file (superseded by the new split files for new work).

## What was reviewed first

`agents/refiner/outbox/vumat_local_validation/validate_vumat.py` and its
`local_vumat_validation.json` were already in the repo (produced against the
old single-file `VUMAT_tension_only.for`). They correctly show 4/6 requested
behaviors passing (tension, compression clamp, failure deletion, post-deletion
zero) and 2/6 failing (no shear response, no bending suppression) — expected,
since that file predates the truss/beam split and was never meant to carry
shear or suppress bending. That result is consistent with what this session
built on top of it; no discrepancy found.

`docs/BUGS.md` BUG-016 (real Abaqus 2024, ROAR, 2026-09-28): the pilot VUMAT
compiles and links cleanly but Abaqus's Explicit packager rejects the job
before increment 1 (`zero or negative initial dilatational modulus`) because
the packager's stiffness probe apparently lands in the tension-only material's
legitimately-zero-stiffness compression branch. This is the key open blocker
that the new files below try to address (unconfirmed — see below).

## A decision needed before writing the beam VUMAT

Abaqus/Explicit's documented VUMAT-capable element types are continuum
(solid), shell, membrane, and truss — beam is not on that list. Separately,
Abaqus/Explicit's native beams (B31/B32) are Timoshenko (shear-flexible); a
true Euler-Bernoulli beam (B33) exists only in Abaqus/Standard, which uses
UMAT, not VUMAT. So "elastic-brittle VUMAT + Euler-Bernoulli beam + Explicit"
is not a combination Abaqus offers natively. Asked the human 2026-09-29; the
recommended option was chosen: target Abaqus/Explicit's native B31 with a
VUMAT anyway, accepting "Euler-Bernoulli" as a loose description of "the
native 3D beam element" rather than insisting on B33/UMAT/Standard, or
building a custom VUEL-style beam. This is recorded as **RISK-017** in
`docs/BUGS.md` — a real open risk, not yet reproduced either way, because
whether Abaqus even calls a VUMAT for a B31 section point (and with what
`strainInc` layout) is unconfirmed without a real run.

## What was built

| File | What it is |
|---|---|
| `vumat/VUMAT_truss.for` | Elastic-brittle VUMAT for T3D2. Tension-only (E=100 GPa); any shear component is discarded (zeroed) every call. Failure at `PROPS(2)` deletes the point (`STATEV(1)=0`). |
| `vumat/VUMAT_beam.for` | Elastic-brittle VUMAT for B31. Axial tension-only (E=100 GPa, same failure rule) plus fully elastic transverse shear (G=50 GPa); any further ("bending") component is suppressed in both signs. Failure zeroes axial **and** shear in the same increment (see fix below), then deletes the point. |
| `vumat/VUMAT_fibers_combined.for` | A dispatcher (branches on `cmname`) pasting the two bodies above under one `SUBROUTINE VUMAT`. Exists only because Abaqus links one user-subroutine file per job, and the T4 smoke test below uses both fiber types in the same job. |
| `verification/validate_vumat_fibers.py` | A from-scratch local material-point oracle (independent transcription, not shared code with the VUMAT sources) checking 12 requested behaviors across both materials. All 12 pass. |
| `tests/test_vumat_fibers.py` | Two pytest tests wrapping the oracle's truss/beam checks into the repo's normal test run. Both pass; full suite otherwise unaffected (see below). |
| `verification/make_t4.py` → `verification/roar/t4/` | Generates the 1-element/4-fiber smoke test in two host variants (below). |
| `docs/BUGS.md` | Added RISK-017; appended an update note to BUG-016 recording the `RESSTIFF` mitigation attempt as unconfirmed. |
| `docs/PROGRESS.md` | Added Checkpoint 9. |

Both new VUMATs, and the future-damage-tracking note the goal asked for, are
in the files' own header comments (a tracked damage variable is explicitly
called out as a planned replacement for the current instantaneous-deletion
rule — this session did not implement damage tracking, only noted it).

### Fixing the BUG-016 blocker (now confirmed — see "ROAR run results" above)

Since a truly zero-stiffness branch is the suspected cause of BUG-016's
packager error, both new files replace the exact-zero compression/bending
branches with `RESSTIFF = 1.0D-4` times the nominal modulus — small enough to
be physically negligible in the tension/shear-dominated regime these fibers
are meant for, but nonzero so Abaqus's pre-increment-1 stiffness probe (if
that is really what's failing) has a slope to find. This paragraph originally
ended by calling it unconfirmed; it is no longer unconfirmed — ROAR job
55900454 ran `c3d8_fiber_smoke` (both fiber materials, both element types)
through the packager and the full step with no error.

### A bug the local oracle caught in this session's own code

Writing `verification/validate_vumat_fibers.py` against `VUMAT_beam.for`
surfaced a real defect before any Abaqus run was needed: on the increment
where the axial trial stress crosses the failure threshold, the original
draft still updated the shear component from the same increment's
`strainInc` before the deletion flag took effect, so a just-broken beam
fiber could carry one extra increment of shear stress. Fixed in both
`VUMAT_beam.for` and `VUMAT_fibers_combined.for`: crossing the failure
threshold now zeroes every stress component immediately, in the same call,
rather than waiting for `STATEV(1)=0` to be read back on the next call. The
oracle's `beam_failure_deletes_shear_too` check went from FAIL to PASS after
this fix (see `verification/evidence/vumat_fibers_local_validation.json`).

### The 12 requested-behavior checks (all pass, locally)

Run with `python verification/validate_vumat_fibers.py --strict` (exit 0);
full detail in `verification/evidence/vumat_fibers_local_validation.json`.

- Truss: tension is elastic at 100 GPa; compression is clamped to the tiny
  `RESSTIFF` residual (not exact zero — flagged explicitly, since "does not
  load in compression" and "nonzero regularization" are in tension with each
  other and the report should not paper over that); failure at the threshold
  deletes the point; a deleted point stays at zero; shear is discarded
  regardless of any pre-existing shear stress or shear strain increment.
- Beam: tension is elastic at 100 GPa; shear is elastic at 50 GPa·γ;
  compression is clamped to the same tiny residual; a "bending" component is
  suppressed to near-zero even when there is significant pre-existing
  "bending" stress and a nonzero curvature-like strain increment, in **both**
  signs (checked explicitly, since a one-sided clamp would be a compression
  rule, not a no-bending rule); failure zeroes axial and shear together and
  deletes the point; a deleted point stays at zero.

### The 1-element/4-fiber VUEL interaction smoke test

`verification/make_t4.py` builds a unit-cube host (8 corner nodes) with 2
truss fibers and 2 beam fibers whose end nodes are literally 4 of the host's
own 8 corner nodes — no separate fiber nodes, no Abaqus `*Embedded Element`.
That keyword's embedding algorithm is documented for standard
continuum/shell/etc. hosts; it is not documented for a `*User Element` host,
and the mesher's own writer never targets one, so there was no existing
embedding path to reuse for a VUEL host. Sharing corner-node DOFs directly is
the simplest coupling available for a single host element, and is enough to
check that a fiber's internal force reaches the same global equations as
`uel/VUEL.for`'s own nodal force output — real load transfer through
ordinary equilibrium, not an approximation of one.

Two variants were generated, to separate the two open questions above instead
of conflating them in one job:

- `verification/roar/t4/vuel_fiber_smoke.inp` — host = `uel/VUEL.for` (the
  project's existing Total-Lagrangian hex user element, untouched).
- `verification/roar/t4/c3d8_fiber_smoke.inp` — host = native `C3D8R`, same
  fiber layout. If this fails the same way as the VUEL variant, the cause is
  the fiber VUMATs (BUG-016/RISK-017) and not VUEL coupling; if only the VUEL
  variant fails, the cause is specific to the user-element host.

Each has a matching job-specific `user=` Fortran file
(`vuel_fiber_smoke_user.for` = `VUEL.for` + `VUMAT_fibers_combined.for`
concatenated; `c3d8_fiber_smoke_user.for` = just the combined VUMAT),
generated by the same script rather than hand-duplicated, plus
`verification/roar/t4.sbatch` to submit both, mirroring the existing
`t3.sbatch` pattern. SI units (m, kg, s, Pa) throughout, to match the goal's
GPa values directly — a deliberate departure from the mm/tonne/s/MPa
convention `verification/make_t3.py`'s mesher-driven decks use, since this is
a standalone hand-built job, not mesher output.

**Update: both decks have now been run** (see "ROAR run results" above). My
static reasoning at the time this paragraph was first written (before any
run) turned out to be right about one thing (`*Boundary` needing
instance-qualified node references) and to miss two others entirely: BUG-018
(the beam section `n1`/radius data-line issue — I explicitly claimed to have
"checked by hand" that each `n1` was perpendicular to its own axis, which is
true and irrelevant, since the real defect was that Abaqus wasn't reading my
`n1` at all) and BUG-019 (the `U1` vs `VU1` element-type key). Leaving that
original claim in the historical section below as a record of what looked
sufficient before a real run and wasn't.

## What was not done

- **RESSTIFF is now confirmed to clear BUG-016's packager error** (job
  55900454) — no longer an open item, though see "ROAR run results" above
  for what this one run does and doesn't establish.
- **RISK-017 (VUMAT-on-beam support) is now cleared for this Abaqus 2024
  install** (same job) — also no longer open in the "might not run at all"
  sense; the remaining open question is the quantitative-physics one noted
  above, not whether it runs.
- **`embmesh/writers.py` still has BUG-018's defect** (combined radius+n1 on
  one `*Beam Section` data line) — this was found and fixed only in this
  session's own `verification/make_t4.py`, not in the actual mesher. Any
  mesher-generated beam deck whose fiber direction coincides with Abaqus's
  default-normal preference will still hit this. Not fixed in the mesher
  itself this session (out of scope for a VUMAT-progress task; flagged in
  `docs/BUGS.md` BUG-018 for a follow-up).
- **ODB field-output extraction was not done.** Both completed jobs' `.odb`
  files exist on ROAR scratch; pulling actual stress/strain time histories
  out of them (the way `verification/roar/extract_energy.py` already does
  for energy) to numerically confirm zero compression/bending stress in this
  specific run, rather than relying on the local oracle plus "the job didn't
  error," is a reasonable next step not taken this session.
- **Damage tracking** was not implemented — only noted as a planned future
  version, per the goal.
- **No changes to `verification/make_t3.py`, `verification/roar/t3/`, or
  `vumat/VUMAT_tension_only.for`.** Those still test the original pilot file
  and were left as-is; the new split VUMATs are new, separate deliverables,
  not a retrofit of the existing T3 pipeline.
- Ran the full `pytest` suite as a regression check: 14 passed (including the
  2 new tests) plus 6 pre-existing `PermissionError`s from pytest's
  `tmp_path`/cache fixtures under this OneDrive-synced folder — the same
  environment issue this repo's own evidence already documents
  (`verification/evidence/T0_pytest_basetemp.txt`), not something this
  session's changes caused.

## Suggested next step (updated after the ROAR run)

The "get approval to submit" step above happened and both variants now
complete successfully — that suggested next step is done. Reasonable
follow-ups, none done yet:

1. Fix BUG-018 in `embmesh/writers.py` itself (not just this session's test
   generator), since it affects any real mesher-generated beam deck, not
   only this smoke test.
2. Extract the two completed jobs' ODB field output to numerically confirm
   zero (or near-`RESSTIFF`) compression/bending stress in this specific
   run, closing the "quantitative physics not yet checked" gap noted above.
3. Decide whether `RESSTIFF = 1.0e-4` is the right value for real fiber/host
   stiffness ratios beyond this smoke test's own SI-unit property choices,
   before using these VUMATs on a real (non-smoke-test) job.
