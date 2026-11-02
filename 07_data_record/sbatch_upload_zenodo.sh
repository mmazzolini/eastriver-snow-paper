#!/bin/bash
#SBATCH --job-name=upload_zenodo
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=/global/scratch/users/marcomaz/web_logs/slurm-%x-%j.out
# Uploads the packed data record to a Zenodo draft (upload_zenodo.py; it never publishes).
# The token comes from the environment of the submitting shell (sbatch exports it by default):
#   export ZENODO_TOKEN=...; sbatch 07_data_record/sbatch_upload_zenodo.sh [--deposition ID] [--sandbox] [--dry-run]
set -euo pipefail
if [ -z "${ZENODO_TOKEN:-}" ] && [[ " $* " != *" --dry-run "* ]]; then
    echo "ZENODO_TOKEN is not set: export it in the shell that runs sbatch" >&2
    exit 1
fi
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env
python -u /global/home/users/marcomaz/paper_repo/07_data_record/upload_zenodo.py "$@"
