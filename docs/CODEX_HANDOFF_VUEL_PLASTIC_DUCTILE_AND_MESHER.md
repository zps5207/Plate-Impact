# Goal prompt for Codex: finish the elastic-plastic/ductile-failure VUEL, then integrate it into the embmesh mesher

Paste everything below this line to Codex as its goal/task prompt.

---

## Context you must read before writing any code

This project (Abaqus/Explicit plate-impact simulation tooling) already has
two related, mostly-finished pieces of work. Read these in order before
doing anything:

1. `docs/VUEL_FAILURE_CRITERION_REPORT_2026-10-01.md` — confirms, against
   real Abaqus 2024 runs on ROAR, that a `*User Element` (VUEL) cannot
   trigger Abaqus's native element deletion or SPH particle conversion.
   Any failure/erosion behavior must be entirely homegrown inside the
   user subroutine.
2. `docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md` through
   `docs/VUEL_PLASTIC_FAILURE_STAGE4_REPORT_2026-10-01.md` — the staged
   plan and results for `uel/VUEL_failure.for` (branch
   `vuel-plastic-failure`), which already has:
   - Stage 0: formulation plan (additive Green-Lagrange J2 plasticity on
     the existing Total-Lagrangian St. Venant-Kirchhoff `(S,E)` pair —
     **not** a multiplicative `F=Fe·Fp` model; see that file for why).
   - Stage 1: linear-hardening J2 plasticity, closed-form radial return,
     verified to ~6% against an analytic bilinear bar (tension,
     compression, unload/permanent-set).
   - Stage 2: confirmed the engineering-strain failure trigger still
     works correctly with plasticity active (no code change needed).
   - Stage 3: added a Jacobian (`min det(F)` over 8 Gauss points)
     collapse trigger, since 1-D engineering strain is bounded at -1
     under compression and cannot catch compression/shear collapse.
     Verified on heavy-compression and combined-shear-collapse decks.
   - Stage 4: fixed two dead-state bookkeeping bugs (Rayleigh/bulk-
     viscosity dissipation kept accumulating for failed elements;
     `dtimeStable` was never relaxed for a failed element). Confirmed a
     fully-orphaned node (all its elements failed) goes into exact
     constant-velocity free flight. **Important finding**: a 3-element
     chain with staggered failure thresholds did NOT cascade — once the
     first element died, the remaining structure lost its anchor and
     rang violently (undamped) instead of redistributing load, so the
     intended sequential failure never happened. This is why Stage 5
     (ramped degradation) matters.
3. `docs/abaqus-explicit-quirks.md` — a running list of confirmed real
   Abaqus/Explicit 2024 behaviors that are easy to get wrong and are NOT
   documented clearly by Abaqus itself. At minimum, internalize:
   - `*User Element` type keys must start with `VU`, not `U`.
   - **`*UEL Property` data lines silently truncate beyond 8 values per
     line — no error, no warning.** This cost the most debugging time in
     this project (looked exactly like disabled plasticity). Any time
     `nprops` grows past 8, split the data across multiple lines (8 per
     line, continue on the next).
   - `*Element Output`/`*El Print` do **not** support `SVARS` for a
     `*User Element` in Abaqus/Explicit. There is no way to get a VUEL's
     internal state into the ODB or .dat file. Diagnosis must go through
     the subroutine's own `WRITE(*,*)` to stdout, or indirect node-level
     `RF`/`U`/`V` history.
   - `*Beam Section`'s `n1` normal must be on its own data line, not
     combined with the radius on one line (silently dropped otherwise).
   - A Python deck generator's `Path.write_text()` on Windows defaults to
     CRLF line endings, which breaks a `bash for n in $(cat decks.txt)`
     loop reading the deck list on ROAR (the `\r` becomes part of the
     filename). Always pass `newline=''` in any generator meant to run on
     ROAR.
4. `docs/BUGS.md` BUG-020 and BUG-021 — BUG-020: native `*Embedded
   Element` does **not** work with a `*User Element` host (confirmed:
   every embedded fiber node rejected uniformly, regardless of actual
   position — Abaqus's point-location search doesn't even attempt it
   against a non-native host). BUG-021: no native deletion/SPH conversion
   for a VUEL (same root cause family as BUG-020 — Abaqus's higher-level
   adaptive features are wired to native element+material bookkeeping
   only).
