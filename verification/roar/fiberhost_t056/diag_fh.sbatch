#!/bin/bash
#SBATCH --job-name=diag_fh
#SBATCH --account=rhk12_cr_default
#SBATCH --partition=basic
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=16G
#SBATCH --time=1:00:00
source ~/.bashrc
module load abaqus
cd /scratch/zps5207/ctv/fh056/diag
abaqus python diag_fh.py /scratch/zps5207/ctv/fh056/nv3_fh/nv3_fh.odb > diag_nv3_fh.txt 2>&1
echo done >> diag_nv3_fh.txt
