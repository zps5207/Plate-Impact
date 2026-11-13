#!/bin/bash
# Submit script for T-049 ball isolation test matrix on ROAR.
# Working directory: /storage/home/zps5207/scratch/ctv/t049/
#
# Usage:
#   bash submit_matrix.sh datacheck    # Run datachecks for all 10 decks
#   bash submit_matrix.sh solve        # Run solves for all 10 decks (requires user approval)
#   bash submit_matrix.sh chain        # Submit datacheck -> solve dependency chains

set -eu

B="/storage/home/zps5207/scratch/ctv/t049"
case "$(readlink -f "$B")" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $(readlink -f "$B"))"; exit 64 ;;
esac

cd "$B"

MODE="${1:-datacheck}"
echo "=== Submitting T-049 Ball Isolation Test Matrix (Mode: $MODE) ==="

DECKS=(
  "01:t049_01_baseline_plate_dmg_on.inp"
  "02:t049_02_baseline_plate_dmg_off.inp"
  "03:t049_03_host_only_erode.inp"
  "04:t049_04_host_embedded_no_contact.inp"
  "05:t049_05_fiber_node_thick_0618.inp"
  "06:t049_06_fiber_node_thick_dmg_off.inp"
  "07:t049_07_fiber_node_thin_0050.inp"
  "08:t049_08_ball_coarse_mesh.inp"
  "09:t049_09_fiber_penalty_scale.inp"
  "10:t049_10_fiber_beam_elem_surf.inp"
)

case "$MODE" in
  datacheck)
    echo "Submitting 10 DATACHECK jobs..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      job="t049_chk${num}"
      jid=$(sbatch --parsable --job-name="$job" --time=00:10:00 --cpus-per-task=1 --mem=16G --export=ALL,MODE=datacheck,INP="decks/$inp" run_test.sbatch)
      echo "  [$num] Submitted datacheck $job (JobID: $jid) for $inp"
    done
    ;;

  solve)
    echo "Submitting 10 SOLVE jobs (8 CPUs, 16 GB, 30 min limit)..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      job="t049_sol${num}"
      jid=$(sbatch --parsable --job-name="$job" --time=00:30:00 --cpus-per-task=8 --mem=16G --export=ALL,MODE=run,INP="decks/$inp" run_test.sbatch)
      echo "  [$num] Submitted solve $job (JobID: $jid) for $inp"
    done
    ;;

  chain)
    echo "Submitting paired datacheck -> solve chains..."
    for item in "${DECKS[@]}"; do
      num="${item%%:*}"
      inp="${item##*:}"
      cjob="t049_chk${num}"
      sjob="t049_sol${num}"
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
