#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s3_ic2_to_50m
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --time=01:00:00
# Synthetic IC2 snow depth at 50 m (s3_ic2_to_50m.py).
# Usage: sbatch sbatch_s3_ic2_to_50m.sh <3 m feather> <output 50 m feather>
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load gcc; module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env
python -u "$HERE/s3_ic2_to_50m.py" --in "${1:?3 m feather}" --out "${2:?output feather}"
