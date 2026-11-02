# 04_forcing — MuSA forcing files

Builds the daily forcing files that MuSA (FSM2) reads for the two water years (2022-10-01 to
2023-09-30 and 2023-10-01 to 2024-09-30): hourly meteorology from TopoPyScale for the 5400 model
cells (x = 0) and the 400 IC2 cells (x = 1), one netCDF file per day.

## Environment

`downscaling` (`../environments/downscaling.yml`; Python 3.9, numpy 1.24.2, xarray 2023.4.1). The
wrappers put it first on `PATH` (`PYENV` = environment folder). Compute node: savio4_htc, 8 cores.

## Run order

```bash
cd 04_forcing
sbatch sbatch_s1_forcing_model_cells.sh 23     # x = 0 -> DATA_NP/Forcing23_x0/   (25-40 min, 11-13 GB)
sbatch sbatch_s1_forcing_model_cells.sh 24
# after s1:
sbatch sbatch_s2_forcing_ic2_cells.sh 23       # x = 1 + join -> DATA_NP/Forcing23/  (5-8 min)
sbatch sbatch_s2_forcing_ic2_cells.sh 24
# after s2:
sbatch sbatch_s3_check_forcing.sh 23           # checks, exit code 1 on failure (~21 min)
sbatch sbatch_s3_check_forcing.sh 24
```

Every script takes `--year 23|24` and output/input folder options (`--help`); the defaults are in the
paths block of each script. s1 and s2 skip days whose output file exists.

## Inputs and outputs

| Step | Inputs | Outputs |
|---|---|---|
| s1 | TopoPyScale output of the model points, `downscali3/outputs_alt/downscaled/correct_mu025/down_pt_0000..5399.nc` (hourly, 2022-10-01 to 2024-09-30), the 5400 model cells of `GP_points.csv` (the original run also downscaled 100 unused points, `down_pt_5400..5499.nc`) | `DATA_NP/Forcing<yy>_x0/<YYYY-MM-DD>.nc`: time 24, y 5400, x 1 (x = 0) |
| s2 | TopoPyScale output of the IC2 cells, `downscaliNP<yy>/outputs/downscaled/down_pt_000..399.nc` (points = rows of `DATA_NP/points/IC2NP_<yy>.csv`); s1 output | `DATA_NP/Forcing<yy>_/<YYYY-MM-DD>.nc` (x = 1 only, y 400); `DATA_NP/Forcing<yy>/<YYYY-MM-DD>.nc`: time 24, y 5400, x 2, x = 1 NaN for y ≥ 400 (MuSA `nc_forcing_path`) |
| s3 | `DATA_NP/Forcing<yy>/`, both TopoPyScale outputs, the two point lists, `all_data50from3_1105.nc` (elevation `Zs`) | report on stdout; optional figure (`--fig`) |

Variables (TopoPyScale names and units): `SW`, `LW` (W m⁻²), `tp` (mm h⁻¹), `t` (K), `ws` (m s⁻¹),
`q` (kg kg⁻¹), `p` (Pa; the attribute says "bar", as written by TopoPyScale), and `RH` (%), computed as

    w  = 0.5 (1 − sqrt(1 − 4 q))
    e  = 0.5 p (−1 + sqrt(1 + 4 w / 0.622))
    es = 610.94 exp(17.625 Tc / (243.04 + Tc)),   Tc = t − 273.15
    RH = min(100, 100 e / es)

In both projects y = TopoPyScale point number = row of the point list. The files are sorted by point
number: the older scripts (`B/GP4MuSA/treat_TSpoints_get_ind_pts<yy>.py`) used an unsorted `glob`, which
gave 398 of the 400 IC2 cells the forcing of other cells (the files used in the paper come from the
sorted version, `np_forcing.py`).

## Files and originals

| File | Original (`/global/home/users/marcomaz/B/GP4MuSA/`) | Changes |
|---|---|---|
| `s1_forcing_model_cells.py` | none as one script. The x = 0 data used in the paper were copied by `NP/np_forcing.py` from `DATA_GP5400_400/Forcing<yy>`, written by an older chain (`treat_TSpoints_get_ind_pts<yy>.py`, x = 0 block, via `DATA_GP5500/Forcing100\|124`) whose first writer no longer exists | new: the processing of `np_forcing.py` applied to points 0..5399 of `correct_mu025`; reads only the water year from the two-year files |
| `s2_forcing_ic2_cells.py` | `NP/np_forcing.py` | x = 0 from s1 instead of `DATA_GP5400_400/Forcing<yy>`; command-line options instead of the `YEAR` variable; the `VALIDATE` mode (comparison with the older, unsorted forcing) is not included |
| `s3_check_forcing.py` | `NP/np_check_forcing.py`, `NP/chk_x0_order.py` | the x = 0 identity is checked against the TopoPyScale output (as in `chk_x0_order.py`) instead of `DATA_GP5400_400`, for all raw variables every 30th day, and the same test is added for x = 1; point-list check added; section 3 of the original (comparison with the earlier IC2 cell selection) not included; figure optional |
| `sbatch_s1_forcing_model_cells.sh`, `sbatch_s2_forcing_ic2_cells.sh`, `sbatch_s3_check_forcing.sh` | `NP/sbatch_np_py.sh` | one wrapper per script; s1 sets `NPY_DISABLE_CPU_FEATURES` (below) |

