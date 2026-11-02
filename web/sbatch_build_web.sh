#!/bin/bash
#SBATCH --job-name=build_web
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/global/scratch/users/marcomaz/web_logs/slurm-%x-%j.out
# Builds the website data files (web/build_web_data.py) into $WEB_OUT (default /global/scratch/users/marcomaz/web_data).
set -euo pipefail
module load gcc
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env
export OMP_NUM_THREADS=4
cd "$(dirname "$0")" 2>/dev/null || cd /global/home/users/marcomaz/paper_repo/web
python -u /global/home/users/marcomaz/paper_repo/web/build_web_data.py
