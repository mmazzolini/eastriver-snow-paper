# 01 ERA5 download and TopoPyScale downscaling

This stage downloads hourly ERA5 data for the East River basin (Colorado) and downscales it
with TopoPyScale to two point sets:

- the 5400 model points (the MuSA model cells, `GP_points.csv`), water years 2023 and 2024
  in one run (2022-10-01 to 2024-10-01 23:00);
- the 400 ICESat-2 (IC2) cells of each water year (DATA_NP), one project per year.

The outputs are TopoPyScale `down_pt_*.nc` files (hourly air temperature, humidity,
pressure, wind, precipitation, longwave and shortwave radiation per point). They are the
input of the forcing stage (`04_forcing`).

## Environment

Conda env `downscaling` (`../environments/downscaling.yml`): Python 3.9, TopoPyScale 0.2.2,
cdsapi 0.7.5, xarray 2023.4.1, netCDF4 1.6.3, dask 2023.4.1. On Savio it is used with

    export PATH=/global/home/users/marcomaz/miniforge3/envs/downscaling/bin:$PATH

TopoPyScale is release 0.2.2 with two patched files (`solar_geom.py`, `topo_scale.py`). The
changes are in `topopyscale_v0.2.2_eastriver.patch` (this folder, archived with the code):

    git clone https://github.com/ArcticSnow/TopoPyScale && cd TopoPyScale && git checkout v0.2.2
    git apply --whitespace=nowarn <this folder>/topopyscale_v0.2.2_eastriver.patch && pip install .

The same code is on the branch `v0.2.2-eastriver` of the fork
(`pip install git+https://github.com/mmazzolini/TopoPyScale@v0.2.2-eastriver`); the patch applied
to v0.2.2 gives that branch exactly.

The patches: solar azimuth `180 - azimuth` (sign of the illumination angle); `mu0` floored
at 0.25 where it divides the direct beam and in the illumination angle, and direct
shortwave capped at the top-of-atmosphere value; surface-level subsets indexed by the point
ids of `df_centroids`; `outputs/tmp` no longer cleared at the start; dask masks computed
first. Every other file is identical to tag v0.2.2. The installed package on Savio is
identical to that branch (checked file by file).

The download needs a CDS account with the ERA5 licences accepted and `~/.cdsapirc` for the
new CDS (`url: https://cds.climate.copernicus.eu/api` and the personal key); cdsapi reads it.
The savio4_htc compute nodes have outbound internet.

## Run order

All jobs run on compute nodes through the sbatch wrappers (account `fc_mgirotto`).

1. **ERA5 download** (savio4_htc). Set `output_dir` in `config_era5.yml`, then

       sbatch sbatch_s1_download_era5.sh config_era5.yml

   25 monthly SURF files and 25 PLEV files (2022-10 to 2024-10). Each month is one SURF
   request and six PLEV requests (one per pressure level, all six variables); the CDS
   refuses one PLEV request with all levels of a month ("cost limits exceeded"). In the
   test the CDS ran the requests one after another, about 4 min per PLEV request and 8 min
   per SURF request, so about 30 min per month and 12-15 h for the period. Months already
   written are skipped, so if the job ends with "monthly file(s) not written" (failed or
   unfinished requests), submit the same command again.

2. **Model points** (savio3). `GP_points.csv` (the 5400 model cells, written by
   `02_gp_model_points/s5_make_points_csv.py`) and `srtm_eastriver_clipped.tif` are also in the
   data record (`input_data/points/`, `input_data/DEM/`). Make a TopoPyScale project folder `P` (any new folder):

       mkdir -p P/inputs/climate P/inputs/dem P/outputs
       ln -s <output_dir>/SURF_*.nc <output_dir>/PLEV_*.nc P/inputs/climate/
       cp srtm_eastriver_clipped.tif GP_points.csv P/inputs/dem/
       sbatch sbatch_s2_downscale_model_points.sh P            # all 5400 points
       sbatch sbatch_s2_downscale_model_points.sh P 0 10       # only points 0..9

   The config is `config_GP_points.yml` (read from this folder). The script computes
   `outputs/ds_param.nc`, `outputs/da_horizon.nc` and `outputs/ds_solar.nc` when they are not
   in `P/outputs/` (about 20 min for the 5400 points), reads them back from these files, then
   downscales in chunks of 390 points (about 2 min for 10 points with `CPU_cores: 10`).
   TopoPyScale writes the three files as 16-bit integers (scale_factor/add_offset), so the
   values read back differ slightly from the computed ones; the original outputs were made
   from the values read back (see Checks), and the script does the same. Points already in
   `outputs/downscaled/` are skipped, so a stopped run can be resubmitted; delete the files of
   the chunk that was running if the job was killed while writing. At the end of every
   chunk TopoPyScale reads all `down_pt_*.nc` files of the folder back into memory
   (`read_downscaled`), as in the original run. In one test job, TopoPyScale's parallel
   opening of the ERA5 files (`xr.open_mfdataset(parallel=True)`) stopped with
   "NetCDF: Unknown file format" on a valid file; the same command run again read it.

