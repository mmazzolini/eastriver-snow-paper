#!/bin/bash
#SBATCH --job-name=map21_NP
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=330G
#SBATCH --time=06:00:00
#SBATCH --array=0-7
#SBATCH --output=slurm-%x-%A_%a.out
#SBATCH --error=slurm-%x-%A_%a.err
# Mapping of the ensembles to the 50 m grid (21_maptogrid_NP.py), one task per (run, prior|posterior):
# 0/1 23GP prior/posterior, 2/3 24GP, 4/5 23GC, 6/7 24GC. ~1-1.5 h per task with 4 workers.
# Usage (from 06_postprocessing): sbatch sbatch_21_maptogrid_NP.sh [--members 0,1] [--out-dir DIR]
set -euo pipefail
echo "[$(date '+%F %T')] START job=${SLURM_JOB_ID} task=${SLURM_ARRAY_TASK_ID} host=$(hostname)"

module load gcc
module load anaconda3
eval "$(conda shell.bash hook)"
conda activate base
conda activate gpy-env

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MUSA_POST_NWORKERS=4

cd "${SLURM_SUBMIT_DIR}"
python -u 21_maptogrid_NP.py "${SLURM_ARRAY_TASK_ID}" "$@"

echo "[$(date '+%F %T')] END job=${SLURM_JOB_ID} task=${SLURM_ARRAY_TASK_ID}"
