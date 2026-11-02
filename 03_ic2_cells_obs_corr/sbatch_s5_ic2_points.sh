#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s5_ic2_points
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --time=00:20:00
# Point lists of the selected IC2 cells (s5_ic2_points.py), with the DEM check.
# Usage: sbatch sbatch_s5_ic2_points.sh <dir with IC2sel_<yr>_B_K30.npz> <output dir>
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/03_ic2_cells_obs_corr
module load gcc; module load anaconda3
eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env
python -u "$HERE/s5_ic2_points.py" --sel "${1:?selection dir}" --out "${2:?output dir}" --topo
