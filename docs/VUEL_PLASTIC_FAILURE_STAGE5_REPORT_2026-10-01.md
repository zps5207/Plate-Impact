# VUEL Plastic-Failure Project — Stage 5 Report

Date: 2026-10-01
Branch: `vuel-plastic-failure`

## Objective

Verify the degradation-ramp failure behavior added to `uel/VUEL_failure.for`
(`props(12) = DEGRADE_TIME`, `props(13) = COMP_RESIDUAL_BULK_FRAC`,
`svars(106) = DAMAGE`) against a five-case T11 suite, on ROAR, with real
Abaqus/Explicit numbers.

## Submission history

| Job ID     | Result  | Notes |
|------------|---------|-------|
| 55978518   | FAILED (exit 64) | `t11.sbatch`'s own safety guard refused to run. Root cause below. No Abaqus jobs executed. |
| 55978605   | COMPLETED (exit 0) | All 5 cases ran; checker passed. |

### Job 55978518 — guard false-refusal (not a physics failure)

`/storage/home/zps5207/scratch` is a symlink to `/scratch/zps5207`. Slurm
resolves `$SLURM_SUBMIT_DIR` to the real path, so the script saw
`/scratch/zps5207/vuel_stage5_t11_20261001_01`, which did not match the
guard's literal pattern `/storage/home/zps5207/scratch/*`, even though the
directory is legitimately under scratch. `t11.sbatch` exited 64 with:

```text
REFUSING: Stage 5 must run under /storage/home/zps5207/scratch
```

Fix applied to `verification/roar/t11.sbatch`: canonicalize
`$SLURM_SUBMIT_DIR` with `readlink -f` before the guard check, and accept
either the symlinked or real scratch prefix. The guard's intent (refuse to
run outside scratch) is unchanged — it now just resolves symlinks before
comparing. Re-verified locally that the directory still rejects any path
outside both prefixes before resubmitting.

### Job 55978605 — successful run

Submitted from the corrected script, under:

```text
/storage/home/zps5207/scratch/vuel_stage5_t11_20261001_01
```

Ran on compute node `p-bc-5421`, start 20:52:23 EDT, done 20:53:46 EDT
(≈83s). Slurm output (`t11_55978605.out`):

```text
host: p-bc-5421  date: Thu Oct  1 20:52:23 EDT 2026
t11_instant_chain rc=0
t11_ramp_chain rc=0
t11_ramp_tension rc=0
t11_zero_cycle rc=0
t11_residual_cycle rc=0
checker rc=0
done Thu Oct  1 20:53:46 EDT 2026
```

`sacct`: `55978605|COMPLETED|0:0` (batch and extern steps both `COMPLETED`).

## Per-case results (from `t11_results.json`)

1. **`t11_instant_chain`** — reproduces Stage 4 instant-zero behavior.
   Element 1 fails at `t=0.0029956952`; `node2_v1_final = 40.522`.
   `strict_checks.instant_chain_reproduces_stage4 = true`.

2. **`t11_ramp_chain`** — cascading failure under a nonzero degradation
   ramp. Elements 1 and 2 fail at `t=0.0029956952` and `t=0.003948871`;
   `node2_v1_final = 141.789`.

3. **`t11_ramp_tension`** — degradation ramp under tension.
   - Failure at `t=0.0061275549`, ramp completes at `t=0.0081700711`
     (measured duration `0.0020425162`, matching the configured
     `DEGRADE_TIME`).
   - `pass_duration = true`
   - `pass_force_persists_during_ramp = true` (reaction force doesn't drop
     to zero instantly — it decays over the ramp)
   - `pass_force_zero_after_ramp = true` (`max_abs_rf_after_completion =
     0.0`)

4. **`t11_zero_cycle`** — compression/tension cycle with zero residual
   bulk fraction (`COMP_RESIDUAL_BULK_FRAC = 0`).
   - `pass_zero_control = true`
   - `zero_cycle_max_abs_rf_tension_plateau = 0.0` — confirms no spurious
     stiffness remains once fully degraded, including under the tension
     plateau.

5. **`t11_residual_cycle`** — same cycle with a nonzero compression-only
   residual bulk fraction.
   - `pass_compression_residual = true`
   - `pass_no_residual_tension = true` —
     `residual_cycle_max_abs_rf_tension_plateau = 0.0`, confirming the
     residual stiffness is compression-only as designed.
   - Final reaction force: measured `1177470208.0` vs. expected
     `1177470100.3566337` — relative error `9.14e-8`, i.e. matches the
     analytical compression-only-residual prediction to within numerical
     noise.

## Overall verdict

`"pass": true` in `t11_results.json`, with all `strict_checks` true
(`compression_only_residual`, `instant_chain_reproduces_stage4`,
`ramp_tension`) and all three `cycles` pass flags true. Stage 5 is
**verified**.

## Evidence retained in repo

```text
verification/roar/t11/evidence_20261001/
  t11_55978605.out
  t11_results.json
  t11_instant_chain.stdout
  t11_ramp_chain.stdout
  t11_ramp_tension.stdout
  t11_zero_cycle.stdout
  t11_residual_cycle.stdout
```

## Files changed this stage

- `verification/roar/t11.sbatch` — symlink-safe scratch-directory guard
  (see job 55978518 above). No change to module loads, run logic, or the
  checker invocation.
- `docs/VUEL_PLASTIC_FAILURE_STAGE5_REPORT_2026-10-01.md` — this report.
- `verification/roar/t11/evidence_20261001/` — retrieved Slurm/Abaqus/
  checker evidence, added above.

No changes were made to `uel/VUEL_failure.for`, `uel/VUEL.for`,
`verification/make_t11_degradation.py`, or
`verification/t11_check_degradation.py` during this stage — Codex's local
implementation and verification scripts ran unmodified and passed as
submitted.

## Process note

Per current project direction, code editing and generation for subsequent
stages is being handed to agy and Codex; this session's role going forward
is orchestration — ROAR connection/MFA handling, job submission and
monitoring, evidence retrieval, and reporting.
