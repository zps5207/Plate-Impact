---
name: node-contact-project
description: "Plate-impact node-contact work (Oct 2026): T-011 delivered+verified+pushed; 5-speed series done on ROAR; full renders submitted 2026-10-14, report pending"
metadata:
  node_type: memory
  type: project
  modified: 2026-10-15T02:46:21.083Z
  originSessionId: abfc1576-3377-4c6f-8da0-300c0b363b1f
---

State as of 2026-10-14 (end of session). Branch `vuel-plastic-failure`, commit fbeb3cc pushed (T-011 + all earlier work). Since then UNCOMMITTED: `verification/roar/render_ghost_failure.py` (new passes/views), `render_variant.sbatch`, `summarize_nc.py`, `build_nc_report.py`, `reports/NODE_CONTACT_SPEED_SERIES_REPORT.html`, `verification/roar/t_nc/` (post-proc data), `Flat-nodecontact/` (excluded via .git/info/exclude, with *.exe, *.pkg, lfs-storage).

**Done:** T-011 (Codex) copied into project, 56 tests pass, flags-off output byte-identical, 3 decks (plate/fibers/both) regenerated identical to Codex's and passed Abaqus datacheck (jobs 56386652-4). Speed series 100-500 m/s (plate-only node contact, thickness auto 0.489 mm) ran to completion (jobs 56386750-4, `ctv/nc/vNNN/`). Post-processing (jobs 56406472-6) pulled to `verification/roar/t_nc/vNNN/full`; summary: ball speed at 70 us 97/187/279/372/465 m/s, KE lost 3.3/8.4/8.8/8.6/8.7%, ghosts deleted 313/882/1151/1446/1684, islands 8/33/0/0/0. Ball passes through the plate at all speeds (flagged to user as something for them to judge). Fiber node surface only datachecked, never solved.

**Renderer changes (user request):** no state/frame text, no triad/title; views iso + side (flat-on close-up of the y=0 symmetry plane, parallel projection, plate on the right, window extended one ball radius below plate); two renderings: `status` (solid) and `wire` (grey thin hex edges, blue fibers, nodeSymbols=OFF). Tested on v300 (frames_test..test4); the last tweak (window extension) was NOT test-rendered.

**Pending (user said they'd remind me tomorrow):** full renders submitted 2026-10-14: jobs 56407411-56407415 (r100..r500), 240 PNGs each in `ctv/nc/vNNN/frames/{status,wire}/{iso,side}/`. TODO: check they finished, pull key frames into `reports/nc_series_img/` as vNNN_{status,wire}_{iso,side}.png, rerun `python verification/roar/build_nc_report.py`, show the user, then commit/push if asked. Watchers were cancelled (computer off).

**ROAR access:** agent was restarted this session (`ssh-agent -s > ~/.ssh/agent-env; source ~/.ssh/agent-env; ssh-add` by the user, passphrase needed each new session); I `source ~/.ssh/agent-env` in each Bash call. A Duo push per ssh; "Permission denied (keyboard-interactive)" = push not approved. Don't redirect stdin (`</dev/null`) when piping tar over ssh. See [[roar-ssh-access]].

Other open items: thickness-sweep report never written; high-speed (2000-3000 m/s) element-vs-node surface comparison; fiber-node solver run (needs user decision); T-011 multi-step decks not handled (contact added to first step only).
