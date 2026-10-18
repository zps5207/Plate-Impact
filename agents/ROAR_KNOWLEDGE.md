# ROAR (Penn State HPC): connection and job-submission knowledge

Collected from the Plate Impact project (embedded-fiber VUEL work), last verified 13 Oct 2026. Written so it can be dropped into another project or an app (for example the AI terminal) as standing instructions. Items marked **[verified]** were seen working in this project; **[recalled]** are standard cluster or Abaqus behaviour I did not re-test here.

---

## 1. Who and where

| Item | Value |
|---|---|
| Cluster | Penn State ROAR (ICDS), login host `submit.hpc.psu.edu` |
| User | `zps5207` |
| SSH alias | `roar` (in `~/.ssh/config`: `HostName submit.hpc.psu.edu`, `User zps5207`, `IdentityFile ~/.ssh/id_ed25519`) |
| Slurm account | `rhk12_cr_default` (put `#SBATCH --account=rhk12_cr_default` in every script) |
| Work directory | `/storage/home/zps5207/scratch` (symlink to `/scratch/zps5207`) |
| Modules used | `module load anaconda/2023.09`, `module load abaqus`, `module load intel` |
| Abaqus | 2024 (Explicit used; `abaqus python` is Python 3.10 with numpy) |
| Platform of the local machine | Windows 11, Git Bash (the Claude Bash tool) |

Rules the user set (relayed from their CLAUDE.md):
- ssh and sbatch against ROAR are allowed, **but every cluster submission needs the user's explicit approval each time** (a general "please run it" for a named piece of work counts for that work; ask again for new work).
- Never ask for or store the SSH key passphrase.
- Sbatch scripts must run under `/storage/home/zps5207/scratch` (see the guard in section 5).

---

## 2. Connecting from the Claude Bash tool [verified]

ROAR requires key authentication **plus a Duo/Microsoft MFA push** on every new SSH connection. Fully unattended access is impossible: the user approves a silent push on their phone. There is no ControlMaster reuse (Windows OpenSSH), so each `ssh`/`scp` call is a new connection and a new push.

### One-time per session

1. The user opens a Git Bash window with the agent unlocked and runs, **at the local prompt (not inside `ssh roar`)**:
   ```bash
   eval "$(ssh-agent -s)"; ssh-add ~/.ssh/id_ed25519      # enter passphrase
   echo $SSH_AUTH_SOCK
   ```
   and pastes the printed path, for example `/c/Users/salas/.ssh/agent/s.ATzq1vYbXP.agent.s3WHyaClQb`. The path changes with every agent.
2. Claude uses it in each Bash call (shell state does not persist between calls):
   ```bash
   export SSH_AUTH_SOCK='<pasted path>'
   ssh -o ConnectTimeout=60 roar '<remote command>'
   ```
3. Check the agent is alive with `ssh-add -l` (it lists the key; "Could not open a connection" means the socket is stale).

### Pitfalls seen

| Symptom | Cause / fix |
|---|---|
| `Permission denied (keyboard-interactive)` | Duo push missed or declined. Just retry and tell the user a push is coming. Do **not** use `-o BatchMode=yes`: it disables the MFA prompt and always reports this error. |
| Stale socket (`Could not open a connection to your authentication agent`) | The agent died or the path changed. Ask the user for a new `echo $SSH_AUTH_SOCK`. The `!` prompt shell does not run `.bashrc`, so it will not restart the agent. |
| "control-master" / "connection reset" | Stale `~/.ssh/sockets`: `rm -rf ~/.ssh/sockets`. |
| Banner text mixed into output | ROAR prints a long login banner (and a post-quantum key-exchange warning). It is on stdout. **When streaming binary data (tar) through ssh, put nothing else in the remote command**, or the archive is corrupted ("This does not look like a tar archive"). Redirect `2>/dev/null` and filter text output with `grep -v` on banner lines. |
| One push per call | Batch work into one ssh call (upload, submit, and a status check together) to minimise pushes. |

