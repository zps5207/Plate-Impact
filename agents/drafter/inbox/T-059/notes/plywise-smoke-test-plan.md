---
name: plywise-smoke-test-plan
description: Plan for the 4-way plywise vs solid 500 m/s smoke test (flat + concave), decisions made, tasks queued
metadata:
  type: project
---

Decided 2026-10-17: two NEW plywise ROAR runs (flat Meshing/Flatv2.inp, concave
Meshing/Flat-concave-roar/concave_hostonly.inp), compared 4-way with the EXISTING solid
runs from reports/CURVED_VS_FLAT_REPORT.html (v500star_100 flat, cc500_100 concave; same
500 m/s, step 1e-4 s, output 7e-8 s, VUEL+ghost host, node ball contact). Plywise must use
the same host: VU1 + ghost (ghost-scale 1e-4, mass ratio 1.0001), fibers embedded in the
ghosts, per-ply SVAR107 fiber-fraction stiffness correction. Plies = 8 (solid had 8 fiber
layers, d=1 mm, gap 0.2 mm). Cohesive: Hazzard 2018 Dyneema preset, ballistic rate,
always overwrite deck cohesive numbers. Damage output not needed (visual/capability check).
Virgin decks are 10-layer -> collapse step (T-036). Tasks: T-033 GUI toggle (Codex),
T-034 cohesive material (agy), T-036 collapse (agy), T-037 plywise VUEL-ghost (Codex),
T-035 GUI material dropdown (not yet written). Abaqus has never read a plywise deck:
ROAR datacheck first. See [[plywise-mesher-design]], [[roar-job-resource-limits]].
User's stack.inp cohesive numbers match Hazzard at ply 0.1375 mm (user confirmed typo).

**Submitted 2026-10-17 ~18:40:** dir /storage/home/zps5207/scratch/ctv/pw/{pw_flat500_100,pw_cc500_100}.
Flat: datacheck 56524336 -> solve 56524337 -> energy 56524338. Concave: datacheck 56524339 -> solve 56524340 -> energy 56524341.
Solves 8 tasks / 32 GB (user preferred 16 GB generally; not asked again). Local decks Meshing/plywise-500/{flat,concave}/output.inp
(built by verification/roar/build_plywise_500.py). Solid baselines to compare: v500star_100 (flat), cc500_100 (concave).
Next: read datacheck .dat for ***ERROR first (never seen by Abaqus before), then export/render + 4-way report.
Ghost params in the solid runs: ghost-scale 1e-4, ghost-ductile-failure-strain 1e-6, vuel-eps-fail 0.113800332690901.

**Results 2026-10-17 (all done):** 4 plywise 500 m/s runs completed. v1 (flat/concave 56524507/56524512) lacked element ball
contact and fiber BCs (flat v1 energy anomaly). v3 (56525373/56525375) = merged T-039/T-040 decks, datacheck clean. Reports:
reports/PLYWISE_VS_SOLID_REPORT.html (4-way: ball speed within ~1%, deleted host 11.7%/12.2% plywise vs 14.8%/27.5% solid,
penetration 3-9 nodes, 0.1-0.4 mm, plywise ~2x deeper) and reports/HOST_FAILURE_ANALYSIS_REPORT.html (VUEL vs ghost).
KEY FINDING: ~344-350 plywise VU1 elements fail in the very first increment (t=6.4 ns), ghosts stay; none in solid runs;
not the Vf>=1 clamp cells; unidentified. Ghost deletions exceed VUEL failures later (concave solid +27%). VUEL state can't be
written to ODB (Element Output unsupported for UEL) -> only job.stdout. Per-element match failed (jElem != export order, npz has
no labels). Abaqus/Explicit rejects surface-based cohesive behavior on *Contact Pair -> cohesive via general contact
(Contact Property Assignment per pair); fixed. Scripts: verification/roar/{build_plywise_500,build_pw_report,build_failure_report,
fiber_orphan_analysis,vuel_vs_ghost_timing}.py. Local results: Meshing/plywise-500/results/.
**Plan for next session (user):** build a one-to-one comparison with Valerie Martin's work to learn whether the early
failure is a property thing or an element thing; user will supply a new deck (different material properties, maybe new
fixture BC). Suggested first steps: VUEL failure message with coords+Vf, 1 us run; labels in viewer export; no-fiber control.
