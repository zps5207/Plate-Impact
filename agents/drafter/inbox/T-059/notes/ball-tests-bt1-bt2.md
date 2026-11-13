---
name: ball-tests-bt1-bt2
description: "Ball-failure test suites bt1 (done, report built) and bt2 (6 jobs submitted 2026-10-26, pending): job IDs, paths, what to do when they finish"
metadata:
  node_type: memory
  type: project
  originSessionId: 52891edc-1e4b-4eb7-899f-1f6a89e6198b
  modified: 2026-10-27T01:14:29.269Z
---

State as of 2026-10-26 ~21:15, written before the user restarted the terminal for a new Claude Code version. Background monitors die with the session; re-arm if needed.

**bt1 (DONE, 1000 m/s, 12 us, vp5 ball, 8-16 tasks):** b1_beamsurf, b2_newball, b3_both, b4_d4fix, b5_steelA, b6_316L in ROAR `/scratch/zps5207/ctv/bt1/<deck>/`. All six extracted (viewer npz + `<deck>_extract.json` via `ex_vp5.py`, `export_viewer_plywise.sbatch` with TEND=1.2e-5) and copied to `Meshing/vals-plywise-balltests/results/`, packed as `viewer_<deck>/`. Report: `reports/VALS_BT1_BALL_TESTS_REPORT.html` (builder `verification/roar/build_bt1_report.py`, renders `render_bt1_views.py`). Viewer server: `python agents/drafter/outbox/T-021/serve_viewer.py Meshing/vals-plywise-balltests/results --port 8800`, open `/viewer.html?data=/data/viewer_<deck>` (server may be dead after restart).
Findings: energy fine in all; ball erodes steadily from ~1.5-1.9 us (80-90 elem/us) in every variant; ball hex Jacobian inversion 2.0% (b4 best) to 2.6% at 12 us (user's read: elements invert and blow up before deleting); beam fibers (b1,b3) delete more fibers earlier; b2 new ball mesh is ~3x faster (dt 2.6e-8). b0_base was never run (vp5 is the baseline).

**bt2 (SUBMITTED, pending at 21:13):** decks in `Meshing/vals-plywise-balltests2/`, builder `verification/roar/ball_tests/build_ball_tests2.py [out_dir] [speed]`. ROAR `/scratch/zps5207/ctv/bt2/<deck>/`, submitted via run.sh with `--nodes=1 --ntasks-per-node=8 --mem=32G`.
- 1000 m/s: 56809399 c1_beam_d4 (beam+D4=+0.002), 56809400 c2_truss_d4_md80 (truss+D4+max degradation 0.8), 56809401 c3_beam_d4_md80
- 500 m/s: 56809430 c1_beam_d4_v500, 56809431 c2_truss_d4_md80_v500, 56809432 c3_beam_d4_md80_v500 (still 12 us step, so earlier-stage penetration; 24 us offered, not built)
- b4_d4fix is the truss+D4+maxdeg1 reference.

**Why:** user wants to know if beam fibers + D4 are more stable, and whether lowering max degradation to 0.8 helps. Max degradation only affects the Matrix (energy evolution); ball steel and Fiber damage evolution displacement = 0 (abrupt fail), so it will NOT change ball inversion. User knows this was flagged. Beam fibers will need a new VUMAT to act like fibers (user's statement).

**How to apply:** first check state with `sacct -j 56809399,56809400,56809401,56809430,56809431,56809432`. When done: run extraction (same recipe as bt1: viewer export + ex_vp5.py per deck, one `sbatch` each, TEND=1.2e-5), scp, pack, serve, add to a bt2 report (copy build_bt1_report.py; include inversion-fraction metric). ROAR SSH: `source ~/.ssh/agent-env`, then `ssh roar ...`, user approves a Duo push; if it says Permission denied (keyboard-interactive) the push was not approved, ask again. See [[roar-ssh-access]], [[roar-run-sh-template]], [[results-viewer-project]].

Lessons this session: first guess (CRLF) for the 6-second b1-b4 failures was wrong; real cause was stale `.lck` files from earlier attempts, check the `slurm-*.out` before theorizing. Python `write_text` on Windows writes CRLF (fixed with newline="\n" in build_ball_tests.py, harmless).
