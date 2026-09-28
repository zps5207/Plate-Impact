#!/bin/bash
# TODO: fill ROAR account, partition, Abaqus module/license settings.
#SBATCH --job-name=embmesh-vumat
#SBATCH --time=00:10:00
module load anaconda/2023.09
module load abaqus
module load intel
abaqus job=tension input=vumat/samples/tension.inp user=vumat/VUMAT_tension_only.for interactive

