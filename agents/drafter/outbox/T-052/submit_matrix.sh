#!/bin/bash
# Submit script for T-052 hex inversion test matrix on ROAR.
# Working directory: /storage/home/zps5207/scratch/ctv/t052/
#
# Usage:
#   bash submit_matrix.sh datacheck    # Run datachecks for all 10 decks (fast syntax/model verification)
#   bash submit_matrix.sh solve        # Run solves for all 10 decks (requires explicit user approval)
#   bash submit_matrix.sh chain        # Submit datacheck -> solve dependency chains

set -eu

B="/storage/home/zps5207/scratch/ctv/t052"
case "$(readlink -f "$B")" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $(readlink -f "$B"))"; exit 64 ;;
esac

cd "$B"

MODE="${1:-datacheck}"
echo "=== Submitting T-052 Hex Inversion Test Matrix (Mode: $MODE) ==="

DECKS=(
  "01:t052_01_ref_truss_d4.inp"
  "02:t052_02_distortion_control_on.inp"
  "03:t052_03_hourglass_enhanced.inp"
  "04:t052_04_hourglass_viscous.inp"
  "05:t052_05_ball_no_deletion.inp"
  "06:t052_06_fiber_contact_thin_0050.inp"
  "07:t052_07_fiber_contact_none.inp"
  "08:t052_08_ball_ogrid_mesh.inp"
  "09:t052_09_ball_alone_plain_plate.inp"
  "10:t052_10_combined_best_practice.inp"
)

case "$MODE" in
  datacheck)
    echo "Submitting 10 DATACHECK jobs..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      job="t052_chk${num}"
      jid=$(sbatch --parsable --job-name="$job" --time=00:10:00 --cpus-per-task=1 --mem=16G --export=ALL,MODE=datacheck,INP="decks/$inp" run_test.sbatch)
      echo "  [$num] Submitted datacheck $job (JobID: $jid) for $inp"
    done
    ;;

  solve)
    echo "Submitting 10 SOLVE jobs (8 CPUs, 16 GB, 30 min limit)..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      job="t052_sol${num}"
      jid=$(sbatch --parsable --job-name="$job" --time=00:30:00 --cpus-per-task=8 --mem=16G --export=ALL,MODE=run,INP="decks/$inp" run_test.sbatch)
      echo "  [$num] Submitted solve $job (JobID: $jid) for $inp"
    done
    ;;

  chain)
    echo "Submitting paired datacheck -> solve chains..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      cjob="t052_chk${num}"
      sjob="t052_sol${num}"
      cjid=$(sbatch --parsable --job-name="$cjob" --time=00:10:00 --cpus-per-task=1 --mem=16G --export=ALL,MODE=datacheck,INP="decks/$inp" run_test.sbatch)
      sjid=$(sbatch --parsable --job-name="$sjob" --dependency=afterok:$cjid --time=00:30:00 --cpus-per-task=8 --mem=16G --export=ALL,MODE=run,INP="decks/$inp" run_test.sbatch)
      echo "  [$num] Chain submitted: $cjob ($cjid) -> $sjob ($sjid)"
    done
    ;;

  *)
    echo "Unknown mode: $MODE. Choose 'datacheck', 'solve', or 'chain'."
    exit 1
    ;;
esac

echo ""
echo "Monitor queue with: squeue -u zps5207 -h -o '%i %j %T %M'"
