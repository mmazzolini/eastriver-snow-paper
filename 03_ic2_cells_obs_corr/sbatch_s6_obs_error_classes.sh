#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s6_obs_error
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --time=00:20:00
# Observation error classes (s6_obs_error_classes.py). Usage: sbatch sbatch_s6_obs_error_classes.sh
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load gcc; module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env
python -u "$HERE/s6_obs_error_classes.py"
