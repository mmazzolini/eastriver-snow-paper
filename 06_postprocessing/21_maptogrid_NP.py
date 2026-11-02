"""Map the prior and posterior ensembles of the four paper runs to the 50 m grid on the ASO date.

One (run, prior | posterior) per call (task 0-7, see TASKS). The snow depth of the 5400 model
cells (x = 0 of En_snd<yy>[_Pr].nc) on the ASO date is the training set of a regression on
the terrain features of all_data50from3_1702.nc, one member at a time: GP runs use the
Matern 5/2 kernel with the variance and length scales of the GP model (var_4.npy,
lnscale_4.npy); GC runs use the Gaspari-Cohn kernel, length scale 5, variance = mean over
members of the variance of the field. sigma_y = 0.5 for both (kernels in mapping_kernels.py).

Inputs:
    <DATA>/<run>/En_snd<yy>.nc, En_snd<yy>_Pr.nc     ensembles (20b_save_netEN.py), mm
    <ALL_DATA>      terrain features on the 50 m grid; grid cells = rows of 2022-04-21 without NaN
    <SCALER>        feature scaler (scikit-learn StandardScaler, joblib)
    <GP_DIR>/indPTS_4.npy, var_4.npy, lnscale_4.npy   scaled features of the 5400 model cells,
                    GP variance and length scales
Outputs (in <DATA>/<run>/, or --out-dir):
    <Prior|Post><yy>_mapped<yymmdd>_ens.nc   variable Prior | Posterior (en, y, x, date), m
    <Prior|Post><yy>_mapped<yymmdd>.nc       ensemble mean
Environment: gpy-env (../environments/gpy-env.yml); MUSA_POST_NWORKERS (processes, default 4).
Run (from 06_postprocessing): sbatch sbatch_21_maptogrid_NP.sh          (array 0-7)
    one task on a compute node: python 21_maptogrid_NP.py <task> [--members 0,1] [--out-dir DIR]
    (--members maps only these members; the GC variance still uses all members)
Original: B/Post/21_maptogrid_NP.py, which loaded map_one_ensemble from
    B/Post/21_maptogridGP_ensembles_all_20230401.py and B/Post/21_maptogridGC_ensembles_all_onedate.py
    (here mapping_kernels.py).
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import joblib
import numpy as np
import xarray as xr

from mapping_kernels import map_one_ensemble_gc, map_one_ensemble_gp

# ---- paths and settings
SCRATCH = "/global/scratch/users/marcomaz/"
DATA = SCRATCH + "DATA_GP5400_400/"                  # run folders <run>/ with En_snd<yy>*.nc
ALL_DATA = SCRATCH + "all_data50from3_1702.nc"       # terrain features, 50 m grid
SCALER = SCRATCH + "GP_models/scaler.save"
GP_DIR = SCRATCH + "GP_models/5500_iter/"            # indPTS_4, var_4, lnscale_4
RUNS = [  # (kernel, year, run, ASO date)
    ("GP", 23, "23GPpow2NPnbm_var", "2023-04-01"),
    ("GP", 24, "24GPpow2NPnb_var", "2024-04-03"),
    ("GC", 23, "23GCpow2NP_var", "2023-04-01"),
    ("GC", 24, "24GCpow2NP_var", "2024-04-03"),
]
TASKS = [(r, p) for r in RUNS for p in ("Prior", "Posterior")]   # 0/1 23GP, 2/3 24GP, 4/5 23GC, 6/7 24GC
SIGMA_Y = 0.5
GC_LENGTHSCALE = 5
FEATURE_DATE = "2022-04-21"                          # date whose rows define the grid cells
DROP_FEATURES = ["Sx200", "Sx100", "sinA", "TPI1000", "DAH"]
NWORKERS = int(os.environ.get("MUSA_POST_NWORKERS", "4"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("task", type=int, nargs="?", default=None, help="0-7 (default SLURM_ARRAY_TASK_ID)")
    ap.add_argument("--members", default=None, help="comma-separated members to map (default all)")
    ap.add_argument("--out-dir", default=None, help="output folder (default <DATA>/<run>/)")
    a = ap.parse_args()
    tid = a.task if a.task is not None else int(os.environ["SLURM_ARRAY_TASK_ID"])
    (kernel, yy, run, date), which = TASKS[tid]
    stem = "Prior" if which == "Prior" else "Post"
    tag = date[2:].replace("-", "")
    in_file = os.path.join(DATA, run, f"En_snd{yy}_Pr.nc" if which == "Prior" else f"En_snd{yy}.nc")
    out_dir = a.out_dir or os.path.join(DATA, run)
    os.makedirs(out_dir, exist_ok=True)
    out_ens = os.path.join(out_dir, f"{stem}{yy}_mapped{tag}_ens.nc")
    out_mean = os.path.join(out_dir, f"{stem}{yy}_mapped{tag}.nc")
    print(f"task {tid}: {kernel} {run} {which} {date}\n  in  {in_file}\n  out {out_ens}", flush=True)

    map_one_ensemble = map_one_ensemble_gp if kernel == "GP" else map_one_ensemble_gc

    results = xr.open_dataset(in_file)
    snd = results.sel(t=date).snd            # (y, x, en), mm
    assert snd.dims == ("y", "x", "en"), snd.dims
    x0 = snd.sel(x=0).values                 # (5400, en) = flatten(order="F")[:5400]
    assert np.isfinite(x0).all() and (x0 >= 0).all(), "missing / filled x=0 cells"
    print(f"  x=0 mean snd {x0.mean() / 1000:.3f} m", flush=True)

    all_data = xr.open_dataset(ALL_DATA)
    all_data = all_data.drop_vars(DROP_FEATURES, errors="ignore")
    df = all_data.drop_vars(["spatial_ref"], errors="ignore").to_dataframe().dropna(subset=["Xs"])
    df0_valid = df.loc[df.index.get_level_values("date") == FEATURE_DATE].dropna().copy()
    scaler = joblib.load(SCALER)
    pred_features = scaler.transform(df0_valid.drop(columns="snow_depth"))

    all_ptsT = np.load(os.path.join(GP_DIR, "indPTS_4.npy"))
    sigma_y = SIGMA_Y
    if kernel == "GP":
        var = np.load(os.path.join(GP_DIR, "var_4.npy"))
        ls = np.load(os.path.join(GP_DIR, "lnscale_4.npy"))
    else:
        var = np.mean(np.var(x0 / 1000, axis=0))   # mean over members of the field variance (m2)
        ls = GC_LENGTHSCALE
    print(f"  var {np.atleast_1d(var)[0]:.4f}", flush=True)

    nsize = x0.shape[1]
    members = list(range(nsize)) if a.members is None else [int(m) for m in a.members.split(",")]
    tasks = [(e, x0[:, e].astype(float), all_ptsT, pred_features, var, ls, sigma_y) for e in members]
    workers = max(1, min(NWORKERS, nsize))

    by_en = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(map_one_ensemble, t) for t in tasks]
        for i, f in enumerate(as_completed(futs), 1):
            e, vals = f.result()
            by_en[e] = vals
            if i % 10 == 0:
                print(f"  {i}/{len(members)}", flush=True)

    das = []
    for e in members:
        d = df0_valid.copy()
        d[which] = by_en[e]
        da = d[which].to_xarray()
        da.name = which
        das.append(da.assign_coords(en=e).expand_dims("en"))
    ens = xr.concat(das, dim="en").sortby("en")
    ens.to_netcdf(out_ens)
    ens.mean(dim="en").to_netcdf(out_mean)
    print(f"  saved; basin mean {float(ens.mean()):.3f} m\nDone", flush=True)


if __name__ == "__main__":
    main()
