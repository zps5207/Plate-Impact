#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=v500_fiber_contact
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=run_v500_fiber_contact_%j.out

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: submit under /storage/home/zps5207/scratch ($real_submit_dir)"; exit 64 ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host=$(hostname) date=$(date) mode=${MODE:-run}"

if [ "${MODE:-run}" = datacheck ]; then
  abaqus job=v500_fiber_contact_check input=output.inp user=VUEL_failure.for datacheck interactive > datacheck.stdout 2>&1
else
  abaqus job=v500_fiber_contact input=output.inp user=VUEL_failure.for interactive > job.stdout 2>&1
fi
rc=$?
echo "abaqus rc=$rc done=$(date)"
exit "$rc"
