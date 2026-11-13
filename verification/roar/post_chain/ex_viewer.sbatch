#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=post_%x_%j.out
# Post chain step 1: ODB -> <V>_viewer.npz (WebGL viewer export) + <V>_extract.json (energies, deletions).
# Submitted by submit_post.sh; vars: D (dir under /scratch/zps5207/ctv), V, TEND, FRAMES,
# RESTART (0/1), TSPLIT (restart split time, s; only for RESTART=1).
# RESTART=1: Step-1 in <V>.odb covers 0..TSPLIT, Step-2 in <V>_r.odb covers TSPLIT..TEND; parts are merged.
set -u
module load anaconda/2023.09
module load abaqus
module load intel
S=/scratch/zps5207/ctv/scripts
cd /scratch/zps5207/ctv/$D/$V || exit 66
echo "host $(hostname) start $(date) D=$D V=$V TEND=$TEND FRAMES=$FRAMES RESTART=${RESTART:-0}"
if [ "${RESTART:-0}" = "1" ]; then
  T2=$(python3 -c "print($TEND-$TSPLIT)")
  F1=$(python3 -c "print(max(2,round($FRAMES*$TSPLIT/$TEND)))")
  F2=$((FRAMES-F1))
  abaqus python $S/export_odb_viewer_plywise.py $V.odb --step Step-1 --output ${V}_p1.npz \
    --start-time 0 --end-time $TSPLIT --frame-count $F1 > export_p1.stdout 2>&1
  echo "export p1 rc=$?"
  abaqus python $S/export_odb_viewer_plywise.py ${V}_r.odb --step Step-2 --output ${V}_p2.npz \
    --start-time 0 --end-time $T2 --frame-count $F2 > export_p2.stdout 2>&1
  echo "export p2 rc=$?"
  python3 $S/merge_viewer_npz.py ${V}_p1.npz ${V}_p2.npz $TSPLIT ${V}_viewer.npz
  echo "merge rc=$?"
  abaqus python /scratch/zps5207/ctv/vp5/ex_vp5.py $V.odb ${V}_extract.json;          echo "extract p1 rc=$?"
  abaqus python /scratch/zps5207/ctv/vp5/ex_vp5.py ${V}_r.odb ${V}_r_extract.json;    echo "extract p2 rc=$?"
else
  abaqus python $S/export_odb_viewer_plywise.py $V.odb --output ${V}_viewer.npz \
    --start-time 0 --end-time $TEND --frame-count $FRAMES > export_viewer_${V}.stdout 2>&1
  echo "export rc=$?"
  abaqus python /scratch/zps5207/ctv/vp5/ex_vp5.py $V.odb ${V}_extract.json
  echo "extract rc=$?"
fi
echo "done $(date)"