---

## 3. Moving files [verified]

Prefer **one ssh connection with tar piped through it** (one Duo push for any number of files):

```bash
# upload
tar cf - file1.py file2.sbatch dir/ | ssh roar 'cd /storage/home/zps5207/scratch/myjob && tar xf -'

# download (nothing else may be printed by the remote command)
cd local/target && ssh roar 'cd /storage/home/zps5207/scratch/myjob && tar cf - results/' 2>/dev/null | tar xf -
```

Notes:
- `scp` also works but costs another push per call.
- Large ODBs (about 6 GB) should stay on ROAR; download only extracted JSON/CSV.
- On Windows, a path given to a native Python through a heredoc is **not** translated from `/c/...` to `C:\...`; use Windows-style or relative paths inside Python, or pass the path as a shell argument.
- Avoid apostrophes inside bash heredocs sent through the Bash tool; they have broken command parsing. Use the file Write tool for scripts instead.

---

## 4. Waiting for jobs without spamming pushes [verified]

- A foreground `sleep N` chained to a command is blocked by the Claude harness. Use the **Monitor** tool with a single long-lived ssh connection that polls on the remote side:
  ```bash
  ssh -o ConnectTimeout=60 -o ServerAliveInterval=30 roar '
    prev=""
    for i in $(seq 1 56); do
      q=$(squeue -u zps5207 -h -o "%j:%T" | sort | tr "\n" " ")
      [ "$q" != "$prev" ] && echo "$(date +%H:%M) $q"
      prev="$q"
      [ -z "$q" ] && { echo ALLDONE; break; }
      sleep 540
    done' 2>&1 | grep --line-buffered "^[0-9][0-9]:\|ALLDONE"
  ```
- **Use `grep --line-buffered`.** Without it the output is held until the pipe closes, and a monitor that expires first delivers nothing.
- Monitor caps at 30 minutes (`timeout_ms` 1800000); re-arm for longer waits (each re-arm is a new connection).
- Emit only changes and terminal states, not every poll.
- Per-job progress for Abaqus/Explicit: `tail -n 4 job.sta | head -n 2` gives the last increment line (column 2 is step time).

---

## 5. Submitting jobs [verified]

### Sbatch template (Abaqus job with a user subroutine)

```bash
#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=myjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=48G
#SBATCH --time=06:00:00
#SBATCH --output=run_%x_%j.out

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $real_submit_dir)"; exit 64 ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"

abaqus job=$SLURM_JOB_NAME input=output.inp user=VUEL_failure.for interactive > job.stdout 2>&1
rc=$?
echo "abaqus rc=$rc"; echo "done $(date)"
exit $rc
```

Key points:
- The **guard** uses `readlink -f` because `~/scratch` is a symlink to `/scratch/zps5207`.
- Use `abaqus ... interactive` inside the batch script so the script waits for the solver. The Fortran user subroutine (`user=`) is compiled by the intel module on the node.
- Submit from the job's own directory: `cd /storage/home/zps5207/scratch/<job> && sbatch script.sbatch`. Pass variables with `sbatch --job-name=NAME --export=ALL,VAR=value script.sbatch`.
- Dependent jobs: `sbatch --dependency=afterany:<jobid> ...` (afterany runs the analysis even if the solver hits its time limit and leaves a partial ODB).
- Slurm prints `sbatch: slurm_job_submit: No account features found and no partition specified. Using cluster default.` This is normal.
- Typical sizes: a 24,000-element explicit job (1000 frames) ran about 33 minutes on 1 CPU, 48 GB. The ODB was 6 GB.
- **Datacheck first** for deck changes: `MODE=datacheck` runs `abaqus ... datacheck interactive` (about a minute). Abaqus reports unknown parameters and misplaced keywords as `***ERROR` in `<job>.dat`. It caught two wrong keywords from a recipe in this project.

### Status commands

```bash
squeue -u zps5207 -h -o "%i %j %T %M"        # my jobs
sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS
scancel <jobid>                              # cancel (ask the user first)
```

