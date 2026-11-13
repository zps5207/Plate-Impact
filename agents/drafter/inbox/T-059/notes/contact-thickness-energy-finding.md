---
name: contact-thickness-energy-finding
description: "Coupon tests (2026-10-22): vp4's 0.635 mm node-contact thickness on host nodes creates energy and spurious host deletions; an eroding element-based host surface fixes it. Applies to vp4/Vals decks."
metadata:
  type: project
---

Small 6-ply impact coupon (verification/roar/delam/, make_coupon.py, ROAR ctv/delam/, 500 m/s block, fixed cohesive card). Energy never conserved with vp4-style node contact on every host node (thickness 0.635 mm): KE rose 61->89 J, total energy fell 61->53.6 J, 709/1536 hosts deleted.
- Ball starting 1 mm higher (no initial overlap) did NOT fix it (xgap).
- Contact thickness 0.1 mm conserved energy (60.4 J) and cut deletions to 280 (xthin).
- Host as eroding element-based surface (HOST_SURF, fibers still node-based 0.618 mm) conserved energy (60.65 J), 275 hosts and 40 fibers deleted (xerode). This is the user's preferred fix: floating nodes of deleted elements leave the contact.
- xkeep (host never deleted, max degradation 0.99) failed after 25 s of wall time; cause not diagnosed.
- Also: native Abaqus keeps nodal mass of deleted elements (test 5, RF/A = m/8 for the cube); PRESELECT field output does not include CSDMG (needs explicit *Contact Output).

**Why:** explains the energy gain (3.5 -> 5.8 J) and likely many spurious host deaths in vp4; the vp4 deck uses EMBMESH_PLATE_NODES with 0.635 mm thickness.
**How to apply:** next vp4/Vals rerun should use an element-based eroding host contact surface (and add *Contact Output CSDMG,CSMAXSCRT,CSTRESS,CDISP); needs a mesher change (build_vals_plywise.py / plywise_contact.py). Ask the user before submitting. Related: [[vals-vp4-results-and-fiber-briefs]], [[fiber-segment-cohesive-idea]].
