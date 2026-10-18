#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=energy_%x_%j.out
# Usage (from the ODB's directory): sbatch --job-name=en_cc500_100 --export=ALL,V=cc500_100 post_energy.sbatch
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
echo "host: $(hostname)  date: $(date)  V=$V"
abaqus python ${SCRIPTS:-.}/extract_energy_history.py $V.odb --output ${V}_energy.csv > energy_${V}.stdout 2>&1
rc=$?
echo "energy rc=$rc"; echo "done $(date)"
exit $rc
