#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=render_%x_%j.out
# Usage: sbatch --job-name=rN --export=ALL,V=v300,FRAMES=60,OUT=frames,VIEWS=iso;side;sidev render_variant.sbatch
# (VIEWS uses ';' because sbatch --export splits on commas)
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
echo "host: $(hostname)  date: $(date)  V=$V FRAMES=${FRAMES:-60}"
abaqus cae noGUI=$SLURM_SUBMIT_DIR/scripts/render_ghost_failure.py -- $V.odb \
  --output-dir ${OUT:-frames} --passes status,wire --views $(echo "${VIEWS:-iso;side}" | tr ';' ',') --fps ${FPS:-30} \
  --start-time ${TSTART:-0} --end-time ${TEND:-7.0e-5} --frame-count ${FRAMES:-60} \
  > render_${OUT:-frames}.stdout 2>&1
rc=$?
echo "render rc=$rc"; echo "done $(date)"
exit $rc
