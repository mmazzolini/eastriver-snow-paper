#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio3
#SBATCH --job-name=s3_down_ic2
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH --time=06:00:00
# TopoPyScale downscaling of ERA5 to the 400 IC2 cells of one year (s3_downscale_ic2_cells.py).
# Usage: sbatch sbatch_s3_downscale_ic2_cells.sh <project dir>
#   e.g. sbatch sbatch_s3_downscale_ic2_cells.sh /global/scratch/users/marcomaz/downscaliNP23
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/01_era5_downscaling
export PATH=/global/home/users/marcomaz/miniforge3/envs/downscaling/bin:$PATH
echo "PROJECT=${1:?project dir}"
python -u "$HERE/s3_downscale_ic2_cells.py" "$1"
