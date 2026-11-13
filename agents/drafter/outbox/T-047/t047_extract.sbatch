#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=t047_extract
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=run_%x_%j.out

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/ctv/t046*|/scratch/zps5207/ctv/t046*) ;;
  *) echo "REFUSING: must run under ctv/t046 (resolved: $real_submit_dir)"; exit 64 ;;
esac

module load anaconda/2023.09
module load abaqus
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"

abaqus python extract_t046.py .
rc=$?
echo "extraction rc=$rc"

abaqus python check_tests.py .
check_rc=$?
echo "check_tests rc=$check_rc"

echo "done $(date)"
exit $rc
