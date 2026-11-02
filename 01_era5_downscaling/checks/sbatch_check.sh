#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=r01_check
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --time=01:00:00
# Runs one of the check scripts of this folder on a compute node.
# Usage: sbatch sbatch_check.sh <check script> [arguments]
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/01_era5_downscaling/checks
export PATH=/global/home/users/marcomaz/miniforge3/envs/downscaling/bin:$PATH
SCRIPT=${1:?check script}; shift
python -u "$HERE/$SCRIPT" "$@"
