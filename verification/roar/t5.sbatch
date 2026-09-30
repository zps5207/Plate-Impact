#!/bin/bash
#SBATCH --job-name=verif_t5
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=t5_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"
for n in $(cat decks_t5.txt); do
  mkdir -p "run_$n"; cp "t5/$n.inp" "run_$n/"
  USER_ARG=""
  if [ -f "t5/${n}_user.for" ]; then
    cp "t5/${n}_user.for" "run_$n/"
    USER_ARG="user=${n}_user.for"
  fi
  ( cd "run_$n"
    abaqus job="$n" input="$n.inp" $USER_ARG interactive > "$n.stdout" 2>&1
    echo $? > "$n.rc" )
  echo "$n rc=$(cat run_$n/$n.rc)"
done
echo "done $(date)"
