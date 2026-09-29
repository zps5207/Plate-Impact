# Mailbox protocol
protocol_version: 1

Agents in this project communicate through files, not chat. Each worker has a folder under agents:
  agents/<role>/inbox/    briefs and input files, written by the Hub
  agents/<role>/outbox/   results and deliverables, written by the worker
  agents/<role>/done/     archived briefs and results, moved there by the Hub
Roles are drafter, refiner and critic. The Hub is the Claude Code pane at the project root. Which tool runs each role is set in the app roles.json.

## Brief
The Hub writes agents/<role>/inbox/T-###.md using agents/TEMPLATE.md. IDs are unique across the whole project: use the highest T-### found anywhere under agents plus one. Input files the worker needs are copied by the Hub into agents/<role>/inbox/T-###/.

## Worker steps
1. Find the newest brief in inbox that has no matching T-###-RESULT.md in outbox.
2. Read it fully and do only what it says. You may read the rest of the project for context, but never edit anything outside your own agents/<role>/ folder.
3. Put deliverable files in outbox/T-###/.
4. Write outbox/T-###-RESULT.md as your last action, in the format below.
5. If the brief is unclear or something blocks you, do not guess. Write the RESULT with status BLOCKED and say what is missing.

## Result format
task_id:
role:
status: DONE | DONE_WITH_CONCERNS | BLOCKED | FAILED
files_changed:
summary:
checks_run:
not_verified:
suggestions:
concerns:
denied_actions:

Be honest in not_verified: list everything you did not actually check.

## Hub steps
1. Write the brief and any input files. Tell the human the task ID and which pane to click Check mailbox in. The Hub cannot type into worker panes.
2. When the human says the result is ready, read the RESULT and the deliverables. Do not trust status or summary alone: open the files, diff them against the project, and run checks where you can.
3. Decide: accept, request rework with a new brief that references the previous task ID, or escalate to the human. At most 2 rework rounds per task.
4. Apply accepted deliverables to the project yourself by copying from outbox/T-###/. Workers never write to the project tree.
5. Optionally archive by moving the handled brief, input folder, RESULT and deliverables into agents/<role>/done/.
6. Work serially by default. Give two workers briefs at the same time only if their files do not overlap.

If the project has its own AGENTS.md, CLAUDE.md or delegation docs, follow them. They override this file where they conflict.
