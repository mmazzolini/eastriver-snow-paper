# 03 – ICESat-2 cells, observations and prior correlation

Scripts that produce the ICESat-2 (IC2) observations assimilated by MuSA in the East
River basin (Colorado) for 2023 and 2024, and the prior correlation fields used to draw
the correlated prior and to localise the update:

1. ATL03 photon download with SlideRule (YAPC photon scores).
2. Synthetic IC2 snow depth: ASO lidar snow depth sampled at the IC2 photon positions
   on the 3 m grid, then aggregated to the 50 m model grid.
3. Selection of the 400 observed IC2 cells per year ("B_K30" selection).
4. Point lists of the selected cells, observation error classes, MuSA observation files.
5. Prior correlation fields: GP (Matern 5/2) and Gaspari–Cohn (GC).

Both years use the photon positions of the 2023-04-01 overpass (rgt 173); only the ASO
date of the sampled snow depth changes: 2023-04-01 for 2023, 2024-04-03 (observation)
and 2024-05-20 (GP fit in the cell selection) for 2024.

## Environments (Savio)

| Name | Activation | Used by |
|---|---|---|
| SlideRule venv | `module load anaconda3; python -m venv <dir>; source <dir>/bin/activate; pip install sliderule geopandas pyarrow` (check: sliderule 5.6.3, Python 3.11; set `SLENV` in `sbatch_s1_download_atl03.sh`) | s1 |
| anaconda3 base | `module load anaconda3; eval "$(conda shell.bash hook)"; conda activate base` | s2 |
| gpy-env | `module load gcc; module load anaconda3; eval "$(conda shell.bash hook)"; conda activate base; conda activate gpy-env` (GPy 1.13.2, paramz, netCDF4 from `~/.local`) | s3–s7 |
| MuSAenv | `module load anaconda3; source activate base; source activate MuSAenv` | s8 |

The original download notebook ran with a kernel `sliderule_k` whose environment
(`~/.conda/envs/sliderule_env`, Python 3.12) no longer exists; its client version is
not recorded. All other scripts run on compute nodes (`sbatch`, account `fc_mgirotto`,
partition `savio4_htc`); every script has an `sbatch_*.sh` wrapper in this folder.

## Run order

`S=/global/scratch/users/marcomaz`. Output arguments are required (no script writes to
the original data folders by default).

| Step | Command | Time |
|---|---|---|
| s1 | `sbatch sbatch_s1_download_atl03.sh <ATL03_yapc.feather>` | a few minutes for the 2023-03-31 granule (check); the 2023-04-01 granule is ~40 times larger. Needs internet (Savio compute nodes have it) |
| s2 | `sbatch sbatch_s2_ic2_synth3.sh 2023-04-01 <IC2_synt3_.feather>`; same with `2024-05-20 <IC2_synt3_24.feather>` and `2024-04-03 <IC2_synt3_24_new.feather>` | ~2 h each |
| s3 | `sbatch sbatch_s3_ic2_to_50m.sh <3 m feather> <50 m feather>` for the pairs `IC2_synt3_` → `IC2_synt50from3_23`, `IC2_synt3_24` → `IC2_synt50from3_24`, `IC2_synt3_24_new` → `IC2_synt50from3_24april` | < 1 min |
| s4 | `sbatch sbatch_s4_select_ic2_cells.sh 23 <sel dir>`; same with `24` | ~2–3 min per year |
| s5 | `sbatch sbatch_s5_ic2_points.sh <sel dir> <points dir>` | < 1 min |
| s6 | `sbatch sbatch_s6_obs_error_classes.sh` (prints the error classes) | < 1 min |
| s7 | `sbatch sbatch_s7_obs_and_gp_corr.sh <points dir> <data dir>` | ~2 min |
| s8 | `sbatch sbatch_s8_gc_corr.sh <points dir> <data dir> [--recipe-check]` | < 1 min per year |

Fixed inputs (GP model files, terrain stacks) are set in the "paths and settings" block
of each script and point to `$S`. Outputs of earlier steps are passed as arguments to
s3, s5, s7 and s8; s2 (`ATL03_FEATHER`), s4 (`FEATHER`, `FEATHER_APR24`) and s6
(`FEATHER_23`) read them from the paths in their settings block.

## Inputs from outside this folder

