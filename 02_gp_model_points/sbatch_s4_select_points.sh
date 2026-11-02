#!/bin/bash
#SBATCH --job-name=gp_s4_select
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=56
#SBATCH --mem=500G
#SBATCH --time=72:00:00
#SBATCH --output=slurm-%x-%j.out
# Runs s4_select_points.py (5400 points; about 13 h of computing in the original runs, which ran out of memory at 4400 points).
# Usage (from this folder): sbatch sbatch_s4_select_points.sh <all_data50from3_1702.nc> <models_..._nind400.npy> <iter_dir> [restart_round]
set -eo pipefail
module purge
module load anaconda3/2024.02-1-11.4   # Python 3.11.7; GPy, paramz, netCDF4, geopandas, pyproj come from ~/.local/lib/python3.11
cd "${SLURM_SUBMIT_DIR}"
which python
if [ -n "$4" ]; then RESTART=(--restart-round "$4"); else RESTART=(); fi
python -u s4_select_points.py --predictors "$1" --model "$2" --iter-dir "$3" "${RESTART[@]}"