5. `docs/TODO.md`'s "VUEL host toggle" entry — the mesher (`embmesh/`)
   currently only supports a native `C3D8R` host with native
   `*Embedded Element` fiber coupling. A VUEL host option was requested,
   investigated, and **shelved pending a different coupling strategy**
   because of BUG-020. That shelved work is now **in scope for you** —
   see Task 2 below.
6. `uel/VUEL.for` — the **production** elastic-only VUEL. **Never modify
   this file.** `uel/VUEL_failure.for` is its branch; your plasticity/
   ductile-failure work continues on that branch's file (or a renamed
   successor — your call, documented).

## Non-negotiable working rules (carried over from how this project has
been run so far — deviating from these has cost real time before)

- **Work on a branch** (continue on `vuel-plastic-failure`, or branch from
  it — your call, document which). Never touch `uel/VUEL.for`.
- **Do not guess Abaqus behavior.** If a claim depends on Abaqus semantics
  not already confirmed in `docs/abaqus-explicit-quirks.md` or the Stage
  reports, test it on ROAR before relying on it. Document whatever you
  find (success or failure) in `docs/abaqus-explicit-quirks.md` or
  `docs/BUGS.md`, matching the existing entries' style (repro, expected,
  actual, evidence).
- **Every stage: build a deck generator under `verification/` (Python,
  `newline=''` on every write), a matching `.sbatch` under
  `verification/roar/`, run it on ROAR, pull real numbers back via
  `abaqus python` against the ODB (remember: no `SVARS`/`S` field output
  for a VUEL — use `RF`/`U`/`V` node history, or the subroutine's own
  `WRITE` to stdout), and write a dated report file
  (`docs/..._STAGE{N}_REPORT_<date>.md` or similarly named) with the
  actual numbers. Do not claim a pass without the numbers.**
- **Commit after each stage passes**, not before — one commit per stage,
  with the evidence summarized in the commit message (job IDs, key
  numbers), same style as the existing Stage 1-4 commits on this branch
  (`git log` on `vuel-plastic-failure` to see the pattern).
- **ROAR submission**: `module load anaconda/2023.09`, `module load
  abaqus`, `module load intel` (for ifort, needed to compile the user
  subroutine) — see any `verification/roar/t*.sbatch` for the exact
  pattern to copy. Submission goes to the `open` Slurm account by default
  (no `#SBATCH --account=` line); if you hit multi-hour queue delays, that
  is likely the account's fair-share/billing-minutes limit, not a stuck
  job — check `squeue`'s pending reason and `sprio`, do not assume
  something is broken.
- **Ask before changing physics, thresholds, or the props/svars
  interface layout** (same rule this project's human maintainer gave for
  Stages 0-4) — otherwise proceed autonomously.
- When something fails, diagnose and fix it within the current stage and
  record the lesson in `docs/abaqus-explicit-quirks.md` or `docs/BUGS.md`
  before moving on. Do not skip ahead with an unexplained failure.

---

## Task 1: Finish the elastic-plastic, ductile-failure VUEL

### Task 1a — Stage 5 (already scoped, not yet done): ramped degradation

Per the Stage 4 report's own recommendation: add an optional **ramped
force degradation** path for a failed element, instead of the current
instant drop to zero stress/force. Behind a new prop flag (keep the
current instant-zero behavior as the default/baseline — do not remove
it). Suggested design, propose and confirm before implementing if it
changes the svars layout:
- A new prop, e.g. `DEGRADE_TIME` (seconds) or `DEGRADE_RATE`: once
  failed, linearly (or exponentially — your call, document the choice)
  ramp the stress scale factor from 1.0 down to 0.0 over that time/rate,
  rather than an instant step. Needs one new per-element state value
  (time-of-failure, or an accumulated degradation fraction) in `svars`.
- Also add the goal's other suggested option: an optional
  **compression-only residual stiffness** for failed elements (i.e., a
  failed element still resists further compression, modeling crushed
  material that can't support tension/shear but still has some bulk
  resistance) — behind its own separate prop flag, combinable with or
  independent of the ramped degradation.
- Verify both against the Stage 4 zero-rhs baseline: rerun
  `t10_three_chain` (or an equivalent new deck) with ramped degradation
  turned on and confirm/report whether it changes the "doesn't cascade,
  rings instead" finding from Stage 4 — this was the explicit motivation
  for building this stage.

### Task 1b — Ductile failure criterion (new scope, requested directly by
the project owner)

