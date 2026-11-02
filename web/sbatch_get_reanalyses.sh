#!/bin/bash
#SBATCH --job-name=get_rean
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/global/scratch/users/marcomaz/web_logs/slurm-%x-%j.out
# Downloads SNODAS, UA 800 m and WLDAS for the two survey dates (web/get_reanalyses.py).
set -euo pipefail
module load gcc
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env
python -u /global/home/users/marcomaz/paper_repo/web/get_reanalyses.py