**RH and numpy's AVX-512 exp.** The RH values of the x = 0 files used in the paper equal the formula
evaluated with the scalar (libm) `exp`. On the AVX-512 nodes of savio4_htc numpy uses its own vectorised
`exp`, which differs in the last bits: RH differs by up to 5.7·10⁻¹⁴ % in ~17 % of the values (one day tested
in the downscaling, gpy-env and MuSAenv environments; with AVX-512 disabled the difference is 0). The s1 wrapper therefore disables numpy's AVX-512
code paths (`NPY_DISABLE_CPU_FEATURES`). The x = 1 RH of the paper files was computed with numpy's AVX-512
`exp` (np_forcing.py on savio4_htc), so s2 is run with the default settings. Without these settings, or on
other CPUs, only RH changes, at this level.

## Checks

Run on savio4_htc on 2026-10-13; test outputs in `/global/scratch/users/marcomaz/repo_checks/04_forcing/`
(deleted after the comparison), compared read-only with `DATA_NP/Forcing<yy>` (`compare_forcing.py` there).

| Check | Result |
|---|---|
| `py_compile` of the three scripts, `bash -n` of the wrappers | OK |
| s1 (x = 0) vs x = 0 of `DATA_NP/Forcing<yy>`, all days, all variables | 2023: 365/365 days, 2024: 366/366 days bitwise equal for `SW`, `LW`, `tp`, `t`, `ws`, `q`, `p`, `RH` (max \|diff\| 0 for each); time, y, x and `reference_time` values equal |
| s2 x = 1 files vs `DATA_NP/Forcing<yy>_` | 365/365 and 366/366 days bitwise equal for all 8 variables; xarray `identical` (values and attributes) for every file |
| s2 final files (x = 0 from s1) vs `DATA_NP/Forcing<yy>`, all days, all variables | 365/365 and 366/366 days bitwise equal for all 8 variables (max \|diff\| 0), same NaN pattern (x = 1, y ≥ 400), same coordinates (2024: `reference_time` per x, 2022-10-01 / 2023-10-01, as in the files used); xarray `identical` for every file |
| s1 without the AVX-512 setting (first test, default numpy on savio4_htc) | the 7 TopoPyScale variables bitwise equal on all days; `RH` max \|diff\| 5.7·10⁻¹⁴ % (22,528 of 129,600 values on 2022-10-01) |
| s3 on `DATA_NP/Forcing23` and `DATA_NP/Forcing24` (read-only) | ALL CHECKS PASSED for both years: 365 / 366 files; dims (24, 5400, 2); no NaN at active cells; x = 0 equals the TopoPyScale point of the same number for 5400/5400 cells and x = 1 for 400/400 cells (13 days, 312 h, 7 variables, max \|diff\| 0); x = 1 ranges within limits (t 245.7–296.8 K, RH 4.8–100 %); point lists in row order; annual mean t residual of the IC2 cells p5/p50/p95 −0.21/−0.06/0.13 K (2023) and −0.21/−0.07/0.09 K (2024); tp ratio p50 0.93 / 0.94; no IC2 cell with \|t residual\| > 2 K or tp ratio outside 0.5–2; daily t correlation with the nearest model cell: min 1.000 (3 decimals) |

Encoding differences that remain (values unaffected): the y coordinate is stored as int64 instead of
int32 (the older x = 0 chain kept the int32 `point_id` of TopoPyScale; `np_forcing.py` writes int64 for
x = 1, and s1 follows it), and in the intermediate s1 files `reference_time` has the units
"days since 2022-10-01 00:00:00" instead of "days since 2022-10-01" (the final s2 files have the latter,
as the files used).

Not checked: the `gpy-env` environment for s1–s3 (the scripts were tested with `downscaling` only); the
TopoPyScale runs themselves (their output is the input here).
