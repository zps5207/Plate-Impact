#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=post_%x_%j.out
# Post chain step 2: pack <V>_viewer.npz into the WebGL viewer folder viewer_<V>/ (numpy only).
# Vars: D, V.
set -u
module load anaconda/2023.09
cd /scratch/zps5207/ctv/$D/$V || exit 66
python3 /scratch/zps5207/ctv/scripts/pack_viewer_data.py ${V}_viewer.npz --output viewer_$V
echo "pack rc=$?"
