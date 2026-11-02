#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s2_ic2_synth3
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --time=24:00:00
# Synthetic IC2 snow depth at 3 m (s2_ic2_synth3.py).
# Usage: sbatch sbatch_s2_ic2_synth3.sh <ASO date YYYY-MM-DD> <output feather>
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base      # environment of the original notebook
python -u "$HERE/s2_ic2_synth3.py" --aso-date "${1:?ASO date}" --out "${2:?output feather}"
