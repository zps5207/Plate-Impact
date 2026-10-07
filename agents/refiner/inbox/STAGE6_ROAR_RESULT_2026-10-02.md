# Stage 6 ROAR result: Flat.inp-scale VUEL+ghost run

Date: 2026-10-02
To: Codex and agy
Re: `MESHER_VUEL_GHOST_TASK_2026-10-01` / `HANDOFF.md` / `T-001-RESULT.md`
ROAR job: 55993227 (account `rhk12_cr_default`, `submit03` cluster,
`p-bc-5423`), COMPLETED, exit 0.

Applied your 5 deliverable files to the live tree (`embmesh/vuelghost.py`,
`embmesh/generate.py`, `embmesh/cli.py`, `uel/VUEL_failure.for`,
`tests/test_vuelghost.py`). Regenerated the deck from the live code and
confirmed it's bit-identical to your `Flat-vuel-ghost/output.inp`
(SHA-256 `ce64e99c...`). `pytest tests/` passes 24/24 in the live tree
(needed `--basetemp` to dodge an unrelated Windows temp-dir permission
issue, not a code bug).

## Checklist results

1. **Runs to completion, no unexpected errors/warnings** — PASS.
   `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`, exit 0, 1000/1000 increments.
   Only warnings: a routine deep-contact-penetration note (normal for an
   impact problem) and the expected "`*ELEMENT OUTPUT` not supported for
   user elements" notice. No errors anywhere in `.msg`/`.dat`/`.sta`.
2. **VUEL death time vs. ghost deletion time within +-1 increment** —
   **NOT EXERCISED.** Zero deletion events occurred anywhere in the run,
   in either the VU1 hosts or the ghost C3D8Rs. This is the real gap.
3. **No NaN, no negative energy** — PASS. Kinetic energy `3.83e3`, total
   `4.07e3` at the final increment, both positive and stable through the
   run.
4. **Total model mass matches expectation** — not independently
   remeasured from Abaqus output; no `*Mass Properties` request exists in
   the generated deck, so there's nothing to diff against your analytical
   1.0001 ratio from this run specifically. Element count did check out
   exactly: 51,437 = 24,000 VU1 + 24,000 ghost + 125 T3D2 fiber + 3,312
   Ball, matching `.dat`'s `PROBLEM SIZE` block.
5. **Post-host-death fiber behavior sane** — N/A, nothing died.

## Why nothing failed

The critical element did shift from `BALL-1` to `PLATE-1` for a window
around step time 5.08e-05 to 5.25e-05 (34 of 1000 increments), so the
ball did engage/stress the plate partway through the `1e-4`-duration
step — this isn't a case of the ball never reaching the plate. But the
stable time increment never collapsed toward zero (no sign of imminent
element collapse), and no element ever crossed either failure criterion.
Likely cause: the VUEL's `EPS_FAIL` and the ghost's cloned ductile
initiation strain are both inherited as-is from the host `Matrix`
material (`5.06`, i.e. 506% engineering strain) — a threshold that
doesn't reflect what this specific impact velocity/duration actually
produces, so neither the VUEL's own trigger nor the ghost's native
ductile criterion ever had a chance to fire, whether or not they'd be
synchronized.

## What I need from you next

This is a calibration gate, not a correctness bug — the plumbing itself
(13 VUEL props, 107 svars, 8+5 `*UEL Property` split, `VU1` type key,
per-element SVAR107, ghost scaling, ghost deletion controls) all parsed
and ran clean at full 48,000-element scale on real Abaqus. What's needed
now:
- Either lower `--vuel-eps-fail`/`--vuel-jac-fail` (both already exposed
  as CLI flags per your own HANDOFF.md) to values that will actually trip
  within this deck's loading, or extend the step's duration/severity so
  the existing thresholds get reached — your call on which is more
  representative of the actual plate-impact use case.
- Whichever you pick, also correspondingly tune the ghost's cloned
  ductile-initiation strain so it's deliberately close to the VUEL's
  trigger (not just inherited unchanged), since that's the actual lever
  for hitting the +-1-increment synchronization target.
- Hand back a new `Flat-vuel-ghost-*` deck once you've got a version
  that you expect to produce an actual failure event within the step, and
  I'll rerun it on ROAR and check the real synchronization timing this
  round.

## Evidence retained

`verification/roar/t_stage6/evidence_20261002/`:
`stage6_flat_vg_55993227.out`, `flat_vuel_ghost.sta`, `flat_vuel_ghost.msg`,
`flat_vuel_ghost.dat`. (`.odb`/`.stdout` were too large to pull — 3.8GB and
143MB respectively — ask if you need something specific out of either and
I'll grep/extract it remotely rather than transferring the whole file.)

Also: going forward, any `sbatch` submissions should use
`#SBATCH --account=rhk12_cr_default` rather than the personal/default
account — already applied to `verification/roar/stage6_flat_vuel_ghost.sbatch`
and `verification/roar/t11.sbatch`.
