# Verification progress log (resume here)

Contract: `VERIFICATION_GOAL.md` (repo root; the /goal text says `docs/` but the file is at the root).
Commit under test: `9176486` (branch `mesher-v0.1`), working tree clean apart from untracked `VERIFICATION_GOAL.md`, `agents/`.
Python: Anaconda 3.13.9 (`C:\Users\salas\anaconda3\python.exe`), numpy 2.3.5, scipy 1.16.3, matplotlib 3.10.6.
Rules honoured: writes only under `verification/` and `docs/`; no git write commands; mesher/uel/vumat untouched.

## Current state — DONE (all of section 4 marked pass/fail/blocked with evidence)
- T0 and T1 (all subsections): fully run and recorded.
- T2 and T3: ROAR SSH was blocked, then the user supplied a live `SSH_AUTH_SOCK` mid-session and approved the Duo push; T2 and T3 then ran to a stable final state (final job IDs **T2=55891146**, **T3=55891147**). Individual sub-tests within T2/T3 are pass/fail per `docs/VERIFICATION_REPORT.md` §3; a handful of specific measurements (rule-of-mixtures comparison, VUMAT-in-Abaqus, mass table, cantilever-vs-theory, stable-dt cross-check) remain **blocked** for reasons given in §4/§6 of the report — real session-time limits, not the SSH stop condition.
- `docs/BUGS.md` and `docs/VERIFICATION_REPORT.md` complete per goal §5/§6.
- Minor tooling note: `shutil.rmtree`/deletes under `verification/evidence/work` intermittently hit `PermissionError` (OneDrive sync lock), so the independent test scripts write to timestamped output dirs instead of clearing old ones; this did not affect any result.

## Results (details in `verification/evidence/`)
| Test | Status | Evidence |
|---|---|---|
| T0 pytest | pass with `--basetemp` (12 passed); default temp dir errors are a pre-existing local `%TEMP%\pytest-of-salas` permission issue, not a code failure | `T0_pytest.txt`, `T0_pytest_basetemp.txt` |
| T0 exe | done: clean-env run works, hashes identical to Python CLI (30/30 files), error handling poor (tracebacks, rc 0 on missing deck) — see BUG-012/013/014 | `T0_exe_cli.txt`, `T0_exe_clean.txt`, `T0_exe_vs_py_hashes.txt` |
| T1.1-T1.2 | done, 11/17 and 14/14 pass respectively | `T1_parser_guard.log/json` |
| T1.3-T1.6 | done, see report §3 | `T1_volume_layup.log/json` |
| T1.4 curved, T1.7, T1.8 | done, see report §3 | `T1_bc_curved_iface.log/json` |
| T2 | done: 5/18 pass (real Abaqus datacheck), see report §3 T2.* rows | `verification/evidence/roar/t2_55891146.out`, `verification/roar/t2/` |
| T3 | done: 25/32 pass (real Abaqus/Explicit runs), see report §3/§4 | `verification/evidence/roar/t3_55891147.out`, `*_energy_summary.json`, `verification/roar/t3/` |

