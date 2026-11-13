#!/bin/bash
#SBATCH --account=rhk12_cr_default
#SBATCH --job-name=ex_triax
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=run_ex_triax_%j.out

set -u
real_submit_dir=$(readlink -f "$SLURM_SUBMIT_DIR")
echo "host: $(hostname)  date: $(date)  dir: $real_submit_dir"

module load anaconda/2023.09
module load abaqus
cd "$SLURM_SUBMIT_DIR"

# 1. Native 0-70 us ODB
if [ -f "nv3_native.odb" ]; then
    echo "--- Extracting triaxiality from nv3_native.odb ---"
    abaqus python extract_triaxiality_odb.py nv3_native.odb nv3_native_triaxiality.json --step Step-1
    echo "nv3_native rc=$?"
fi

# 2. Native 70-100 us restart ODB
if [ -f "nv3_native_r.odb" ]; then
    echo "--- Extracting triaxiality from nv3_native_r.odb ---"
    abaqus python extract_triaxiality_odb.py nv3_native_r.odb nv3_native_r_triaxiality.json --step Step-2
    echo "nv3_native_r rc=$?"
fi

# 3. VUEL 0-70 us ODB (if present)
if [ -f "nv3_vuel.odb" ]; then
    echo "--- Extracting triaxiality from nv3_vuel.odb ---"
    abaqus python extract_triaxiality_odb.py nv3_vuel.odb nv3_vuel_triaxiality.json --step Step-1
    echo "nv3_vuel rc=$?"
fi

# 4. VUEL 70-100 us restart ODB (if present)
if [ -f "nv3_vuel_r.odb" ]; then
    echo "--- Extracting triaxiality from nv3_vuel_r.odb ---"
    abaqus python extract_triaxiality_odb.py nv3_vuel_r.odb nv3_vuel_r_triaxiality.json --step Step-2
    echo "nv3_vuel_r rc=$?"
fi

echo "Done: $(date)"
