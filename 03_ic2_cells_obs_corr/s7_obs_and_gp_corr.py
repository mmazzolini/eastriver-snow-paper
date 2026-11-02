"""MuSA observation files of the 400 ICESat-2 cells and the GP prior correlation field, per year.

Observations: the IC2 snow depth exp(y_obs) - 1 of the 400 selected cells is written
at y = 0..399, x = 1 of the MuSA grid (time 1, y 5400, x 2); all other cells hold
the fill value -9999. The error field "sd" holds 0.37 / 0.84 / 1.40 m by terrain
slope (< 10, 10-40, > 40 degrees; s6_obs_error_classes.py); the "_var" files hold
sd**2, which is how MuSA reads the field (as a variance).
GP correlation: Matern 5/2 kernel (length scales lnscale_4, variance 1) between the
5400 model cells (indPTS_4, rows 0-5399) and the observed cells (rows 5400-5799),
padded with NaN rows to 10800 (= 5400 x 2 grid cells; rows of inactive cells are NaN).

Inputs:  <points>/IC2NP_<yr>_X.npy, IC2NP_<yr>_Y.npy (s5_ic2_points.py),
         GP_models/scaler.save, GP_models/5500_iter/{lnscale_4,indPTS_4}.npy.
Outputs: <out>/Obs23/IC2_23-04-01.nc, Obs23_var/IC2_23-04-01_var.nc,
         <out>/Obs24/IC2_24-04-03.nc, Obs24_var/IC2_24-04-03_var.nc;
         <out>/Corr<yr>/Corr.npy (10800 x 10800 float64, ~0.9 GB), Orderows.npy,
         DistMask_05.npy (1 where Corr > 0.5, else NaN) and the symlink
         DistMaskGP_05.npy -> DistMask_05.npy.
Environment: gpy-env (GPy, netCDF4).
Run:     sbatch sbatch_s7_obs_and_gp_corr.sh <points dir> <out dir> [--years 23 24] [--skip-corr]
Original: /global/home/users/marcomaz/B/GP4MuSA/NP/np_obs_corr.py (run with NP/sbatch_np_py.sh);
          outputs in /global/scratch/users/marcomaz/DATA_NP/. The original copied the
          files of the earlier data set (DATA_GP5400_400/Obs*) as templates and replaced
          the values; here the same file layout is written directly. The original also
          copied DATA_GP5400_400/mask/{mask,mask_repr}.nc to DATA_NP/mask/ (not done here).
"""
import argparse
import os

import GPy
import joblib
import netCDF4 as nc
import numpy as np
import pandas as pd

# ---- paths and settings ------------------------------------------------------
SCRATCH = "/global/scratch/users/marcomaz/"
SCALER = SCRATCH + "GP_models/scaler.save"
LNSCALE = SCRATCH + "GP_models/5500_iter/lnscale_4.npy"
MODEL_PTS = SCRATCH + "GP_models/5500_iter/indPTS_4.npy"     # 5400 model cells (scaled features)
DATE = {23: "23-04-01", 24: "24-04-03"}                     # observation dates (file names)
NY, NX, N_OBS = 5400, 2, 400                                 # MuSA grid; observed cells y < 400, x = 1
FILL = -9999.0
SD_CLASSES = (0.37, 0.84, 1.40)                              # slope < 10, 10-40, > 40 degrees
VAR_DESCRIPTION = "observation error VARIANCE (m2) = sd**2 (sd 0.37/0.84/1.40 by slope)"
# -------------------------------------------------------------------------------


