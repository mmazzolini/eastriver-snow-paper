# 02 - GP model of snow depth and selection of the simulation points

This folder holds the scripts of two steps:

1. A sparse Gaussian-process (GP) model of snow depth on 7 topographic predictors,
   fitted to the ASO lidar snow depth of 2022-04-21 in the East River basin (Colorado).
2. The selection of the 5400 simulation points (50 m cells) used for the forcing and
   the MuSA runs of 2023 and 2024: the 400 inducing points of the GP, snapped to grid
   cells, plus 5 x 1000 cells chosen where the prior variance not explained by the
   points already selected is largest.

The scripts are cleaned copies of the original scripts and notebook cells (see
"Original files"). The computations, libraries, parameters, feature order and
operation order are those of the originals. The checks below compare them with the
files that were used.

## Contents

| File | Purpose |
|---|---|
| `s1_fit_scaler.py` | StandardScaler of the 7 predictors on the 296,799 ASO 2022-04-21 cells (`scaler.save`) |
| `s2_fit_sparse_gp.py` | Sparse GP fit (Matern 5/2 ARD, 300/400/500 inducing points, noise sigma 0.25 fixed, y = log(sd+1)) |
| `s3_save_kernel.py` | Kernel lengthscales and variance of the 400-inducing-point model (`lnscale_-1.npy`, `var_-1.npy`) |
| `s4_select_points.py` | Snapping of the 400 inducing points and 5 rounds of +1000 cells (`indPTS_0..4.npy`, ...); option `--restart-round` |
| `s5_make_points_csv.py` | Back-transform of `indPTS_4.npy` to UTM (EPSG:32613) and lat/lon; points CSV |
| `sbatch_s*.sh` | Slurm wrappers (Savio, account `fc_mgirotto`, partition `savio4_htc`) |
| `requirements_gp.txt` | Pinned package versions (verified in a job, see "Environment") |
| `checks/` | Check scripts and their Slurm wrapper (`sbatch_checks.sh`) |

## Predictors and target

`all_data50from3_1702.nc` is a 50 m grid
(x 809 x y 995, WGS 84 / UTM 13N) with the predictors and the ASO snow depth of
2022-04-21, 2022-05-18, 2023-04-01 and 2024-05-20 (`snow_depth`). The GP uses 7
predictors in this order:

`Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150`

(`Xs`, `Ys`: grid distances in m from the centre of the upper-left cell, x = Xs + 308089,
y = 4322447 - Ys in EPSG:32613; `Zs`: elevation; `slope`; `cosA`: cosine of the aspect;
`TPI150`: topographic position index; `GSAfrac`: annual ground snow-covered area fraction from the
USGS Landsat snow covered area products, Selkowitz et al. 2017). `Sx200, Sx100, sinA, TPI1000, DAH` are in the file but dropped. The training cells are those where the predictors and the ASO snow
depth of 2022-04-21 are defined (296,799 cells); the target is y = log(sd + 1).

The data record holds the 7 predictors of this file (`input_data/GP_predictors/predictors_50m.nc`,
same grid and values) but not the ASO snow depth, which is not redistributed (Airborne Snow
Observatories, Inc.). To rerun s1–s5 from the record, add the ASO snow depth of 2022-04-21 on the
same grid as `snow_depth` with dims `(date, y, x)` and empty `DROP_VARS` in the scripts (the five
unused predictors are not in the record).

All scripts build the data frame with a dummy `n_ind` dimension (a leftover of tests
with several numbers of inducing points): `to_dataframe()` repeats the data along it and
one copy is kept. This does not change any value; it is kept so that the code is the
code that ran.

## Environment

Two environments were used on Savio. The steps ran as follows (from the notebook kernel
specifications, the paths in the original log `pingSel.out`, and the creation date of
`gpy-env`, 2026-03-05):

| Step | Original run | Environment |
|---|---|---|
| s2 | 2025-02-27/28 | A |
| s3, s4 | 2025-08-21/22 | A (notebook kernel `GPy_k`) |
| s5 | 2025-08-22 (`GP_points3.csv`), 2025-10-24 (`GP_points3_B.csv`) | A (notebook kernel `GPy_k`) |
| s1 | 2026-04-23 | B (`gpy-env`) |

**A** - module `anaconda3/2024.02-1-11.4` (the Python of the Jupyter kernel `GPy_k`)
plus user packages in `~/.local/lib/python3.11/site-packages`.
**B** - conda env `gpy-env` (`module load gcc; module load anaconda3; eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env`);
it also imports GPy, paramz, netCDF4, geopandas, pyproj and shapely from `~/.local`
(user site-packages come first on `sys.path`).

