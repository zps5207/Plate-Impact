#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=export_viewer_%x_%j.out
# Usage (from the ODB's directory): sbatch --job-name=ev_v300 --export=ALL,V=v300,FRAMES=150 export_viewer.sbatch
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
echo "host: $(hostname)  date: $(date)  V=$V FRAMES=${FRAMES:-150}"
abaqus python /storage/home/zps5207/scratch/ctv/scripts/export_odb_viewer.py $V.odb \
  --output ${V}_viewer.npz --start-time ${TSTART:-0} --end-time ${TEND:-7.0e-5} \
  --frame-count ${FRAMES:-150} > export_viewer_${V}.stdout 2>&1
rc=$?
echo "export rc=$rc"; echo "done $(date)"
exit $rc
