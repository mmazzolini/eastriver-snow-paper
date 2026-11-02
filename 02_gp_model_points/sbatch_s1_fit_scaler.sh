#!/bin/bash
#SBATCH --job-name=gp_s1_scaler
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=slurm-%x-%j.out
# Runs s1_fit_scaler.py (StandardScaler of the 7 predictors) in the conda env gpy-env.
# Usage (from this folder): sbatch sbatch_s1_fit_scaler.sh <all_data50from3_1702.nc> <out_file>
set -eo pipefail
module purge
module load gcc
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env                 # Python 3.11.14, scikit-learn 1.8.0
cd "${SLURM_SUBMIT_DIR}"
which python
python -u s1_fit_scaler.py --predictors "$1" --out "$2"
