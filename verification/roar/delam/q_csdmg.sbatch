#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=0:30:00
#SBATCH --output=q_csdmg_%x_%j.out
# Probe CSDMG storage. Usage: sbatch --job-name=q_$V --export=ALL,V=$V q_csdmg.sbatch   (ODB in ctv/bt3/$V)
set -u
module load abaqus
cd /scratch/zps5207/ctv/bt3/$V
abaqus python /scratch/zps5207/ctv/scripts/q_csdmg.py $V.odb
