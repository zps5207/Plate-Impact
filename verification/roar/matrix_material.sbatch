#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=matrix_material
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=matrix_material_%x_%j.out
# usage: sbatch [--time=HH:MM:SS] [--job-name=mm_r1] matrix_material.sbatch <rate tag: r0p01|r1|r1000> [extra abaqus options]

set -u
TAG=${1:?rate tag required}
EXTRA="${2:-}"   # extra abaqus options, e.g. double=both
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $real_submit_dir)"; exit 64 ;;
esac

module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
echo "host: $(hostname)  date: $(date)  tag: $TAG"

for n in $(grep "_${TAG}\$" matrix_material/decks_matrix_material.txt); do
  mkdir -p "run_$n"
  cp "matrix_material/$n.inp" "run_$n/"
  if [ -f "matrix_material/${n}_user.for" ]; then
    cp "matrix_material/${n}_user.for" "run_$n/"
    ( cd "run_$n"
      abaqus job="$n" input="$n.inp" user="${n}_user.for" $EXTRA interactive > "$n.stdout" 2>&1
      echo $? > "$n.rc" )
  else
    ( cd "run_$n"
      abaqus job="$n" input="$n.inp" $EXTRA interactive > "$n.stdout" 2>&1
      echo $? > "$n.rc" )
  fi
  echo "$n rc=$(cat run_$n/$n.rc)"
done

abaqus python dump_matrix_curves.py . "_${TAG}"
echo "done $(date)"
