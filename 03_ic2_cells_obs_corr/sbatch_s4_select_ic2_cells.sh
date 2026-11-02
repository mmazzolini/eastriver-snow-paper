#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s4_select_ic2
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --time=01:00:00
# Selection of the 400 IC2 cells (s4_select_ic2_cells.py).
# Usage: sbatch sbatch_s4_select_ic2_cells.sh <year 23|24> <output dir>
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load gcc; module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env
python -u "$HERE/s4_select_ic2_cells.py" "${1:?year}" "${2:?output dir}"
