"""Compare SURF/PLEV files written by s1_download_era5.py with the files used for the paper.

For each file: dimensions, coordinates (values and attributes), variables, dtypes,
variable and global attributes, and the maximum absolute difference of every variable.

Inputs:  two inputs/climate folders (new download, reference) and a month YYYYMM.
Outputs: report on stdout.
Environment: conda env `downscaling`.
Run:     python check_s1_era5.py <new dir> <reference dir> 202301
         (light; on a compute node, e.g. inside an sbatch job)
Original: none (check written for the repository).
"""
import sys

import numpy as np
import xarray as xr

# ---- paths and settings ------------------------------------------------------
NEW_DIR, REF_DIR, MONTH = sys.argv[1], sys.argv[2], sys.argv[3]
FILES = ["SURF_{}.nc", "PLEV_{}.nc"]
IGNORE_GLOBAL_ATTRS = ["history"]   # holds the date of the CDS conversion
# -------------------------------------------------------------------------------


def attrs_diff(a, b, ignore=()):
    keys = sorted(set(a) | set(b))
    return {k: (a.get(k), b.get(k)) for k in keys
            if k not in ignore and str(a.get(k)) != str(b.get(k))}


for pattern in FILES:
    name = pattern.format(MONTH)
    new = xr.open_dataset(f"{NEW_DIR}/{name}")
    ref = xr.open_dataset(f"{REF_DIR}/{name}")
    print(f"===== {name}")
    print("dims new", dict(new.sizes), "| ref", dict(ref.sizes))
    print("variables new", list(new.data_vars), "| ref", list(ref.data_vars))
    print("coords new", list(new.coords), "| ref", list(ref.coords))
    for c in ref.coords:
        if c not in new.coords:
            print(f"  coord {c}: missing in new")
            continue
        same = np.array_equal(new[c].values, ref[c].values)
        print(f"  coord {c}: values equal {same}; attrs diff {attrs_diff(new[c].attrs, ref[c].attrs)};"
              f" dtype {new[c].dtype} / {ref[c].dtype}")
    print("global attrs diff (history ignored):", attrs_diff(new.attrs, ref.attrs, IGNORE_GLOBAL_ATTRS))
    print("history new:", new.attrs.get("history"))
    print("history ref:", ref.attrs.get("history"))
    for v in ref.data_vars:
        if v not in new:
            print(f"  {v}: missing in new")
            continue
        a, b = new[v].values, ref[v].values
        d = np.abs(a.astype(np.float64) - b.astype(np.float64))
        print(f"  {v:5s} shape {a.shape} dtype {a.dtype}/{b.dtype}  max|diff| {np.nanmax(d):.3e}"
              f"  NaN new/ref {int(np.isnan(a).sum())}/{int(np.isnan(b).sum())}"
              f"  attrs diff {attrs_diff(new[v].attrs, ref[v].attrs)}"
              f"  encoding zlib/complevel/chunks new {new[v].encoding.get('zlib')}/{new[v].encoding.get('complevel')}/{new[v].encoding.get('chunksizes')}"
              f" ref {ref[v].encoding.get('zlib')}/{ref[v].encoding.get('complevel')}/{ref[v].encoding.get('chunksizes')}")
