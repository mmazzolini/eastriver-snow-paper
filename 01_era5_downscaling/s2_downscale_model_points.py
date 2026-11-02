"""TopoPyScale downscaling of hourly ERA5 to the 5400 model points, run in chunks of points.

Sets up the TopoPyScale project (DEM parameters, horizon, solar geometry for all
points; each written to outputs/ if missing), reloads it from those files, then calls
TopoPyScale's downscale_climate() on consecutive chunks of points. Points whose output
file already exists are skipped, so an interrupted run can be restarted. TopoPyScale names the output files with as many digits as the largest
point index of the call; they are renamed to the digits of the whole point set
(down_pt_0000.nc .. down_pt_5399.nc).

Inputs:  config_GP_points.yml; in the project folder: inputs/climate/SURF_*.nc,
         PLEV_*.nc (2022-10 .. 2024-10, s1_download_era5.py), inputs/dem/
         srtm_eastriver_clipped.tif and GP_points.csv (the 5400 model cells,
         02_gp_model_points/s5_make_points_csv.py); outputs/da_horizon.nc (horizon angles of the DEM; computed here
         with TopoPyScale's compute_horizon if absent).
Outputs: <project>/outputs/downscaled/down_pt_NNNN.nc (hourly, 2022-10-01 00:00 ..
         2024-10-01 23:00: t, u, v, q, p, tp, precip_lapse_rate, ws, wd, w, vp, cse, LW,
         SW, SW_direct, SW_diffuse, cos_illumination); outputs/ds_param.nc, ds_solar.nc,
         df_centroids.pck; outputs/tmp/ (per-point intermediate files, left in place).
Environment: conda env `downscaling` (TopoPyScale 0.2.2 with the two patched files of
         branch v0.2.2-eastriver).
Run:     sbatch sbatch_s2_downscale_model_points.sh <project dir> [first last]
         (python s2_downscale_model_points.py <project dir> [--first i] [--last j]
         [--chunk n]; first/last select points by position, default all)
Original: /global/scratch/users/marcomaz/downscali3/finish_downscalin_new_approach.ipynb
         cells 4 (project, DEM and point parameters, solar geometry), 5 (df_centroids.pck),
         7 (skip points already downscaled), 15 (downscale_climate), and
         /global/scratch/users/marcomaz/downscali3/downscale_in_steps.py (chunks of 390
         points). Output of the original run:
         /global/scratch/users/marcomaz/downscali3/outputs_alt/downscaled/correct_mu025/.
"""
import argparse
import os
from pathlib import Path

# ---- paths and settings ------------------------------------------------------
HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config_GP_points.yml"
CENTROIDS_FILE = "./outputs/df_centroids.pck"   # relative to the project folder
DOWNSCALED_DIR = "./outputs/downscaled/"        # where TopoPyScale writes down_pt_*.nc
CHUNK = 390                                     # points per downscale_climate() call
# -------------------------------------------------------------------------------

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("project_dir", help="TopoPyScale project folder (inputs/, outputs/)")
p.add_argument("--config", default=str(CONFIG_FILE), help="TopoPyScale config file")
p.add_argument("--first", type=int, default=0, help="first point (position in the csv)")
p.add_argument("--last", type=int, default=None, help="last point + 1 (default: all)")
p.add_argument("--chunk", type=int, default=CHUNK, help="points per downscale_climate call")
a = p.parse_args()

config_file = os.path.abspath(a.config)
os.chdir(a.project_dir)   # the config uses project.directory: ./
from TopoPyScale import topoclass as tc  # noqa: E402

print("TopoPyScale project", os.getcwd(), "config", config_file, flush=True)

# cell 4: project files (DEM parameters, horizon, solar geometry of all points); each is
# computed and written to outputs/ only if it is not there yet
mp = tc.Topoclass(config_file)
mp.load_project()
mp.compute_dem_param()
mp.extract_pts_param()
if mp.da_horizon is None:
    # The original project already had outputs/da_horizon.nc (TopoPyScale's
    # compute_horizon, horizon_increments of the config); compute it if it is missing.
    mp.compute_horizon()
if mp.ds_solar is None:
    mp.compute_solar_geometry()

# downscale_in_steps.py: downscale from the project files as read back from outputs/.
# TopoPyScale writes ds_param.nc, da_horizon.nc and ds_solar.nc as 16-bit integers
# (scale_factor/add_offset), so the values read back differ slightly from the in-memory
# ones; the original outputs were made with the values read back. (Reopening ds_solar.nc
# with compute_solar_geometry() instead gives a dask/h5netcdf dataset, and the forked
# worker processes of the radiation step then hang.)
mp.load_project()
mp.extract_pts_param()

# cell 5
centroids = mp.toposub.df_centroids.copy()
centroids.to_pickle(CENTROIDS_FILE)


def out_file(idx, n_digits):
    pattern = mp.config.outputs.file.downscaled_pt   # down_pt_*.nc
    return DOWNSCALED_DIR + pattern.replace("*", str(idx).zfill(n_digits))


# cell 7: skip points whose output file exists
n_digits = len(str(centroids.index.max()))   # 4 for 5400 points
todo = centroids.iloc[a.first:a.last]
done = [idx for idx in todo.index if os.path.exists(out_file(idx, n_digits))]
todo = todo.drop(index=done)
print(f"{len(todo)} points to downscale ({len(done)} already done)", flush=True)

# downscale_in_steps.py / cell 15: downscale_climate() on chunks of points
for start in range(0, len(todo), a.chunk):
    chunk = todo.iloc[start:start + a.chunk]
    print(f"chunk: points {chunk.index.min()} .. {chunk.index.max()}", flush=True)
    mp.toposub.df_centroids = chunk
    mp.downscale_climate()
    nd = len(str(chunk.index.max()))   # digits TopoPyScale used for this chunk
    if nd != n_digits:
        for idx in chunk.index:
            os.replace(out_file(idx, nd), out_file(idx, n_digits))
print("done", flush=True)
