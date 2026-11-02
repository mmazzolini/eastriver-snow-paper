#!/bin/bash
#SBATCH --job-name=s3_check
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=slurm-%x-%j.out
# Checks of the MuSA forcing of one water year (s3_check_forcing.py); exit code 1 on failure.
# Usage (from 04_forcing): sbatch sbatch_s3_check_forcing.sh <yy> [--forcing-dir D --fig FILE.png]
# Python: the downscaling environment (PYENV = its folder).
set -euo pipefail
yy=${1:?usage: sbatch sbatch_s3_check_forcing.sh <yy> [options]}
shift
export PATH=${PYENV:-/global/home/users/marcomaz/miniforge3/envs/downscaling}/bin:$PATH
cd "${SLURM_SUBMIT_DIR}"
python -u s3_check_forcing.py --year "$yy" "$@"
