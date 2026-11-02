"""Daily MuSA forcing of the 5400 model cells (x = 0) from the TopoPyScale output.

The TopoPyScale output of the model points (01_era5_downscaling/s2, GP_points.csv; here the
original run correct_mu025) holds one hourly file per point, down_pt_<n>.nc, for 2022-10-01 to 2024-09-30. This script sorts the files by point number,
keeps points 0..5399 (the 5400 model cells, y = point number; the original run also holds
100 unused points 5400..5499), selects one water year and
writes one netCDF file per day with x = 0 only. Variables, units, relative humidity and
file layout follow s2_forcing_ic2_cells.py (x = 1), which joins both halves.

Inputs:
    <TOPO>/down_pt_0000.nc ... down_pt_5399.nc   hourly TopoPyScale output of the model cells
Outputs:
    <out-dir>/<YYYY-MM-DD>.nc   one file per day of the water year (365 or 366 files);
                                dims (time 24, y 5400, x 1), x = 0; variables SW, LW, tp, t,
                                ws, q, p (TopoPyScale units) and RH (%)
Environment: downscaling (../environments/downscaling.yml); 8 cores. The wrapper sets
    NPY_DISABLE_CPU_FEATURES (AVX-512 off) so that RH matches the files used bit for bit; with
    numpy's AVX-512 exp, RH differs by up to 6e-14 % (README, Checks).
Run (from 04_forcing): sbatch sbatch_s1_forcing_model_cells.sh 23   (and 24)
    on a compute node:   python s1_forcing_model_cells.py --year 23 [--out-dir DIR]
Original: none as a single script. The x = 0 forcing used in the paper runs was copied by
    B/GP4MuSA/NP/np_forcing.py from DATA_GP5400_400/Forcing<yy>, written by an older chain
    (B/GP4MuSA/treat_TSpoints_get_ind_pts<yy>.py, x = 0 block, via DATA_GP5500/Forcing100|124).
    The processing here is that of np_forcing.py applied to these points; README, Checks,
    compares its output with the files used.
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
TOPO = SCRATCH + "downscali3/outputs_alt/downscaled/correct_mu025/"  # TopoPyScale output, model points
OUT_DEFAULT = SCRATCH + "DATA_NP/Forcing{yy}_x0/"                     # default --out-dir
N_MODEL = 5400                                                        # points 0..5399 = model cells
VAR_LIST = ["SW", "LW", "tp", "t", "ws", "q", "p"]                    # variables kept (+ RH)
DROP = ["u", "v", "precip_lapse_rate", "wd", "w", "cse", "SW_diffuse", "cos_illumination", "SW_direct"]
NW = int(os.environ.get("SLURM_NTASKS", "8"))                         # worker processes

ALL = None   # all points for the water year, set in main() and shared with the workers (fork)
OUT = None


def point_files():
    """down_pt_<n>.nc sorted by point number n, first N_MODEL points."""
    files = glob(TOPO + "down_pt_*.nc")
    num = [int(re.search(r"down_pt_(\d+)\.nc$", f).group(1)) for f in files]
    files = [f for _, f in sorted(zip(num, files))]
    assert sorted(num)[:N_MODEL] == list(range(N_MODEL)), f"expected down_pt_0000..{N_MODEL - 1}"
    return files[:N_MODEL]


def load_all(files, start, end):
    """All model points for the water year, read once."""
    pts = []
    for f in files:
        ds = xr.open_dataset(f, drop_variables=DROP).sel(time=slice(start, end)).load()
        ds.point_id.values = int(ds.point_id.values)
        pts.append(ds)
        ds.close()
    return xr.concat(pts, dim="point_id")


def save_day(d):
    fn = d.strftime("%Y-%m-%d") + ".nc"
    if os.path.exists(OUT + fn):
        return fn
    da = ALL.sel(time=slice(d, d + np.timedelta64(23, "h")))
    da = da.rename({"point_id": "y"}).assign_coords(x=0).expand_dims(dim="x")
    da = da.assign_coords(y=np.arange(0, N_MODEL))
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
    ds.to_netcdf(OUT + fn, compute=True)
    return fn


def main():
    global ALL, OUT
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, required=True, choices=[23, 24], help="water year (yy)")
    ap.add_argument("--out-dir", default=None, help="output folder (default DATA_NP/Forcing<yy>_x0/)")
    a = ap.parse_args()
    OUT = os.path.join(a.out_dir or OUT_DEFAULT.format(yy=a.year), "")
    os.makedirs(OUT, exist_ok=True)

    start = pd.Timestamp(f"20{a.year - 1}-10-01")
    dates = pd.date_range(start=start, end=start + pd.DateOffset(years=1), freq="D")[:-1]
    ALL = load_all(point_files(), dates[0], dates[-1] + pd.Timedelta(hours=23))
    print("loaded", dict(ALL.sizes), flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=NW) as ex:
        res = list(ex.map(save_day, dates))
    print(f"{len(res)} days written to {OUT}", flush=True)


if __name__ == "__main__":
    main()
