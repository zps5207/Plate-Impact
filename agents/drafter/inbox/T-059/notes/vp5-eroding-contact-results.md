---
name: vp5-eroding-contact-results
description: "vp5 (vp4 native rerun with eroding element-based host contact) results, ROAR job IDs, files and report location"
metadata:
  node_type: memory
  type: project
  originSessionId: 16400265-7560-4676-92db-8fdee096136d
  modified: 2026-10-23T21:29:29.644Z
---

vp5 = vp4 native deck with `EMBMESH_PLATE_ELEMS` (eroding element surface) as the ball's host contact + `*Contact Output` for CSDMG. ROAR `ctv/vp5/vals_native_erode`, solve 56651971 (2h23m, OK), extraction 56702825 (`vp5_extract2.json`), viewer export 56702833.

Results (2026-10-23): ALLKE peak +6.8% over 3.55 kJ (vp4 +73%); ETOTAL ends +7.9% (vp4 ended 17% below); hosts deleted 1,351/80,500 (vp4 517); fibers 70/206,930; ball elements 3,161/18,500 deleted; CSDMG: 1,796 points failed, 13,930 past half of 378,267. Ball node-median velocity stays -1000 m/s (barely slowed, unexplained). ODB energy histories are in J (not mJ; corrected 2026-10-27, quarter ball at 1000 m/s = 3.55 kJ).

**Why:** answers whether thick node contact on dead host nodes caused vp4's energy gain; mostly yes, but host deletion went up.
**How to apply:** report `reports/VALS_VP5_ERODING_CONTACT_REPORT.html` (builder `verification/roar/build_vp5_report.py`, renders `render_vp5_views.py`); local data in `Meshing/vals-plywise-erode/results/`. Viewer symmetry camera fixed in `agents/drafter/outbox/T-021/pack_viewer_data.py` (frames plate only, camera outside the cut plane). See [[contact-thickness-energy-finding]].
