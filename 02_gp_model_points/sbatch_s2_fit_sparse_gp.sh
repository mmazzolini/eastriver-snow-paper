#!/bin/bash
#SBATCH --job-name=gp_s2_fit
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=72:00:00
#SBATCH --output=slurm-%x-%j.out
# Runs s2_fit_sparse_gp.py (sparse GP fits with 300, 400, 500 inducing points; in the original run the 300 and 400 fits took about 5 h and 7 h).
# Usage (from this folder): sbatch sbatch_s2_fit_sparse_gp.sh <all_data50from3_1702.nc> <model_dir>
set -eo pipefail
module purge
module load anaconda3/2024.02-1-11.4   # Python 3.11.7; GPy, paramz, netCDF4, geopandas, pyproj come from ~/.local/lib/python3.11
cd "${SLURM_SUBMIT_DIR}"
which python
python -u s2_fit_sparse_gp.py --predictors "$1" --model-dir "$2"
