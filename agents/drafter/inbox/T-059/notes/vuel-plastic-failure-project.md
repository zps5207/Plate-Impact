---
name: vuel-plastic-failure-project
description: "Ongoing multi-stage project (branch vuel-plastic-failure): extending uel/VUEL_failure.for into a self-contained elastic-plastic hex with homegrown failure (plasticity + engineering-strain trigger + Jacobian trigger + permanent dead state), for the HB26 embedded-element plate-impact method"
metadata:
  node_type: memory
  type: project
  originSessionId: 8c4f2768-6153-4392-b9d2-c9f5008bc3e5
  modified: 2026-10-12T17:11:21.911Z
---

Started 2026-10-01. Goal: extend [[vuel-failure-criterion-finding]]'s
engineering-strain-failure VUEL branch (`uel/VUEL_failure.for`, branch
`vuel-plastic-failure`) into a full self-contained elastic-plastic hex with
homegrown failure, since native Abaqus deletion/SPH conversion is confirmed
impossible for a VUEL. Plan: `docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md`.
Stages, each verified on ROAR + committed before the next:

- **Stage 0 (done):** plan + user-confirmed formulation choice: additive
  Green-Lagrange J2 return mapping (closed-form, linear isotropic
  hardening) directly on the existing (S,E) Lagrangian pair -- NOT a
  multiplicative Fe*Fp model. props(8:10)=SIGY0,HMOD,IPLAST; nsvars
  49->105.
- **Stage 1 (done, commit 8953353):** plasticity verified against analytic
  1-D bilinear bar (tension/compression/unload) to ~6%, permanent set to
  0.24%. Report: `docs/VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.md`.
  Two real Abaqus/tooling bugs found, now in
  `docs/abaqus-explicit-quirks.md`: **`*UEL Property` data lines silently
  truncate beyond 8 values per line** (no error -- this cost the most
  debugging time, looked exactly like disabled plasticity), and a Python
  deck generator's `Path.write_text()` on Windows writes CRLF which
  breaks a bash `for` loop reading the deck list on ROAR (fix:
  `newline=''`).
- **Stage 2 (done, commit 67cbd8f):** engineering-strain failure trigger
  re-verified alongside plasticity, no subroutine code changes needed
  (failure check is structurally independent of plastic state). ROAR job
  55972088: trip at eps=0.0203 (EPS_FAIL=0.02), RF exactly 0 the next
  frame onward. Report:
  `docs/VUEL_PLASTIC_FAILURE_STAGE2_REPORT_2026-10-01.md`.
- **Stage 3 (done, commit 0704157):** Jacobian trigger (props(11)=JAC_FAIL,
  min(det(F)) over 8 GPs, default 0.05) added alongside the engineering-
  strain trigger. ROAR job 55972126: both heavy-compression (u1=-0.97) and
  shear-collapse (combined u1=-0.8/u2=+4.0) decks trip cleanly, RF exactly
  0 after, no NaN. Note: St.Venant-Kirchhoff elastic law shows known
  large-strain pathology (non-monotonic/huge stress, negative .sta total
  energy) at extreme strain before the geometric trigger catches it --
  documented, not a trigger defect, but worth remembering if JAC_FAIL is
  tuned later. Report:
  `docs/VUEL_PLASTIC_FAILURE_STAGE3_REPORT_2026-10-01.md`.
- **Stage 4 (done, commit fc1167e):** found+fixed two real bookkeeping
  bugs: Rayleigh/bulk-viscosity dissipation kept accumulating for a dead
  element (now guarded), dtimeStable never relaxed for a dead element
  (now 1D30 sentinel). ROAR job 55972253: ALLIE drops to exactly 0 and
  ALLVD freezes bit-identical at the trip; a fully-orphaned node (two
  equal segments failing simultaneously) locks to exactly constant
  velocity (textbook free-flight). KEY FINDING: a 3-element chain with
  staggered thresholds does NOT cascade as expected -- once the first
  element dies, the remaining un-anchored structure rings violently
  (undamped, V swings -90 to +150 m/s) instead of redistributing load,
  so elements 2/3 never reach their own thresholds. Strong motivator for
  Stage 5's ramped-degradation option and for using nonzero damping in
  any real multi-element VUEL chain. Report:
  `docs/VUEL_PLASTIC_FAILURE_STAGE4_REPORT_2026-10-01.md`.
- **Stage 5 (done, commit 74fab09):** ramped degradation + compression-only
  residual stiffness for failed elements (props(12)=DEGRADE_TIME,
  props(13)=COMP_RESIDUAL_BULK_FRAC, svars(106)=DAMAGE), implemented
  locally by Codex and verified on ROAR via a 5-case T11 suite
  (instant_chain, ramp_chain, ramp_tension, zero_cycle, residual_cycle).
  ROAR job 55978518 false-refused (exit 64) on a symlink bug in
  `t11.sbatch`'s own scratch-directory safety guard
  (`/storage/home/zps5207/scratch` -> `/scratch/zps5207`; guard compared
  literal `$SLURM_SUBMIT_DIR` against the symlinked prefix only) -- fixed
  by canonicalizing with `readlink -f` before the guard check, same
  restriction otherwise. Resubmitted as job 55978605: COMPLETED, all 5
  cases rc=0, checker rc=0, `pass=true`, all strict_checks true
  (compression-only residual confirmed zero stiffness in tension,
  residual final RF matches analytic prediction to 9e-8 relative error).
  Report: `docs/VUEL_PLASTIC_FAILURE_STAGE5_REPORT_2026-10-01.md`.