Replace or augment the current failure logic so it is a genuine
**ductile failure model**, not just the ad hoc engineering-strain
trigger from the earlier branch stages. Concretely:

1. **Add a critical-equivalent-plastic-strain failure criterion**: once
   `PEEQ` (already tracked per Gauss point, per Stage 1) at any Gauss
   point meets/exceeds a new prop `PEEQ_FAIL`, the element fails via the
   same latch mechanism already in place (`svars(49)`). This is the
   standard, simplest ductile-failure criterion (constant critical
   plastic strain) and should be your default/baseline ductile model.
2. **Consider (propose to the project owner before implementing, since
   it changes the physics materially) a stress-triaxiality-dependent
   ductile failure model** (e.g., a simplified Johnson-Cook-style
   fracture strain `eps_f(triaxiality) = D1 + D2*exp(-D3*sigma*/sigma_eq)`
   where `sigma* = hydrostatic/sigma_eq`), which is the standard way real
   ductile failure depends on stress state (shear-dominated vs.
   tension-dominated loading fail at very different plastic strains).
   This is more physically correct for a plate-impact application
   (mixed tension/compression/shear states) than a constant critical
   PEEQ, but is a bigger, riskier change — get explicit confirmation on
   the model form and its new props before writing it.
3. Decide how the new ductile criterion interacts with the two existing
   triggers (engineering-strain, Jacobian): all three should be checked
   each increment (first one found wins the log message, same pattern as
   the existing two), each independently capable of latching the element
   dead. Keep the engineering-strain trigger too (it's still a tension-
   only check, cheap, and already verified) unless you have a specific
   reason to remove it — ask first if you want to.
4. Verify the new criterion the same way Stage 1/2 verified plasticity
   and the engineering-strain trigger: a single-hex uniaxial test driven
   well past the new `PEEQ_FAIL` (or, for the triaxiality-dependent
   version, at least two single-hex tests at clearly different stress
   states — e.g. uniaxial tension vs. a combined shear+compression state
   like `t9_shear_collapse` — to confirm the fracture strain actually
   differs as the model predicts), confirming trip-at-expected-PEEQ,
   RF-exactly-zero-after, same evidence pattern as every earlier stage.

### Task 1c — Stage 6 (already scoped, observation only): embedded-fiber
interaction

Build a small plate-impact-style test using the mesher's existing
ghost-`C3D8R`/embedded-`T3D2`-fiber coupling (the production, already-
working coupling — NOT your new VUEL host, see Task 2), but with a VUEL
host for the non-fiber-bearing elements if the geometry allows, or
otherwise placed adjacent to the fiber-bearing region. Observe (do not
redesign) what happens to the embedded fibers when their neighboring VUEL
host elements go dead (do fibers continue deforming independently? does
anything blow up?). Report findings; this is explicitly observational
per the original Stage 6 scope.

### Checkpoint before moving to Task 2

Do not start Task 2 until Task 1a/1b/1c are each committed with their own
verification report, following the same per-stage discipline as Stages
1-4. The project owner should review/confirm the ductile failure model
choice (Task 1b item 2 especially) before Task 2 begins, since Task 2
will bake whichever VUEL version you finish into the mesher's generated
decks.

---

## Task 2: Integrate the finished VUEL into the embmesh mesher

This resumes the shelved work described in `docs/TODO.md`'s "VUEL host
toggle" entry. Read that file's entry in full — it already identifies the
blocker (BUG-020) and the two candidate coupling strategies. Your job is
to pick one, build it, verify it on ROAR, and only then build the
toggle itself.

### Task 2a — Solve the fiber-coupling problem for a VUEL host

Native `*Embedded Element` does not work against a `*User Element` host
(BUG-020, confirmed). You need a different coupling mechanism. Two
candidates were identified (pick one, or propose and confirm a third):

1. **Node-snapped coupling**: generate the fiber mesh so its nodes are
   exactly coincident with the host VUEL mesh's own nodes, sharing DOFs
   directly (no `*Embedded Element` needed — ordinary shared-node
   equilibrium, like `uel/VUEL.for`'s own `t4`/`t5` smoke tests already
   do for a single element). This is the only coupling **confirmed
   working** with a VUEL so far, but only demonstrated for one host
   element with fiber endpoints exactly at its corners. Generalizing
   this to a real multi-element host and an arbitrary fiber
   diameter/pitch layup is real design work: fiber layer positions will
   likely need to be constrained to the host's actual node grid rather
   than freely chosen from `--diameter`/`--gap` the way the native-host
   path currently allows. You will need to decide (and document) how
   much flexibility is lost, and whether/how to warn the user when their
   requested fiber geometry can't be snapped to the host grid without
   unacceptable distortion.