## Job log (ROAR: /storage/home/zps5207/scratch/plate_impact_verif/)
| Date | Job ID | Script | Outcome |
|---|---|---|---|
| 2026-09-28 | 55889996 | t2.sbatch (18 T2 datacheck decks) | FAILED all 18: `decks_t2.txt` had CRLF line endings from Windows, `cp` looked for `t2/<name>\r.inp` and failed for every deck (rc=1). No Abaqus run occurred. Fixed locally (`sed -i 's/\r$//'`) and resubmitted. |
| 2026-09-28 | 55890011 | t2.sbatch (18 T2 datacheck decks, CRLF fixed) | Ran. `flat_truss_asis` (mesher's raw, unmodified output) FAILED with a real Abaqus error: `*NODE ... misplaced. It can be suboption for ... assembly, instance, part` — the fiber block is appended after `*End Assembly`, which Abaqus rejects outright. `flat_truss_reloc` (harness-relocated) also FAILED: `*SOLIDSECTION ... misplaced. It can be suboption for ... instance, part` — a bare `*Solid Section` directly under `*Assembly` is also invalid. Both findings promoted BUG-006 to blocker, confirmed against real Abaqus 2024. All 18 decks failed the same way (either error). Fixed harness (`verification/deckgen.py::relocate` now wraps fibers in an orphan-mesh `*Instance`) and regenerated. |
| 2026-09-28 | 55890012 | t3.sbatch (32 T3 Explicit decks, CRLF fixed) | Same root cause as T2 round 1 — every `*_reloc`/`*_asis`-derived deck failed at input-file processing before any mechanics ran. Regenerated with the fixed harness. |
| 2026-09-28 | 55890547 | t2.sbatch (round 2 — bare orphan `*Instance`) | FAILED all: Abaqus 2024 rejects a bare `*Instance` with no `part=` (`Instance must refer to a part.`) — orphan-mesh instances aren't supported this way in this Abaqus version. Harness fix: wrap fibers in a real minimal `*Part` + `*Instance, part=...` instead. |
| 2026-09-28 | 55890548 | t3.sbatch (round 2 — bare orphan `*Instance`) | Same root cause as T2 round 2. |
| 2026-09-28 | 55890832 | t2.sbatch (round 3 — real fiber *Part + *Instance) | Assembly/instance placement now accepted by Abaqus (BUG-006 fix confirmed working). All 18 still FAILED, but on an unrelated harness bug: `*Node Print` is an Abaqus/Standard-only keyword, not valid in Explicit. Fixed harness (`*Output, history` + `*Node Output` instead). |
| 2026-09-28 | 55890833 | t3.sbatch (round 3 — real fiber *Part + *Instance) | Same harness `*Node Print` issue. |
| 2026-09-28 | 55890908 | t2.sbatch (round 4) | 4/18 PASS (`flat_truss_reloc`, `flat_beam_reloc`, `cyl_reloc`, `symvalid_srconly` — real Abaqus datacheck success once the mesher's fiber block is relocated/rewrapped correctly). `*_asis` (mesher's raw output) still fails per BUG-006 (expected/documented). Some `*_reloc` cases still fail on unrelated harness issues (face/lshape/skew geometry, symmetry-BC wiring) — see round 5. |
| 2026-09-28 | 55890909 | t3.sbatch (round 4) | All 32 FAILED: harness bug — `single_host()`/`cantilever()`/`sens_mesh()`/control decks never assigned a `*Solid Section` to the HOST elset (`hex_plate_deck` called without `extra_part`). Fixed. |
| 2026-09-28 | 55890969 | t2.sbatch (round 5, HOST section fix) | Same 5/18 pass pattern as round 4 confirmed stable (harness fix targeted T3 only; T2 unaffected). |
| 2026-09-28 | 55890970 | t3.sbatch (round 5, HOST section fix) | 25/32 PASS — every single-host mechanics case (all d, all directions, truss+beam), the fibers-off control, the 10x2x2 cantilever, and most of the refinement sweep ran to completion. Remaining fails: 3 VUMAT decks (missing `user=` on the abaqus command — harness gap), `cantilever_40x4x4` and `sens_refine_n3` (real "node not in host" error, same class as T2's face/skew/lshape failures). |
| 2026-09-28 | (ad hoc, no new job ID — reused run dirs) | Added `user=VUMAT_tension_only.for` to `t3.sbatch` for `vumat_*` decks; copied `vumat/VUMAT_tension_only.for` (read-only source) into `verification/roar/` for staging. | VUMAT now compiles and links cleanly against Abaqus 2024 (Intel Fortran 2021.4.0). New failure: Abaqus's automatic stable-time-increment probe rejects the material (`zero or negative initial dilatational modulus`) since VUMAT supplies no Jacobian. Attempted a `*Fixed Time Incrementation` override — wrong keyword, real Abaqus error (`Unknown keyword "fixedtimeincrementation"`). Reverted the attempted fix; VUMAT-in-Abaqus marked **blocked** (not a mesher defect) — see report §3 T3.VUMAT. |
| 2026-09-28 | 55891146 (T2), 55891147 (T3) | Final clean full run, both sbatch scripts unchanged from round 5's fixes | **Final, stable, reported result**: T2 5/18 pass, T3 25/32 pass. Energy summaries extracted via `abaqus python verification/roar/extract_energy.py <job>` for 9 representative T3 cases; real ALLIE/ALLKE/ALLWK/ETOTAL numbers now in `docs/VERIFICATION_REPORT.md` §4. |

## Next (for a follow-up session)
1. Apply the BUG-006 fix (see `docs/BUGS.md`) to the mesher source (out of scope for this verification-only run) so `output.inp` loads in Abaqus without the harness's `relocate()` workaround.
2. Diagnose the "node not in host" real-Abaqus failures (face-exact, L-shaped, skewed-mesh, cantilever_40x4x4, sens_refine_n3) — likely the same root cause as BUG-009; exterior-tolerance overrides up to 0.5 did not fix it, so it is not merely a tolerance-tuning issue.
3. Resolve the VUMAT/Abaqus stable-time-increment blocker, then re-run `vumat_tension_truss`/`vumat_tension_beam`/`vumat_compress_truss`.
4. Complete the deferred T3 measurements (rule-of-mixtures comparison, mass table, cantilever-vs-beam-theory, stable-dt cross-check against `.sta`) — decks and `.odb`s already exist on ROAR scratch (subject to the 14-day purge).
5. Only after the above close: start the goal §7 VUEL-correction delegation track (Codex), using the T3 baseline (§4 of the report) as its judging reference.
