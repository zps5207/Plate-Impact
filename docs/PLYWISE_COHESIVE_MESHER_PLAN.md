# Ply-wise meshing with cohesive interfaces: plan

Status: plan, revision 4 (2026-10-16). Nothing here is implemented.
Branch context: `vuel-plastic-failure`. Ball vs. plate/fibers contact is the node-based
contact from T-011 (`embmesh/contact.py`), assumed throughout.

Revision 2 incorporates the user's corrections: plies are a pure **translation stack**
(no radial scaling), fibers are **always 0/90**, one fiber layer per ply, **centered**
in the ply's host layer.

## 1. Goal

A second mesher mode, **ply-wise**, alongside the existing monolithic mode:

- Each ply is one layer of C3D8R host elements containing **one unidirectional layer** of
  embedded fibers, centered through the ply thickness.
- Plies alternate fiber direction 0 / 90.
- Adjacent plies are joined by **cohesive surface contact** (traction-separation with
  damage) so delamination can be represented.
- Works for flat plates and **curved plates** (any surface shape whose front and back
  faces are congruent, see 3.1).
- Input is a Flatv2-style `.inp` with **one element through the thickness**; the mesher
  subdivides it into plies.
- Ply count from an explicit count or an approximate ply thickness.

## 2. Stackable plate model

The through-thickness axis is the **stack axis**. The input plate's front and back faces
have the same surface geometry: the back face is the front face translated by a single
vector **s** (the stack vector). Consequently:

- Every ply has the **identical hex mesh** (the input in-plane mesh), translated by `s/N`
  from its neighbor.
- Ply `k`'s top nodes and ply `k+1`'s bottom nodes coincide in position, so interfaces
  are conformal by construction.
- A plate can be extended by more plies without changing the mesh pattern; thickness is
  just `N * |s|/N`.
- This holds for flat plates and for curved plates (a dome, a cylindrical panel, a
  saddle...), because the stack is a translation of the surface, not a radial offset.
  Plies are therefore measured **along the stack axis**, not along the local surface
  normal. On steeply sloped regions the hexes become sheared (see risks).

GUI toggle: **"Stackable plate (front/back faces congruent)"**, on by default. The mesher
validates it: every hex's top node minus its bottom node must equal the same vector `s`
within a tolerance, otherwise it stops with an error that names the offending element.
With the toggle off, ply-wise mode is unavailable (monolithic mode remains).

## 3. Mesh construction

### 3.1 Input convention

One `C3D8R` per in-plane cell, one element through the thickness. The mesher:

1. Finds each hex's thickness axis (`geometry.hex_thickness_axis`) and orients all hexes
   consistently (bottom face to top face).
2. Extracts `s` and verifies congruence (section 2).
3. Resolves the ply count `N` (3.2).
4. Writes `N` copies of the in-plane hex layer, ply `k` offset by `k*s/N`.

**Nodes.** Each ply owns its nodes. Interface nodes are **duplicated** (coincident, one
set per ply) so cohesive contact and delamination act between independent surfaces. Node
numbering is regular: `node(k, i) = base + k*n_layer_nodes + i`.

### 3.2 Ply count / thickness (Abaqus-like)

Mutually exclusive inputs:

- `--ply-count N`: `h = |s| / N`.
- `--ply-thickness h0` (approximate): `N = max(1, round(|s| / h0))`, `h = |s| / N`. The
  report records requested vs. actual `h` and the relative difference.

`h` is the ply thickness along the stack axis.

**Hard floor: `h >= d`** (fiber diameter); `h == d` is allowed (decided), in which case the
fiber surface is tangent to the cohesive interfaces. If the requested `h0` or count
violates the floor, stop with an error that gives the maximum allowed `N` for this plate. Warn if the actual
`h` differs from the requested `h0` by more than ~20%.

### 3.3 Fibers: one layer per ply, centered

- Ply `k` has direction **0 if k is even, 90 if odd** (GUI option swaps which comes
  first). 0 and 90 are the **two global axes other than the stack direction** (e.g. X and
  Y for a Z stack). The stack vector is therefore expected to be (nearly) axis-aligned;
  the mesher snaps to the dominant axis and errors if the stack vector is more than a
  small angle off a global axis.
