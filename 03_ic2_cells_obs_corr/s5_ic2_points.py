"""Point lists of the 400 selected ICESat-2 cells per year (for TopoPyScale and MuSA).

Row i of the B_K30 selection (s4_select_ic2_cells.py) becomes point name i, which
is the observed MuSA cell y = i, x = 1. Coordinates are the 50 m grid-cell centres
(UTM 13N) converted to latitude/longitude. The scaled GP features and the
observation log(snow depth + 1) are written alongside.
Optional check (--topo): every point falls on a 50 m grid centre, its DEM elevation
matches the elevation feature, and no cell is repeated.

Inputs:  <sel dir>/IC2sel_<yr>_B_K30.npz, GP_models/scaler.save;
         for --topo: all_data50from3_1105.nc (50 m terrain stack).
Outputs: <out>/IC2NP_<yr>.csv (index, x, y, name, lat, lon),
         <out>/IC2NP_<yr>_X.npy (400 x 7 scaled features),
         <out>/IC2NP_<yr>_Y.npy (400 x 1, log(snow depth + 1)).
Environment: gpy-env (pandas, pyproj, xarray, joblib/scikit-learn).
Run:     sbatch sbatch_s5_ic2_points.sh <sel dir> <out dir>
         (python s5_ic2_points.py --sel <dir> --out <dir> [--topo])
Original: /global/home/users/marcomaz/B/GP4MuSA/NP/np_points.py (run with NP/sbatch_np_py.sh);
          outputs in /global/scratch/users/marcomaz/DATA_NP/points/.
"""
import argparse
import os

import joblib
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

# ---- paths and settings ------------------------------------------------------
SCRATCH = "/global/scratch/users/marcomaz/"
SCALER = SCRATCH + "GP_models/scaler.save"
TOPO_50M = SCRATCH + "all_data50from3_1105.nc"      # only for --topo
YEARS = [23, 24]
# -------------------------------------------------------------------------------

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--sel", required=True, help="directory with IC2sel_<yr>_B_K30.npz")
p.add_argument("--out", required=True, help="output directory")
p.add_argument("--topo", action="store_true", help="check the points against the 50 m DEM")
a = p.parse_args()
OUT = os.path.join(a.out, "")
os.makedirs(OUT, exist_ok=True)

scaler = joblib.load(SCALER)
COLS = list(scaler.feature_names_in_)
to_ll = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)

for yr in YEARS:
    d = np.load(os.path.join(a.sel, f"IC2sel_{yr}_B_K30.npz"))
    x, y = d["xg"].astype(float), d["yg"].astype(float)
    lon, lat = to_ll.transform(x, y)
    pts = pd.DataFrame({"x": x, "y": y, "name": np.arange(len(x)), "lat": lat, "lon": lon})
    pts.to_csv(OUT + f"IC2NP_{yr}.csv")
    np.save(OUT + f"IC2NP_{yr}_X.npy", d["X"])
    np.save(OUT + f"IC2NP_{yr}_Y.npy", d["y_obs"])
    print(f"20{yr}: {len(pts)} points, unique {len(set(zip(x, y)))}", flush=True)
    if a.topo:
        # grid cell exists and its elevation matches the elevation feature
        topo = xr.open_dataset(TOPO_50M)
        raw = scaler.inverse_transform(pd.DataFrame(d["X"], columns=COLS))
        zt = topo["Zs"].sel(x=xr.DataArray(x, dims="p"), y=xr.DataArray(y, dims="p"), method="nearest")
        dx = np.abs(zt.x.values - x).max(), np.abs(zt.y.values - y).max()
        dz = np.abs(zt.values - raw[:, COLS.index("Zs")])
        print(f"   grid offset {dx}, |Zs feature - DEM| median {np.median(dz):.1f} max {dz.max():.1f} m, "
              f"NaN Zs {np.isnan(zt.values).sum()}", flush=True)
    print(pts.head(3).to_string(), flush=True)
