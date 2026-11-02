"""TopoPyScale downscaling of hourly ERA5 to the 400 IC2 cells of one water year (DATA_NP).

Runs the TopoPyScale sequence of the model-point downscaling (project, DEM parameters,
point parameters, solar geometry, downscale_climate) for the 400 observed (IC2) cells of
one year, all points in one downscale_climate() call. Run once per project
(water year 2023 and 2024).

Inputs:  in the project folder: config_GP.yml (= config_NP23.yml or config_NP24.yml);
         inputs/climate/SURF_*.nc, PLEV_*.nc (s1_download_era5.py); inputs/dem/
         srtm_eastriver_clipped.tif and IC2NP_<yy>.csv (400 points); outputs/da_horizon.nc
         and outputs/ds_param.nc (copied from the model-point project; this script does not
         compute the horizon). The project must not contain outputs/df_centroids.pck or
         outputs/ds_solar.nc of another point set: TopoPyScale loads them when present.
Outputs: <project>/outputs/downscaled/down_pt_000.nc .. down_pt_399.nc (hourly, water year:
         2022-10-01 .. 2023-10-01 23:00 or 2023-10-01 .. 2024-10-01 23:00);
         outputs/df_centroids.pck, ds_solar.nc; outputs/tmp/ (intermediate files).
Environment: conda env `downscaling` (TopoPyScale 0.2.2 with the two patched files of
         branch v0.2.2-eastriver). About 16-32 min per year on one savio3 node.
Run:     sbatch sbatch_s3_downscale_ic2_cells.sh <project dir>
         (python s3_downscale_ic2_cells.py <project dir>)
Original: /global/home/users/marcomaz/B/GP4MuSA/NP/np_topopyscale.py (run with
         sbatch_np_topo.sh on /global/scratch/users/marcomaz/downscaliNP23 and downscaliNP24;
         same sequence as downscali3/finish_downscalin_new_approach.ipynb cells 4, 5, 15).
"""
import os
import sys

# ---- paths and settings ------------------------------------------------------
PROJECT_DIR = sys.argv[1]                       # e.g. /global/scratch/users/marcomaz/downscaliNP23
CONFIG_FILE = "./config_GP.yml"                 # relative to the project folder
CENTROIDS_FILE = "./outputs/df_centroids.pck"   # relative to the project folder
# -------------------------------------------------------------------------------

os.chdir(PROJECT_DIR)   # the config uses project.directory: ./
from TopoPyScale import topoclass as tc  # noqa: E402

print("TopoPyScale project", os.getcwd(), flush=True)
mp = tc.Topoclass(CONFIG_FILE)
mp.load_project()
mp.compute_dem_param()          # loads outputs/ds_param.nc
mp.extract_pts_param()          # slope, aspect, svf, elevation of the points (nearest DEM cell)
mp.compute_solar_geometry()     # computes outputs/ds_solar.nc for these points
mp.toposub.df_centroids.copy().to_pickle(CENTROIDS_FILE)
print(mp.toposub.df_centroids.head(), flush=True)
mp.downscale_climate()
print("done", flush=True)