3. **IC2 cells, one project per water year** (savio3, about 16-32 min each). For year
   `yy` = 23 or 24, in a new folder `Pyy`:

       mkdir -p Pyy/inputs/climate Pyy/inputs/dem Pyy/outputs
       cp config_NPyy.yml Pyy/config_GP.yml
       ln -s <output_dir>/SURF_*.nc <output_dir>/PLEV_*.nc Pyy/inputs/climate/
       cp srtm_eastriver_clipped.tif IC2NP_yy.csv Pyy/inputs/dem/
       cp P/outputs/da_horizon.nc P/outputs/ds_param.nc Pyy/outputs/
       sbatch sbatch_s3_downscale_ic2_cells.sh Pyy

   `IC2NP_yy.csv` (400 points) comes from `03_ic2_cells_obs_corr/s5_ic2_points.py`. Start
   from a project without `df_centroids.pck` and `ds_solar.nc`. TopoPyScale loads them when
   present. In the original runs the solar geometry was computed and used in memory, and a
   `ds_solar.nc` read back holds 16-bit packed values.

## Inputs and outputs

| Script | Inputs | Outputs |
|---|---|---|
| `s1_download_era5.py` | `config_era5.yml`, `~/.cdsapirc` | `<output_dir>/SURF_YYYYMM.nc` (z, d2m, sp, t2m, strd, ssrd, tp), `PLEV_YYYYMM.nc` (z, t, u, v, q, r at 500, 600, 700, 800, 900, 1000 hPa); 5 x 5 grid at 0.25°, lat 39.265..38.264, lon -107.52..-106.519, hourly |
| `s2_downscale_model_points.py` | `config_GP_points.yml`; `P/inputs/climate/` (s1), `P/inputs/dem/srtm_eastriver_clipped.tif`, `GP_points.csv` | `P/outputs/downscaled/down_pt_0000.nc` .. `down_pt_5399.nc`; `ds_param.nc`, `da_horizon.nc`, `ds_solar.nc`, `df_centroids.pck`; `outputs/tmp/` (intermediate, can be deleted afterwards) |
| `s3_downscale_ic2_cells.py` | `Pyy/config_GP.yml` (= `config_NPyy.yml`); `Pyy/inputs/climate/`, DEM, `IC2NP_yy.csv`; `Pyy/outputs/da_horizon.nc`, `ds_param.nc` | `Pyy/outputs/downscaled/down_pt_000.nc` .. `down_pt_399.nc` (one water year); `ds_solar.nc`, `df_centroids.pck`, `outputs/tmp/` |

On Savio the files used for the paper are:

- ERA5: `/global/scratch/users/marcomaz/downscaliNP23/inputs/climate/` (identical copies in
  `downscali3`, `downscali24`, `downscaliNP24`; the folder `inputs/climate2/` holds an older,
  different dataset).
- DEM: `/global/scratch/users/marcomaz/downscali3/inputs/dem/srtm_eastriver_clipped.tif`.
- Model points: `/global/scratch/users/marcomaz/downscali3/inputs/dem/GP_points.csv` (a copy of
  `GP_points3.csv`, the 5400 cells); outputs
  `/global/scratch/users/marcomaz/downscali3/outputs_alt/downscaled/correct_mu025/`. The original
  run used `GP_points3_B.csv`, the same 5400 points followed by 100 earlier ICESat-2 cells that
  were never used, so that folder holds 5500 files; `down_pt_0000..5399.nc` are the model cells.
- IC2 cells: projects `/global/scratch/users/marcomaz/downscaliNP23` and `downscaliNP24`
  (`outputs/downscaled/down_pt_000..399.nc`).

## Mapping to the original files

