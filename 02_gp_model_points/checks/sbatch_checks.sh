#!/bin/bash
#SBATCH --job-name=gp02_checks
#SBATCH --account=fc_mgirotto
#SBATCH --partition=savio4_htc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=03:00:00
#SBATCH --output=slurm-%x-%j.out
# Runs the checks of 02_gp_model_points against the files used in the paper:
# s1 (in gpy-env and in anaconda3/2024.02-1), s3 and s5 are rerun into OUT and compared
# with the originals; s2 and s4 are compared as code (ast diff) and the original
# outputs of s4 are checked for consistency (no rerun of the GP fit or of the selection).
# Usage (from 02_gp_model_points): sbatch checks/sbatch_checks.sh [out_dir]
set -eo pipefail

# ---- paths and settings (original files on Savio) ----------------------------
S=/global/scratch/users/marcomaz
B=/global/home/users/marcomaz/B
PRED=$S/all_data50from3_1702.nc
MODEL400=$S/GP_models/models_MatSel/models_noP_Sparse_M52_2022_04_21_nind400.npy
ITER=$S/GP_models/5500_iter
SCALER=$S/GP_models/scaler.save
CSV_B=$S/downscali3/inputs/dem/GP_points3_B.csv
CSV_3=$S/downscali3/inputs/dem/GP_points3.csv
XY=$S/GP_models/models_MatSel/indXY_5400.npy
XY_IC2=$S/GP_models/models_MatSel/IC2indXY_5400.npy
PTS_OLD=$S/GP_models/models_MatSel/indPTS_5400.npy   # older selection (July 2025)
OUT=${1:-$S/repo_checks/02_gp_model_points}

cd "${SLURM_SUBMIT_DIR}"
mkdir -p "$OUT"/s1 "$OUT"/s3 "$OUT"/s5

env_a() { module purge; module load anaconda3/2024.02-1-11.4; }
env_b() { module purge; module load gcc; module load anaconda3; eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env; }

echo "######## versions: anaconda3/2024.02-1 + ~/.local"
( env_a; python -u checks/print_versions.py )
echo "######## versions: gpy-env"
( env_b; python -u checks/print_versions.py )

echo "######## s1 in gpy-env and in anaconda3/2024.02-1"
( env_b; python -u s1_fit_scaler.py --predictors "$PRED" --out "$OUT"/s1/scaler_gpyenv.save )
( env_a; python -u s1_fit_scaler.py --predictors "$PRED" --out "$OUT"/s1/scaler_anaconda2024.save )
( env_b; python -u checks/check_s1_scaler.py "$SCALER" "$OUT"/s1/scaler_gpyenv.save "$OUT"/s1/scaler_anaconda2024.save )

echo "######## code diff s2 / s4 (+ py_compile)"
( env_a; python -u checks/check_code_diff.py \
    $B/GP_sno/100.py s2_fit_sparse_gp.py \
    $B/GP4MuSA/200_selINDP.py s4_select_points.py \
    $B/GP4MuSA/200B_selINDP.py s4_select_points.py )

echo "######## s3"
( env_a; python -u s3_save_kernel.py --predictors "$PRED" --model "$MODEL400" --out-dir "$OUT"/s3 )
( env_a; python -u checks/check_s3_kernel.py "$ITER" "$OUT"/s3 )

echo "######## s5"
( env_a; python -u s5_make_points_csv.py --predictors "$PRED" --points "$ITER"/indPTS_4.npy --out-dir "$OUT"/s5 )
( env_a; python -u checks/check_s5_points.py "$OUT"/s5 "$CSV_B" "$CSV_3" "$XY_IC2" "$XY" "$PTS_OLD" "$PRED" )

echo "######## s4 original outputs"
( env_a; python -u checks/check_s4_outputs.py "$PRED" "$MODEL400" "$ITER" $B/GP4MuSA/pingSel.out )
echo "######## done"
