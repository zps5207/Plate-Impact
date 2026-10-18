task_id: T-030
role: drafter
status: DONE
files_changed:
  - agents/drafter/outbox/T-030/embmesh/plycohesive.py
  - agents/drafter/outbox/T-030/tests/test_plycohesive.py
  - agents/drafter/outbox/T-030/run_demo.py
  - agents/drafter/outbox/T-030/demo_4ply/source_4ply.inp
  - agents/drafter/outbox/T-030/demo_4ply/output_4ply_cohesive.inp
summary: |
  Built the cohesive ply-interface emitter and step inserter module for the plywise mesher in outbox/T-030/embmesh/plycohesive.py.
  Key capabilities delivered:
  - cohesive_contact_lines: Given interface pairs [(Ply-k_top, Ply-(k+1)_bottom)], emits Abaqus *Contact Pair blocks referencing the specified *Surface Interaction (default 'Cohesion') with mechanical constraint=KINEMATIC.
  - Slave convention inference: In Meshing/stack.inp, the contact pair data line is 'back, front2' where 'back' belongs to Plate-1 (lower ply) and 'front2' belongs to Plate-2 (upper ply). Because Abaqus defines the first surface as slave and second as master, the reference deck implies slave='lower'. Both slave='lower' (default) and slave='upper' are supported.
  - Unique cpset naming: By default (unique_cpset=True), emits distinct cpset names ('cohesion_1', 'cohesion_2', ...) for each pair; supports shared cpset ('cohesion') when unique_cpset=False.
  - insert_cohesive_contact & insert_cohesive_contact_into_deck:
    * Refuses clearly with MesherInputError if the source deck has no *Surface Interaction matching the requested name (does not invent interaction properties).
    * Refuses clearly if the deck has no *Step block.
    * Places contact pairs inside the step under the ** INTERACTIONS comment block and before output requests and general contact, exactly matching Meshing/stack.inp.
    * Idempotent: verifies existing contact pair data lines and will not insert duplicate pairs on rerun.
  - Executed on a 4-ply deck built from Meshing/stack.inp structure with 3 cohesive interfaces; verified with parse_deck.
inserted_text: |
  ** Interaction: cohesion_1
  *Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_1
  Ply-1_top, Ply-2_bottom
  ** Interaction: cohesion_2
  *Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_2
  Ply-2_top, Ply-3_bottom
  ** Interaction: cohesion_3
  *Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_3
  Ply-3_top, Ply-4_bottom
general_contact_findings: |
  Report for subsequent task T-031 on general-contact interaction with plywise meshing:
  1. Surface-based inclusion: In Meshing/stack.inp, Surf-1 is explicitly defined using element faces of instance Plate-1. In an N-ply deck, Plate-1 is split into Ply-1..Ply-N. If Surf-1 is left pointing to Plate-1, Abaqus will throw a fatal error for an unresolved instance set.
  2. Over-inclusive surface: If Surf-1 is updated to include all faces of all plies, self-contact (Surf-1, ) in general contact would attempt penalty enforcement across the ply-to-ply interfaces. Even though *Contact Pair handles cohesive traction and damage separation, having general contact active on the same faces can cause severe constraint conflicts and artificially prevent delamination opening.
  3. All-exterior inclusion: If general contact is changed to *Contact Inclusions, ALL EXTERIOR, Abaqus/Explicit treats each ply instance as a separate body. Because Ply-k and Ply-(k+1) are separate instances, their facing interface surfaces are topologically 'exterior' to each instance and would be picked up by general contact.
  4. Recommendation for T-031:
     - Approach A: Define the plate general-contact surface (Surf-1) to include ONLY the true laminate exterior faces (bottom of Ply-1, top of Ply-N, and side/rim faces of all plies), omitting internal interface faces Ply-k_top and Ply-(k+1)_bottom.
     - Approach B: If ALL EXTERIOR or a broader set is used, explicitly add a *Contact Exclusions block inside *Contact, op=NEW listing every interface pair (Ply-k_top, Ply-(k+1)_bottom).
checks_run:
  - Unit test suite: 7 of 7 tests passed in outbox/T-030/tests/test_plycohesive.py:
    * test_n_plies_gives_n_minus_1_pairs_and_surface_order (slave='lower', slave='upper', unique vs shared cpset, invalid slave error)
    * test_missing_interaction_raises (raises MesherInputError if interaction missing or mismatched)
    * test_missing_step_raises (raises MesherInputError if deck has no *Step)
    * test_insertion_lands_inside_step_before_output_requests (tested both with and without existing ** INTERACTIONS comment)
    * test_idempotent_on_rerun (no duplicates on re-insertion)
    * test_round_trip_through_parser (re-parsed by parse_deck)
    * test_no_invented_surface_interactions (verifies no interactions are added or modified)
  - Combined drafter outbox test suite: 22 passed in 0.86 s (9 for T-027, 6 for T-029, 7 for T-030).
  - Main project regression suite: 72 passed in 1.81 s.
  - Demonstration run on 4-ply deck: outbox/T-030/demo_4ply/output_4ply_cohesive.inp generated and parsed cleanly.
not_verified:
  - Abaqus was not run (neither Abaqus solver nor datacheck was executed).
  - Open question 1 (cpset naming): Whether Abaqus/Explicit strictly requires unique cpset names per pair or allows identical names. By default, unique 'cohesion_<k>' is emitted, which is safer, but Abaqus solver acceptance of identical vs unique cpset names is unknown without solver execution.
  - Open question 2 (shared interaction): Whether Abaqus/Explicit accepts multiple *Contact Pair blocks referencing the same *Surface Interaction without warnings. Standard Abaqus syntax documentation supports sharing, but runtime solver behavior is unknown.
  - T-031 general contact wiring was analyzed and reported, but not implemented (per brief instructions).
suggestions:
  - When the Hub integrates T-030 with T-028 (plywise mesh) and T-029 (ply fibers), wire cohesive insertion after instance generation and before fiber embedding.
concerns:
  - None. Module behaves deterministically and conforms exactly to the reference deck formatting.
denied_actions: none
