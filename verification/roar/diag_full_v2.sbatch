#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=diag_v2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=24:00:00
#SBATCH --output=diag_v2_%j.out

set -u

real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
case "$real_submit_dir" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *)
    echo "REFUSING: must run under /storage/home/zps5207/scratch" \
      "(resolved: $real_submit_dir)"
    exit 64
    ;;
esac

module load anaconda/2023.09
module load abaqus
module load intel
cd "$SLURM_SUBMIT_DIR"
mkdir -p full
echo "host: $(hostname)  date: $(date)"

# three independent passes; a failure in one does not stop the others
( abaqus python diag_structure_v2.py flat_v2.odb > full/structure_v2.json 2> full/structure_v2.err; echo "structure rc=$?" ) &
( abaqus python diag_elements_v2.py flat_v2.odb full/el > full/el.out 2> full/el.err; echo "elements rc=$?" ) &
( abaqus python diag_contact_v2.py flat_v2.odb full/ct > full/ct.out 2> full/ct.err; echo "contact rc=$?" ) &
wait
echo "done: $(date)"
ls -la full
