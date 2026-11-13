#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=post_%x_%j.out
# Post chain final step: write PULL_MANIFEST.txt listing what pull_and_view.sh downloads,
# and PULL_READY (only if the viewer folder is complete). Vars: D, V.
set -u
cd /scratch/zps5207/ctv/$D/$V || exit 66
M=PULL_MANIFEST.txt
rm -f PULL_READY
{
  echo "run $V  dir ctv/$D/$V  bundled $(date)"
  for f in viewer_$V ${V}_extract.json ${V}_r_extract.json $V.sta $V.msg $V.dat; do
    [ -e "$f" ] && echo "file $f $(du -sh "$f" | cut -f1)"
  done
  echo "--- step logs"
  grep -h -E ' rc=' post_*_${V}_*.out 2>/dev/null
} > $M
cat $M
if [ -f viewer_$V/manifest.json ]; then
  touch PULL_READY; echo "PULL_READY"
else
  echo "NOT READY: viewer_$V/manifest.json missing"; exit 1
fi
