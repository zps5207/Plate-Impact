#!/bin/bash
#SBATCH --job-name=t9dbg
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=t9dbg_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR/dbg9"
abaqus job=t9_shear_collapse input=t9_shear_collapse.inp user=t9_shear_collapse_user.for interactive > t9_shear_collapse.stdout 2>&1
echo $? > t9_shear_collapse.rc
echo "done $(date)"