| Repository file | Original | Notes |
|---|---|---|
| `s1_download_era5.py` | TopoPyScale 0.2.7 `fetch_era5.py` in env `downi` (locally edited: `era5_request_surf`, `era5_request_plev`, `process_SURF_file`, `remap_CDSbeta`), called from `downscali3/finish_downscalin_new_approach.ipynb` cells 17, 19, 21, 22; PLEV pieces joined in `downscali3/merge_plev_vars.ipynb` cells 2-5, 7-9 | Same request fields (area = extent ± 0.4°, grid 0.25/0.25, hourly, netCDF, `download_format: unarchived`), same post-processing. The original PLEV files were downloaded in pieces (600-1000 hPa without r, one request per level; r separately; 500 hPa separately) and joined by hand; here every month and level is one request with all six variables. Written to run in env `downscaling` without TopoPyScale. |
| `config_era5.yml` | `downscali3/config_GP2.yml` (period, extent, levels) and the request fields of `fetch_era5.py` | `Total precipitation` and `TOA incident solar radiation` of the original request are written with their API names `total_precipitation`, `toa_incident_solar_radiation`. |
| `s2_downscale_model_points.py` | `downscali3/finish_downscalin_new_approach.ipynb` cells 4, 5, 7, 15; `downscali3/downscale_in_steps.py` | Cell 4 writes the project files once; the downscaling then starts from them as `downscale_in_steps.py` did (`load_project`, `extract_pts_param`, chunks of 390 points, `downscale_climate`). Added: `compute_horizon` when `da_horizon.nc` is missing (the original project already had it), `compute_solar_geometry` only when `ds_solar.nc` is missing, and renaming of the outputs to four digits (TopoPyScale pads to the largest index of each call). |
| `config_GP_points.yml` | `downscali3/config_GP2.yml` | The config of the original run was overwritten; `config_GP2.yml` is the closest surviving one (same period). Changed: `csv_file: GP_points.csv` (the 5400 model cells; `config_GP2.yml` names `GP_points3.csv`, the same file) and `CPU_cores: 10` (was 2; number of worker processes only). |
| `s3_downscale_ic2_cells.py`, `sbatch_s3_downscale_ic2_cells.sh` | `B/GP4MuSA/NP/np_topopyscale.py`, `sbatch_np_topo.sh` | Only docstring, path block and comments changed; the wrapper takes the project folder as argument instead of `YEAR`. As in the original, `ds_param.nc` and `da_horizon.nc` are read from the copied files and the solar geometry is computed and used in memory. |
| `config_NP23.yml`, `config_NP24.yml` | `downscaliNP23/config_GP.yml`, `downscaliNP24/config_GP.yml` | Byte-identical copies. |
| `checks/` | none | Comparison scripts used for the checks below. |

## Checks

All checks were run on 2026-10-13 on compute nodes; outputs under
`/global/scratch/users/marcomaz/repo_checks/01_era5_downscaling/`, logs in
`/global/scratch/users/marcomaz/repo_checks/logs/` (`r01_*`).

**s1, ERA5 download (month 2023-01).** `s1_download_era5.py` was run with a copy of
`config_era5.yml` restricted to 2023-01 (`s1_test/config_era5_test202301.yml`; jobs
39871078 for the SURF request, 39882726 for the PLEV requests and the post-processing).
`checks/check_s1_era5.py` (job 39884976) compared the two files with
`downscaliNP23/inputs/climate/SURF_202301.nc` and `PLEV_202301.nc`:

- same dimensions (time 744, level 6, latitude 5, longitude 5), variables (SURF z, d2m, sp,
  t2m, strd, ssrd, tp; PLEV z, t, u, v, q, r in this order), coordinate values and
  attributes (levels 500..1000 hPa increasing), variable attributes, dtypes (float32) and
  compression (zlib level 1, one chunk);
- global attributes equal except `history` (date and cfgrib/ecCodes version of the CDS
  conversion: cfgrib 0.9.15.1 / ecCodes 2.48.2 now, 0.9.15.0 / 2.41.0 in 2025);
- maximum absolute difference 0 for all 13 variables. The SURF file has the same size in
  bytes (321556); the PLEV file is 1792108 vs 1791783 bytes.

