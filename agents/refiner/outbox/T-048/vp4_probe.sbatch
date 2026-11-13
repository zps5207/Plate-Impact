#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=t048_vp4_probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=t048_vp4_probe_%j.out

set -euo pipefail
work=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$work" in
  /storage/home/zps5207/scratch/ctv/t048|/scratch/zps5207/ctv/t048) ;;
  *) echo "Refusing to run outside ctv/t048 (resolved: $work)" >&2; exit 2 ;;
esac

cd "$SLURM_SUBMIT_DIR"
module load anaconda/2023.09
module load abaqus
module load intel
abaqus python vp4_odb_probe.py /storage/home/zps5207/scratch/ctv/vp4/vals_native/vals_native.odb native_vp4
abaqus python vp4_odb_probe.py /storage/home/zps5207/scratch/ctv/vp4/vals_vuel/vals_vuel.odb vuel_vp4