---

## 6. Reading Abaqus results on ROAR

- ODB reads use `abaqus python script.py job.odb` (Python 3.10, numpy available). Run them as batch jobs (4 CPU, 96 GB handled a 6 GB ODB) rather than on the login node.
- **Use `fieldOutput.bulkDataBlocks`** (numpy arrays: `b.nodeLabels`, `b.elementLabels`, `b.data`, `b.instance.name`) instead of iterating `.values`. A full 1001-frame read of 24,000 elements took about 4 minutes, versus 20 to 30 minutes with `.values`.
- Reading `.values` of a large field is very slow; run long extractions with `nohup`/sbatch.
- `float32` values are not JSON serializable: use `json.dumps(..., default=float)`.
- `STATUS` is stored at `WHOLE_ELEMENT`.
- **User-element (UEL/VUEL) state variables cannot be written to the ODB** (the `*Element Output ... SDV` request is accepted but nothing appears). Reconstruct state from nodal displacements instead (this matched the solver log exactly in this project).
- History output lives in `step.historyRegions['Assembly ASSEMBLY'].historyOutputs` (ALLKE, ALLIE, ALLPD, ALLVD, ALLFD, ALLAE, ETOTAL).
- The solver log (`.sta`, `.msg`, `.dat`) is small; fetch it directly.

---

## 7. Abaqus/Explicit facts found on this cluster [verified unless marked]

- User element type keys must start with `VU` (e.g. `VU1`) for VUEL.
- A VUEL cannot delete itself or take part in contact. Pair it with a node-coincident native element for visual deletion and contact.
- General contact with element-based surfaces extends to faces exposed by element deletion automatically (a whole-body surface gave a bit-identical result to the original-face surface).
- `*Surface Property Assignment` must be inside `*Contact`. `*Contact Controls` takes no `name` parameter; the penalty scale form accepted by datacheck is `*Contact Controls Assignment, type=SCALE PENALTY` with data ` , , <factor>`. A large penalty scale collapsed the stable time step (about 1e-10 s) and made the run very slow.
- A **node-based contact surface** (`*Surface, type=NODE` on the plate node set, listed in `*Contact Inclusions` against the ball surface, with `*Surface Property Assignment, property=THICKNESS`) stopped a steel ball that otherwise passed through a soft plate whose contact surface carried only a 1e-4 scaled ghost element.
- `*Contact Output` history and ball `STATUS` field output did not make it into the ODB in this setup.

---

## 8. Safety checklist for Claude (or any agent) before touching ROAR

1. Has the user approved *this* submission? If unsure, ask.
2. Is the working directory under `/storage/home/zps5207/scratch`? (The sbatch guard refuses otherwise.)
3. Did a datacheck pass for any changed deck?
4. Will the call trigger a Duo push? Tell the user so they can approve it.
5. Never delete or overwrite remote results without looking at them first; ODBs are large and not backed up here.
6. Use one connection per batch of work (tar through ssh) and one monitor per wait.
7. Report outcomes faithfully (failed jobs, partial ODBs, time-limit hits) with the file or log line that shows it.

---

## 9. Where things are in the Plate Impact project

| Path | Contents |
|---|---|
| `verification/roar/*.sbatch` | Job scripts (solver, render, analysis) |
| `verification/roar/diag_*_v2.py`, `island_*_v2.py` | ODB analysis scripts |
| `verification/roar/make_contact_variants.py` | Builds contact-variant decks from the mesher output |
| `verification/roar/run_variant.sbatch`, `post_variant.sbatch` | Generic run and post-analysis scripts (variant name from job name) |
| `agents/ROAR_SSH.md`, `agents/refiner/ROAR_SSH.md` | Earlier SSH notes |
| ROAR: `/storage/home/zps5207/scratch/flat_v2/` | Baseline flat_v2 run and its ODB |
| ROAR: `/storage/home/zps5207/scratch/ctv/` | Contact-variant runs (one directory per variant) |
