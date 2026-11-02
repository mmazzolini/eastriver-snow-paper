#!/bin/bash
#SBATCH --job-name=gp_s3_kernel
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=slurm-%x-%j.out
# Runs s3_save_kernel.py (kernel lengthscales and variance of the 400-inducing-point model).
# Usage (from this folder): sbatch sbatch_s3_save_kernel.sh <all_data50from3_1702.nc> <models_..._nind400.npy> <iter_dir>
set -eo pipefail
module purge
module load anaconda3/2024.02-1-11.4   # Python 3.11.7; GPy, paramz, netCDF4, geopandas, pyproj come from ~/.local/lib/python3.11
cd "${SLURM_SUBMIT_DIR}"
which python
python -u s3_save_kernel.py --predictors "$1" --model "$2" --out-dir "$3"