| File | Content | Used by |
|---|---|---|
| `/global/home/groups/fc_mgirotto/East_River_Data/shp/eastriver.shp` | basin outline (bounding box only) | s1 |
| `$S/all_data3_new.nc` | 3 m stack: terrain variables and ASO snow depth of 2022-04-21, 2022-05-18, 2023-04-01, 2024-04-03, 2024-05-20 (the 2024-04-03 layer was appended in `B/GP_sno/0_IC2_synth3.ipynb` cell 3) | s2 |
| `$S/all_data50from3_1702.nc` | 50 m stack (x, y, Xs, Ys) | s3 |
| `$S/all_data50from3_1105.nc` | 50 m stack (Zs), point check only | s5 `--topo` |
| `$S/GP_models/scaler.save` | StandardScaler of the 7 GP features (Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150) | s4–s7 |
| `$S/GP_models/5500_iter/{lnscale_4,var_4,indPTS_4}.npy` | GP kernel of the model cells and the 5400 model cells (scaled features) | s4, s7, s8 |
| `$S/GP_models/models_MatSel/lengthscales_noP_Sparse_M52_2022_04_21_nind5400.npy` | length scales of the stage-0 sparse GP | s4, s6 |
| `$S/GP_models/models_MatSel/IC2_kern5400_<yr>_400.npy`, `$S/DATA_GP5400_400/Corr<yr>/rhoGC1.npy` | earlier IC2 cells and GC field | s8 `--recipe-check` only |

## Outputs

| Step | File(s) | Location of the files used |
|---|---|---|
| s1 | ATL03 photons (feather, index time, x/y in EPSG:32613) | `/global/home/groups/fc_mgirotto/East_River_Data/IS2/ATL03_yapc.feather` |
| s2 | 3 m synthetic IC2 (308 869 rows) | `$S/IC2_synt3_.feather` (ASO 2023-04-01), `$S/IC2_synt3_24.feather` (2024-05-20), `$S/IC2_synt3_24_new.feather` (2024-04-03) |
| s3 | 50 m synthetic IC2 (5977 rows, median/std columns, Xs, Ys) | `$S/IC2_synt50from3_23.feather`, `_24.feather`, `_24april.feather` |
| s4 | candidates and the 400 selected cells | `$S/GP_models/IC2sel/IC2cand_<yr>.npz`, `IC2sel_<yr>_B_K30.npz` |
| s5 | `IC2NP_<yr>.csv` (x, y, name, lat, lon), `IC2NP_<yr>_X.npy` (scaled features), `IC2NP_<yr>_Y.npy` (log(sd+1)) | `$S/DATA_NP/points/` |
| s6 | printed values 0.37 / 0.84 / 1.40 m | – |
| s7 | `Obs23/IC2_23-04-01.nc`, `Obs23_var/IC2_23-04-01_var.nc`, `Obs24/IC2_24-04-03.nc`, `Obs24_var/IC2_24-04-03_var.nc`; `Corr<yr>/Corr.npy`, `Orderows.npy`, `DistMask_05.npy`, symlink `DistMaskGP_05.npy` | `$S/DATA_NP/` |
| s8 | `Corr<yr>/rhoGC1.npy`, `DistMaskGC_05.npy` | `$S/DATA_NP/` |

Observation files: dimensions time 1, y 5400, x 2; float32 `snow_depth` and `sd`, fill
-9999; the 400 IC2 cells are at y = 0–399, x = 1 (row i of the selection = point name i).
`sd` holds 0.37 / 0.84 / 1.40 m by slope class (< 10°, 10–40°, > 40°); the `_var` files
hold sd², which is how MuSA reads the field (as a variance). Correlation files are
10800 × 10800 float64 (~0.9 GB each): rows 0–5399 are the model cells, rows 5400–5799
the observed cells, the remaining rows are padding (NaN in `Corr.npy`, 0 in `rhoGC1.npy`).
The MuSA masks of DATA_NP (`mask/mask.nc`, `mask_repr.nc`) were copied by the original
`np_obs_corr.py` from `DATA_GP5400_400/mask/`; that copy is not part of this folder.

## Original files

| Script | Original | Notes |
|---|---|---|
| `s1_download_atl03.py` | `B/ICESat-2/B_IS2_download.ipynb` cells 1–2, 4, 6, 9, 12, 14, 18–19 | Notebook ran outside Savio. Its last saved settings (2022-11-01 to 2023-06-01, 8 granules, ATL08 class ground only, output `ATL03_winter_yapc.feather`) differ from the content of the file used (2 granules, ATL08 classes 0–4); the script defaults follow the file used. Granules given by name (CMR no longer lists release 006). YAPC `version=3` set explicitly (see Checks). |
| `s2_ic2_synth3.py` | `B/GP_sno/0_IC2_synth3.py` (= `0_IC2_synth3.ipynb` cells 0–1, 4–5, 7, 9, 11, 13–15) | ASO date and output as arguments; `.values` added to the grid-origin subtraction (the original expression fails with the pandas/xarray of gpy-env; numbers unchanged); unused imports removed. |
| `s3_ic2_to_50m.py` | `B/GP_sno/20_IC2_synth3vsAllData.ipynb` cells 0, 36, 39–43 | input/output as arguments. |
| `s4_select_ic2_cells.py` | `B/GP4MuSA/IC2_selINDP.py` + `sbatch_IC2_selINDP.sh` | B_K30 only (the variants A_K10/30/100 and old400 are not computed); year as argument instead of the `YEAR` environment variable. |
| `s5_ic2_points.py` | `B/GP4MuSA/NP/np_points.py` | comparison with the earlier point lists removed. |
| `s6_obs_error_classes.py` | `B/GP4MuSA/IC2_GP_indP.ipynb` cells 0, 5, 8, 11–13, 19, 22–28 | NMAD values (0.39, 0.6·1.48, 1.48 m) and n = 11 as entered in the notebook. |
| `s7_obs_and_gp_corr.py` | `B/GP4MuSA/NP/np_obs_corr.py` + `NP/sbatch_np_py.sh` | The original copied the `DATA_GP5400_400/Obs*` files as templates and replaced the values; the script writes the same layout directly (no template needed). Mask copy and comparisons with the earlier data removed. |
| `s8_gc_corr.py` | `B/GP4MuSA/NP/np_gc_corr.py` (recipe of `4_designGC.ipynb` cell 2) | `GC()` copied from `MuSA_spatial/modules/spatialMuSA.py`; recipe self-check optional; comparisons with the GP field removed. |

