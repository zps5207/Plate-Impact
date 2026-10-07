# Stage 6 renderer round 3: entry-point fix worked, argument parsing doesn't

Date: 2026-10-05
To: Codex
Re: `STAGE6_RENDER_RESULT2_2026-10-05/HANDOFF.md` (entry-point fix)

## Good news: the probe actually passed

Important correction to my own last report: Abaqus/CAE's `noGUI=` kernel
doesn't route Python `print()` to plain stdout -- it goes through the
`.rpy` replay-file mechanism instead. I was only checking captured
stdout, which is why I incorrectly thought nothing ran. Checking
`abaqus.rpy` after the probe run shows:

```
#: visualization module: <kernel built-in>
#: display-group module: <kernel built-in>
#: display-group constructors: LeafFromElementSets, LeafFromPartInstance
#: VISUALIZATION_IMPORT_PROBE: PASS
```

So your entry-point fix (unconditional `main()`) worked correctly. Both
the bootstrap-import fix and the entry-point fix are confirmed good.

## New problem: argument parsing

Ran the renderer the same way:

```
abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
  --output-dir Flat-vuel-ghost-r4/frames
```

Exit code 0, zero PNGs produced. `abaqus.rpy` shows the actual failure:

```
#: usage: ABQcaeK [-h] [--output-dir OUTPUT_DIR] [--step STEP]
#:                [--start-time START_TIME] [--end-time END_TIME]
#:                [--frame-count FRAME_COUNT] [--fps FPS] [--passes PASSES]
#:                [--view VIEW] [--image-width IMAGE_WIDTH]
#:                [--image-height IMAGE_HEIGHT]
#:                [--deformation-scale DEFORMATION_SCALE]
#:                odb
#: ABQcaeK: error: unrecognized arguments: -cae -noGUI -tmpdir /tmp -lmlog ON flat_vg_r4.odb
#* Exit code: 0
#* File "render_ghost_failure.py", line 376, in <module>
#*     main()
#* File "render_ghost_failure.py", line 251, in main
#*     args = parse_arguments()
#* File "render_ghost_failure.py", line 78, in parse_arguments
#*     return parser.parse_args(script_arguments())
```

Whatever `script_arguments()` does to pull the post-`--` args, it's
returning Abaqus's *own* launcher flags (`-cae -noGUI -tmpdir /tmp -lmlog
ON`) concatenated with the real argument (`flat_vg_r4.odb`), rather than
just `flat_vg_r4.odb --output-dir Flat-vuel-ghost-r4/frames`. The real
`--output-dir` flag I passed isn't even in the error message, which
suggests `script_arguments()` isn't finding the actual `--` boundary at
all and is grabbing something upstream of it.

I don't have visibility into `script_arguments()`'s implementation from
here (checking only -- is this your own helper, or an Abaqus-provided
one?) -- can you check what it's actually reading from (`sys.argv`,
`os.environ`, an Abaqus-specific API) on this specific Abaqus 2024
install, since apparently it's not cleanly stripped the way the Abaqus
docs usually describe for `cae noGUI=script.py -- args`?

Note Abaqus's exit-code-0-on-argparse-failure behavior is itself
notable: a `SystemExit(2)` from argparse inside the CAE kernel apparently
gets swallowed into "Exit code: 0" in the .rpy rather than propagating as
a nonzero process exit -- worth keeping in mind for how you detect
failure going forward, since checking exit codes alone won't catch this
class of bug; `abaqus.rpy` seems to be the actual source of truth for
what happened.

## Evidence

`render2.log` (just the license banner) and `abaqus.rpy` (the actual
traceback) are on ROAR at
`/storage/home/zps5207/scratch/vuel_stage6_flat_vg_r4_20261005_01/`. Let
me know if you want me to pull/paste more of either.
