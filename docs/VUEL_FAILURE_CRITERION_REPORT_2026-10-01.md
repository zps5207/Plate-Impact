# VUEL engineering-strain failure criterion: does Abaqus/Explicit honor it? (2026-10-01)

## Question

Branch `uel/VUEL.for` to add a simple failure criterion (max absolute normal
engineering strain, goal suggested ~1.0), run it on ROAR, and find out
empirically whether Abaqus/Explicit will honor that failure by deleting the
element or converting it to SPH particles — the way it does for a native
element whose material (VUMAT/UMAT) sets a `STATUS`-type state variable.

**Short answer: no.** Abaqus has no hook that lets a `*User Element` request
deletion or particle conversion. The subroutine can make itself numerically
inert once its own criterion trips (confirmed below), but the element stays
in the mesh, in the ODB, and in Abaqus's own element count forever — nothing
in Abaqus's bookkeeping (`.sta` file, element count, native STATUS field)
ever learns that anything happened.

## What was built

- **`uel/VUEL_failure.for`** — a branch of `uel/VUEL.for` (production file
  untouched). At each Gauss point, recovers the three normal engineering
  (nominal) strains from the Green-Lagrange normal strains already computed
  by the host formulation: `lambda_i = sqrt(2*E_ii + 1)`, `eng_i = lambda_i
  - 1`. `props(7)` (`EPS_FAIL`) is the trip threshold on
  `max(|eng_1|,|eng_2|,|eng_3|)`, checked once per element per increment
  (pooled over all 8 Gauss points), at the *end* of the increment — the same
  timing Abaqus's own native damage/deletion logic uses. `nsvars` grew from
  48 to 49; `svars(.,49)` is the element's own failure flag (0 = intact,
  1 = failed), read back at the top of the next call. Once failed, the
  element zeroes its own PK2/viscous/bulk stress and internal force
  contribution for every subsequent increment — "numerically inert" — but
  nothing else changes: mass is computed once up front (`jMassCalc` is only
  called once per analysis for a UEL) and is never shed.
