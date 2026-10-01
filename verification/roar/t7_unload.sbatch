#!/bin/bash
#SBATCH --job-name=t7unload
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=t7unload_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR/dbg7b"
abaqus job=t7_tension_unload input=t7_tension_unload.inp user=t7_tension_unload_user.for interactive > t7_tension_unload.stdout 2>&1
echo $? > t7_tension_unload.rc
echo "done $(date)"