The first version sent one PLEV request per month; the CDS refused it ("cost limits
exceeded"), hence the per-level requests.

**s2, model points 0-9.** The final `s2_downscale_model_points.py` was run in a new project
(`s2_test_fresh2/`: empty `outputs/`, ERA5 files of `downscali3/inputs/climate`, the DEM and
the 5500-point file of the original run, `GP_points3_B.csv`, linked) with
`sbatch_s2_downscale_model_points.sh <project> 0 10` and the config then named
`config_GP_5500pts.yml`, in one job (39903711, 19 min). `checks/check_s2_downscaled.py`
(job 39903969) compared the results with `downscali3/outputs_alt/downscaled/correct_mu025/`
and the files of `downscali3/outputs_alt/`:

- `down_pt_0000.nc` .. `down_pt_0009.nc`: same time axis (17568 hours, 2022-10-01 00:00 to
  2024-10-01 23:00) and point_id; maximum absolute difference 0 for all 17 variables
  (t, u, v, q, p, tp, precip_lapse_rate, ws, wd, w, vp, cse, LW, SW, SW_direct,
  SW_diffuse, cos_illumination). No config value other than `csv_file` had to be changed.
- files computed by the script from the DEM: `ds_param.nc` (elevation, slope, aspect,
  aspect_cos, aspect_sin, svf) and `da_horizon.nc` equal in value to the original
  project's (difference 0); `ds_solar.nc` for points 0-9 within 2e-15 rad (SWtoa 5e-13
  W m-2); `df_centroids.pck` (5500 rows) equal in x, y, lat, lon, elevation, slope, aspect,
  aspect_cos, aspect_sin, svf.
- the `ds_param.nc` files of `downscali3/outputs`, `downscaliNP23/outputs` and
  `downscaliNP24/outputs` are equal in value to the one computed here (job 39885148).

**s2 with `GP_points.csv` (5400 points).** The point file and config were then switched to
`GP_points.csv` / `config_GP_points.yml` (the original run's file had 100 more, unused points after
the model cells). From an empty project (`s2_test_gppoints/`), one job (39904347, 23 min) downscaled
points 0–9 and 5390–5399 and compared them with `correct_mu025` (`check_s2_downscaled.py` with
`10` and `5390:5400`): all 17 variables identical (difference 0) for the 20 points; `ds_param.nc`
and `da_horizon.nc` identical; `ds_solar.nc` within 2e-15 rad (SWtoa 5e-13 W m-2) as before;
`df_centroids.pck` (5400 rows) identical to the first 5400 rows of the original in x, y, lat, lon
and all terrain parameters.

Earlier versions of the script, tested on the way:

- Job 39871148 computed the project files and then stopped with the "Unknown file format"
  error described above.
- Job 39882680 hung in the radiation step (worker processes idle for 27 min): that version
  reopened the existing `ds_solar.nc` with `compute_solar_geometry()`.
- Job 39884771 (project files already on disk, read with `load_project()`) gave the same
  zero differences as above (check job 39884977).
- Job 39885147 (empty project; downscaling with the values computed in memory in the same
  process, without reading them back) did not match. t, q, p, tp, wind, vp and cse were
  identical, but the radiation differed: SW and SW_direct up to 404 W m-2, SW_diffuse
  0.43 W m-2, LW 0.065 W m-2, cos_illumination 0.0036 (check job 39903701). The point
  slope, aspect and svf differed by up to 6.5e-4 rad, 3.1e-3 rad and 3.9e-4. The cause is
  the 16-bit packing of `ds_param.nc`, `da_horizon.nc` and `ds_solar.nc` by TopoPyScale;
  the large SW differences are single hours where the horizon shading flips. The original
  outputs therefore come from the values read back from the files, which the final script
  uses.

**s3, IC2 cells.** Not re-run (the outputs are the DATA_NP projects). `py_compile` passes;
`diff` against `B/GP4MuSA/NP/np_topopyscale.py` shows only the docstring, the path block
(`PROJECT_DIR`, `CONFIG_FILE`, `CENTROIDS_FILE` in place of the literals) and comments
(`repo_checks/01_era5_downscaling/s3_diff_np_topopyscale.txt`). The wrapper takes the
project folder as argument instead of the `YEAR` variable (`s3_diff_sbatch.txt`).
`config_NP23.yml` and `config_NP24.yml` are byte-identical to the project configs (`cmp`).

**Other.** The 25 SURF and 25 PLEV files are byte-identical in `downscali3`, `downscali24`,
`downscaliNP23` and `downscaliNP24` (`cmp`). The installed TopoPyScale of env `downscaling`
is identical, file by file, to the branch `v0.2.2-eastriver`, which differs from tag
v0.2.2 only in `solar_geom.py` and `topo_scale.py`. The savio4_htc compute nodes reach the
CDS (HTTP 200, job 39871009).

Not verified: the full 25-month download and the full 5400-point run were not repeated;
the original ERA5 files were assembled from partial downloads with TopoPyScale 0.2.7
(env `downi`), so only the result of that assembly (the monthly files) was compared, not
the intermediate pieces.
