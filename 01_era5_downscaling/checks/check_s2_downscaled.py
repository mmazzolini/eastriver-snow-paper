"""Compare down_pt files of a TopoPyScale test project with the files used for the paper.

For every common point: time axis, point_id and the maximum absolute difference of every
variable. Also compares the project files computed on the way (ds_param.nc,
da_horizon.nc, ds_solar.nc for the same points, df_centroids.pck) with the original
project's files.

Inputs:  test project folder, original project outputs folder, reference down_pt folder,
         points: n (the first n) or a:b (positions a .. b-1).
Outputs: report on stdout.
Environment: conda env `downscaling`.
Run:     python check_s2_downscaled.py <test project> <orig outputs dir> <ref down_pt dir> 10|5390:5400
         (on a compute node, e.g. sbatch sbatch_check.sh check_s2_downscaled.py ...)
Original: none (check written for the repository).
"""
import sys

import numpy as np
import pandas as pd
import xarray as xr

# ---- paths and settings ------------------------------------------------------
TEST_DIR, ORIG_OUT, REF_DIR, PTS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
FIRST, LAST = (int(v) for v in PTS.split(":")) if ":" in PTS else (0, int(PTS))
N_DIGITS = 4                         # down_pt_0000.nc .. down_pt_5399.nc
# -------------------------------------------------------------------------------


def maxdiff(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    both_nan = np.isnan(a) & np.isnan(b)
    d = np.abs(a - b)
    d[both_nan] = 0.0
    return np.nanmax(d) if d.size else np.nan, int((np.isnan(a) != np.isnan(b)).sum())


print("===== down_pt files")
worst = {}
for i in range(FIRST, LAST):
    name = f"down_pt_{str(i).zfill(N_DIGITS)}.nc"
    new = xr.open_dataset(f"{TEST_DIR}/outputs/downscaled/{name}")
    ref = xr.open_dataset(f"{REF_DIR}/{name}")
    same_time = np.array_equal(new.time.values, ref.time.values)
    vars_new, vars_ref = set(new.data_vars), set(ref.data_vars)
    line = [f"{name}: time equal {same_time}, point_id {int(new.point_id)}/{int(ref.point_id)}"]
    if vars_new != vars_ref:
        line.append(f"variables only new {vars_new - vars_ref}, only ref {vars_ref - vars_new}")
    for v in sorted(vars_new & vars_ref):
        d, nan_mismatch = maxdiff(new[v].values, ref[v].values)
        worst[v] = max(worst.get(v, 0.0), d)
        if d > 0 or nan_mismatch:
            line.append(f"{v} {d:.3e} (NaN mismatch {nan_mismatch})")
    print("; ".join(line))
print("max |diff| over the points, per variable:")
for v in sorted(worst):
    print(f"  {v:18s} {worst[v]:.3e}")

print("===== project files")
dp_new = xr.open_dataset(f"{TEST_DIR}/outputs/ds_param.nc")
dp_ref = xr.open_dataset(f"{ORIG_OUT}/ds_param.nc")
for v in ["elevation", "slope", "aspect", "aspect_cos", "aspect_sin", "svf"]:
    print(f"ds_param {v:10s} max|diff| {maxdiff(dp_new[v].values, dp_ref[v].values)[0]:.3e}")
h_new = xr.open_dataset(f"{TEST_DIR}/outputs/da_horizon.nc").horizon
h_ref = xr.open_dataset(f"{ORIG_OUT}/da_horizon.nc").horizon
print(f"da_horizon max|diff| {maxdiff(h_new.values, h_ref.values)[0]:.3e}")
s_new = xr.open_dataset(f"{TEST_DIR}/outputs/ds_solar.nc").isel(point_id=slice(FIRST, LAST))
s_ref = xr.open_dataset(f"{ORIG_OUT}/ds_solar.nc").isel(point_id=slice(FIRST, LAST))
print("ds_solar time equal", np.array_equal(s_new.time.values, s_ref.time.values),
      "point_id equal", np.array_equal(s_new.point_id.values, s_ref.point_id.values))
for v in s_ref.data_vars:
    print(f"ds_solar {v:10s} max|diff| {maxdiff(s_new[v].values, s_ref[v].values)[0]:.3e}")
c_new = pd.read_pickle(f"{TEST_DIR}/outputs/df_centroids.pck")
c_ref = pd.read_pickle(f"{ORIG_OUT}/df_centroids.pck")
print("df_centroids rows new/ref", len(c_new), len(c_ref), "(compared on the common first rows)")
n = min(len(c_new), len(c_ref))
c_new, c_ref = c_new.iloc[:n], c_ref.iloc[:n]
print("df_centroids point_id equal", np.array_equal(c_new.point_id.values, c_ref.point_id.values))
for col in ["x", "y", "lat", "lon", "elevation", "slope", "aspect", "aspect_cos", "aspect_sin", "svf"]:
    print(f"df_centroids {col:10s} max|diff| {maxdiff(c_new[col].values, c_ref[col].values)[0]:.3e}")
