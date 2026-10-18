task_id: T-009
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-009/FINDINGS.md
  - outbox/T-009/audit_deck.py
  - outbox/T-009/audit_output.json
  - outbox/T-009-RESULT.md
summary: Investigated VUEL force and failure logic, documented Abaqus ghost deletion semantics, audited the supplied deck, and analyzed the 58 island histories. Survivors stayed elastic (PEEQ 0) and below the ghost yield stress in sampled frames; no pairing, section, or surface-remap defect was found. The paired VUEL failure state remains unknown.
checks_run: Ran the audit script on flat_v2_output.inp; verified 24,000 complete pairs, zero duplicate/mismatched labels, one ghost section, and 6,216 contact surface elements mapped to ghosts. Ran audit assertions. Summarized all 58 island histories and 538 adjacent dead-ghost histories.
not_verified: Paired VUEL failure flags or exact threshold-crossing times; direct Abaqus 2024 documentation (official 2025 documentation was accessible); a controlled Abaqus 2024 run; which individual fiber segments embed in each island; transient stress peaks between sampled frames.
suggestions: Hub should reconstruct VUEL engineering strain and det(F) at eight Gauss points for every ODB frame for island hosts and deleted controls, then compare to paired ghost PEEQ/STATUS and DUCTCRT if available.
concerns: No code fix is justified until the paired VUEL failure state is established. The existing VUEL and ghost failure measures can disagree.
denied_actions: none
