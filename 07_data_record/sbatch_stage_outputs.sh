#!/bin/bash
#SBATCH --job-name=stage_zenodo
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=03:00:00
#SBATCH --output=/global/scratch/users/marcomaz/web_logs/slurm-%x-%j.out
# Stages the Zenodo data record as a folder tree (stage_outputs.py) and packs it into the upload files (pack_record.py).
set -euo pipefail
module load gcc
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env
python -u /global/home/users/marcomaz/paper_repo/07_data_record/stage_outputs.py
python -u /global/home/users/marcomaz/paper_repo/07_data_record/pack_record.py