2. **A verified `*Tie`/`*MPC`/`*Coupling` alternative** — not attempted
   yet in this project. If you go this route, you must independently
   verify on ROAR that the chosen constraint actually works against a
   VUEL host (do not assume it will just because it's a different
   keyword than `*Embedded Element` — test it the same rigorous way
   BUG-020 was found, with a matched native-host control deck).

Whichever you choose: build the smallest possible verification deck
first (same pattern as `verification/make_t4.py`/`make_t5_uel_embed.py`),
run it on ROAR, and get a clean pass before touching `embmesh/writers.py`
at all.

### Task 2b — Wire the VUEL host option into the mesher

Once coupling is verified:
1. Add a `--host-element-type {c3d8r,vuel}` CLI option (default `c3d8r`,
   preserving all current behavior exactly).
2. In `embmesh/writers.py`, swap the host element/section block: native
   mode keeps `*Element, type=C3D8R` + `*Solid Section`; VUEL mode emits
   `*User Element, type=VU1, ...` + `*Element, type=VU1` +
   `*UEL Property`, auto-filling the VUEL's props array from whatever
   host material properties the deck already carries (E, nu, density at
   minimum — decide and document how/whether the mesher exposes the
   VUEL's plasticity/ductile-failure/Jacobian-trigger props, e.g. new
   CLI flags or a sensible default that disables plasticity/failure
   unless explicitly requested).
3. **Respect the 8-values-per-`*UEL Property`-line limit** in the writer
   — this bit this exact project once already; don't repeat it. Write a
   small unit test asserting the writer never emits more than 8 numbers
   on one `*UEL Property` data line, regardless of how many props the
   finished VUEL ends up needing.
4. Get `nsvars`/`nprops`/`variables=`/`properties=` right and consistent
   between the `*User Element` declaration and whatever VUEL source file
   version you're shipping — add a test that fails loudly if these ever
   drift out of sync (e.g., parse the `.for` file's own header-documented
   layout and cross-check against what the writer emits, or at minimum a
   hardcoded constant shared between the writer and a comment in the
   `.for` file, checked by a test).
5. Add the GUI combobox in `embmesh_desktop.py` for host element type,
   gated so it's disabled/hidden until Task 2a's coupling is verified end
   to end — do not ship a toggle that can silently produce a broken deck
   the way the original investigation found the GUI's naive first attempt
   would have (see `docs/BUGS.md` BUG-020's "consequence" note).

### Task 2c — End-to-end verification

Before calling this done:
1. A ROAR smoke test identical in spirit to `t4`/`t5`/`t6`: one small
   multi-element VUEL-host deck generated **through the mesher's own
   CLI/API** (not hand-written), with a real fiber layup, confirmed to
   run clean on Abaqus 2024.
2. Re-run the mesher's existing test suite (`pytest`) to confirm the
   native `C3D8R` path is byte-identical/unaffected by your changes
   (regression safety — the whole point of a default-preserving CLI flag).
3. A short end-to-end report (same `docs/..._REPORT_<date>.md` pattern)
   covering: which coupling strategy you chose and why, what geometric
   flexibility (if any) was traded away, the ROAR job IDs and pass/fail
   numbers for both the raw-VUEL coupling test and the mesher-generated
   smoke test, and an honest list of anything still not supported (e.g.
   curved layups, specific fiber types) for the VUEL host path.

---

## Summary of deliverables, in order

1. Stage 5 report + commit (ramped degradation / compression-only
   residual).
2. Ductile failure criterion report + commit (constant-PEEQ baseline at
   minimum; triaxiality-dependent model only after explicit confirmation).
3. Stage 6 report + commit (embedded-fiber observation).
4. Fiber-coupling-for-VUEL-host verification report + commit (before
   touching the mesher).
5. Mesher integration (CLI + writer + GUI + tests) + end-to-end
   verification report + commit.

Every one of these five gets its own dated report file with real ROAR
numbers, and its own commit, following the exact discipline already
demonstrated in this branch's Stage 1-4 commits (`git log
vuel-plastic-failure`). Do not batch multiple deliverables into one
commit, and do not mark anything done without the numbers to back it up.
