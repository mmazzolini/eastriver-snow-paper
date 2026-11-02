#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio3
#SBATCH --job-name=s2_down_pts
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH --time=48:00:00
# TopoPyScale downscaling of ERA5 to the 5400 model points (s2_downscale_model_points.py).
# Usage: sbatch sbatch_s2_downscale_model_points.sh <project dir> [first last]
#   e.g. points 0..9 only: sbatch sbatch_s2_downscale_model_points.sh <project dir> 0 10
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/01_era5_downscaling
export PATH=/global/home/users/marcomaz/miniforge3/envs/downscaling/bin:$PATH
PROJECT=${1:?project dir}
RANGE=()
if [ $# -ge 3 ]; then RANGE=(--first "$2" --last "$3"); fi
python -u "$HERE/s2_downscale_model_points.py" "$PROJECT" "${RANGE[@]}"
