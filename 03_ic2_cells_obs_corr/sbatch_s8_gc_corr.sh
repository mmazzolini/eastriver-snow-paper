#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s8_gc_corr
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 16
#SBATCH --time=01:00:00
# Gaspari-Cohn correlation fields (s8_gc_corr.py).
# Usage: sbatch sbatch_s8_gc_corr.sh <points dir> <out dir> [--years 23 24] [--recipe-check]
set -eo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load anaconda3; source activate base; source activate MuSAenv
set -u
python -u "$HERE/s8_gc_corr.py" --points "${1:?points dir}" --out "${2:?output dir}" "${@:3}"
