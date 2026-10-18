#!/bin/bash
# Run on ROAR from the job directory after the files are unpacked there.
# Chain: datacheck -> solve (8 tasks, 32 GB) -> energy -> viewer export -> renders -> flat-baseline energy.
set -eu
D=/storage/home/zps5207/scratch/ctv/nc/cc500_100
cd "$D"
echo "dir: $(pwd -P)"
case "$(pwd -P)" in /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;; *) echo REFUSING; exit 64;; esac
ls -la
J1=$(sbatch --parsable --job-name=cc500_100 --ntasks-per-node=1 --mem=16G --time=00:30:00 --export=ALL,MODE=datacheck run_job.sbatch)
J2=$(sbatch --parsable --job-name=cc500_100 --dependency=afterok:$J1 --export=ALL,MODE=run run_job.sbatch)
J3=$(sbatch --parsable --job-name=en_cc500_100 --dependency=afterany:$J2 --export=ALL,V=cc500_100,SCRIPTS=$D/scripts post_energy.sbatch)
J4=$(sbatch --parsable --job-name=ev_cc500_100 --dependency=afterany:$J3 --export=ALL,V=cc500_100,FRAMES=210,TEND=1.0e-4 export_viewer.sbatch)
J5=$(sbatch --parsable --job-name=rn_cc500_100 --dependency=afterany:$J4 --export="ALL,V=cc500_100,FRAMES=210,TEND=1.0e-4,OUT=frames_video,FPS=24,VIEWS=iso;side;sidev" render_variant.sbatch)
echo "datacheck=$J1 solve=$J2 energy=$J3 export=$J4 render=$J5"
# flat baseline (v500star_100): extract its energy history if the ODB is still on ROAR
FLAT=$(ls -d /storage/home/zps5207/scratch/ctv/nc/v500star_100 2>/dev/null || true)
if [ -n "$FLAT" ] && [ -f "$FLAT/v500star_100.odb" ]; then
  cp $D/scripts/extract_energy_history.py "$FLAT/" 2>/dev/null || true
  J6=$(cd "$FLAT" && sbatch --parsable --job-name=en_v500star_100 --dependency=afterany:$J5 --export=ALL,V=v500star_100,SCRIPTS=$D/scripts $D/post_energy.sbatch)
  echo "flat energy=$J6 ($FLAT)"
else
  echo "FLAT BASELINE ODB NOT FOUND at /storage/home/zps5207/scratch/ctv/nc/v500star_100 ; listing:"
  ls /storage/home/zps5207/scratch/ctv/nc/ 2>/dev/null | head -30
fi
squeue -u zps5207 -h -o "%i %j %T %M %E"
