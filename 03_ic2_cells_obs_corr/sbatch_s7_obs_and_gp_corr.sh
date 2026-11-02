#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s7_obs_gp_corr
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --time=01:00:00
# Observation files and GP correlation (s7_obs_and_gp_corr.py).
# Usage: sbatch sbatch_s7_obs_and_gp_corr.sh <points dir> <out dir> [--years 23 24] [--skip-corr]
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load gcc; module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env
python -u "$HERE/s7_obs_and_gp_corr.py" --points "${1:?points dir}" --out "${2:?output dir}" "${@:3}"
