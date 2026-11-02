#!/bin/bash
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --job-name=s1_era5
#SBATCH --output=slurm-%x-%j.out
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --time=72:00:00
# ERA5 download for TopoPyScale (s1_download_era5.py). The savio4_htc nodes have outbound
# internet; the CDS key is read by cdsapi from ~/.cdsapirc. In the test the CDS ran the requests
# of one user one after another, about 30 min per month (one SURF + six PLEV requests); rerunning
# the same command skips the months already written.
# Usage: sbatch sbatch_s1_download_era5.sh [config_era5.yml]
set -euo pipefail
HERE=/global/home/users/marcomaz/paper_repo/01_era5_downscaling
export PATH=/global/home/users/marcomaz/miniforge3/envs/downscaling/bin:$PATH
python -u "$HERE/s1_download_era5.py" "${1:-$HERE/config_era5.yml}"
