"""Daily MuSA forcing files: 400 IC2 cells (x = 1) joined with the 5400 model cells (x = 0).

Reads the TopoPyScale output of the 400 IC2 cells (down_pt_000..399.nc), sorted by point
number so that y = point number = row of the IC2 cell selection, computes relative humidity
and writes one file per day with x = 1 only. Each day is then joined with the x = 0 file of
s1_forcing_model_cells.py along x. Sorting fixes the unsorted glob of the older scripts
(B/GP4MuSA/treat_TSpoints_get_ind_pts<yy>.py), which gave the IC2 cells the forcing of other cells.

Inputs:
    <TOPO_NP>/down_pt_000.nc ... down_pt_399.nc   hourly TopoPyScale output of the IC2 cells
    <x0-dir>/<YYYY-MM-DD>.nc                      x = 0 files of s1_forcing_model_cells.py
Outputs:
    <out1-dir>/<YYYY-MM-DD>.nc   x = 1 only (time 24, y 400, x 1)
    <out-dir>/<YYYY-MM-DD>.nc    MuSA forcing (time 24, y 5400, x 2); x = 1 is NaN for y >= 400;
                                 variables SW, LW, tp, t, ws, q, p, RH; 365 or 366 files
    Days whose final file exists are skipped.
Environment: downscaling (../environments/downscaling.yml); 8 cores.
Run (from 04_forcing): sbatch sbatch_s2_forcing_ic2_cells.sh 23   (and 24)
    on a compute node:   python s2_forcing_ic2_cells.py --year 23 [--x0-dir D0 --out1-dir D1 --out-dir D]
Original: B/GP4MuSA/NP/np_forcing.py (x = 0 was read from DATA_GP5400_400/Forcing<yy>; the
    VALIDATE mode, a comparison with that older forcing, is not included).
"""
import argparse
import concurrent.futures
import os
import re
from glob import glob

import numpy as np
import pandas as pd
import xarray as xr

# ---- paths and settings
SCRATCH = "/global/scratch/users/marcomaz/"
TOPO_NP = SCRATCH + "downscaliNP{yy}/outputs/downscaled/"   # TopoPyScale output of the 400 IC2 cells
X0_DEFAULT = SCRATCH + "DATA_NP/Forcing{yy}_x0/"            # default --x0-dir (output of s1)
OUT1_DEFAULT = SCRATCH + "DATA_NP/Forcing{yy}_/"            # default --out1-dir (x = 1 only)
OUT_DEFAULT = SCRATCH + "DATA_NP/Forcing{yy}/"              # default --out-dir (MuSA forcing)
N_IC2 = 400
VAR_LIST = ["SW", "LW", "tp", "t", "ws", "q", "p"]          # variables kept (+ RH)
DROP = ["u", "v", "precip_lapse_rate", "wd", "w", "cse", "SW_diffuse", "cos_illumination", "SW_direct"]
NW = int(os.environ.get("SLURM_NTASKS", "8"))               # worker processes

ALL = None   # all IC2 points for the water year, set in main() and shared with the workers (fork)
X0 = OUT_ = OUT = None


def point_files(topo):
    """down_pt_<n>.nc sorted by point number n (the older scripts used the unsorted glob)."""
    files = glob(topo + "down_pt_*.nc")
    num = [int(re.search(r"down_pt_(\d+)\.nc$", f).group(1)) for f in files]
    files = [f for _, f in sorted(zip(num, files))]
    assert sorted(num) == list(range(N_IC2)), f"expected down_pt_000..{N_IC2 - 1}, found {len(num)}"
    return files


def load_all(files):
    """All IC2 points for the whole year, read once."""
    pts = []
    for f in files:
        ds = xr.open_dataset(f, drop_variables=DROP).load()
        ds.point_id.values = int(ds.point_id.values)
        pts.append(ds)
        ds.close()
    return xr.concat(pts, dim="point_id")


def save_day(d):
    fn = d.strftime("%Y-%m-%d") + ".nc"
    if os.path.exists(OUT + fn):
        return fn
    ic2 = ALL.sel(time=slice(d, d + np.timedelta64(23, "h")))
    ic2 = ic2.rename({"point_id": "y"}).assign_coords(x=1).expand_dims(dim="x")
    ic2 = ic2.assign_coords(y=np.arange(0, N_IC2))
    da = ic2
    # relative humidity from specific humidity, pressure and temperature
    Tc = da["t"] - 273.15
    q = da["q"]
    ps = da["p"]
    w = 0.5 * (1 - np.sqrt(1 - 4 * q))
    e = 0.5 * ps * (-1 + np.sqrt(1 + 4 * w / 0.622))
    es = 610.94 * np.exp(17.625 * Tc / (243.04 + Tc))
    RH = e / es * 100
    RH.data[RH.data > 100] = 100
    RH.name = "RH"
    RH.attrs["long_name"] = "Relative Humidity [%]"
    ds = xr.merge((da[VAR_LIST], RH))
    ds.attrs = {"name": "forcing for FSM musa"}
    ds = ds.transpose("time", "y", "x")
    ds.to_netcdf(OUT_ + fn, compute=True)
    # join with the model cells along x (outer join on y: x = 1 is NaN for y >= 400)
    x0 = xr.open_dataset(X0 + fn).sel(x=0)
    x1 = xr.open_dataset(OUT_ + fn)
    xr.concat([x0, x1], dim="x").to_netcdf(OUT + fn)
    x0.close()
    x1.close()
    return fn


def main():
    global ALL, X0, OUT_, OUT
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, required=True, choices=[23, 24], help="water year (yy)")
    ap.add_argument("--x0-dir", default=None, help="x = 0 files of s1 (default DATA_NP/Forcing<yy>_x0/)")
    ap.add_argument("--out1-dir", default=None, help="x = 1 files (default DATA_NP/Forcing<yy>_/)")
    ap.add_argument("--out-dir", default=None, help="MuSA forcing (default DATA_NP/Forcing<yy>/)")
    a = ap.parse_args()
    X0 = os.path.join(a.x0_dir or X0_DEFAULT.format(yy=a.year), "")
    OUT_ = os.path.join(a.out1_dir or OUT1_DEFAULT.format(yy=a.year), "")
    OUT = os.path.join(a.out_dir or OUT_DEFAULT.format(yy=a.year), "")
    for p in [OUT_, OUT]:
        os.makedirs(p, exist_ok=True)

    ALL = load_all(point_files(TOPO_NP.format(yy=a.year)))
    print("loaded", dict(ALL.sizes), flush=True)
    start = pd.Timestamp(f"20{a.year - 1}-10-01")
    dates = pd.date_range(start=start, end=start + pd.DateOffset(years=1), freq="D")[:-1]
    with concurrent.futures.ProcessPoolExecutor(max_workers=NW) as ex:
        res = list(ex.map(save_day, dates))
    print(f"{len(res)} days written to {OUT}", flush=True)


if __name__ == "__main__":
    main()
