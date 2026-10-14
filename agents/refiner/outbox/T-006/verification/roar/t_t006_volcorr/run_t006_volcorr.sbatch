#!/bin/bash
#SBATCH --job-name=t006_volcorr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=t006_volcorr_%j.out

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
done < cases_t006.txt

abaqus python ../../t006_check_volcorr.py "$SLURM_SUBMIT_DIR" \
  > t006_volcorr_check.json
