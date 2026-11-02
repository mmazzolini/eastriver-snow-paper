#!/bin/bash
#SBATCH --job-name=s1_forcing
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%x-%j.out
# Model-cell (x = 0) forcing of one water year (s1_forcing_model_cells.py).
# Usage (from 04_forcing): sbatch sbatch_s1_forcing_model_cells.sh <yy> [--out-dir DIR]
# Python: the downscaling environment (PYENV = its folder).
set -euo pipefail
yy=${1:?usage: sbatch sbatch_s1_forcing_model_cells.sh <yy> [--out-dir DIR]}
shift
export PATH=${PYENV:-/global/home/users/marcomaz/miniforge3/envs/downscaling}/bin:$PATH
# numpy without its AVX-512 exp: the RH of the x = 0 files used in the paper equals the scalar
# (libm) exp; numpy's AVX-512 exp differs by up to 6e-14 % RH in ~17 % of the values.
export NPY_DISABLE_CPU_FEATURES="AVX512F AVX512CD AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL"
cd "${SLURM_SUBMIT_DIR}"
python -u s1_forcing_model_cells.py --year "$yy" "$@"
