#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s1_download_atl03
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --time=02:00:00
# ATL03 download with SlideRule (s1_download_atl03.py); needs internet (Savio compute nodes have it).
# Usage: sbatch sbatch_s1_download_atl03.sh <out.feather> [extra arguments, e.g. --granules G.h5]
# SLENV: Python environment with the SlideRule client (venv or conda env with bin/activate).
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
SLENV=/global/scratch/users/marcomaz/repo_checks/03_ic2_cells_obs_corr/env_sliderule   # venv used for the check
module load anaconda3
unset GDAL_DRIVER_PATH GDAL_DATA PROJ_DATA PROJ_NETWORK   # use the GDAL/PROJ data bundled with the env
source "$SLENV/bin/activate"
python -u "$HERE/s1_download_atl03.py" --out "${1:?output feather}" "${@:2}"
