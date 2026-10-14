#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=06:00:00
#SBATCH --output=post_%x_%j.out

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
mkdir -p full
V=${V}
S=/storage/home/zps5207/scratch/ctv/scripts
( abaqus python $S/diag_structure_v2.py $V.odb > full/structure.json 2> full/structure.err; echo structure rc=$? ) &
( abaqus python $S/diag_elements_v2.py $V.odb full/el > full/el.out 2> full/el.err; echo elements rc=$? ) &
( abaqus python $S/diag_contact_v2.py $V.odb full/ct > full/ct.out 2> full/ct.err; echo contact rc=$? ) &
wait
echo done
