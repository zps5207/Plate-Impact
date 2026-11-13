---
name: vals-vp4-results-and-fiber-briefs
description: "vp4 deletion rerun finished 2026-10-20 (all 4 jobs OK), report built, viewer served; user sees fibers deleting hosts / acting too massive; briefs T-045 (codex) and T-046 (agy) written"
metadata:
  node_type: memory
  type: project
  originSessionId: 82d95981-f45e-432c-8266-b41e0784b62b
  modified: 2026-10-21T14:09:32.685Z
---

vp4 jobs 56580052-055 all COMPLETED (exit 0; VUEL solve 3h53, native 1h56). Post-processing jobs 56589885-888 done. Local data: `Meshing/vals-plywise-del/results/{vuel,native}/` (npz, energy csv, .sta/.msg) and packed viewer folders `viewer_vuel`, `viewer_native`. Report: `reports/VALS_PLYWISE_DELETION_RERUN_REPORT.html` (builder `verification/roar/build_vals_del_report.py`, uncommitted).

Results: ALLKE peaks 5.8 J (VUEL) / 6.1 J (native) vs 3.5 J ball (was 366 / 56 J in vp3), still not conserved; ball keeps about 963/968 m/s with under 1% host deleted (unexplained, vp3 was 742/669); VUEL and native now agree closely. Fiber/ball deletion state is not in the export.

User observation from the movies: fibers delete their hosts when pulling instead of snapping back, and act far more massive than they should. Deck fiber props match Vals.inp (981 kg/m3, E 135 GPa, yield 3.5 GPa, d 0.632 mm area 3.137e-7 m2), so suspect the stiffness/strength mismatch vs the 0.7 GPa, 70 MPa matrix, native mass double-counting (about 1.39x), and unknown VUEL mass handling.

**Why:** briefs delegated so the user can clear chat: T-045 (`agents/refiner/inbox`, codex, data analysis) and T-046 (`agents/drafter/inbox`, agy, mechanism). Results land in `agents/*/outbox/T-045` and `T-046`. Viewer servers were started in the background on ports 8800/8801.
**How to apply:** next session, read the two RESULT files first; see [[vals-plywise-deletion-rerun]], [[roar-ssh-access]].
