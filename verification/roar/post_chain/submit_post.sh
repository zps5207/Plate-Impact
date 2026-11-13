#!/bin/bash
# Submit the full post-processing chain for one finished (or still running) Abaqus run on ROAR:
#   ex_<V>  ODB -> viewer npz + extract json   (16 GB)
#   pk_<V>  npz -> viewer_<V>/ WebGL folder     (16 GB)
#   bd_<V>  PULL_MANIFEST.txt + PULL_READY      (2 GB)
# Chained with afterany (bad/failed runs still get processed). Ends in files that
# verification/roar/post_chain/pull_and_view.sh downloads and opens in the HTML viewer.
#
# Usage (on ROAR):
#   bash /scratch/zps5207/ctv/scripts/post_chain/submit_post.sh <D> <V> <TEND> <FRAMES> [AFTER_JOBID] [TSPLIT]
#     D       dir under /scratch/zps5207/ctv holding run dir V   (e.g. bt3)
#     V       job/run name; expects <D>/<V>/<V>.odb                (e.g. nv3_elem)
#     TEND    end time in s                                          (e.g. 1.0e-4)
#     FRAMES  viewer frames                                          (e.g. 200; 2 per us is the norm)
#     AFTER_JOBID  optional: solve (or restart) job to wait on (afterany); "-" for none
#     TSPLIT  optional: restart run; <V>.odb Step-1 ends at TSPLIT, <V>_r.odb Step-2 continues
# Example, chained behind a solve:  submit_post.sh bt3 nv3_new 1.0e-4 200 57012345
set -eu
D=$1; V=$2; TEND=$3; FRAMES=$4; AFTER=${5:--}; TSPLIT=${6:-}
P=/scratch/zps5207/ctv/scripts/post_chain
RUN=/scratch/zps5207/ctv/$D/$V
[ -d "$RUN" ] || { echo "no run dir $RUN"; exit 2; }
cd "$RUN"
RESTART=0; [ -n "$TSPLIT" ] && RESTART=1
dep=(); [ "$AFTER" != "-" ] && dep=(--dependency=afterany:$AFTER)
a=$(sbatch --parsable --job-name=ex_$V "${dep[@]}" \
      --export=ALL,D=$D,V=$V,TEND=$TEND,FRAMES=$FRAMES,RESTART=$RESTART,TSPLIT=${TSPLIT:-0} $P/ex_viewer.sbatch)
b=$(sbatch --parsable --job-name=pk_$V --dependency=afterany:$a --export=ALL,D=$D,V=$V $P/pk_viewer.sbatch)
c=$(sbatch --parsable --job-name=bd_$V --dependency=afterany:$b --export=ALL,D=$D,V=$V $P/bundle.sbatch)
echo "POST_CHAIN $V ex=$a pk=$b bd=$c (after ${AFTER})"
echo "$(date '+%F %T') $V ex=$a pk=$b bd=$c after=$AFTER TEND=$TEND FRAMES=$FRAMES TSPLIT=${TSPLIT:-}" >> POST_CHAIN.log
