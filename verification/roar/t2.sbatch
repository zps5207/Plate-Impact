#!/bin/bash
#SBATCH --job-name=verif_t2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=t2_%j.out
# T2: Abaqus/Explicit datacheck of mesher-generated decks. Modules copied from existing ROAR/Embedded Elements scripts.
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"; which abaqus; abaqus information=version 2>&1 | head -5
for n in $(cat decks_t2.txt); do
  mkdir -p "run_$n"; cp "t2/$n.inp" "run_$n/"
  ( cd "run_$n"
    if [ "$n" = "xform" ]; then abaqus job="$n" input="$n.inp" interactive > "$n.stdout" 2>&1
    else abaqus job="$n" input="$n.inp" datacheck interactive > "$n.stdout" 2>&1; fi
    echo $? > "$n.rc" )
  echo "$n rc=$(cat run_$n/$n.rc)"
done
echo "done $(date)"
