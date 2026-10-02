#!/bin/bash
#SBATCH --job-name=verif_t11
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:40:00
#SBATCH --output=t11_%j.out

set -u

real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *)
    echo "REFUSING: Stage 5 must run under /storage/home/zps5207/scratch" \
      "(resolved: $real_submit_dir)"
    exit 64
    ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"

echo "host: $(hostname)  date: $(date)"
run_failed=0
for n in $(cat t11/decks_t11.txt); do
  mkdir -p "run_$n"
  cp "t11/$n.inp" "run_$n/"
  cp "t11/${n}_user.for" "run_$n/"
  (
    cd "run_$n"
    abaqus job="$n" input="$n.inp" user="${n}_user.for" \
      interactive > "$n.stdout" 2>&1
    echo $? > "$n.rc"
  )
  rc=$(cat "run_$n/$n.rc")
  echo "$n rc=$rc"
  if [ "$rc" -ne 0 ]; then
    run_failed=1
  fi
done

if [ "$run_failed" -eq 0 ]; then
  abaqus python t11/t11_check_degradation.py "$SLURM_SUBMIT_DIR" \
    > t11_results.json
  check_rc=$?
else
  check_rc=99
fi
echo "$check_rc" > t11_check.rc
echo "checker rc=$check_rc"
echo "done $(date)"

if [ "$run_failed" -ne 0 ] || [ "$check_rc" -ne 0 ]; then
  exit 1
fi
