#!/bin/bash
#SBATCH --job-name=verif_t3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=t3_%j.out
module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"
for n in $(cat decks_t3.txt); do
  mkdir -p "run_$n"; cp "t3/$n.inp" "run_$n/" 2>/dev/null || cp "$n.inp" "run_$n/"
  case "$n" in
    vumat_*) cp VUMAT_tension_only.for "run_$n/" ;;
  esac
  ( cd "run_$n"
    case "$n" in
      vumat_*) abaqus job="$n" input="$n.inp" user=VUMAT_tension_only.for interactive > "$n.stdout" 2>&1 ;;
      *) abaqus job="$n" input="$n.inp" interactive > "$n.stdout" 2>&1 ;;
    esac
    echo $? > "$n.rc" )
  echo "$n rc=$(cat run_$n/$n.rc)"
done
echo "done $(date)"