- **`verification/make_t6_failure.py`** + **`verification/roar/t6/`** —
  single-`VU1`-hex ("T4"-style) compression decks:
  - `t6_compress_nofail` — `EPS_FAIL = 1.0` (the goal's suggested value).
  - `t6_compress_trip` — `EPS_FAIL = 0.3`.
  Both apply a ramped `-0.6` x-displacement (SMOOTH STEP, 0.01 s step) to
  the driven face against a fully pinned opposite face — true uniaxial
  compression (see "False start" below for why the BCs needed fixing).
- **`verification/roar/t6.sbatch`** — same `t4.sbatch`/`t5.sbatch` pattern.

## Physical note on "1 engineering strain" + "compression test"

A 1-D engineering (nominal) strain cannot reach `-1.0` under compression —
that limit is zero volume. It asymptotically approaches `-1` but a
`|strain| >= 1.0` threshold (the goal's suggested value) is **unreachable
from the compressive side** in any stable analysis. `t6_compress_nofail`
demonstrates this by construction: same `-0.6` applied compression as the
trip case, but `EPS_FAIL=1.0` is never approached (max |eng strain| reached
≈0.6, see Results). `t6_compress_trip` uses `EPS_FAIL=0.3` instead, so the
same loading actually exercises the criterion while still being a genuine
compression test.

## False start: the BC pattern mattered

The first attempt reused `verification/make_t4.py`'s minimal
rigid-body-removing BC pattern (it only pins 2 of the 4 back-face nodes in
x, leaving the other 2 free — adequate for T4's tension smoke test, which
only needed *some* valid equilibrium solution). Under compression this let
the single hex deform non-uniformly enough that `max|eng strain|` plateaued
at **0.2998**, just barely under a 0.3 threshold, even with the driven face
displaced the full `-0.6`. Confirmed by adding a temporary unconditional
per-call `WRITE` and re-running (ROAR job 55967615) — see
`verification/roar/t6_dbg.sbatch` pattern (not kept). Fixed by pinning the
*entire* back face (`x=0`: nodes 1,4,5,8) in x, which gives a clean uniaxial
compression state; that is the version committed in `verification/roar/t6/`.

Two other ROAR/Abaqus keyword lessons from getting a VUEL's state variables
into any kind of output, both confirmed on real Abaqus 2024 and neither
previously documented in `docs/abaqus-explicit-quirks.md`:
1. `*Element Output` (field/.odb request) rejects `SVARS` as an identifier
   for a `*User Element`: `***ERROR: UNIDENTIFIED OR INVALID OUTPUT REQUEST
   SVARS`.
2. `*El Print` (the usual UEL-SVARS-to-.dat workaround, per several Abaqus
   forum threads) is an Abaqus/Standard-only keyword: Abaqus/Explicit
   rejects it outright — `***ERROR: THE ELPRINT KEYWORD IS NOT AVAILABLE IN
   Abaqus/Explicit`. Several circulating writeups (ResearchGate, Abaqus
   mailing-list archives) describe `*El Print, ..., SVARS` as *the* fix for
   getting UEL state variables out, without flagging that this applies to
   Standard, not Explicit — worth remembering next time this comes up.

Net effect: there is no supported way to get `uel/VUEL_failure.for`'s own
failure flag into the ODB at all for Explicit. The evidence channel used
instead was the subroutine's own `WRITE(*,*)` to the job's stdout, plus
node-level `RF`/`U` history (both ordinary, fully-supported output).

## Results (ROAR job 55967626, both decks rc=0, `THE ANALYSIS HAS COMPLETED
SUCCESSFULLY`)

**`t6_compress_nofail`** (`EPS_FAIL=1.0`): no `VUEL_FAILURE` message at any
point in the 0.01 s step. Expected — see the physical-bound note above.

**`t6_compress_trip`** (`EPS_FAIL=0.3`): subroutine printed

```
*** VUEL_FAILURE: ELEMENT FAILED, elem =    1  time =  5.0382130E-03  max|eng strain| =  0.300... threshold = 0.300...
```

at `t ≈ 5.04 ms`, as expected (driven face is at ≈-0.3 engineering-strain
displacement roughly halfway through a smooth-step ramp to -0.6). The
reaction force history at the fixed node (`RF1`, extracted from the ODB
with `abaqus python`) makes the "numerically inert" behavior unmistakable:

| frame | t (s)   | RF1 (N)      |
|------:|--------:|-------------:|
| 8     | 0.00409 | 7.19e9       |
| 9     | 0.00463 | 8.35e9       |
| 10    | 0.00504 | **8.97e9**   |
| 11    | 0.00558 | **0.0**      |
| 12    | 0.00613 | 0.0          |
| ...   | ...     | 0.0          |
| 20    | 0.01000 | 0.0          |

`RF1` climbs smoothly for 10 frames, then drops to *exactly* `0.0` at the
very next output frame (the one immediately after the failure message) and
stays there for the rest of the step — the element's own force/stress
contribution genuinely vanished the increment after it failed, exactly as
the subroutine was written to do.

But: **`len(odb.rootAssembly.instances['CELL-1'].elements)` is `1` in every
frame, before and after failure.** No entry resembling "elements deleted",
"converted to particle", or "status" appears anywhere in either job's
`.sta` file. Abaqus's own bookkeeping never registers the event; the only
evidence it happened is this subroutine's own stdout message and the
RF/stress trace going to zero. The element is not removed, not converted,
not flagged in any native field — it is simply present, inert, and
indistinguishable in the mesh/ODB from an element that was never touched.

## Why — consulted literature/documentation

Both of Abaqus's native "something failed, now what" mechanisms are keyed
to a **material-point STATUS state variable**, not anything a `*User
Element` can expose:

- **Ordinary element deletion** (`*Section Controls`, default
  `ELEMENT DELETION=YES`) is driven by a damage model or a VUMAT/UMAT
  setting the state variable named in `*Depvar, delete=N`; `STATUS` field
  output (1=active, 0=deleted) is a *material*-level quantity.
- **Conversion to SPH particles** ("Finite element conversion to SPH
  particles", Abaqus Analysis User's Guide §15.2.2) is even more
  restrictive: eligible host elements are limited to **`C3D8R`, `C3D6`, and
  `C3D4`** (reduced-integration native continuum solids) only, and the
  conversion flag is a state variable that only `VUMAT`/`VUSDFLD` (material
  subroutines, again material-point-scoped) are documented to set. A `VU1`
  user element is neither in the eligible-type list nor does it have a
  `*Material` definition at all (`*UEL Property` is not a material), so
  there is no variable Abaqus's conversion logic could even look at.

This is the same root cause as `docs/BUGS.md` BUG-020 (native
`*Embedded Element` rejecting every node on a VUEL host, confirmed ROAR job
55933355): Abaqus's higher-level adaptive/failure/embedding features are
built against its own native element-and-material bookkeeping, and a
`*User Element` simply isn't wired into any of them. A VUEL is, by design,
a black box to the rest of Abaqus beyond force/mass/stable-dt — which is
exactly what this test now confirms empirically for element failure too,
not just embedding.

Sources: [15.2.2 Finite element conversion to SPH particles (Abaqus 6.13
docs mirror)](http://dsk.ippt.pan.pl/docs/abaqus/v6.13/books/usb/pt04ch15s02aus96.html),
corroborated via [a second mirror](https://ceae-server.colorado.edu/v2016/books/usb/pt04ch15s02aus97.html)
(element-type list and the VUMAT/VUSDFLD-only conversion-flag mechanism);
general element-deletion/`*Depvar,delete=N`/`STATUS` background from
several ResearchGate/Abaqus-mailing-list threads (search only — see session
log, not independently re-verified against the primary manual section for
that specific feature, unlike the SPH-conversion citation above which was
fetched directly).

## What this means for the project

- If element erosion/failure is wanted for a VUEL-hosted mesh, it has to be
  **entirely homegrown** (as demonstrated here: zero the stress/force once
  a criterion trips) — there is no way to get Abaqus's native deletion
  visuals, `.sta` reporting, mass removal, or SPH conversion to engage, no
  matter what state variable is set or how `*Depvar`/`*Section Controls`
  are configured.
- A homegrown "dead" element still occupies its mass and nodes forever
  (VUEL mass is computed once, up front — there's no way to shed it
  mid-analysis the way native deletion does), so for something like a
  fragmenting-material or spall simulation, a VUEL host is a real
  limitation, not just a missing nicety. This reinforces the shelved
  [[vuel-host-toggle-todo]] decision to treat VUEL-host coupling as
  needing its own design work rather than a drop-in toggle.
- No ODB-visible status field is possible for a VUEL's own state (neither
  `*Element Output` nor `*El Print` support it in Explicit) — any
  diagnosis of VUEL-internal state has to go through the subroutine's own
  `WRITE` to stdout, or through indirect node-level history (as done here).

## Reproducing

```
ssh roar "mkdir -p /storage/home/zps5207/scratch/t6"
scp -r verification/roar/t6 verification/roar/t6.sbatch roar:/storage/home/zps5207/scratch/
ssh roar "cd /storage/home/zps5207/scratch && sbatch t6.sbatch"
# after it completes:
ssh roar "cat /storage/home/zps5207/scratch/run_t6_compress_trip/t6_compress_trip.stdout" | grep VUEL_FAILURE
```

Job IDs this session: 55967504/55967514/55967534/55967550 (iteration —
fixed an elset-scoping error, then the `*Element Output`/`*El Print` SVARS
errors), 55967606/55967615 (debug instrumentation run, `dbg_trip`, found
the BC bug), **55967626 (final, both decks rc=0 — the results above)**.
