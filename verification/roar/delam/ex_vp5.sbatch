#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --job-name=ex_vp5b
#SBATCH --output=ex_vp5b_%j.out
set -u
module load anaconda/2023.09
module load abaqus
module load intel
cd /scratch/zps5207/ctv/vp5/vals_native_erode
abaqus python /scratch/zps5207/ctv/vp5/ex_vp5.py vals_native_er.odb vp5_extract2.json
echo "rc=$?"
