# T-011 implementation report

Status: `DONE_WITH_CONCERNS` only because Abaqus/Explicit and the live desktop GUI were unavailable locally. The requested implementation and generated decks are complete.

## Changes

- `embmesh/contact.py` (new)
  - `add_ball_node_contact`: validates the ball instance, writes complete assembly-level ball/plate/fiber sets and surfaces, creates or reuses an interaction, and creates or extends the first step's single `*Contact` block.
  - `median_host_edge_length`: median of all 12 edge lengths for every selected eight-node host element.
  - `median_fiber_segment_length`: median of every generated fiber segment.
  - `resolve_contact_thickness`: validates explicit values and implements `auto`.
  - Existing user surfaces and contact data are retained. An existing `*Contact Inclusions` receives the generated pairs; no second `*Contact` is emitted.
- `embmesh/generate.py`
  - Added `plate_node_contact`, `fiber_node_contact`, `ball_instance`, and `contact_thickness` API parameters.
  - Applies contact only after fiber and optional VU1+ghost deck generation, and records complete contact metadata in `report.json`.
- `embmesh/cli.py`
  - Added `--plate-node-contact`, `--fiber-node-contact`, `--ball-instance`, and `--contact-thickness` to `visualize`.
  - Normal output reports surface names, node counts, resolved thicknesses, and whether the interaction was reused or created.
- `embmesh_desktop.py`
  - Added a Ball contact group with independent Plate/Fibers checkboxes, instance dropdown, and `auto`/numeric thickness field.
  - Contact controls stay disabled until either checkbox is selected; a selected contact requires a ball instance.
- `tests/test_contact.py`, `tests/test_contact_cli.py`
  - Cover defaults/byte-identical disabled behavior, plate/fibers/both, contact-free and existing-contact decks, one-contact preservation, all-node counts, missing ball, zero/auto/explicit thickness, and CLI parsing.

## Behavior by case

- Both flags off: the contact function returns before reading or writing the generated deck; existing deck output and report behavior remain unchanged.
- Plate only: `EMBMESH_PLATE_ALL_NODES` contains every node in the host part, not merely nodes of surviving/selected elements. Its node surface is paired with `EMBMESH_BALL_SURF`. VU1 and ghost elements share these nodes, so deletion of ghosts does not remove the node surface.
- Fibers only: `EMBMESH_FIBER_ALL_NODES` contains every generated fiber node and its surface is paired with the ball.
- Both: both independent inclusion pairs and thickness assignments are written.
- No input contact/interaction: creates one `*Contact, op=NEW`, inclusions, default property assignment, and `EMBMESH_CONTACT` with friction `0.0` and HARD pressure-overclosure.
- Existing contact/interaction: preserves user lines, reuses the first named `*Surface Interaction`, adds pairs to the existing inclusions, and places thickness assignments directly after the contact-property data. The Flatv2 runs reused `General` (friction 0.01/HARD).
- Missing/empty ball selection: clear `ValueError` including available instance names.
- Numeric thickness `0`: no `*Surface Property Assignment` is written.

## Automatic thickness

- Plate: `0.5 * median(all 12 edge lengths of every selected eight-node host element)`.
- Fibers: `0.5 * min(host median edge length, generated-fiber median segment length)`.

The fiber rule is deliberately conservative: it never gives the unvalidated fiber node surface a larger envelope than either the host spacing or its own node spacing. One explicit non-negative number overrides both surfaces.

For Flatv2, the host median is `0.0009779841615185445`, giving plate thickness `0.0004889920807592723`. The median fiber segment is `0.0009428123964848826`, giving fiber thickness `0.0004714061982424413`.

## Generated decks

- `flat_nodecontact/output.inp`: requested VU1+ghost plate-only CLI case; 27,401 plate nodes, 3,312 ball elements, one contact.
- `fibers_only/output.inp`: VU1+ghost fibers-only case; 14,192 fiber nodes, one contact.
- `both/output.inp`: VU1+ghost combined case; 27,401 plate plus 14,192 fiber nodes, one contact.
- `reference_sweep/thk010/output.inp`: generated with the supplied `make_thickness_sweep.py` for comparison.

The generated contact sections match the supplied sweep structure: node-to-ball inclusion, default interaction property, then thickness inside the existing contact block. Expected intentional differences are mesher-owned names and `auto` thickness (`0.000488992...`) versus the reference's explicit 1 mm (`0.001`).

Each generated case also includes `report.json`, `fiber_volume.csv`, and VTK visualization artifacts.

## Checks

- New focused tests: `10 passed`.
- Existing repository tests against staged source overlay: `46 passed`.
- `py_compile` passed for all four staged Python source files.
- Full Flatv2 CLI generation completed for plate-only, fibers-only, and both variants (328 fibers, 24,000 hosts each).
- Structural scan of generated decks:
  - plate-only: one `*Contact`, one node surface, one thickness assignment.
  - fibers-only: one `*Contact`, one node surface, one thickness assignment.
  - both: one `*Contact`, two node surfaces, two thickness assignments.
- Parsed generated set counts agree with reports: 27,401 plate nodes and 14,192 fiber nodes.
- Confirmed thickness keywords immediately follow the existing contact-property assignment and precede output-request comments.

## Verification boundary and concerns

- The keyword shape is verified against the Abaqus-2024-passing form and sweep builder supplied in the brief. It was not independently datachecked here because workers cannot run Abaqus/ROAR.
- Element-set-based free-surface resolution for `EMBMESH_BALL_SURF`, one `*Contact` per Explicit step, and placement of `*Surface Property Assignment` are treated as verified by the supplied sweep evidence, not by a local solver run.
- Fiber node contact remains solver-untested as stated in the brief. Its auto rule is isolated in `resolve_contact_thickness` for easy adjustment.
- The GUI was syntax-checked and its command wiring was inspected, but it was not exercised interactively with the packaged executable.
- The implementation targets the first analysis step, matching Flatv2 and the requested workflow. A future multi-step deck needing activation in a later step would require an explicit step-selection option.
- No project-tree files were edited and no commit was made. Existing dirty changes, including `VUEL_failure.for`, were not touched.
