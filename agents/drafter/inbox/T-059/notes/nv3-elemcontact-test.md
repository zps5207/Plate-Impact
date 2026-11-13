---
name: nv3-elemcontact-test
description: 2026-11-05 test of eroding element-based ball-plate contact (no plate contact thickness) on the smear VUEL deck; ROAR jobs 57004471/472
metadata:
  node_type: memory
  type: project
  originSessionId: 1e4536e3-103b-4b68-a697-53c4d2734d5a
  modified: 2026-11-10T15:36:28.576Z
---

Why: nv3_smear (last night, job 56995145, 5h37m) still had hosts dying before ball impact (t<=0.97 us); the user's reading is that the 0.2117 mm thickness on EMBMESH_PLATE_NODES (all ply nodes) overcloses the inter-ply cohesive interfaces. Cohesive contact is KEPT (user does not want ties); plate-ball contact moved to an eroding element surface, fibers stay node-based.

Built: new `--plate-contact-surface elements` option (embmesh/plywise_contact.py, plywise.py, cli.py; surface EMBMESH_PLATE_ELEMS = Ply-k.EMBMESH_GHOST_HOST free faces); builder `verification/roar/build_newvals_elemcontact_tt3.py`; deck `Meshing/newvals-elemcontact-tt3/vuel/nv_vuel_elem.inp`. ROAR `ctv/bt3/nv3_elem`: datacheck 57004471 -> solve 57004472 (afterok, 16 tasks, 32 GB, 16 h), run.sh/run_dc.sh copied from nv3_smear (only diffs vs template: module load intel, user=VUEL_material.for).

**How to apply:** when results land, check host deletions at t<=0.97 us (expect ~0, was 28,521 at 0.99 us) and node z-motion pre-impact (was 70-100 um in VUEL, ~0 native). Then extract/pack like nv3_smear (ex_/pk_ jobs). Not yet verified that the overclosure theory (T-055) is right. See [[questions-are-not-tasks]].

**Update 2026-11-05 (later):** nv3_elem datacheck 57004471 passed; solve 57004472 queued. User then chose the long-term contact plan: general penalty contact, self contact over an eroding surface with EXTERIOR + INTERIOR faces of the ghost hosts, nodal erosion=YES, cohesion kept on ply interface pairs, fibers node-based vs ball only (embedded, so kept out of plate contact). User accepts higher compute cost for accuracy. Check deck: `verification/roar/build_newvals_interior_tt3.py` -> `Meshing/newvals-interior-tt3/nv3_int.inp` (2 us step, 0.1 us frames). ROAR `ctv/bt3/nv3_int`: datacheck 57004689 -> solve 57004690 (3 h). Check: datacheck errors on INTERIOR / nodal erosion syntax, hosts dead before 0.97 us, pre-impact node motion, contact energy. VUEL cannot carry contact surfaces; contact lives on the ghosts. Mesher integration waits until this check passes ("then we can plan the rest").

**Results so far (2026-11-05 ~11:10):** nv3_elem (57004472) RUNNING: first VUEL_MATERIAL_FAIL at 1.177 us, i.e. AFTER ball contact (0.97 us); zero pre-impact failures (nv3_smear had 27,293 in increment 1). Confirms plate contact thickness on all ply nodes caused the early deaths. Pace ~23 s/increment (dt 3.8e-8) -> ~16-17 h for 100 us, may hit the 16 h limit; restart written every increment. nv3_int first datacheck failed: `*Contact Controls Assignment, nodal erosion=YES` takes NO data lines (fixed in builder); resubmitted datacheck 57005554 -> solve 57005555. Old failed .dat in nv3_int/dc_fail1/.

**Final (checked 2026-11-06):** both COMPLETED. nv3_elem reached 100 us in 13h23m (no restart needed), odb 119 GB; ETOTAL 469.2 -> 439.0 J (-6.4%), ball KE 409 J at end. nv3_int 2 us in 8m43s, ETOTAL 469.2 -> 468.0 J; ran ~3x faster per us than nv3_elem early on (3:33 vs 10:44 wall at 1.03 us). Deletion counts/MP4 not yet extracted (needs ex_/pk_ jobs, user approval). Pass Duo: agent-env was stale; user pasted SSH_AUTH_SOCK.
**Viewer chain submitted 2026-11-06 (user asked "load that up into the html viewer"):** new `ctv/scripts/ex_nv3_1.sbatch` (single-ODB version of ex_nv3_r: export_odb_viewer_plywise + vp5/ex_vp5.py extract; vars V, TEND, FRAMES). Jobs: ex_nv3_int 57045418 (21 frames, 0-2 us) -> pk_nv3_int 57045419 -> ex_nv3_elem 57045420 (200 frames, 0-100 us, ~2.5 h like smear) -> pk_nv3_elem 57045421, afterany chain. Output `ctv/bt3/<V>/viewer_<V>/` (~2 GB for 100 us); pull it with scp -r, then view locally with agents/drafter/outbox/T-021/serve_viewer.py. MP4s not yet in the chain. Bundle jobs added after: bd_nv3_int 57045498, bd_nv3_elem 57045499. Pull with `verification/roar/post_chain/pull_and_view.sh bt3 nv3_int Meshing/newvals-interior-tt3/results` (and bt3 nv3_elem Meshing/newvals-elemcontact-tt3/results). See [[full-post-chain-rule]].

**Pulled 2026-11-10:** nv3_elem viewer (2.1 GB) + extract/sta/msg/dat pulled to `Meshing/newvals-elemcontact-tt3/results/`; served on localhost:8800. nv3_int (2 us check) still on ROAR only, PULL_READY.

**11:22 status + decision:** nv3_elem at 3.93 us after 46 min, ~23 s/inc (nv3_smear was ~7.6 s/inc) -> likely hits the 16 h limit (02:36 on 2026-11-06) near ~95 us. User decided: let it run, restart (Explicit `recover` from the per-increment restart) only if needed. nv3_int datacheck 57005554 PASSED (INTERIOR + nodal erosion syntax accepted); solve 57005555 pending.
