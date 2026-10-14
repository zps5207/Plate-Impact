#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=flat_t007
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=flat_t007_%j.out

set -u

real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *)
    echo "REFUSING: must run under /storage/home/zps5207/scratch" \
      "(resolved: $real_submit_dir)"
    exit 64
    ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"

echo "host: $(hostname)  date: $(date)"

abaqus job=flat_t007 input=output.inp user=VUEL_failure.for \
  interactive > flat_t007.stdout 2>&1
rc=$?
echo "abaqus rc=$rc"
echo "done $(date)"

exit $rc