- **Stage 6 (in progress, not yet committed):** mesher-integrated ghost
  C3D8R + VUEL + embedded T3D2 fibers, built via the agy(Drafter-role
  review)/Codex(Refiner)/Claude(Hub+ROAR) refinement loop -- see
  "Mesher refinement loop" process note below for the mechanics. Codex
  built `embmesh/vuelghost.py`, CLI `--host-mode vuel-ghost` /
  `--ghost-scale` / `--vuel-eps-fail` / `--vuel-jac-fail` /
  `--vuel-degrade-time`, bumped `uel/VUEL_failure.for` nsvars 106->107
  with `svars(107)=FIBER_VOL_FRAC` read from mesher-computed
  `fiber_volume.csv`. agy independently reviewed (24/24 tests, all 4
  deck-correctness checks pass; noted non-blocking gaps: Johnson-Cook/
  multi-column *Plastic mis-scaling, single-host-material assumption,
  misleading SVAR107 debug print, thin test coverage). Claude applied
  the 5 deliverable files to the live tree, confirmed byte-identical
  regeneration (SHA-256 `ce64e99c...`), ran full Flat.inp-scale
  (24,000 VU1 + 24,000 ghost + 125 fiber) on ROAR: job 55993227,
  COMPLETED cleanly, no NaN/errors, element bookkeeping exact. BUT:
  zero deletion events occurred in either VUEL or ghost -- the baseline
  impact (v=1000, step period 1e-4) engaged the plate (critical element
  briefly shifted BALL-1->PLATE-1 around t=5.08e-5 to 5.25e-5) but never
  reached either failure threshold, both inherited unchanged from the
  host `Matrix` material (EPS_FAIL=5.06, i.e. 506% strain -- too high
  for what this impact actually produces). This is a calibration gate,
  not a correctness bug; sent back to agy/Codex 2026-10-02 to either
  lower eps_fail/jac_fail or extend the step, then re-tune the ghost's
  cloned ductile strain to deliberately sit near the VUEL's trigger, and
  hand back a new deck.
  **Round 2 (job 56011920, FAILED exit 1):** Codex's first recalibration
  set VUEL `EPS_FAIL=0.1138` (physically derived: first-yield engineering
  strain under the VUEL's own St.Venant-Kirchhoff measure,
  `sqrt(1+2*SIGY0/E)-1`) and the ghost's native ductile-initiation strain
  to exactly `0`. Abaqus's `*Damage Initiation, criterion=DUCTILE`
  rejects a literal zero (`***ERROR: THE STRAIN AT FAILURE MUST BE
  GREATER THAN ZERO`) -- input-processor rejection before Step-1 even
  started, not a physics failure. One-line fix needed (positive epsilon).
  **Round 3 (job 56020916, COMPLETED):** Codex fixed it with
  `--ghost-ductile-failure-strain 1e-6` (added CLI validation + a
  regression test rejecting non-positive values). Deck ran clean, but
  revealed the real synchronization problem: the VUEL's own `WRITE(*,*)`
  failure messages (NOT visible in `.sta`/`.msg` -- the VUEL's homegrown
  failure never goes through Abaqus's native element-status reporting,
  consistent with [[vuel-failure-criterion-finding]]) show **398 failure
  events from t=5.01e-05 to t=9.47e-05** -- nearly the whole remaining
  step, not a tight cluster -- while the ghost recorded **zero** native
  deletions anywhere in `.sta`/`.msg`/`.dat`. Checked the ghost's
  material block directly: `*Plastic` table `61.1,0 / 70,2` and
  `*Elastic 508,0.4` preserve the same yield-strain ratio as the VUEL
  (~0.12), so the 1e-4 scaling itself isn't the obvious culprit. Sent
  back to Codex 2026-10-02 with the hypothesis that the ghost's native
  true-stress/log-strain plasticity (under `nlgeom=YES`) may simply never
  reach its own yield point under this loading even though the VUEL's
  independent nonlinear-engineering-strain criterion does -- i.e. the two
  failure measures may not be reconcilable by threshold-tuning alone, and
  need field-output-level checking (PEEQ/STATUS on the ghost) to confirm
  whether the ghost ever plasticizes at all.
  **Round 4 (job 56091072, COMPLETED):** Codex added a field-output
  request (`S, LE, PEEQ, SDEG, STATUS` on all 24,000 ghosts, 1000
  intervals) plus `extract_ghost_diagnostics.py`, an Abaqus-side ODB->CSV
  reducer (needed because the ODB hit 5.2GB -- transferring it whole
  isn't viable). Ran the reducer directly on the ROAR submit node
  (~30+ min for a single-process read of 1001 frames x 24,000 elements;
  first launch attempt was killed by local low-memory pressure, not a
  remote issue -- relaunched via `nohup`/background on the remote side).
  **Result: ghost deletion IS happening** -- 396 ghost elements deleted,
  first at `t=5.0205e-05`, cascading to 396 by `t=9.99e-05`. Compared
  against the VUEL's own 398 `WRITE(*,*)` failure events (first at
  `t=5.0098e-05`, from round 3's stdout): first deaths are ~1.07e-7s
  apart, which is one field-output sampling interval (the true solver
  increment is ~6.6e-9s, ~15,051 increments/step, so this is about as
  tight as this diagnostic's resolution can confirm) -- i.e. the two
  mechanisms are genuinely near-synchronized. Round 3's "zero ghost
  deletions" read was a **false negative**: native Abaqus element
  deletion doesn't get reported as text in `.sta`/`.msg` by default: it
  took this field-output request to actually see it. The round
  2 threshold calibration (VUEL `EPS_FAIL=0.1138` from
  `sqrt(1+2*SIGY0/E)-1`, ghost ductile strain `1e-6`) was correct all
  along. Sent back to Codex 2026-10-05 asking for an Abaqus/CAE
  visualization script (PNG frames over the `t=4.5e-5` to `1.0e-4`
  failure-cascade window, colored by ghost STATUS/PEEQ) since the user
  wants MP4s/images/a final report.
  **Visualization (5 iterations, 2026-10-05/06):** Codex's
  `render_ghost_failure.py` (Abaqus/CAE `noGUI=` script) needed its own
  round of fixes, each caught by running on ROAR rather than guessed:
  wrong kernel/Visualization import order (missing
  `executeOnCaeStartup()` before `import visualization`), an
  `if __name__=="__main__"` guard that never fires under `noGUI=`
  execution (fixed by calling `main()` unconditionally), Abaqus's own
  launcher flags (`-cae -noGUI -tmpdir ...`) leaking into the script's
  own argparse because the `--` separator doesn't survive, and `STATUS`
  requested at `INTEGRATION_POINT` when Abaqus only reports it at
  `WHOLE_ELEMENT`. Key lesson banked: Abaqus/CAE routes `print()` through
  the `.rpy` replay file, not real stdout, and can report shell exit
  code 0 even when `argparse` raised `SystemExit(2)` internally -- an
  authoritative `status.json` (STARTED/FAILED-with-traceback/COMPLETE)
  that the script itself writes is the only reliable success signal for
  these scripts, not stdout or exit code. Final run against
  `flat_vg_r4.odb`: 480 PNGs (240 STATUS + 240 displacement passes,
  1920x1080, 30fps/8s each, `t=4.5e-5` to `1.0e-4`), `status.json`
  confirms `COMPLETE`/`png_count:480`/`status_output_position:
  WHOLE_ELEMENT`. STATUS pass is clean throughout. Displacement pass has
  a known cosmetic issue (sent back to Codex, not blocking): Ball-1
  drops out of frame partway through, likely the frozen first-frame
  camera's clip planes not accounting for the ball's continued motion;
  separately, scattered disconnected line fragments appear after
  failure, which are probably real physics (dead VUEL nodes in
  free-flight, matching Stage 4's known unanchored-node finding) rather
  than a rendering bug.
  MP4s assembled locally (`ffmpeg` via `imageio-ffmpeg`, no system
  ffmpeg installed). Final report published as a Claude Artifact:
  https://claude.ai/artifact/5FhrAAJPbpmAKRzvCqbWtr (private, owner-only).
  **Committed and pushed 2026-10-07** (commit `d20cbd9`, branch
  `vuel-plastic-failure` on GitHub `zps5207/Plate-Impact`). Per the
  user's explicit call, `reports/` (local HTML copies of the stage
  reports, with embedded images/video) and all raw PNG frame sequences +
  rendered MP4s stay **local-only, never pushed** -- only compact text
  evidence (CSV/JSON/sta/msg/out logs) went to git. `docs/VUEL_PLASTIC_
  FAILURE_STAGE6_REPORT_*.md` still not written -- still open.
  **Wireframe-host render attempt: abandoned 2026-10-07, round 3
  (translucent-shaded host) stands as final.** A 4th round (wireframe
  host instead of translucent-shaded, via two simultaneous Abaqus
  session display groups with different render styles) was sent to
  Codex, who hit `AttributeError: 'DGCommonOptions' object has no
  attribute 'setValues'` on real Abaqus 2024. Codex ran out of usage
  before a retry; the same task was handed to agy (Drafter,
  `agents/drafter/inbox/T-003.md`) as a continuation, who added a
  `set_options()` helper that falls back from `.setValues(...)` to plain
  `setattr(...)` when the method doesn't exist -- this ran on ROAR and
  hit a *second*, independent failure: `TypeError: readonly Attribute`.
  Two different mechanisms for mutating a `DisplayGroupInstance`'s
  `odbDisplayOptions.commonOptions` both failed on real Abaqus, strongly
  suggesting that object is read-only post-construction and the whole
  "two simultaneously-styled display groups in one viewport" approach
  isn't viable in Abaqus 2024's scripting API, not just under-researched.
  **Superseded same day.** User then looked at the actual translucent
  render and found it looked bad in practice (solid-looking slab, heavy
  black THICK outline, translucency not visually meaningful at any
  tested value including 0.85) -- confirms Claude's original suspicion
  that Abaqus's shaded-translucency compositing has a visual ceiling
  regardless of parameter value. Rather than another round through
  Codex/agy on the fragile two-display-group API, Claude made a minimal,
  low-risk edit directly to the already-proven single-shared-display-
  group script (same code path that made the working translucent
  version, no new untested API): flipped `viewport.odbDisplay.
  commonOptions`'s `renderStyle` from `SHADED` to `WIREFRAME` globally
  for the fiber pass. Verified via 1-frame smoke test: host renders as
  a clean thin outline (genuinely see-through, not just technically
  translucent), and the previously-sparse red fiber specks resolve into
  a dense, clearly visible T0/T90 grid (the density was always there,
  just hidden behind the shaded host). Trade-off, accepted by the user:
  Ball-1 also loses its solid fill and renders as an outline (global
  wireframe doesn't fill any leaf regardless of per-leaf fillColor
  overrides). Full 240-frame fiber pass re-rendered, pulled, MP4
  reassembled, and this (not the translucent version) is what's now in
  `reports/stage6_assets/`, `reports/presentation/`, the Claude
  Artifact (version 5), and `verification/roar/t_stage6/
  evidence_20261005_r4/frames/fibers/` (local-only, per the
  images/video-not-pushed rule).

**Ghost non-deletion / island bug, found 2026-10-09:** user spotted (by
inspecting the ODB directly, not just the render) that some ghost
elements near the crater never delete while the ball visually passes
through. Confirmed real by Claude (Hub) via ODB `STATUS` field, not a
rendering artifact: banding ghost elements by radial distance from the
impact point (job 56218897's ODB) shows the crater core (r<=0.004m)
deletes 100% cleanly, but the crater rim (r=0.006-0.010m) is patchy, and
**48 elements are true "islands"** -- still-present (STATUS=1) with
>=60% of their nearby neighbors already deleted (e.g. elem 39117: 119/157
neighbors dead, itself never deletes), spanning multiple through-
thickness depths, not one bad ply. Confirmed VU1 and ghost share the
exact same node labels (`vuelghost.py:convert_to_vuel_ghost`, ~line
284-307 -- new ghost element label, SAME node connectivity as the host,
not duplicate/tied nodes), so "decoupled" can't mean literal kinematic
divergence; the desync is in each element's own internal failure state.
Separately (likely unrelated, flagged as a caution not a cause): the
VUEL's `*** VUEL_FAILURE` stdout log has scrambled element labels under
what looks like concurrent/unsynchronized `WRITE(*,*)` calls (found
`elem = 31200` where VU1 labels only go to 24000; 31200 = 7200+24000,
exactly the ghost-label range) -- stdout-based per-element auditing is
unreliable, use ODB fields instead. Also found: no VU1 SDV field output
exists in the deck (only the ghost's native fields are requested), so
VU1's own `svars(49)` failure flag currently cannot be cross-checked
per-element from the ODB -- a real gap for root-causing this.
Diagnostic scripts: `verification/roar/diagnose_central_elements.py`,
`diagnose_central_elements2.py` (radial-band + neighbor-island check).
**Sent to agy as T-007** (`agents/drafter/inbox/T-007.md`,
`agents/drafter/inbox/T-007/` evidence bundle) 2026-10-09 for root-cause
brainstorm -- per [[agent-delegation-preference]], routed to agy since
Codex is usage-constrained. Not yet resolved.

**Follow-up verification run, started 2026-10-09:** per user request,
two changes together on a fresh deck: (1) Ball-1 moved from 0.05m to
exactly 0.01m standoff from the plate (edited a copy,
`Meshing/Flat_t006_close.inp`, NOT the canonical `Meshing/Flat.inp` --
translation and rotation-origin both shifted by the same delta to keep
the rotation pivot correct, verified via `embmesh.parser` that the gap
is exactly 0.01 before submitting); (2) denser fiber packing via
`--gap 0.0002` (was 0.001) in both the ply and within-ply directions
(the mesher's `flat_disc_fibers` already uses one shared `gap` param for
both), producing 328 fiber rows / 13,864 T3D2 elements (up from 125/5250).
ROAR job 56220096, directory `/storage/home/zps5207/scratch/flat_t006b/`.
**Completed 2026-10-09** (47 min, clean, 1532 VU1 failure/degradation
events, final KE 4125J/total 4164J). Island bug re-ran and reproduced:
52 islands this time (vs 48 on run 1) -- same ring pattern, confirms the
bug is robust across both ball-approach and fiber-density changes, not a
fluke. Added as a second dataset to agy's T-007 evidence
(`diagnose_bands_b.json`). Rendered (ROAR job 56222570, 10 min, both
STATUS and wireframe-fiber passes, 240 frames each) -- the island bug is
visible directly in the STATUS render as small protruding un-deleted
stubs at the crater edge, not just in the diagnostic JSON. Report
appended as a second section to the same Claude Artifact (not a new one):
https://claude.ai/artifact/MMQqX2vjefXyQ1PD3ELbgm (version 4).

**T-007 result (agy, 2026-10-09): BRAINSTORM done, hypothesis unverified,
diagnostic patch applied.** agy confirmed (matching Claude's own finding)
that VU1 and ghost share identical node connectivity -- kinematic
decoupling is geometrically impossible -- but their *failure states* have
zero software link: VU1's `svars(KBLOCK,49)` lives in Fortran memory,
ghost's `STATUS` is managed by Abaqus's own solver, and nothing signals
one from the other. agy's hypothesis (unverified, explicitly flagged as
such): a criterion mismatch at the crater rim -- VU1's 1D Green-Lagrange
normal-engineering-strain trigger is insensitive to pure shear but can be
inflated by the quadratic term under shear distortion, while the ghost's
native J2 equivalent-plastic-strain ductile criterion is shear-sensitive
but can lag under C3D8R single-point reduced integration -- so right at
the elastic/plastic transition ring the two criteria can disagree, unlike
deep in the crater core where both are saturated regardless. Correctly
did NOT guess a fix -- proposed only an empirical next step: add VU1 SDV
field output (`SDV49`/`106`/`107`) so VU1's own failure state becomes
directly queryable from the ODB (previously only the unreliable stdout
log existed for this, see the stdout-corruption finding above).
**Claude (Hub) reviewed the diagnostic patch script
(`agents/drafter/outbox/T-007/patch_vuel_sdv_output.py`), confirmed its
string-replacement targets match the live `embmesh/vuelghost.py` exactly,
and applied it** (adds `EMBMESH_VUEL_DIAGNOSTICS` instance elset +
`*Element Output ... SDV49, SDV106, SDV107` field-output request, mirrors
the existing ghost diagnostic pattern). One existing test
(`test_vuelghost.py::test_vuel_ghost_conversion_has_pairs_scaled_material_and_svar107`)
needed updating since it asserted strict text adjacency with `*End Step`
that the new block now sits between -- fixed, 46/46 pytest. Regenerated
the run-2 deck (closer ball + dense fibers, matching the 52-island
dataset) with this SDV output added, submitted as **ROAR job 56225085**,
dir `/storage/home/zps5207/scratch/flat_t007/`. Not yet complete as of
this note -- once done, cross-reference `SDV49` at the 52 known island
element labels (host label = ghost label - 24000, per the ghost=host+24000
mapping confirmed earlier) against their ghost `STATUS` to confirm or
refute agy's hypothesis before any physics/threshold change is
considered, per this project's standing rule.

  **Follow-up same day:** user asked for thinner lines (~1/3) and a
  solid ball. Tested pushing `FIBER_HOST_TRANSLUCENCY` to its true
  maximum (1.0) with `renderStyle=SHADED` restored, hoping a fully
  transparent host fill would coexist with the ball's separate opaque
  leaf color -- confirmed this does NOT work: host still renders
  essentially solid at translucency 1.0, same as 0.65 and 0.85,
  conclusively proving the shaded-translucency ceiling is a hard limit
  of this batch-rendering context, not a tuning problem. Solid ball is
  therefore not achievable without reopening the already-twice-failed
  per-leaf/per-group render-style API (user declined to retry that).
  Edge thickness, however, *was* a simple win: `edgeLineThickness`
  `MEDIUM` -> `THIN` on the wireframe version, confirmed visibly thinner
  on a smoke test, full 240-frame fiber pass re-rendered a second time.
  **This thin-line wireframe version is the final, accepted fiber
  render** (replaces the MEDIUM-thickness one from a few hours earlier
  same day). Updated in all four places again: `reports/stage6_assets/`,
  `reports/presentation/`, Claude Artifact (version 6), and
  `verification/roar/t_stage6/evidence_20261005_r4/frames/fibers/`.
  The fiber render task is closed.
  Also flagged but not yet fixed (separate, smaller task, not started): the displacement/fiber render passes
  never exclude `STATUS=0` (dead) elements from their display group the
  way the STATUS pass's primary-variable contouring does natively, so
  the ball visually "passes through" the plate without a hole ever
  appearing even after real deletions -- root-caused by reading
  `render_ghost_failure.py`, not yet sent as its own task.

- **Stage 7 (started 2026-10-07): VUEL volume-fraction stiffness
  correction.** Separate track from Stages 0-6 (those were entirely
  plasticity/failure; this is the double-counted-stiffness problem
  `docs/VERIFICATION_REPORT.md` section 4 measured: 20-27x too-high
  internal energy at Vf~0.58-0.79 with the plain `*Embedded Element`
  approach). `svars(107)=FIBER_VOL_FRAC` was already plumbed in during
  Stage 6 but confirmed unused (`WRITE(*,*)` debug print only) -- grep
  confirmed before starting this stage.
  Gemini brainstormed the mechanism (new role, first use in this
  project -- `agents/gemini/{inbox,outbox}/`, `agents/roles/gemini.md`,
  task `T-002`): confirmed the existing `*Initial Conditions,
  TYPE=SOLUTION` -> `svars(107)` data path is already the efficient,
  correct mechanism (no CSV file I/O needed inside Fortran, nothing to
  change there); compared on-the-fly vs. `jMassCalc`-cached computation
  (on-the-fly is cheap enough, ~0.05s total across the whole run, no
  new svars slot needed); proved scalar-stress-scaling is mathematically
  equivalent to rebuilding a per-element elasticity matrix for isotropic
  linear elasticity; and surfaced without resolving the key physics risk
  -- scaling elastic stiffness without also scaling SIGY0/HMOD shifts
  the yield strain and would invalidate Stage 1/2 calibration.
  **User decided both open questions 2026-10-07:** correction factor
  `eta = 1 - Vf` (simple rule-of-mixtures, not a more complex
  micromechanics model), and yes, scale `SIGY0`/`HMOD` by the same
  `eta` to preserve the calibrated yield strain.
  Claude then worked out (before handing to Codex) that this can't be a
  late single multiply on the final `STRESS_PK2` -- `CMAT`/`BULK_MODULUS`
  are reused downstream for Rayleigh viscous stress and the post-failure
  residual compression stiffness, both of which would stay uncorrected
  if only the final stress got scaled. Full derivation (confirmed `eta`
  cancels out of the radial-return `DGAMMA` denominator when `AMU` and
  `HMOD` are scaled by the same factor, so `PEEQ`/plastic-strain
  evolution stays numerically identical, only stress magnitude changes)
  is in the task sent to Codex:
  `agents/refiner/inbox/VUEL_VOLUME_FRACTION_CORRECTION_2026-10-07.md`
  -- the fix moves `ALAMBDA`/`AMU`/`BULK_MODULUS`/`CMAT`/`SIGY0`/`HMOD`
  from call-level scalars to per-element (`KBLOCK`-loop) values scaled
  by `eta_k`, not a post-hoc stress multiply.
  **Implemented by Codex 2026-10-07**, diff-reviewed line-by-line against
  the spec (every flagged use site correctly swapped to the `_K`
  per-element version, including the residual-energy term Claude hadn't
  explicitly listed -- Codex caught it independently; `CWAVE`/
  `dtimeStable` correctly left on unscaled, conservative wave speed).
  Deck hashes confirmed consistent (frozen baseline byte-identical to
  live committed file, all 4 Stage7 decks byte-identical to the
  delivered VUEL). **Run on ROAR, job 56159537, 2026-10-07: mixed
  result, not yet accepted.** `vf0` vs. frozen-pre-Stage7 regression is
  an exact no-op (0.0 error) -- the restructuring itself introduces no
  regression. But `Vf=0.5`'s force-half and post-yield-slope-half checks
  genuinely fail (8-9% and 12-20% respectively), and the yield-strain-
  match check's apparent pass is an artifact of a bug in `stage7_check_
  vf.py`'s `rel()` (uses `max(abs(b),1.0)`, which floors the denominator
  to 1.0 for any sub-1.0 quantity like strain, turning it into an
  absolute- not relative-error check) -- real numbers show ~24% yield-
  strain mismatch between `Vf=0` and `Vf=0.5`. Claude's hypothesis, sent
  back to Codex (`agents/refiner/inbox/VUEL_VOLUME_FRACTION_CORRECTION_RESULT_2026-10-07.md`):
  these are `*Dynamic, Explicit`/`SMOOTH STEP`-ramp decks, not quasi-
  static, so differently-stiff elements have different natural periods
  and may be compared at mismatched points in their own dynamic
  transient when sampled by **strain** rather than **time** -- asked
  Codex to either compare at matching time, or add a slow/quasi-static-
  rate deck variant to check if the mismatch shrinks as loading rate
  drops (would confirm a verification-methodology gap, not a Fortran
  defect).
  **Resolved and verified 2026-10-07 (job 56163976).** Codex confirmed
  the checker bug (true `rel()` now in `stage7_vf_metrics.py`, real
  fast-rate yield mismatch was ~24%, not <3%), correctly pointed out
  matching-time wasn't an independent test here (prescribed displacement
  makes time and strain 1:1), and instead added 10x-slower (0.1s ramp)
  tension/compression decks as the actual discriminator. Result: at the
  slow rate, yield-strain error drops to ~7.7e-8, elastic half-force
  error to ~0.00015%, post-yield half-slope error to 0.1-0.3%, all four
  slow checks pass both directions, `Vf=0` regression stays exact.
  Confirms the fast-rate mismatch was a genuine dynamic/inertial-
  transient artifact (differently-stiff elements have different natural
  periods under the same fixed-duration ramp), not a flaw in the
  `eta=1-Vf`/scaled-SIGY0-HMOD formulation or its Fortran implementation.
  **Applied, tested (34/34 pytest), committed, and pushed 2026-10-07**
  (commit `0cc1e8f`, branch `vuel-plastic-failure`). Stage 7 is done.

**Post-Stage-7 follow-on work (2026-10-09), same branch:**
- **T-004 (Codex/Refiner, applied to live tree):** `embmesh/fibers.py`'s
  `flat_disc_fibers` now subdivides each straight fiber row into
  `n = max(1, round(span / target_length))` evenly-spaced segments,
  `target_length = cbrt(median(host element volume))`. Previously one
  T3D2 per row; on the real `Flat.inp` deck this is 5,250 fiber
  elements instead of 125. `writers.py`/`volume.py` needed no changes
  (already generic over N-point polylines, confirmed by concrete test
  not just inspection). 41/41 -> 46/46 pytest.
- **T-005 (agy/Drafter, brainstorm only, not applied as-is) /
  T-006 (Codex/Refiner, applied to live tree, ROAR-verified):**
  alternative to Stage 7's stiffness-scaling: scale the VUEL's own
  **integration volume** (`DVOL_EFF = eta_k * DVOL_GEOM`,
  `eta_k = max(1-Vf, 1e-6)` per element from the existing `svars(107)`
  path) instead of material constants. User's refinement on top of
  agy's draft: **split** the force/energy integration so PK2 stress +
  Stage 5 residual stiffness (physical) use `DVOL_EFF`, while Rayleigh
  viscous + bulk-viscosity stress (numerical stabilization) stay on
  unscaled `DVOL_GEOM` -- preserving Stage 7's original intent that
  those terms track true geometric size. `CHARLEN`/`CWAVE`/
  `dtimeStable` untouched (geometric volume only), unlike Stage 7 which
  could only leave these "conservatively" approximate.
  ROAR job 56218654 (11-case bundle, `verification/roar/t_t006_volcorr/`):
  all 6 checks pass -- `vf0` regression exact 0.0 error; slow-rate
  Vf=0.5 half-force exact 0.0 error; **`dtimeStable` identical at Vf=0
  and Vf=0.5, 0.0 relative error** (the headline win over Stage 7);
  viscous/bulk force stays unscaled to 1.9e-8 relative error (proves
  the split works); mixed-Vf-in-one-block test confirms two elements
  with `Vf=0.3/0.6` in the same `nblock=2` call each get their own
  distinct `eta_k` (reaction ratio matches expected to 6.5e-9). One
  real bug found+fixed by Claude (Hub): the checker's `tagged_rows`
  only read a tag's own line, but Fortran list-directed `WRITE(*,*)`
  wraps long records onto a second physical line -- all underlying
  Abaqus runs had actually succeeded; only the checker's parser needed
  fixing (no resubmission).
  Both applied to the live tree (`uel/VUEL_failure.for`,
  `tests/test_stage7_vf.py`, `tests/test_t006_volume_split.py`,
  `verification/t006_*.py`). 46/46 pytest after both T-004+T-006 applied.
- **Full-scale verification render (2026-10-09), same day:** regenerated
  the real `Flat.inp` deck against the live (T-004+T-006) tree
  (`embmesh.cli visualize Meshing/Flat.inp --host-mode vuel-ghost
  --diameter 0.001 --gap 0.001 --vuel-eps-fail 0.113800332690901
  --ghost-ductile-failure-strain 1e-6`, matching Stage 6's round-3/4
  calibration), ran on ROAR (job 56218897, 54 min, COMPLETED, 807
  failure/degradation events -- about double Stage 6's 396-398, not yet
  investigated further), rendered both the STATUS pass and a
  reconstructed wireframe fiber pass (job 56219348, 4 min, 240 frames
  each) via `verification/roar/render_ghost_failure.py`. That render
  script's `set_fiber_display` had to be reconstructed by Claude
  directly: the live committed copy was still round-3's translucent-
  shaded version; the actual final wireframe-render edits described in
  [[vuel-plastic-failure-project]]'s Stage 6 history were applied live
  during that session and never saved back to any repo file. Rebuilt
  from the documented mechanism (global `commonOptions.renderStyle=
  WIREFRAME`, `edgeLineThickness=THIN`, single shared display group --
  not the two-display-group approach, which is independently confirmed
  broken on real Abaqus 2024 twice over) and verified by actually
  running it on ROAR, not just local contract validation. Report
  published as a Claude Artifact (videos + stills, both passes):
  https://claude.ai/artifact/MMQqX2vjefXyQ1PD3ELbgm (private,
  owner-only). Per the established rule, the 5.6GB ODB and raw PNG
  frames stayed on ROAR/local only, never pushed.

**flat_v2 run + island investigation (2026-10-12):** user built
`Meshing/Flatv2.inp` (element-surface contact pairs Surf-1/Surf-2 instead of
ALL EXTERIOR, ball 1 mm from plate, Mild Steel+JC ball, step 7e-5). Hub fixed
two mesher gaps: `parser.py` crashed on `*Surface, type=ELEMENT` elset-name
lines, and `vuelghost.py` now remaps element-surface elsets from host labels
(VU1, no contact faces) to ghost labels (+24000). ROAR job 56286114 COMPLETED
(34 min, 0 errors, dir `scratch/flat_v2/`). Core r<=4mm 100% deleted, but 58
island ghosts survive (48/52 in earlier runs), mid-thickness, r 8-10mm.
**Key finding: all 85 alive near-axis ghosts have PEEQ exactly 0 -- they never
yielded**, so the ghost J2 criterion could not fire. VU1 SDV49/106/107 field
output is ACCEPTED but writes NOTHING for a user element (confirmed via ODB
field list), so VU1's per-element failure flag is unreadable. Report artifact:
https://claude.ai/artifact/PovbVkVhMgkoFMTWDBLPW4. User insists elements that
should delete are still alive; delegated two independent investigations:
T-008 (agy, physics angle, `agents/drafter/inbox/T-008.md`) and T-009 (Codex,
code/Abaqus-semantics angle, `agents/refiner/inbox/T-009.md`), each with its
own evidence bundle; Hub extracting `island_history_v2.json` (ROAR) to add to
both. Uncommitted: T-004, T-006, T-007 patch, parser+remap fixes.

Rules the user set: work on this branch only, never touch production
`uel/VUEL.for`; commit after each verified stage with real numbers (no
claiming pass without evidence); ask before any choice that changes
physics/thresholds/interface (props/svars layout); don't guess Abaqus
semantics -- test on ROAR. See [[roar-ssh-access]] for cluster access,
[[abaqus-explicit-quirks]] for the accumulating list of confirmed
real-Abaqus behaviors found along the way.

**Process change (2026-10-01, from Stage 5 onward):** the user wants code
editing and generation for subsequent stages handed to agy and Codex, to
conserve this session's usage. This session (Claude) keeps orchestration:
ROAR SSH/Duo connection handling, job submission/monitoring, evidence
retrieval, and reporting/memory upkeep -- i.e. "maintaining the plot" of
the project across agents.

**Mesher refinement loop / multi-agent protocol (discovered 2026-10-02):**
this project already has a formal file-based multi-agent protocol, not
just the ad hoc Codex handoffs used for Stage 5. See `agents/PROTOCOL.md`,
`agents/TEMPLATE.md`, and `agents/roles/*.md`. Roles: **Hub** (planner/
gatekeeper, the Claude Code pane at the project root -- i.e. this
session), **Drafter** (fast first draft; **agy**, runs in Antigravity),
**Refiner** (correctness-focused improvement of the Drafter's work;
**Codex**), **Critic** (review-only, never edits; runs in Grok Build --
not yet used by name in this project). Each role has
`agents/<role>/inbox/` (briefs, written by the Hub) and
`agents/<role>/outbox/` (deliverables/RESULT.md, written by the worker).
Briefs should be `T-###.md` per `agents/TEMPLATE.md` (ID = highest
existing T-### anywhere under `agents/` + 1 -- none existed before
T-001). Only the Hub applies accepted deliverables to the live project
tree; workers write only inside their own `agents/<role>/` folder. In
practice Codex has been flexible about picking up non-`T-###`-named
briefs dropped directly in his inbox (e.g. the Stage 5 and Stage 6
free-form `.md` task files), but agy expects the formal brief in his own
`agents/drafter/inbox/` -- dropping a brief only in
`agents/refiner/inbox/` means agy never sees it. For Stage 6, Codex ran
ahead and produced a full draft+refine pass solo before any Drafter brief
existed; Claude (Hub) then used agy for an after-the-fact independent
review/test pass (T-001) rather than a competing draft, to avoid the two
colliding on the same files -- a reasonable adaptation of the protocol
when one worker gets there first, not the normal order.
Applying a worker's outbox deliverable to the live tree needs explicit
user approval each time (the harness's own permission classifier blocks
it as "Modify Shared Resources" otherwise, which lines up with the
protocol's own Hub-review-before-apply rule).

Also note: by Stage 5, other in-repo agent dirs (`agents/critic/`,
`agents/drafter/`, `agents/roles/`) and several ROAR_SSH.md copies had
already appeared from parallel agent activity outside this session's own
edits -- these turned out to be exactly this pre-existing protocol
infrastructure, not random clutter.
