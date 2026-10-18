task_id: T-033
role: refiner
status: DONE
files_changed:
  - outbox/T-033/embmesh_desktop.py
  - outbox/T-033/embmesh/cli.py
  - outbox/T-033/embmesh.spec
  - outbox/T-033/tests/test_gui_plywise.py
  - outbox/T-033/sample-run/output.inp
  - outbox/T-033/sample-run/report.json
  - outbox/T-033/sample-run/preview.html
summary: |
  Added a Plywise laminate checkbox and form for ply count or thickness, optional
  layup with symmetric/repeat expansion, fiber properties, thickness axis,
  cohesion, and ball contact. The plywise command builder and interaction parser
  are pure functions. The CLI now writes report.json and, with --preview,
  preview.html beside output.inp. The embmesh spec includes the dynamically
  imported plywise modules.
  In plywise mode the existing precise-volume checkbox is disabled because the
  plywise CLI has no --precise-volume flag. The existing desktop form has no
  curved-mode/axis/center, host-mode/VUEL-ghost, element-set, symmetry, or
  node/element-offset controls to disable; none of their CLI flags is sent on
  the plywise path. The shared fiber diameter/gap/type and thickness-axis
  controls remain applicable. The existing ball-contact controls remain active.
checks_run: |
  Python syntax compilation passed. Full staged suite: 105 passed (including
  12 new GUI/command tests). The generated command ran on
  Meshing/plate1hex_curved_ball.inp and wrote output.inp, report.json, and
  preview.html; report has four plies, resulting thickness 0.0025, and no
  warnings. Tk smoke test instantiated the window, captured the unchanged
  non-plywise argument list, and toggled the plywise frame.
not_verified: |
  No visual screenshot or manual interaction with the real desktop window.
  No PyInstaller build. No Abaqus execution or physics validation.
suggestions: []
concerns: []
denied_actions: []
