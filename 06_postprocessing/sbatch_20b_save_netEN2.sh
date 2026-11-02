#!/bin/bash
#SBATCH --job-name=save_netEN
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=30
#SBATCH --mem=150G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
# MuSA prior ensembles of one run -> En_snd<yy>_Pr.nc (20b_save_netEN.py --prior).
# Usage (from 06_postprocessing): export MUSA_DIR=<MuSA folder>/ MUSA_POST_OUTDIR=<run>; sbatch sbatch_20b_save_netEN2.sh
# Called this way by eastriver/run_experiment.sh of the MuSA repository (POSTPROC_DIR = this folder).
set -euo pipefail
: "${MUSA_DIR:?set MUSA_DIR}" "${MUSA_POST_OUTDIR:?set MUSA_POST_OUTDIR}"

module load gcc
module load anaconda3
source activate base
source activate MuSAenv

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MUSA_POST_NWORKERS=${SLURM_CPUS_PER_TASK}

cd "${SLURM_SUBMIT_DIR}"
python -u 20b_save_netEN.py --prior
