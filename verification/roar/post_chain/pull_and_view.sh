#!/bin/bash
# Local side of the post chain: download what bundle.sbatch marked ready and open the WebGL viewer.
# One ssh connection (one Duo push). Needs SSH_AUTH_SOCK exported (see the roar-ssh-access notes).
#
# Usage (Git Bash, from the repo root):
#   verification/roar/post_chain/pull_and_view.sh <D> <V> <LOCAL_DEST> [--no-serve] [--port N]
#   e.g. verification/roar/post_chain/pull_and_view.sh bt3 nv3_elem Meshing/newvals-elemcontact-tt3/results
# Files land in <LOCAL_DEST>/: viewer_<V>/, <V>_extract.json, <V>.sta, <V>.msg, <V>.dat, PULL_MANIFEST.txt
set -eu
D=$1; V=$2; DEST=$3; shift 3
SERVE=1; PORT=8800
while [ $# -gt 0 ]; do
  case $1 in --no-serve) SERVE=0;; --port) PORT=$2; shift;; esac; shift
done
HERE=$(cd "$(dirname "$0")" && pwd)
VIEWER=$HERE/../../../agents/drafter/outbox/T-021/serve_viewer.py
mkdir -p "$DEST"
R=/scratch/zps5207/ctv/$D/$V
ssh -o ConnectTimeout=30 roar "cd $R && [ -f PULL_READY ] || { echo NOT_READY >&2; cat PULL_MANIFEST.txt >&2 2>/dev/null; exit 3; };
  tar cf - PULL_MANIFEST.txt viewer_$V \$(ls ${V}_extract.json ${V}_r_extract.json $V.sta $V.msg $V.dat 2>/dev/null)" \
  </dev/null | tar xf - -C "$DEST"
[ -f "$DEST/viewer_$V/manifest.json" ] || { echo "pull failed: no $DEST/viewer_$V/manifest.json"; exit 1; }
cat "$DEST/PULL_MANIFEST.txt"
echo "pulled to $DEST"
if [ $SERVE = 1 ]; then
  echo "serving viewer_$V on http://localhost:$PORT (Ctrl+C to stop)"
  python "$VIEWER" "$DEST/viewer_$V" --port $PORT
fi
