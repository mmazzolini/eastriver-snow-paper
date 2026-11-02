#!/bin/bash
#SBATCH --job-name=s2_forcing
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%x-%j.out
# IC2-cell (x = 1) forcing joined with the model cells (s2_forcing_ic2_cells.py).
# Usage (from 04_forcing): sbatch sbatch_s2_forcing_ic2_cells.sh <yy> [--x0-dir D0 --out1-dir D1 --out-dir D]
# Python: the downscaling environment (PYENV = its folder).
set -euo pipefail
yy=${1:?usage: sbatch sbatch_s2_forcing_ic2_cells.sh <yy> [options]}
shift
export PATH=${PYENV:-/global/home/users/marcomaz/miniforge3/envs/downscaling}/bin:$PATH
cd "${SLURM_SUBMIT_DIR}"
python -u s2_forcing_ic2_cells.py --year "$yy" "$@"
