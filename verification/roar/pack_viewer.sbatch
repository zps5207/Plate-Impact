#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=pack_%x_%j.out
# Chain step 4: pack <V>_viewer.npz into the WebGL viewer folder viewer_<V>/ (numpy only, no Abaqus).
# Usage: sbatch --job-name=pk_$V --dependency=afterany:<extract id> --export=ALL,V=$V pack_viewer.sbatch
set -u
module load anaconda/2023.09
cd /scratch/zps5207/ctv/bt3/$V
python3 /scratch/zps5207/ctv/scripts/pack_viewer_data.py ${V}_viewer.npz --output viewer_$V
echo "pack rc=$?"
