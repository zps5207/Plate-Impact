#!/bin/bash
#SBATCH --job-name=stage7_vf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=stage7_vf_%j.out

set -euo pipefail
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"

while IFS= read -r job; do
  mkdir -p "run_${job}"
  cp "${job}.inp" "${job}_user.for" "run_${job}/"
  (cd "run_${job}" && abaqus job="${job}" input="${job}.inp" \
      user="${job}_user.for" interactive > "${job}.stdout" 2>&1)
done < decks_stage7_vf.txt

abaqus python ../../stage7_check_vf.py \
  run_stage7_tension_vf0/stage7_tension_vf0.odb \
  run_stage7_tension_vf05/stage7_tension_vf05.odb \
  run_stage7_tension_vf0_baseline/stage7_tension_vf0_baseline.odb \
  run_stage7_compression_vf0/stage7_compression_vf0.odb \
  run_stage7_compression_vf05/stage7_compression_vf05.odb \
  run_stage7_compression_vf0_baseline/stage7_compression_vf0_baseline.odb \
  > stage7_vf_check.json
