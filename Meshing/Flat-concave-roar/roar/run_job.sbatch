#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=run_%x_%j.out
# Usage (from the job directory): sbatch --job-name=cc500_100 --export=ALL,MODE=datacheck run_job.sbatch
#                                  sbatch --job-name=cc500_100 --export=ALL,MODE=run --dependency=afterok:<datacheck id> run_job.sbatch
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
echo "host: $(hostname)  date: $(date)  job=$SLURM_JOB_NAME mode=${MODE:-run} cpus=${SLURM_NTASKS_PER_NODE:-1}"
if [ "${MODE:-run}" = "datacheck" ]; then
  abaqus job=$SLURM_JOB_NAME input=output.inp user=VUEL_failure.for datacheck interactive > job.stdout 2>&1
else
  abaqus job=$SLURM_JOB_NAME input=output.inp user=VUEL_failure.for cpus=${SLURM_NTASKS_PER_NODE:-1} interactive > job.stdout 2>&1
fi
rc=$?
echo "abaqus rc=$rc"; echo "done $(date)"
# a datacheck that wrote ***ERROR to the .dat must stop the dependent solve
if [ "${MODE:-run}" = "datacheck" ] && grep -q "\*\*\*ERROR" $SLURM_JOB_NAME.dat 2>/dev/null; then
  echo "DATACHECK ERRORS FOUND:"; grep -m5 -A3 "\*\*\*ERROR" $SLURM_JOB_NAME.dat; exit 2
fi
exit $rc
