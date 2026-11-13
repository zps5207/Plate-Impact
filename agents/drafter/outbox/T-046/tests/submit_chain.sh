#!/bin/bash
# Submit chain for T-046 fiber-host interaction tests on ROAR.
# Working directory: /storage/home/zps5207/scratch/ctv/t046/
#
# Sequential dependency chain:
#   Test 1 (fiber alone):     chk1 -> sol1
#   Test 2 (single host):     chk2 -> sol2
#   Test 3 (vuel ghost):      chk3 -> sol3
#   Test 4 (3x3 host block):  chk4 -> sol4
#   Test 5 (mass retention):  chk5 -> sol5
#
# Uses --dependency=afterany so subsequent tests are not skipped if an earlier one fails.
# --export uses commas (values here are not lists).

set -eu

B="/storage/home/zps5207/scratch/ctv/t046"
case "$(readlink -f "$B")" in
  /storage/home/zps5207/scratch/*|/scratch/zps5207/*) ;;
  *) echo "REFUSING: must run under /storage/home/zps5207/scratch (resolved: $(readlink -f "$B"))"; exit 64 ;;
esac

cd "$B"

echo "=== Submitting T-046 Test Suite to ROAR ==="

# Test 1: Single Fiber Alone
C1=$(sbatch --parsable --job-name=t046_chk1 --time=00:10:00 --mem=16G --export=ALL,MODE=datacheck,INP=test1_fiber_alone.inp run_test.sbatch)
S1=$(sbatch --parsable --job-name=t046_sol1 --dependency=afterok:$C1 --time=00:15:00 --mem=16G --export=ALL,MODE=run,INP=test1_fiber_alone.inp run_test.sbatch)

# Test 2: Single Native Host + Fiber
C2=$(sbatch --parsable --job-name=t046_chk2 --dependency=afterany:$S1 --time=00:10:00 --mem=16G --export=ALL,MODE=datacheck,INP=test2_single_host_pull.inp run_test.sbatch)
S2=$(sbatch --parsable --job-name=t046_sol2 --dependency=afterok:$C2 --time=00:15:00 --mem=16G --export=ALL,MODE=run,INP=test2_single_host_pull.inp run_test.sbatch)

# Test 3: Single VUEL + Ghost Host + Fiber
C3=$(sbatch --parsable --job-name=t046_chk3 --dependency=afterany:$S2 --time=00:10:00 --mem=16G --export=ALL,MODE=datacheck,INP=test3_vuel_ghost_pull.inp run_test.sbatch)
S3=$(sbatch --parsable --job-name=t046_sol3 --dependency=afterok:$C3 --time=00:15:00 --mem=16G --export=ALL,MODE=run,INP=test3_vuel_ghost_pull.inp run_test.sbatch)

# Test 4: 3x3 Host Block + Fiber Tow
C4=$(sbatch --parsable --job-name=t046_chk4 --dependency=afterany:$S3 --time=00:10:00 --mem=16G --export=ALL,MODE=datacheck,INP=test4_block_3x3_pull.inp run_test.sbatch)
S4=$(sbatch --parsable --job-name=t046_sol4 --dependency=afterok:$C4 --time=00:20:00 --mem=16G --export=ALL,MODE=run,INP=test4_block_3x3_pull.inp run_test.sbatch)

# Test 5: Mass Retention Verification
C5=$(sbatch --parsable --job-name=t046_chk5 --dependency=afterany:$S4 --time=00:10:00 --mem=16G --export=ALL,MODE=datacheck,INP=test5_mass_conservation.inp run_test.sbatch)
S5=$(sbatch --parsable --job-name=t046_sol5 --dependency=afterok:$C5 --time=00:15:00 --mem=16G --export=ALL,MODE=run,INP=test5_mass_conservation.inp run_test.sbatch)

echo "Jobs submitted successfully:"
echo "  Test 1: chk=$C1 sol=$S1"
echo "  Test 2: chk=$C2 sol=$S2"
echo "  Test 3: chk=$C3 sol=$S3"
echo "  Test 4: chk=$C4 sol=$S4"
echo "  Test 5: chk=$C5 sol=$S5"
echo ""
echo "Monitor queue with: squeue -u zps5207 -h -o '%i %j %T %M %E'"