Not included: `B/GP4MuSA/3_makeObs.ipynb` and `B/GP_sno/101_makeMuSAobs.ipynb` (earlier
observation files), `B/GP_sno/0_IC2_synth50.ipynb`, `B/GP4MuSA/3_makeCorr.ipynb`,
`3b_makeCorr.py`, `4_designGC.ipynb` cells 3–13, the IC2 selection variants A_K* / old400.

## Checks

Run on savio4_htc on 2026-10-13; test outputs in
`/global/scratch/users/marcomaz/repo_checks/03_ic2_cells_obs_corr/`, logs in
`/global/scratch/users/marcomaz/repo_checks/logs/`.

| Step | Check | Result |
|---|---|---|
| s1 | Granule `ATL03_20230331045749_01501906_006_02.h5` (2023-03-31, rgt 150) downloaded again with `sbatch_s1_download_atl03.sh` (sliderule client and server 5.6.3) and compared with the 2023-03-31 rows of `ATL03_yapc.feather` | 309 454 photons in both; identical counts per spot, ATL08 class and ATL03 confidence; after sorting, the time index and 20 of 23 columns identical (incl. `height`, `atl08_class`, `yapc_score`). Differences: `y_atc` max 4.9e-4 m (float32 rounding), x max 3.9e-6 m, y max 8.7e-7 m; `yapc_score` stored as uint16 (file: uint8). YAPC version tests on the same granule: SlideRule default 21.5 % of scores equal (max diff 251, corr 0.92); `version` 1 or 2: 29.0 % equal; `version=3`: 100 % equal (used in the script). The notebook's ground-only setting returns 106 272 photons (ATL08 class 1 only). CMR lists no release-006 granule for 2023-03-31 to 2023-04-02 (release 007: the same two granules). |
| s2 | Rerun for the three ASO dates (2 h each) and comparison of all 17 columns with the existing 3 m feathers | `IC2_synt3_24_new.feather` (2024-04-03), `IC2_synt3_.feather` (2023-04-01) and `IC2_synt3_24.feather` (2024-05-20): identical (308 869 rows, all columns array_equal with NaN equal). |
| s3 | Rerun on the three 3 m feathers, all 31 columns compared | `IC2_synt50from3_24april`, `_23`, `_24`: identical (5977 rows, max abs diff 0 in every column). |
| s4 | Rerun for both years, all arrays compared | `IC2cand_23/24.npz` and `IC2sel_23/24_B_K30.npz` identical (array_equal for every key). |
| s5 | Rerun from the original selection files | `IC2NP_23/24.csv`, `_X.npy`, `_Y.npy` byte-identical; points on grid centres (offset 0), elevation feature vs DEM median 3.0 / 3.2 m. |
| s6 | Recompute the error classes | rho_mean = 0.886555579941265 (as printed in the notebook); sd 0.3693 / 0.8410 / 1.4016 m → 0.37 / 0.84 / 1.40 m (variances 0.1369 / 0.7056 / 1.96 m²). |
| s7 | Four observation files written without template, compared with DATA_NP (format, dimensions, variables, attributes incl. order, storage, raw data); correlation files per year | all four observation files equivalent (400 valid values each, max diff 0). `Corr.npy`, `DistMask_05.npy`, `Orderows.npy` identical for 2023 and 2024 (array_equal, NaN equal), symlink target identical; test copies deleted after each year. |
| s8 | 2023 and 2024 with `--recipe-check` (MuSAenv: numpy 1.26.4, scipy 1.15.2) | recipe check: earlier fields reproduced (max diff 0 / 2.7e-15, same NaN pattern); `rhoGC1.npy` and `DistMaskGC_05.npy` identical to DATA_NP for both years (array_equal, NaN equal); test copies deleted after each year. |

Not downloaded again: the 2023-04-01 granule (13.1 M photons). The SlideRule client
version of the original download is not recorded.
