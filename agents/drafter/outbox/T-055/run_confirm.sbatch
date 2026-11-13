#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=nv3_vuel_fix
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=nv3_vuel_fix_%j.out

# Confirming run for T-055 fix
# Runs datacheck or short 1 us solve to verify:
# 1. 0 initial contact overclosures between plies
# 2. 0 VUEL material failure before ball contact (t <= 0.97 us)

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
echo "host: $(hostname)  date: $(date)  dir: $real_submit_dir"

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"

# Run short explicit solve or datacheck
abaqus job=nv3_vuel_fixed input=nv3_vuel_fixed.inp user=VUEL_material.for cpus=6 double=both interactive
