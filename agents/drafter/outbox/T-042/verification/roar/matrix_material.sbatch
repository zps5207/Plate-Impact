#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=matrix_material
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=matrix_material_%j.out

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $real_submit_dir)"; exit 64 ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)"

for n in $(cat matrix_material/decks_matrix_material.txt); do
  mkdir -p "run_$n"
  cp "matrix_material/$n.inp" "run_$n/"
  if [ -f "matrix_material/${n}_user.for" ]; then
    cp "matrix_material/${n}_user.for" "run_$n/"
    ( cd "run_$n"
      abaqus job="$n" input="$n.inp" user="${n}_user.for" interactive > "$n.stdout" 2>&1
      echo $? > "$n.rc" )
  else
    ( cd "run_$n"
      abaqus job="$n" input="$n.inp" interactive > "$n.stdout" 2>&1
      echo $? > "$n.rc" )
  fi
  echo "$n rc=$(cat run_$n/$n.rc)"
done

echo "Running verification checks..."
if [ -f "check_matrix_material.py" ]; then
  abaqus python check_matrix_material.py "$SLURM_SUBMIT_DIR" > matrix_material_results.json 2>&1
  echo "check rc=$?"
fi
echo "done $(date)"