Versions printed inside a compute job (`checks/print_versions.py`):

| Package | A: anaconda3/2024.02-1 + ~/.local | B: gpy-env (+ ~/.local) |
|---|---|---|
| Python | 3.11.7 | 3.11.14 |
| numpy | 1.26.4 | 1.26.4 |
| scipy | 1.11.4 | 1.17.1 |
| pandas | 2.1.4 | 3.0.1 |
| xarray | 2023.6.0 (engine netcdf4) | 2026.2.0 |
| netCDF4 | 1.7.2 (~/.local) | 1.7.2 (~/.local) |
| scikit-learn | 1.2.2 | 1.8.0 |
| joblib | 1.2.0 | 1.5.3 |
| GPy | 1.13.2 (~/.local) | 1.13.2 (~/.local; the env's own 1.13.1 is shadowed) |
| paramz | 0.9.6 (~/.local) | 0.9.6 (~/.local) |
| geopandas | 1.0.1 (~/.local) | 1.0.1 (~/.local) |
| pyproj (PROJ) | 3.6.1 (9.3.0) (~/.local) | 3.6.1 (9.3.0) (~/.local) |
| shapely | 2.0.6 (~/.local) | 2.0.6 (~/.local) |

`requirements_gp.txt` pins environment A. `scaler.save` is a scikit-learn 1.8.0 pickle;
see the s1 check for loading it with other versions.

## Run order

Submit from this folder (each wrapper passes its arguments to the script; outputs go
where the arguments say, nothing is written next to the original files):

```bash
P=/path/to/all_data50from3_1702.nc
OUT=/path/to/output
sbatch sbatch_s1_fit_scaler.sh   $P $OUT/scaler.save
sbatch sbatch_s2_fit_sparse_gp.sh $P $OUT/models_MatSel
sbatch sbatch_s3_save_kernel.sh  $P $OUT/models_MatSel/models_noP_Sparse_M52_2022_04_21_nind400.npy $OUT/5500_iter
sbatch sbatch_s4_select_points.sh $P $OUT/models_MatSel/models_noP_Sparse_M52_2022_04_21_nind400.npy $OUT/5500_iter
#   after a failure in round J (indPTS_J.npy written, model_J.npy missing):
#   sbatch sbatch_s4_select_points.sh $P <...nind400.npy> $OUT/5500_iter J
sbatch sbatch_s5_make_points_csv.sh $P $OUT/5500_iter/indPTS_4.npy $OUT
```

Each step needs the output of the previous one (s1 is independent: s2-s5 refit the same
scaler internally, as the originals did). Without arguments the scripts read the
original files on Savio (paths and settings block at the top of each script) and
write to `./output/`.

Notes:
- s2 sets no random seed. GPy starts the inducing inputs from a random subset of the
  cells, so a rerun gives a different local optimum. The original output folder holds
  the 300 and 400 fits (about 5 h and 7 h); there is no file for 500. The 400 fit is
  used downstream.
- s3 and s4 set the noise variance to 0.5^2 before loading the s2 parameters; the
  loaded parameter array overwrites it with the s2 value 0.0625 (= 0.25^2), which is the
  value used for the snapping. The selection models of s4 have a fixed noise variance of
  0.25 (= 0.5^2); in the selection criterion it is a constant.
- s4 needs a large-memory node: the round-4 model allocates several
  296,799 x 5400 float64 arrays (about 12 GiB each; the original run failed allocating
  9.7 GiB for 4400 points).

## Inputs and outputs

| Script | Inputs | Outputs (original location on Savio) |
|---|---|---|
| s1 | `all_data50from3_1702.nc` | `scaler.save` (`/global/scratch/users/marcomaz/GP_models/scaler.save`) |
| s2 | `all_data50from3_1702.nc` | `models_noP_Sparse_M52_2022_04_21_nind{300,400,500}.npy` (`GP_models/models_MatSel/`); GPy `param_array` = inducing inputs (n x 7), kernel variance, 7 lengthscales, noise variance |
| s3 | `all_data50from3_1702.nc`, `..._nind400.npy` | `lnscale_-1.npy`, `var_-1.npy` (`GP_models/5500_iter/`) |
| s4 | `all_data50from3_1702.nc`, `..._nind400.npy`, `lnscale_-1.npy`, `var_-1.npy` | per round j = 0..4: `indPTS_j.npy` (400 + 1000(j+1) points x 7, standardised predictors), `indY_j.npy` (log(sd+1)), `lnscale_j.npy`, `var_j.npy`, `model_j.npy` (`GP_models/5500_iter/`) |
| s5 | `all_data50from3_1702.nc`, `indPTS_4.npy` | `GP_points.csv`, the point file of the downscaling (= `downscali3/inputs/dem/GP_points3.csv`, the point file of the TopoPyScale configuration `downscali3/config_GP2.yml`; rows 0..5399 of `GP_points3_B.csv` hold the same points; columns index, x, y, name, lat, lon) |

## Original files

| Script | Original | What was kept |
|---|---|---|
| s1 | `B/GP4MuSA/IC2_GP_indP_apr24.ipynb` cells 0, 2, 10 (scaler lines), 11 | data frame and scaler fit, `joblib.dump` |
| s2 | `B/GP_sno/100.py` (run from `/global/scratch/users/marcomaz/GP_models`) | all statements of the fit; removed: unused imports (incl. the local module `spM`), host-dependent paths, two unused ICESat-2 tables, commented-out code |
| s3 | `B/GP4MuSA/200_GP_indP.ipynb` cells 0, 2, 4, 7 (model loading), 15, 16 | data, model loading, `np.save` of the kernel |
| s4 | `B/GP4MuSA/200_selINDP.py` (same code as `200_GP_indP.ipynb` cells 0, 2, 4, 7, 9-11, 14, 15, 18, 20, 23); restart: `B/GP4MuSA/200B_selINDP.py` | all statements; removed: unused imports, host-dependent paths, unused plot lines and bounds; added: `--restart-round` |
| s5 | `B/GP4MuSA/sample_forcing.ipynb` cells 0-2, 9, 15, 19, 24, 28-34, 39 | back-transform, UTM shift, lat/lon, CSV (the notebook was later edited for other point sets; the script follows the `indPTS_4.npy` path). The x, y array that cell 19 saves as `indXY_5400.npy` is not written: the file at that path was saved on 2025-08-22 00:31, before `indPTS_4.npy` existed, and holds the older selection (see Checks) |

Superseded files not used here: `B/GP_sno/100_100.py`, `100_200.py`, `3_GP*`,
`10_GPy_dev_GC`, `11_GP_*`, `100_GP_final*`, `101_GP_indP`, `B/GP_sno/200_GP_indP.ipynb`
(older copy), `GP_models/models_MatSel/indPTS_{1400,3400,5400,tmp}.npy`, `indXY_5400.npy`
(conversion of `indPTS_5400.npy`; loaded only by the older forcing script
`B/GP4MuSA/treat_TS_get_ind_pts.py`, commented out in `treat_TSpoints_get_ind_pts23/24.py`)
and related files.

### History of the selection run (s4)

Reconstructed from the file times in `GP_models/5500_iter/`, the log
`B/GP4MuSA/pingSel.out` and the editor's local history of the two scripts
(`~/.local/share/code-server/User/History/`, saved versions of `200_selINDP.py` and
`200B_selINDP.py`):

| Time (Pacific, PDT) | Event |
|---|---|
| 2025-08-21 12:02 | `lnscale_-1.npy`, `var_-1.npy` saved from `200_GP_indP.ipynb` (s3) |
| 2025-08-21 12:19 | last save of `200_selINDP.py` before the run (it adds `n_ind=400`, needed to run) |
| 2025-08-21 12:26 - 20:42 | rounds 0-2 complete (`indPTS_0..2`, `model_0..2`); round-3 points saved (`indPTS_3`, 20:42) |
| 2025-08-21 20:56 | MemoryError while building the round-3 model (array 296,799 x 4400, `pingSel.out`) |
| 2025-08-21 23:55 - 2025-08-22 00:05 | `200B_selINDP.py` created as a copy with `j=3`: snapping commented out, round-3 fit from `indPTS_3` and `lnscale_2`/`var_2`, then the loop for round 4 |
| 2025-08-22 01:55, 02:05 | `lnscale_3`/`var_3`/`model_3`, then `indPTS_4`/`indY_4` |
| 2025-08-22 02:49 | `200B_selINDP.py` changed to `j=4` with the loop commented out (round-4 fit only) |
| 2025-08-22 05:26 | `lnscale_4`/`var_4`/`model_4` |

`s4_select_points.py --restart-round 3` corresponds to the first `200B` run and
`--restart-round 4` to the second (the current `200B_selINDP.py`).

**Edit of `200_selINDP.py` on 2026-01-13.** The editor history has two entries for that
day: at 07:17:03 (PST) line 165 was changed from `GPy.models.SparseGPRegression(...)` to
`GPy.models.GPRegression(...)`, and at 07:17:09 the change was undone (entry marked
"undoRedo"). The current file is byte-identical to the version saved on 2025-08-21
12:19 (the version that ran). The edit has no effect on the code. The line numbers of
the traceback in `pingSel.out` (line 166) also match the current file.

## Checks

Run with `sbatch checks/sbatch_checks.sh [out_dir]` from this folder (job 39883772, outputs
in `/global/scratch/users/marcomaz/repo_checks/02_gp_model_points/`). The GP fit (s2)
and the selection (s4) were not rerun.

| Check | Result |
|---|---|
| s1 rerun in B (`gpy-env`) vs `scaler.save` | identical: feature order `Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150`, `n_samples_seen_` = 296,799, `mean_`, `scale_`, `var_` (max abs diff 0) |
| s1 rerun in A (anaconda3/2024.02-1) vs `scaler.save` | same feature order and cell count; `mean_`, `scale_` differ in the last bit (max abs diff 1.4e-12 / 1.8e-12, max rel diff 4.9e-16 / 2.4e-16). s2-s5 refit the scaler in environment A, as the originals did |
| s2 vs `B/GP_sno/100.py` | `py_compile` OK. AST comparison without comments/docstrings: differences are only the removed unused imports (`socket`, `r2_score`, `matplotlib`, `Pool`, `spM`, `pandas`), the host-dependent paths, the reading and reformatting of `IC2_synt50from3_{23,24}.feather` (not used by the fit), the argparse/paths block and the output path of `np.save`; `sigma_y` and `n_inds` moved to the settings block with the same values. The fit was not rerun |
| s4 vs `B/GP4MuSA/200_selINDP.py` | `py_compile` OK. Differences: removed unused imports, host-dependent paths, `xmin/xmax/ymin/ymax` and the two plot lines; argparse/paths block; `np.load`/`np.save` paths through `ITER_DIR`; the function `compute_gp_prior_variance_vectorized_constant_diag` defined before the snapping instead of after it; snapping and round-0 model inside `if args.restart_round is None:`; `for j in range(first_round, 5)` instead of `range(5)`. The selection was not rerun |
| s4 restart branch vs `B/GP4MuSA/200B_selINDP.py` | the `else:` branch has the same statements as the active code of `200B` (kernel from `lnscale_{j-1}`/`var_{j-1}`, `indPTS_j`/`indY_j`, fixed noise and inducing inputs, `optimize`, saves) |
| s3 rerun vs `lnscale_-1.npy`, `var_-1.npy` | identical (max abs diff 0); lengthscales 2.179, 5.379, 2.196, 3.379, 9.646, 10.691, 29.390; variance 0.4816; noise variance 0.0625 |
| s4 step 1 (snapping) replayed vs `indPTS_0[:400]`, `indY_0[:400]` | identical; 400 distinct cells |
| s4 original outputs | `indPTS_j` has 400 + 1000(j+1) rows and starts with `indPTS_{j-1}` (j = 1..4), same for `indY_j`; `model_j` holds `indPTS_j`, `var_j`, `lnscale_j` and noise variance 0.25 (j = 0..4); all 5400 rows of `indPTS_4` are distinct training cells and `indY_4` is their log(sd+1); the lengthscales printed in `pingSel.out` at the start of rounds 0-3 equal `lnscale_-1..2` (8 decimals) |
| s5 rerun vs `GP_points3.csv` | byte-identical (header + 5400 lines); all columns identical |
| s5 rerun vs `GP_points3_B.csv` rows 0..5399 | index, x, y, name identical; lat differs in 674 rows (max abs diff 7.1e-15 deg), lon in 2022 rows (max 1.4e-14 deg), with floats parsed exactly (`round_trip`); 2446 text lines differ. Environments A and B both give the `GP_points3.csv` values |
| s5 points | all 5400 points are distinct cell centres of the predictors grid |
| `GP_points3_B.csv` rows 5400..5499 | 100 rows (index 0..99) = `IC2indXY_5400.npy` (earlier ICESat-2 cells, not used) |
| original `GP_models/models_MatSel/indXY_5400.npy` | not the s5 points (403 of 5400 rows equal); equal to the conversion of the older selection `models_MatSel/indPTS_5400.npy` (2025-07-08; 554 distinct points) |

Not verified: the GP fit (s2) and the variance-based selection and kernel refits of s4
were not rerun (s2 has no random seed; s4 takes about 13 h on a large-memory node). The
environment that wrote the lat/lon of `GP_points3_B.csv` (2025-10-24) was not
identified.
