#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=render_t006b
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=render_t006b_%j.out

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

abaqus cae noGUI=render_ghost_failure.py -- flat_t006b.odb \
  --output-dir frames_regular --passes status,displacement \
  > render_regular.stdout 2>&1
rc1=$?
echo "regular rc=$rc1"

abaqus cae noGUI=render_ghost_failure.py -- flat_t006b.odb \
  --output-dir frames_fibers --passes fibers \
  > render_fibers.stdout 2>&1
rc2=$?
echo "fibers rc=$rc2"

echo "done $(date)"

exit $(( rc1 != 0 ? rc1 : rc2 ))
