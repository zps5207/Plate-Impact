task_id: T-031
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-031/embmesh/plywise_contact.py (new)
  - outbox/T-031/embmesh/plywise.py
  - outbox/T-031/embmesh/cli.py
  - outbox/T-031/tests/test_plywise_contact.py (new)
  - outbox/T-031/CONTACT_VERIFICATION.md (new)
  - outbox/T-031/_verification/ (temporary staged package, test output, and real-run files; not intended for project merge)
summary: Plywise ball contact now combines every Ply-k node set and optional FiberInstanceRef node sets; chooses only noncohesive interactions; constrains general contact to ball pairs; comments dangling old impact surfaces and references when contact is on and warns when off; adds CLI flags. Real ten-ply deck with copied Ball part reparsed and yielded only the plate/ball inclusion. See CONTACT_VERIFICATION.md for block and report values.
checks_run: Full staged suite 72 passed (68 existing plus 4 new); real ten-ply output reparsed; official Abaqus documentation checked for repeated assembly Nset append behavior and explicit general-contact inclusion semantics.
not_verified: Abaqus/Explicit input data check; contact dynamics, forces, and cohesive separation; T-029 fiber generator integration because its instances do not yet exist; later-step general-contact redefinitions.
suggestions: Hub should merge only the five listed deliverable files, run an Abaqus data check, and inspect contact output on a short job.
concerns: Temporary _verification directory remains in the outbox. Automatic approval review rejected recursive removal twice. The real reference deck had no dangling Surf-1 lines; synthetic tests exercised removal and warning behavior.
denied_actions: Automatic approval review rejected removal of outbox/T-031/_verification by recursive Remove-Item; reason was policy block, with no further reason supplied.
