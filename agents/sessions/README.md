# Sessions
sessions-readme-version: 1

AI Terminal records every pane session here, automatically.

  agents/sessions/<id>/session.json    who ran, when, git state before and after, files touched, outcome
  agents/sessions/<id>/transcript.log  terminal output with colors stripped; local only, never committed
  agents/sessions/packages/P-*.md      one file per packaging run: what was committed, what was left out and why

The Hub (Claude Code) can read all of this. Commands, run from the project root:

  node agents/sessions/sessions.mjs status                 what is pending, running, uncommitted, unpushed
  node agents/sessions/sessions.mjs list                   every recorded session and its state
  node agents/sessions/sessions.mjs tail <id> [lines]      end of a pane's transcript
  node agents/sessions/sessions.mjs ship --dry-run         show what packaging would commit, change nothing
  node agents/sessions/sessions.mjs ship [--sessions S-1,S-2] [--all] [--push]

ship writes a package log, stages the files the chosen sessions left uncommitted, commits, and with --push pushes.
It never force-pushes, skips files that look like credentials, and aborts if unrelated files are already staged.
Sessions that could not be committed (still running, not selected, files skipped, commit failed) are recorded
with the reason in their session.json and in the package log.

Files are attributed to sessions by time window and content, so panes working at the same moment may list the same file.
