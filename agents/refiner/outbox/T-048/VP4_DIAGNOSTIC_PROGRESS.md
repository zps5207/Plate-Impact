# vp4 diagnosis in progress (22 October 2026)

## Direct local evidence

- In both executed vp4 `.sta` files, Abaqus reports **128 secondary nodes pinched between tied surfaces** and roughly **388,000 initial node-face overclosures**. About 387,858 remain unresolved and are stored as offsets. The maximum reported initial overclosure is **0.55139 mm** at a Ply-19/Ply-20 interface. Abaqus also warns that some general-contact nodes penetrate tracked faces by more than half a typical element dimension. These warnings warrant a contact-initialization audit; they do not alone prove the cause of early host deletion.
- A direct check of the generated native deck's element face pairs and instance translations found **zero reference-coordinate mismatch** between opposing ply-interface nodes across 16,100 face-node pair checks. All assigned top/bottom facets lie on the corresponding z plane. The Abaqus overclosure warning therefore does not reflect a simple ply translation error; it may arise from the contact surface/offset formulation or perimeter topology and needs the warned-node locations and contact fields to resolve.
- Existing T-045 exports show first host deaths at 1.75 µs native and 2.10 µs VUEL. For all deaths through 8 µs, I measured the nearest ball node in the **preceding** viewer frame using `ball_proximity.py`. A ball node lay within one host-element size for **55/56 native** and **53/53 VUEL** early deaths. T-045's previously hot-fiber criterion held for **0/56 native** and **2/53 VUEL** early deaths. Thus the early failures are spatially associated with the advancing ball, while this particular fiber-motion indicator is almost absent. Node proximity is geometric association, not a measured contact force.
- Across the full 70 µs, the same ball-node proximity screen is positive for **321/517 native** and **350/612 VUEL** host deaths. Ball positions in the viewer also include any deleted ball-node geometry, so late-time proximity should be interpreted cautiously.
- The existing energy CSVs report `ETOTAL` falling from **3.546 J** to **2.949 J native** and **2.589 J VUEL**. `ALLKE` simultaneously peaks at **6.128 J native** and **5.789 J VUEL**. The CSVs include only `ALLKE`, `ALLIE`, `ALLWK`, `ALLVD`, and `ETOTAL`; they cannot allocate the discrepancy among contact penalty, constraint, damage, artificial, and other terms. Per Abaqus's documented energy balance, ETOTAL should remain approximately constant for a sound analysis. This is a material energy-accounting problem, but saying that the extra ALLKE is caused by fiber mass or deleted-node mass is unsupported.
- The five small T-046 ODB tests remain as recorded in `RECONCILE.md`: tests 2–4 delete only their protruding free fiber segment; no host/ghost or embedded fiber deletes. They do not reproduce vp4 host failure.

## Next read-only check

`vp4_odb_probe.py` is prepared for the two existing ROAR ODBs (38 GB native, 43 GB VUEL). It writes all early STATUS, S, LE, PEEQ and available damage fields in an impact ROI through 10 µs; full fiber STATUS at the same 200 ODB frames used in the current viewer exports; ODB field/history inventories; and Abaqus-generated contact-warning node-set samples. The paired `vp4_probe.sbatch` uses one CPU, 16 GB, an 8-hour limit, and writes only to `ctv/t048/`. Both current files were uploaded. A per-submission approval request is pending under the ROAR rules.

## Decision after extraction

1. Match first host STATUS=0 events with prior host stress/damage, live adjacent fiber stress/STATUS, and ball state. Check whether the warned contact nodes intersect the early-failure region.
2. Quantify how many >4.6%-stretched viewer segments are STATUS=0 and whether live fibers carry the extreme geometry. Use this to correct the viewer or constitutive model only after identifying the state.
3. If contact initialization is implicated, prepare a minimal contact-geometry variant that removes the specific pinch/overclosure mechanism and rerun a small impact patch before a full vp4 solve. If live fiber stress precedes host damage, design an interface/load-transfer variant instead.

No model parameters or production decks have been changed yet. The current evidence supports a targeted contact/early-event diagnostic before selecting a constitutive fix.

## Viewer correction prepared

The current `verification/roar/odb_viewer.py` draws the complete fiber connectivity at every frame. Its exporter stores host STATUS but discards fiber STATUS, so deleted fibers could appear to keep stretching in the video. Replacement copies of `odb_viewer.py` and `export_odb_viewer.py` are in this outbox. The viewer accepts `--fiber-status STATUS.NPZ` from the read-only probe and filters line cells for STATUS=0; the exporter includes fiber STATUS in future NPZ files when Abaqus provides it. Both retain a deleted state if Abaqus omits that element at later frames. A synthetic two-frame masking test passed. Existing native and VUEL exports both have 200 viewer frames, 206,930 fiber segments, and frame indices exactly matching the probe's sampling schedule. The probe sidecar still needs to be retrieved and checked for a STATUS field, count, and times before using it for the full vp4 result.

The corrected `vp4_odb_probe.py` was uploaded to `ctv/t048/` on ROAR. The sbatch submission remains subject to the project's explicit per-job approval rule.

## Inbox handoff at 11:49 local, 22 October

`inbox/T-048-NOTE-from-claude.md` reports completion of the earlier five small T-046 ODB extractions and corrects my test-5 mass reading. I independently checked its `RF1/A1` result in `inbox/T-048-odb/t046_sol5.json` and updated `RECONCILE.md`. That handoff does **not** include `native_vp4_*`, `vuel_vp4_*`, or a `t048_vp4_probe` Slurm log. It does not establish that the new vp4 probe was submitted or completed.
