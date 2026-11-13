#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=run_%x_%j.out
#
# Runner for T-052 hex inversion test matrix decks on ROAR
# Usage:
#   sbatch --job-name=t052_chk01 --export=ALL,MODE=datacheck,INP=decks/t052_01_ref_truss_d4.inp run_test.sbatch
#   sbatch --job-name=t052_sol01 --export=ALL,MODE=run,INP=decks/t052_01_ref_truss_d4.inp run_test.sbatch

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

INP_FILE="${INP:-output.inp}"
JOB_NAME="${SLURM_JOB_NAME}"
CPUS="${SLURM_CPUS_PER_TASK:-8}"

echo "host: $(hostname)  date: $(date)  job=$JOB_NAME  mode=${MODE:-run}  inp=$INP_FILE  cpus=$CPUS"

if [ "${MODE:-run}" = "datacheck" ]; then
  abaqus job=$JOB_NAME input=$INP_FILE datacheck interactive > ${JOB_NAME}.stdout 2>&1
else
  abaqus job=$JOB_NAME input=$INP_FILE cpus=$CPUS interactive > ${JOB_NAME}.stdout 2>&1
fi
rc=$?
echo "abaqus rc=$rc"; echo "done $(date)"

# Flag datacheck errors
if [ "${MODE:-run}" = "datacheck" ] && grep -q "\*\*\*ERROR" ${JOB_NAME}.dat 2>/dev/null; then
  echo "DATACHECK ERRORS FOUND IN ${JOB_NAME}.dat:"
  grep -m10 -A3 "\*\*\*ERROR" ${JOB_NAME}.dat
  exit 2
fi

# Touch completion marker
if [ $rc -eq 0 ]; then
  touch "${JOB_NAME}.DONE"
fi

exit $rc
