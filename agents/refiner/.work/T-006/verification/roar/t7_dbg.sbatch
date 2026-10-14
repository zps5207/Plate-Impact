#!/bin/bash
#SBATCH --job-name=t7dbg
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=t7dbg_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR/dbg7"
abaqus job=t7_tension_plastic input=t7_tension_plastic.inp user=t7_tension_plastic_user.for interactive > t7_tension_plastic.stdout 2>&1
echo $? > t7_tension_plastic.rc
echo "done $(date)"
