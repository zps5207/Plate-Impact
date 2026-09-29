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

No Abaqus run happened this session (no ROAR submission was made — see
**What was not done** below). Everything here is either new source, or checked
by a local, non-Abaqus Python transcription oracle. That distinction matters:
this project has already found (BUG-016) that a VUMAT which looks correct at
the source level can still be rejected outright by real Abaqus/Explicit, so
nothing below should be read as "confirmed to run."

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

### Fixing the BUG-016 blocker (unconfirmed)

Since a truly zero-stiffness branch is the suspected cause of BUG-016's
packager error, both new files replace the exact-zero compression/bending
branches with `RESSTIFF = 1.0D-4` times the nominal modulus — small enough to
be physically negligible in the tension/shear-dominated regime these fibers
are meant for, but nonzero so Abaqus's pre-increment-1 stiffness probe (if
that is really what's failing) has a slope to find. **This is a candidate
fix only.** It has not been run against real Abaqus. BUG-016 stays open for
these files until a ROAR run either clears or reproduces the packager error.

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

**These decks have not been run.** They are new keyword text I wrote by hand
(no mesher, no Abaqus datacheck), so — exactly like every other deck in this
repo before its first real ROAR run — keyword-syntax mistakes are plausible
until Abaqus itself parses them. I checked the parts I could reason about
concretely (e.g., `*Boundary` needs `CELL-1.<node>` instance-qualified
references at assembly level, not bare integers — caught and fixed during
generation; each `*Beam Section`'s `n1` is checked by hand to be perpendicular
to its own element's axis) but I do not have Abaqus available in this
environment to datacheck it end-to-end.

## What was not done

- **No Abaqus run, on ROAR or anywhere else.** This session did not ask the
  human to approve a ROAR submission (the project's stated rule is that every
  cluster submission needs explicit approval each time, and an SSH/Duo push
  is disruptive to ask for mid-task without a clear go-ahead). Everything
  under "confirmed" language above is about local, non-Abaqus checks only. If
  you want the T4 decks actually run, that is the natural next step and needs
  your approval for the ROAR submission itself.
- **RESSTIFF is unverified against the actual BUG-016 error.** It is a
  reasoned candidate fix, not a confirmed one.
- **RISK-017 (VUMAT-on-beam support) is unverified either way.** It might
  work exactly as assumed, might error immediately and cleanly, or might run
  silently with a different `strainInc` layout than assumed. Only a real run
  distinguishes these.
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

## Suggested next step

Get your approval to submit `verification/roar/t4/c3d8_fiber_smoke.inp` (the
simpler variant — no VUEL, isolates the beam-VUMAT question) to ROAR first.
Its outcome should be read as follows: an immediate input-file-processing
error naming beam elements would confirm the "VUMAT isn't supported on B31"
concern outright; the BUG-016-style packager error would show whether
`RESSTIFF` actually fixes it; a clean run through the step would clear both
open questions for the simplest case. Only after that would running
`vuel_fiber_smoke.inp` add information about VUEL coupling specifically.