def write_obs(path, obs, err, var_file):
    """Write one observation file (layout of the MuSA observation files used)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with nc.Dataset(path, "w", format="NETCDF4") as f:
        f.createDimension("time", 1)
        f.createDimension("y", NY)
        f.createDimension("x", NX)
        for v, val in [("snow_depth", obs), ("sd", err)]:
            var = f.createVariable(v, "f4", ("time", "y", "x"), fill_value=FILL)
            if v == "snow_depth":
                var.setncattr("grid_mapping", "crs")
            if v == "sd" and var_file:
                var.setncattr("description", VAR_DESCRIPTION)
            a = np.full(var.shape, FILL, dtype=var.dtype)
            a[0, 0:N_OBS, 1] = val
            var[:] = a


p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--points", required=True, help="directory with IC2NP_<yr>_X.npy and _Y.npy")
p.add_argument("--out", required=True, help="output data directory (Obs<yr>*, Corr<yr>)")
p.add_argument("--years", type=int, nargs="+", default=[23, 24], choices=[23, 24])
p.add_argument("--skip-corr", action="store_true", help="write the observation files only")
a = p.parse_args()

scaler = joblib.load(SCALER)
COLS = list(scaler.feature_names_in_)
lengthscales = np.load(LNSCALE)
k = GPy.kern.Matern52(input_dim=7, lengthscale=lengthscales, variance=1, ARD=True)
all_pts0 = np.load(MODEL_PTS)

for yr in a.years:
    X = np.load(os.path.join(a.points, f"IC2NP_{yr}_X.npy"))
    obs = np.exp(np.load(os.path.join(a.points, f"IC2NP_{yr}_Y.npy"))[:, 0]) - 1
    slope = scaler.inverse_transform(pd.DataFrame(X, columns=COLS))[:, COLS.index("slope")]
    sd = np.where(slope < 10, SD_CLASSES[0], np.where(slope > 40, SD_CLASSES[2], SD_CLASSES[1]))
    print(f"20{yr}: obs mean {obs.mean():.2f} m, min {obs.min():.2f}, max {obs.max():.2f}; "
          f"sd classes 0.37/0.84/1.40: {(sd == 0.37).sum()}/{(sd == 0.84).sum()}/{(sd == 1.40).sum()}", flush=True)

    # --- observation files: error as sd and as variance (sd**2)
    for suf, err in [("", sd), ("_var", sd ** 2)]:
        name = os.path.join(a.out, f"Obs{yr}{suf}", f"IC2_{DATE[yr]}{suf}.nc")
        write_obs(name, obs, err, var_file=(suf == "_var"))
        with nc.Dataset(name) as f:
            s, e = f["snow_depth"][:], f["sd"][:]
            print(f"  {name}: valid {s.count()} (x=1,y<400: {s[0, :400, 1].count()}), "
                  f"err values {np.unique(e.compressed()).round(4)}", flush=True)
    if a.skip_corr:
        continue

    # --- GP correlation: model cells + observed cells padded with NaN to 5400 rows
    cdir = os.path.join(a.out, f"Corr{yr}", "")
    os.makedirs(cdir, exist_ok=True)
    obs_pts = np.vstack((X, np.full((NY - X.shape[0], 7), np.nan)))
    all_pts = np.vstack((all_pts0, obs_pts))
    np.save(cdir + "Orderows.npy", np.lexsort(all_pts.T[::-1]))
    full_cov = k.K(all_pts, all_pts)
    np.save(cdir + "Corr.npy", full_cov)
    np.save(cdir + "DistMask_05.npy", np.where(full_cov > 0.50, 1, np.nan))
    if not os.path.lexists(cdir + "DistMaskGP_05.npy"):
        os.symlink("DistMask_05.npy", cdir + "DistMaskGP_05.npy")
    # checks on the active block (5400 model cells + 400 observed cells)
    act = np.r_[np.arange(NY), NY + np.arange(N_OBS)]
    C = full_cov[np.ix_(act, act)]
    print(f"  Corr{yr}: shape {full_cov.shape}, symmetric {np.allclose(C, C.T)}, "
          f"diag {np.diag(C).min():.6f}-{np.diag(C).max():.6f}, NaN in active block {np.isnan(C).sum()}, "
          f"obs-obs median rho {np.median(C[NY:, NY:][np.triu_indices(N_OBS, 1)]):.3f}, "
          f"obs per model cell (rho>0.5) median {np.median((C[:NY, NY:] > 0.5).sum(1)):.0f}", flush=True)
    del full_cov, C
