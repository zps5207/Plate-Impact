# Interactive ODB viewer: plan

Written 16 Oct 2026. Status: **paused, plan only.** Nothing below the "Done so far" section has been built.

## Goal

An HTML page you can open online (a private Artifact link) and rotate, zoom and pan **while the impact animation plays**, like looking at an ODB in Abaqus Viewer. It replaces the fixed-camera MP4s as the best way to show the wireframe case.

Scope decisions from the user:
- **Extraction stays on ROAR.** The ODB is read there (needs Abaqus), and the result is brought back. This PC has no Abaqus, so "extract locally" is out of scope.
- **The deliverable is the online viewer.** Packaging it into the mesher app is a later, optional step for a possible release.
- **Test bed: the 500 m/s case** (`ctv/nc/v500/v500.odb`). Other speeds follow once v500 works.

## Done so far

| Item | State |
|---|---|
| `verification/roar/export_odb_viewer.py` + `export_viewer.sbatch` | Ran on ROAR for **v300** (job 56481180, 1 min 18 s, 16 GB). Output `ctv/nc/v300/v300_viewer.npz`, 55 MB, 150 frames. Not yet run for v500. |
| `embmesh/viewer_assets/` | Pinned three.js r147 UMD files (three, OrbitControls, LineSegments2, LineSegmentsGeometry, LineMaterial) for an offline single-file viewer. |
| `v300_viewer.npz` contents | host 24,000 `C3D8R` on 27,401 nodes; ball 2,992 `C3D8R` + 320 `C3D6R` on 3,642 nodes; fibers 13,864 `T3D2` on 14,192 nodes. Per-frame deformed positions for all three, plus host STATUS (1 = alive). |
| Not checked | That the STATUS array really shows deletions (no warning in the log, but the file was never opened). |

## Pipeline

```
ROAR:   v500.odb --export_odb_viewer.py--> v500_viewer.npz   (positions per frame, STATUS, connectivity)
local:  v500_viewer.npz --packager (numpy)--> viewer bundle    (face/edge tables, int16 delta data, gzip)
online: viewer.html + data file --> Artifact (private link)
```

## Viewer features (user's list)

1. Play, pause, scrub slider, step frame, speed, loop. Time label in microseconds.
2. Orbit, pan and zoom with the mouse at any time, including during playback. Camera presets: isometric, symmetry-plane (plate vertical, ball left to right), reset.
3. **Host render mode:** wireframe, solid, or hidden. Wireframe shows exterior edges only, updated as elements are deleted (same rule as the Abaqus renders).
4. **Fibers only:** host hidden, fibers (and optionally the ball) shown.
5. **Independent colors:** host, fiber, ball and background.
6. **Independent line thickness:** host, fiber and ball wireframe widths in pixels (needs the fat-line material, not plain WebGL lines, which are always 1 px).
7. Defaults match the renders: grey host `#8C8C8C`, blue fibers `#0033CC`, dark ball `#606060`, white background.
8. Nice to have: host opacity in solid mode, edges overlay on solid.

## Data format (the contract between packager and viewer)

The Hub fixes this so the viewer and packager can be built in parallel.

- **Roles:** `host`, `ball`, `fiber`. Each has its own node list (`n` nodes) and element lists by type.
- **Positions:** per role, `frames x n x 3`, quantized to uint16 over that role's bounding box across all frames, then delta-coded along time (wraps modulo 65536), split into low/high byte planes, then gzip. The viewer decodes with `DecompressionStream('gzip')` and a running sum.
- **Host STATUS:** `frames x elements` uint8, XOR-coded against the previous frame, then gzip. 1 = alive.
- **Topology (built by the packager, not by Abaqus):** for solid roles, the unique faces with owner element and neighbor element (`-1` if none), faces as 4 node indices (triangles repeat the last node). A face is drawn when its owner is alive and its neighbor is missing or dead. Fibers (`T3D2`) are plain edges.
- **Header JSON:** roles, node and element counts, frame times, bounding boxes, the plate thickness axis (camera up), the default colors.
- **Size target: at most 15 MB for the data file** (the Artifact limit is 16 MB per file). If v500 comes out larger: fewer frames, a shorter window (for example 0 to 40 us, since impact is early), or coarser quantization.

## Task split

I stay the Hub: I write briefs, review results, run ROAR, publish, and commit. Workers write only inside their own `agents/<role>/` folder, per `agents/PROTOCOL.md`. IDs continue from T-011.

| Task | Worker | What | Files (no overlap) |
|---|---|---|---|
| Hub-0 | Hub | Run the export for **v500** on ROAR (16 GB), download the `.npz`, open it and confirm STATUS shows deletions and the ball moves | `verification/roar/` |
| T-012 | agy (Drafter) | First complete viewer: single `viewer_template.html` using the inlined three.js files, all features above, loads the data per the contract. Tested against a small synthetic bundle until the real one exists. | `agents/drafter/outbox/T-012/` |
| T-013 | Codex (Refiner) | Packager `odbviewer.py`: `.npz` to bundle per the contract, with unit tests (round-trip of the quantization and delta coding, face-ownership logic on a 2-element mesh, size report). | `agents/refiner/outbox/T-013/` |
| T-014 | Codex or agy | Review pass: Codex reviews T-012 for correctness (decoding matches the contract, deletion logic, memory use per frame); agy reviews T-013. Cross-review so each tool checks the other's work. | outbox of the reviewer |
| Hub-1 | Hub | Integrate T-012 + T-013 on the real v500 bundle, check size, view it in a browser, publish as a private Artifact | `reports/` |
| Later | agy/Codex | Optional: ship the packager and viewer in the mesher app release (a "View results" step that takes the ROAR export). | `embmesh/`, `embmesh_desktop.py` |

Work serially where files overlap; T-012 and T-013 can run at the same time because their files do not overlap.

**Why split this way:** this will use a lot of credits. Drafting the long single-file viewer goes to agy (fast, coverage first), and the numeric packager with tests goes to Codex (correctness first). The Hub keeps ROAR access, review and publishing so workers never touch the cluster.

## Acceptance for the v500 test bed

- Opens in a browser from the Artifact link with no install and no network beyond the page itself.
- Plays 0 to 70 us; orbiting does not stop playback.
- The ball visibly moves through the plate and deleted host elements disappear.
- Host wireframe/solid/hidden, fibers only, colors and line widths all work and are independent.
- Looks like the Abaqus wireframe renders at the default settings.
- Data file under 15 MB, or a stated reason and fallback.
- Honest not-verified list: browsers other than the one tried, the GPU cost on a laptop, and anything not opened by the Hub.

## Open questions and risks

- **Artifact limits:** 16 MB per file and 16 MB for the page, so the data must be a separate file under 15 MB or be reduced. The three.js files are about 650 KB and go inline in the page.
- **Fat lines on thousands of segments** may be slow when the host wireframe has many exposed edges after failure; if so, cap edges or fall back to 1 px lines.
- **STATUS at the right output position:** the Abaqus render script resolves a STATUS output position; the extractor takes the minimum over all blocks. Confirm this matches the renders (deleted count at 70 us for v500 should match `ghost_deleted` in `verification/roar/t_nc/summary.json`).
- **Node-coincident ghost host:** the host drawn is the ghost element set only; the VU1 elements are not drawn, same as the renders.
- **Sharing:** an Artifact is private by default. Sharing the link with others is your decision.
- **Credits:** run T-012 and T-013 once each; allow at most 2 rework rounds per task, per the protocol.
