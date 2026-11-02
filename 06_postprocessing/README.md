# 06_postprocessing — MuSA ensembles to netCDF and to the 50 m grid

Two steps after a MuSA run:

1. `20b_save_netEN.py` collects the per-cell ensemble files of one run into one netCDF file of daily
   snow depth: posterior (default) or prior (`--prior`), 5400 model cells (x = 0) and 400 IC2 cells
   (x = 1), 100 members.
2. `21_maptogrid_NP.py` maps the members of the 5400 model cells on the ASO date (2023-04-01,
   2024-04-03) to the 296,799 cells of the 50 m basin grid, by regression of log(snow depth + 1) on
   terrain features, one member at a time: Matern 5/2 kernel for the GP runs, Gaspari–Cohn kernel for
   the GC runs (`mapping_kernels.py`).

## Environments

| Script | Environment | Notes |
|---|---|---|
| `20b_save_netEN.py` | `MuSAenv` (`../environments/MuSAenv.yml`) | the MuSA package (`modules/`, `constants.py`) must be importable from `MUSA_DIR` to unpickle the ensembles |
| `21_maptogrid_NP.py`, `mapping_kernels.py` | `gpy-env` (`../environments/gpy-env.yml`) | GPy, scikit-learn (scaler), joblib |

Environment variables: `MUSA_DIR` (MuSA folder whose `config.py` is the run's config), `MUSA_POST_OUTDIR`
(output folder name, relative to `<save_ensemble_path>/..`, or an absolute path), `MUSA_POST_NWORKERS`
(processes; the wrappers set it), `MUSA_PRED_CHUNK` (GC prediction chunk, default 2000).

## Run order

```bash
cd 06_postprocessing
# 1. per run, after MuSA (eastriver/run_experiment.sh of the MuSA repository submits these two
#    itself when POSTPROC_DIR points to this folder)
export MUSA_DIR=/path/to/MuSA/ MUSA_POST_OUTDIR=24GPpow2NPnb_var
sbatch sbatch_20b_save_netEN.sh       # posterior -> <data>/24GPpow2NPnb_var/En_snd24.nc
sbatch sbatch_20b_save_netEN2.sh      # prior     -> <data>/24GPpow2NPnb_var/En_snd24_Pr.nc
# 2. after the four runs: 8 array tasks (0/1 23GP prior/posterior, 2/3 24GP, 4/5 23GC, 6/7 24GC)
sbatch sbatch_21_maptogrid_NP.sh
```

`config.py` in `MUSA_DIR` must describe the run (MuSA's pre-processing installs it). To post-process a
run later, point `MUSA_DIR` to a folder that holds a copy of the run's config as `config.py` and links to
the MuSA `modules/` and `constants.py` (this is how the check below was run).

## Inputs and outputs

| Step | Inputs | Outputs |
|---|---|---|
| 20b | `<save_ensemble_path>/ensbl_<y>_<x>.pkl.blp` (posterior) or `0pri_ensbl_<y>_<x>_obs<b>.pkl.blp` (prior); `nc_maks_path`, `date_ini`, `date_end`, `ensemble_members` from `config.py` | `En_snd<yy>.nc` / `En_snd<yy>_Pr.nc`: `snd` (y 5400, x 2, t 365/366, en 100), int64, mm (daily mean, truncated), fill −9999 where no cell file exists (x = 1, y ≥ 400), zlib level 9 |
| 21 | `<data>/<run>/En_snd<yy>[_Pr].nc`; `all_data50from3_1702.nc` (terrain features; grid cells = rows of 2022-04-21 without NaN); `GP_models/scaler.save`; `GP_models/5500_iter/indPTS_4.npy`, `var_4.npy`, `lnscale_4.npy` | `<data>/<run>/<Prior\|Post><yy>_mapped<yymmdd>_ens.nc` (variable `Prior` or `Posterior`, dims en, y 808, x 626, date; m) and `..._mapped<yymmdd>.nc` (ensemble mean) |

Runs mapped by `21_maptogrid_NP.py` (`RUNS`; `<data>` = `DATA_GP5400_400`):

| Run | Water year | Kernel | Variance, length scale | ASO date |
|---|---|---|---|---|
| `23GPpow2NPnbm_var` | 2023 | Matern 5/2 (ARD) | `var_4.npy`, `lnscale_4.npy` | 2023-04-01 |
| `24GPpow2NPnb_var` | 2024 | Matern 5/2 (ARD) | `var_4.npy`, `lnscale_4.npy` | 2024-04-03 |
| `23GCpow2NP_var` | 2023 | Gaspari–Cohn | mean over members of the field variance (m²), 5 | 2023-04-01 |
| `24GCpow2NP_var` | 2024 | Gaspari–Cohn | mean over members of the field variance (m²), 5 | 2024-04-03 |

Noise SD `sigma_y = 0.5` in both cases. The features are scaled with the stored scaler; the training
points are the 5400 model cells (`indPTS_4.npy`, x = 0 of `En_snd`).

## Files and originals

| File | Original (`/global/home/users/marcomaz/B/Post/`) | Changes |
|---|---|---|
| `20b_save_netEN.py` | `20b_savePost_netEN.py`, `20b_savePrior2_netEN.py` | the two scripts differ only in the file pattern (`e*` / `0pri_ensbl_*`) and the output suffix (`_Pr`); merged, `--prior` selects them. `MUSA_DIR` and `MUSA_POST_OUTDIR` are required (the originals fell back to `MuSA_spatial/` and `24GPnosp`). Unused imports and variables, commented-out code and a one-element loop removed; main block in `main()`. |
| `sbatch_20b_save_netEN.sh`, `sbatch_20b_save_netEN2.sh` | same names | run from the submit folder; same resources and environment; names kept because the MuSA driver calls them |
| `mapping_kernels.py` | `map_one_ensemble` of `21_maptogridGP_ensembles_all_20230401.py`; `GaspariCohn` and `map_one_ensemble` of `21_maptogridGC_ensembles_all_onedate.py` | copied verbatim; names `map_one_ensemble_gp` / `map_one_ensemble_gc` (the GC function's cache attribute uses the new name). The `main()` of the originals (older runs) is not included. |
| `21_maptogrid_NP.py` | `21_maptogrid_NP.py` | imports from `mapping_kernels.py` (the original loaded the two files by path); paths and settings block; options `--members` and `--out-dir` (defaults: all members, run folder, as before) |
| `sbatch_21_maptogrid_NP.sh` | `sbatch_21_maptogrid_NP.sh` | run from the submit folder; extra arguments are passed to the script |

`import modules.fsm_tools` in `20b_save_netEN.py` is not used directly but is needed: importing the MuSA
modules in that order lets pickle load the ensemble objects. Without it, unpickling fails with a circular
import (`modules.internal_class` → `met_tools` → `spatialMuSA` → `internal_class`).

## Checks

Run on savio4_htc on 2026-10-13; test outputs in `/global/scratch/users/marcomaz/repo_checks/06_postprocessing/`,
compared read-only with the files used in the paper (`compare_post.py` there); the converted and mapped
test files were deleted after the comparison (the test `MUSA_DIR`, `musa_dir24/`, is kept).

| Check | Result |
|---|---|
| `py_compile` of the three scripts | OK |
| `diff` with the originals | computational lines unchanged; differences are the docstring, imports, the paths block, `--prior`, the `main()` wrapper and comments (table above) |
| `mapping_kernels.py` vs the original functions and class, after undoing the renames | 126 of 126 code lines identical |
| 20b, run `24GPpow2NPnb_var`, posterior (`MUSA_DIR` = copy of `MuSA_paper/eastriver/config24_GPpow2NPnb_var.py` as `config.py` + links to `MuSA_paper/modules`, `constants.py`) vs `DATA_GP5400_400/24GPpow2NPnb_var/En_snd24.nc` | `snd` bitwise equal: 0 of 395,280,000 values differ; coordinates, dtype (int64), fill count and encoding (zlib 9) equal; xarray `identical` True. 5800 files in 156 s with 30 processes |
| 20b `--prior`, same run, vs `En_snd24_Pr.nc` | bitwise equal (0 of 395,280,000 differ); xarray `identical` True |
| 21, task 3 (GP, `24GPpow2NPnb_var`, posterior), members 0 and 1, vs `Post24_mapped240403_ens.nc` | bitwise equal, max \|diff\| 0, same NaN pattern (296,799 grid cells); printed variance 1.4578 as in the original log |
| 21, task 5 (GC, `23GCpow2NP_var`, posterior), members 0 and 1, vs `Post23_mapped230401_ens.nc` | bitwise equal, max \|diff\| 0, same NaN pattern; variance 1.2743 as in the original log |

Not checked: the other runs, the prior mapping, members 2–99 and the ensemble-mean files (with two
members the mean differs by construction). They use the same code paths.
