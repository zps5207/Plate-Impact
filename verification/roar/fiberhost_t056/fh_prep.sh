#!/bin/bash
# Prepare fh056 bisect decks A (native other-ply only) and B (USER own-ply only); print run.sh + submit info. No submission.
set -u
B=/scratch/zps5207/ctv/fh056
S=$B/nv3_fh
cd $S || exit 1
echo "=== nv3_fh dir"; ls -la | head -40
echo "=== run.sh"; cat run.sh
echo "=== run_dc.sh diff"; diff run.sh run_dc.sh
echo "=== sacct submit lines"
sacct -j 57206650,57206655,57206656,57206657,57206658 --format=JobID%12,JobName%14,State,Elapsed,NCPUS,ReqMem,SubmitLine%250 2>/dev/null | grep -v '\.ba\|\.ex'
echo "=== msg: deep penetration / warnings"
grep -n -i -B2 -A8 "deep penetration" nv3_fh.msg | head -80
grep -c -i "warning" nv3_fh.msg
echo "=== sta tail"; tail -25 nv3_fh.sta
for V in A B; do
  D=$B/nv3_fh$V; mkdir -p $D
  cp run.sh run_dc.sh VUEL_material.for $D/ 2>/dev/null
  # own-ply pair  : EMBMESH_FIBER_NODES_PLY_k , EMBMESH_HOST_PLY_k   (inclusion, 2 fields)
  # own-ply assign: EMBMESH_FIBER_NODES_PLY_k , EMBMESH_HOST_PLY_k , FiberHostBaseline
  awk -v V=$V '
    /^\*Contact Inclusions/ {inc=1; print; next}
    /^\*/ {inc=0}
    {
      if (match($0,/^EMBMESH_FIBER_NODES_PLY_([0-9]+) , EMBMESH_HOST_PLY_([0-9]+)( , FiberHostBaseline)?$/)) {
        split($0,f," , "); a=f[1]; b=f[2]; sub(/EMBMESH_FIBER_NODES_PLY_/,"",a); sub(/EMBMESH_HOST_PLY_/,"",b)
        own=(a==b)
        if (V=="A" && own) next      # A: drop own-ply USER pairs (inclusions + assignments)
        if (V=="B" && !own) next     # B: drop other-ply native pairs
      }
      print
    }' nv3_fh.inp > $D/nv3_fh$V.inp
  echo "=== variant $V: lines kept"
  grep -c "^EMBMESH_FIBER_NODES_PLY_[0-9]* , EMBMESH_HOST_PLY_[0-9]*$" $D/nv3_fh$V.inp
  grep -c "FiberHostBaseline$" $D/nv3_fh$V.inp
  diff <(wc -l < nv3_fh.inp) <(wc -l < $D/nv3_fh$V.inp)
done
ls -la $B/nv3_fhA $B/nv3_fhB
