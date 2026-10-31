#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=run_%x_%j.out

# Native-deck ball tests (no user subroutine). Job name = deck name; MODE=datacheck for a datacheck only.
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
echo "host: $(hostname)  date: $(date)  job=$SLURM_JOB_NAME mode=${MODE:-run}"
if [ "${MODE:-run}" = "datacheck" ]; then
  abaqus job=$SLURM_JOB_NAME input=$SLURM_JOB_NAME.inp datacheck interactive > job.stdout 2>&1
else
  abaqus job=$SLURM_JOB_NAME input=$SLURM_JOB_NAME.inp cpus=16 interactive > job.stdout 2>&1
fi
rc=$?
echo "abaqus rc=$rc"; echo "done $(date)"
exit $rc
