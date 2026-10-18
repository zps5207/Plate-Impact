# T-031 contact verification

The plywise path defines one assembly node set per contact type by appending the nodes of each instance to the same set name. Abaqus [documents that repeated assembly `*Nset` definitions append nodes](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEMODRefMap/simamod-c-node.htm). The ball interaction selection skips any `*Surface Interaction` containing `*Cohesive Behavior`. Existing general-contact inclusion and property assignment blocks are commented before the ball-only pairs are inserted. The existing cohesive `*Contact Pair` remains untouched.

Abaqus/Explicit [limits general contact to the specified inclusion pairs](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEITNRefMap/simaitn-c-contactgeneral.htm). The emitted plate/ball and optional fiber/ball pairs therefore do not include ply/ply contact. This assumes no later step redefines the general-contact domain and no other active broad inclusion remains. The code comments preexisting inclusion blocks in the first step that it augments. Abaqus input processing and mechanics have not been run.

## Real deck run

Input: `Meshing/plate1hex_curved_hostonly.inp`, augmented in the agent's private verification area with the `Ball` part and `Ball-1` instance from `Meshing/stack.inp`. Command equivalent: `plywise ... --instance Plate-1 --plies 10 --ball-instance Ball-1 --plate-node-contact`. The written deck reparsed with `parse_deck`.

```inp
*Contact, op=NEW
*Contact Inclusions
EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF
*Contact Property Assignment
 ,  , EMBMESH_CONTACT
*Surface Property Assignment, property=THICKNESS
EMBMESH_PLATE_NODES, 0.000499309707734973
```

Report contact section: 10 plate instances, 49,820 plate-node memberships, no fiber instances; ball instance `Ball-1`; interaction `EMBMESH_CONTACT` created as frictionless hard contact because the only source interaction was `Cohesion`; host median edge length 0.0009986194154699463 from all 12 C3D8 edges in part `Plate`; automatic plate contact thickness 0.0004993097077349731, about 0.4993 times the 0.001 ply thickness. The auto thickness is within one ply thickness for this deck. Inclusions contain only `(EMBMESH_PLATE_NODES, EMBMESH_BALL_SURF)`. No old impact-surface references existed in this source deck, so the removed-reference list was empty.

## Checks and Abaqus-only work

`pytest tests agents/refiner/outbox/T-031/tests`: **72 passed** (68 existing, 4 new). Tests cover each ply's node membership, fiber instance stubs, cohesive interaction exclusion, limited inclusions, old-surface removal and warning behavior, and parser roundtrip.

An Abaqus/Explicit data check should confirm keyword acceptance, surface membership, and contact property assignment. A short dynamics run should check ball contact activation, the intended gap/contact force, and that cohesive interfaces alone handle ply separation. Contact thickness and stability remain solver checks.