- Fiber layout in the stack plane (the plane perpendicular to `s`): straight parallel
  lines at pitch `d + gap`, laid out with the existing `_layer_positions` logic and the
  existing end/edge inset.
- Fiber **height**: the centerline lies on the ply's **mid-surface**, i.e. halfway
  between ply bottom and top (`h/2` above the ply's bottom face). This is what "centered
  within the host layer" means; when `h > d`, matrix sits above and below the fiber.
- On a **curved** plate, the fiber follows the mid-surface: it is straight in projection
  along the stack axis, and a polyline in 3D. Its vertices are placed at every crossing of
  the fiber's projected line with an in-plane element edge (so each fiber segment lies
  within one host element's mid-surface), plus optional interior points for long
  elements. Because ply meshes are translations of each other, one polyline per fiber
  line is computed from the base layer and translated per ply.
- Embedding is restricted per ply: each fiber is embedded only in **its own ply's** host
  elset (`*Embedded Element, host elset=PLY_k`). Otherwise Abaqus could embed it into a
  neighboring ply and silently defeat delamination.
- Pitch is measured in the stack plane (projected), not along the curved surface
  (decided: every fiber is a straight line in the stack-plane view, only its height follows
  the surface). Fiber
  length per unit projected length is therefore slightly more than 1 on slopes, and the
  true fiber volume fraction is slightly higher there; the report gives the achieved
  per-ply volume fraction using the actual 3D lengths (`volume.py` machinery).
- Each `Fiber` record gains a `ply` index (it already has `layer`).

Fiber volume fraction per ply is set by `d`, pitch and `h` (about `pi d^2 / (4 p h)` for a
single layer). Note `h > d` lowers it; the GUI readout shows the achieved value so the
user can tune `h` or pitch to hit a target.

### 3.4 Fiber diameter limit on curved plates (derived from deck node spacing)

Setup: stack axis z; ply bottom surface `z = f(x,y)`, top surface `f + h` (a translate);
fiber along x or y on the mid-surface `f + h/2`.

**Derivation.** Let `n` be the surface normal at the fiber location, `n ~ (-fx, -fy, 1)`,
and `theta` the angle between `n` and z, so `cos(theta) = 1/sqrt(1 + fx^2 + fy^2)`.
- The fiber tangent lies in the surface (e.g. `t ~ (1, 0, fx)`), so `t . n = 0`: the fiber
  cross-section circle has full extent `d/2` along `n`. No extra tilt term.
- Two translated surfaces are `h` apart vertically but only `h cos(theta)` apart along `n`
  (first order). The fiber center is midway, so the normal distance to each interface is
  `(h/2) cos(theta)`.
- The fiber stays inside its ply iff `d/2 <= (h/2) cos(theta)`, i.e.

      d <= h * cos(theta) = h / sqrt(1 + fx^2 + fy^2)

  (tangent to the interface at equality). For a flat plate `theta = 0` and this reduces to
  the `h >= d` floor.
- Curvature adds a second-order correction of order `h / (2 R)`; for any plate where
  `R >> h` it is far below the slope term. The mesher applies it as a conservative derating
  using the local radius estimated from neighboring element normals, and reports it
  separately.

**Slope from the deck.** The slope comes straight from node spacing: for each input hex,
use the bilinear front face and evaluate `fx, fy` at its four corners and center (the
gradient of a bilinear patch is extremal at corners). Equivalent edge form:
`tan(theta_edge) = dz / ds` for each in-plane edge, where `dz` is the node z-difference
(along the stack axis) and `ds` the projected in-plane distance. Take the **worst element**.

**Reference values** (`d_max / h = cos(theta)`, computed):

| slope angle theta | 0 | 5 | 10 | 15 | 20 | 25 | 30 | 40 | 45 | 60 |
|---|---|---|---|---|---|---|---|---|---|---|
| d_max / h | 1.000 | 0.996 | 0.985 | 0.966 | 0.940 | 0.906 | 0.866 | 0.766 | 0.707 | 0.500 |

As node-spacing examples: `dz/ds = 0.1, 0.2, 0.364, 0.577` correspond to `d_max/h =
0.995, 0.981, 0.940, 0.866`. A spherical cap of radius R reaches `sin(theta) = r/R` at
distance r from the pole; e.g. R = 100, r = 20, 35, 50 gives 11.5, 20.5, 30.0 degrees.

**What the mesher does with this:**
1. Computes `theta_max` (and the element where it occurs) from the deck.
2. Enforces `d <= h * cos(theta_max)`; equality is allowed. This replaces the flat `h >= d`
   floor in 3.2 for curved plates.
3. Reports the largest allowed diameter `d_max = h cos(theta_max)` and the largest ply count
   `N_max = floor(|s| cos(theta_max) / d)`, so the user can choose `N` or `d` up front.
4. Optionally supports a **local** mode (per-element `d_max`) for plates with a few steep
   regions; the global worst-case limit is the default because one `d` applies to all fibers.

**Other edge cases checked:**
- *Fibers inside host hexes:* because the host surface is piecewise bilinear and the
  mid-surface is exactly `bottom + h/2`, a fiber that is straight in projection and has
  vertices at element-edge crossings lies exactly in the mesh mid-surface (linear in the
  line parameter along each projected line within an element whose projection is a
  parallelogram; a general quad adds a small error, which P0 measures).
- *Tiny fiber segments:* a fiber line passing near an in-plane node line creates a very short
  segment, which shortens the truss dt. Snap crossings closer than a tolerance (default 5%
  of the local element edge, tunable) to the node line. The shortest segment is reported
  and feeds the dt estimate.
- *Hex skew:* element volume is `A_xy * h` regardless of slope, but skew grows like
  `1/cos(theta)`; report the minimum Jacobian ratio (same `theta_max` scan).

The cylindrical and spherical fiber generators (`curved_layup.py`) are **not used** in
ply-wise mode. They remain for monolithic mode.

## 4. Cohesive interfaces: formulation options

### Option A: surface-based cohesive contact (recommended, matches the request)

General contact in Abaqus/Explicit, with a `*Surface Interaction` carrying:

- `*Cohesive Behavior` (K_nn, K_ss, K_tt),
- `*Damage Initiation` (e.g. QUADS/MAXS with t_n0, t_s0, t_t0),
- `*Damage Evolution` (energy-based; G_Ic, G_IIc, mixed-mode via BK or power law),
- hard normal contact and `*Friction`, so delaminated plies still contact and slide.

Pros: natural fit with the contact stack already used for the ball; one property block;
interface surfaces follow directly from the ply stack (each ply's top and bottom faces).
Risks: the Abaqus/Explicit rules for cohesive behavior in **general contact** (initially
bonded surfaces with zero clearance, interaction with contact property assignments) must
be confirmed on real Abaqus; penalty stiffness may reduce the stable time increment.

### Option B: COH3D8 cohesive elements

Zero-thickness cohesive elements between plies (`*Cohesive Section`). The stack makes the
conformal mesh free. Pros: well-trodden, native deletion on failure. Cons: more elements,
small characteristic length may force small dt.

### Recommendation

Implement **A**, keep the interface output behind a small writer abstraction so **B** can
be added later. A ROAR spike (two plies, mode I and mode II) before the rest of the work
decides which one we build.

### Interaction with the rest of the contact stack

- Ball vs. plate and ball vs. fibers: existing node-based contact. The plate and fiber node
  sets now span all plies (unioned across plies).
- Ply vs. ply: cohesive interaction through general contact on per-interface surfaces.
- Fibers are centered in the ply (`h >= d`, so at worst tangent to the interfaces) and
  embedded only in their own ply, so there is no direct fiber-to-neighbor-host coupling.
- **VUEL ghost hosts:** native `*Embedded Element` on a VUEL host is a known blocker
  (BUG-020). v1 supports native `C3D8R` hosts only.

## 5. Where do the cohesive parameters come from?

1. All in the GUI/CLI (self-contained, but duplicates what the Abaqus model could carry).
2. Predefined in the `.inp`, applied by the mesher. The deck holds a
   `*Surface Interaction, name=PLY_COHESIVE` (with cohesive behavior and damage). It is
   not assigned to any surface, since ply surfaces do not exist in the one-element deck.
   The mesher detects it by name, creates the ply-interface surfaces, and assigns it.
3. **Both, with precedence (recommended):** GUI field "Interaction name" (default
   `PLY_COHESIVE`). If it exists in the deck, use it and grey out the property fields;
   otherwise write one from the GUI numbers.

Prerequisite: confirm that `deck.unsupported` lines (which would include
`*Surface Interaction` blocks and their data lines) are preserved in the output.

## 6. User interface

### CLI

```
embmesh ... --layup plywise
    --ply-count N | --ply-thickness H
    [--first-ply-direction 0|90]
    [--cohesive-interaction PLY_COHESIVE]
    [--cohesive-kn K --cohesive-ks K --cohesive-kt K
     --cohesive-tn T --cohesive-ts T --cohesive-tt T
     --cohesive-gic G --cohesive-giic G --cohesive-bk ETA]
    [--cohesive-friction MU]
    [--stackable | --no-stackable]
```

### GUI (`embmesh_desktop.py`)

- Layup mode: Monolithic | Ply-wise.
- Ply-wise: ply spec (count or approx thickness), first ply direction, stackable
  checkbox, cohesive section, friction.
- Live readout: stack vector length (total thickness), `N`, actual `h`, fiber diameter vs.
  `h` check, fibers per ply, achieved per-ply volume fraction, estimated node/element
  counts.

### Outputs

- `report.json`: `N`, requested vs. actual `h`, stack vector, per-ply fiber counts,
  achieved volume fractions, cohesive source (deck vs. GUI), stackable flag.
- Preview: color plies by direction, show interfaces.
- Per-ply `*Elset` names (`PLY_1`...), per-interface `*Surface` names.

## 7. Implementation stages

| Stage | Content | Exit criterion |
|---|---|---|
| P0 | Curved-plate verification (section 8) | Embedding, node contact, and impact work on a curved stacked fixture on ROAR. |
| P1 | Cohesive-contact spike: hand-written 2-ply deck, modes I and II, ROAR | Confirms Option A, or we switch to B. Keywords go in `abaqus-explicit-quirks`. |
| P2 | Stack builder: congruence check, `s` extraction, ply count resolution, node/element duplication, ply elsets | Unit tests: counts, volume conservation, conformal interfaces, flat and curved. |
| P3 | Per-ply fibers: mid-surface polylines, 0/90 alternation, per-ply embedding | Tests: fibers inside own ply, centered, correct direction, volume fraction. |
| P4 | Interface writer (Option A) and deck-vs-GUI interaction resolution | Deck passes Abaqus on ROAR. |
| P5 | Contact integration: ball node contact over all plies; ply self-contact | Flat ply-wise impact run on ROAR. |
| P6 | GUI + CLI + report + preview | Desktop tests pass; docs updated. |
| P7 | Verification impact series: delamination visible; monolithic vs. ply-wise; flat vs. curved | Report like `NODE_CONTACT_SPEED_SERIES_REPORT`. |

P2 and P3 are well-bounded code with unit tests and can be delegated as task files in
`agents/*/inbox/`. P0, P1, P5 and P7 need ROAR judgment.

## 8. P0: verifying curved plates (requested)

Since ply-wise is a translation stack, the question is whether the existing framework
handles **warped hexes with a curved fiber polyline**, not cylindrical fiber families.

1. Script (not shipped) to write Flatv2-style one-element-thick decks whose front surface
   is curved (a cylindrical panel and a dome/bowl) and whose back face is the front
   translated by `s`; a ball above the front face.
2. Hand-lay a single 0 and 90 mid-surface polyline layer into each (a prototype of 3.3)
   and run the existing embedding + node-contact path.
3. Checks: no embedded-element rejections; every fiber node inside its host hex
   (`inverse_hex`); `clip_segment_hex_bounds` accuracy on warped hexes; volume
   accounting sane; contact thickness `auto` sensible on sheared hexes.
4. ROAR smoke impact: runs to the end, ball stopped by plate and fibers, no embedding
   warnings, energy balance sane.

Exit: curved fixtures run on ROAR. If embedding on warped hexes is inaccurate, fix that
before P2/P3.

## 9. Risks

- **Sheared hexes on steep slopes.** Translation stacking keeps hex volume uniform in the
  stack direction but skews hexes where the surface is steep, hurting accuracy and
  dt. Add a Jacobian / skew quality report and a warning past a threshold.
- **Stable time increment.** Thin plies plus interface penalty stiffness reduce dt; measure
  in P1 and extend `_stable_time_increment`.
- **Model size.** Host and interface surfaces grow with `N`; show estimates in the GUI.
- **Post-failure contact quality** depends on the general contact definition; verify no
  interpenetration of delaminated plies.
- **Cohesive properties** for the real material are supplied by the user; GUI defaults are
  placeholders, labeled as such.
- **Fiber polyline chord error** on curved plates is limited by splitting at element edges
  (3.3); verify in P0.
- **VUEL host** unsupported in v1.

## 10. Decisions and remaining questions

Decided:
- Pitch is measured in the projected stack plane.
- Fiber directions are the two global axes other than the stack axis.
- `h == d` is allowed on flat plates; on curved plates `d <= h cos(theta_max)` (3.4).
- Cohesive source: the deck's `*Surface Interaction` takes precedence; GUI values are the
  fallback (section 5, option 3).
- First-ply direction is an arbitrary user choice (GUI option, default 0 first).

Remaining:
1. **Fiber end inset at plate edges:** keep the existing `d/2` behavior?
2. **Cohesive formulation:** I will implement surface-based cohesive contact (A) by default
   and use the P1 spike to confirm it; COH3D8 elements (B) is the fallback only if the spike
   fails.

## 11. P0 results (T-022, 2026-10-16; curved Flatv2, R = 0.25 m, theta_max = 11.47 deg)

Deliverables: `agents/refiner/outbox/T-022/` (one-element deck, stack/fiber generator, checks, REPORT.md).

Passed (N = 3, 6, 10; d just below and just above h*cos(theta_max)):
- 0 fiber vertices and 0 segment midpoints outside their own ply's host hexes; no sampled
  penetration; vertical chord deviation <= 3.4e-4 of d.
- The d <= h*cos(theta) limit predicted every clearance PASS/FAIL, and N_max matched
  (3, 6, 10 fit below the limit, 2, 5, 9 above it).
- Tested on the real irregular C-mesh quarter-disc, so the regular-grid triviality is gone.

Findings that change the mesher design:
1. **The real deck is not an exact translation stack.** Independently confirmed on the
   untouched `Flatv2.inp`: the top- and bottom-face nodes differ in projected XZ by up to
   76 um (mean 4.5 um, 95th percentile 16 um). The mesher therefore needs a congruence
   tolerance (relative to element size) and a policy: take the front face as truth,
   rebuild the back face as a translate, and report the maximum mismatch.
2. **Tiny fiber segments remain after 5% snapping** (3 / 24 / 20 short segments for
   N = 3 / 6 / 10; the shortest was 15 nm). Needs vertex merging (merge to the node
   line, then drop zero-length segments), not just snapping, before this is safe for dt.
3. **Per-host volume fractions above 1** (up to 4.2) come from `fiber_volume_rows`
   charging the full cross-section for every host a centerline touches. The test used
   large d (1 to 3 mm) because few plies were requested, so d was comparable to the
   in-plane cell; the same artifact appeared in earlier flat runs (max 2.27). Re-check
   with a realistic d much smaller than the cell, and prefer the precise
   (cross-section-aware) volume routine.

Not verified: Abaqus acceptance of per-ply embedded elements, any ROAR run. The optional
smoke deck was withheld because of finding 3.
