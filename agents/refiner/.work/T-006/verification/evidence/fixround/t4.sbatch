#!/bin/bash
#SBATCH --job-name=verif_t4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=t4_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
for n in flat_truss flat_beam cyl_truss; do
  mkdir -p run_$n; cp decks/$n.inp run_$n/
  ( cd run_$n; abaqus job=$n input=$n.inp datacheck interactive > $n.stdout 2>&1; echo $? > $n.rc )
  echo "$n rc=$(cat run_$n/$n.rc)"
done
