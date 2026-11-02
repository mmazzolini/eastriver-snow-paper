#!/bin/bash
#SBATCH --job-name=check_core
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/global/scratch/users/marcomaz/web_logs/slurm-%x-%j.out
# Checks docs/js/core.js against the notebook reference (web/check_core.mjs). Needs Node.js >= 18
# (here a conda env: conda create -p <env> -c conda-forge nodejs=20).
set -euo pipefail
/global/scratch/users/marcomaz/webtools/nodeenv/bin/node /global/home/users/marcomaz/paper_repo/web/check_core.mjs "${1:-/global/scratch/users/marcomaz/web_data/}"
