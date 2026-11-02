#!/bin/bash
#SBATCH --job-name=gp_s5_csv
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=slurm-%x-%j.out
# Runs s5_make_points_csv.py (UTM and lat/lon CSV of the 5400 points).
# Usage (from this folder): sbatch sbatch_s5_make_points_csv.sh <all_data50from3_1702.nc> <indPTS_4.npy> <out_dir>
set -eo pipefail
module purge
module load anaconda3/2024.02-1-11.4   # Python 3.11.7; GPy, paramz, netCDF4, geopandas, pyproj come from ~/.local/lib/python3.11
cd "${SLURM_SUBMIT_DIR}"
which python
python -u s5_make_points_csv.py --predictors "$1" --points "$2" --out-dir "$3"
