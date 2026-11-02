"""Checks of the daily MuSA forcing of one water year (exit code 1 if a check fails).

1 structure: one file per day of the water year, dims (time 24, y 5400, x 2), variables;
  no NaN at the active cells (x = 0 all y, x = 1 y < 400).
2 identity with the TopoPyScale output, every 30th day, all hours and raw variables:
  x = 0, y = n equals point n of the model-point project (sorted, points 0..5399);
  x = 1, y = n equals point n of the IC2-cell project (sorted, points 0..399).
3 physical ranges at x = 1.
4 IC2 cells vs model cells: annual mean t and total tp against a quadratic fit on elevation
  of the model cells; daily t correlation with the nearest model cell (distance + elevation).

Inputs:
    <forcing-dir>/<YYYY-MM-DD>.nc                     forcing files (s2_forcing_ic2_cells.py)
    <TOPO_MODEL>/down_pt_<nnnn>.nc, <TOPO_IC2>/down_pt_<nnn>.nc   TopoPyScale output
    <POINTS_IC2>, <POINTS_MODEL>                      cell coordinates (x, y; UTM 13N)
    <TOPO_NC>                                         terrain variables on the 50 m grid (Zs)
Outputs: report on stdout; optional figure (--fig) of annual mean t and total tp vs elevation.
Environment: downscaling (../environments/downscaling.yml).
Run (from 04_forcing): sbatch sbatch_s3_check_forcing.sh 23   (and 24)
    on a compute node:   python s3_check_forcing.py --year 23 [--forcing-dir D] [--fig F.png]
Original: B/GP4MuSA/NP/np_check_forcing.py (sections 1, 2, 4; there the x = 0 identity was
    checked against DATA_GP5400_400/Forcing<yy>, and its section 3, a comparison with the
    earlier IC2 cell selection, is not included) and the x = 0 identity test of
    B/GP4MuSA/NP/chk_x0_order.py.
"""
import argparse
import os
import re
import sys
from glob import glob

import numpy as np
import pandas as pd
import xarray as xr

# ---- paths and settings
SCRATCH = "/global/scratch/users/marcomaz/"
FORCING_DEFAULT = SCRATCH + "DATA_NP/Forcing{yy}/"                         # default --forcing-dir
TOPO_MODEL = SCRATCH + "downscali3/outputs_alt/downscaled/correct_mu025/"  # model-point project
TOPO_IC2 = SCRATCH + "downscaliNP{yy}/outputs/downscaled/"                 # IC2-cell project
POINTS_IC2 = SCRATCH + "DATA_NP/points/IC2NP_{yy}.csv"                     # 400 IC2 cells
POINTS_MODEL = SCRATCH + "downscali3/inputs/dem/GP_points.csv"             # the 5400 model cells
TOPO_NC = SCRATCH + "all_data50from3_1105.nc"                              # Zs (elevation)
N_MODEL, N_IC2 = 5400, 400
RAW = ["SW", "LW", "tp", "t", "ws", "q", "p"]
VARS = RAW + ["RH"]
LIM = {"t": (220, 310), "tp": (0, 60), "SW": (0, 1450), "LW": (80, 500), "RH": (0, 100.0001),
       "ws": (0, 60), "p": (50000, 80000), "q": (0, 0.03)}

fails = []


def check(ok, msg):
    print(("  OK   " if ok else "  FAIL ") + msg, flush=True)
    if not ok:
        fails.append(msg)


def sorted_points(folder, n):
    files = glob(folder + "down_pt_*.nc")
    num = [int(re.search(r"down_pt_(\d+)\.nc$", f).group(1)) for f in files]
    files = [f for _, f in sorted(zip(num, files))]
    assert sorted(num)[:n] == list(range(n)), f"{folder}: expected points 0..{n - 1}"
    return files[:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, required=True, choices=[23, 24], help="water year (yy)")
    ap.add_argument("--forcing-dir", default=None, help="forcing folder (default DATA_NP/Forcing<yy>/)")
    ap.add_argument("--fig", default=None, help="write a figure to this file")
    a = ap.parse_args()
    yy = a.year
    folder = os.path.join(a.forcing_dir or FORCING_DEFAULT.format(yy=yy), "")
    t0 = pd.Timestamp(f"20{yy - 1}-10-01")
    dates = pd.date_range(start=t0, end=t0 + pd.DateOffset(years=1), freq="D")[:-1]
    print(f"forcing {folder} (20{yy})", flush=True)

    # ---- 1. structure, NaN; keep t, tp sums and every 30th day for section 2
    fn = sorted(glob(folder + "*.nc"))
    check([os.path.basename(f) for f in fn] == [d.strftime("%Y-%m-%d") + ".nc" for d in dates],
          f"{len(fn)} daily files, one per day of the water year ({len(dates)})")
    d0 = xr.open_dataset(fn[0])
    check(dict(d0.sizes) == {"time": 24, "y": N_MODEL, "x": 2} and set(d0.data_vars) == set(VARS)
          and list(d0.x.values) == [0, 1] and np.array_equal(d0.y.values, np.arange(N_MODEL)),
          f"dims {dict(d0.sizes)}, x {list(d0.x.values)}, y 0..{N_MODEL - 1}, variables {sorted(d0.data_vars)}")
    d0.close()
    sample = list(range(0, len(fn), 30))
    F = {v: [] for v in RAW}                   # sampled days, (24 * len(sample), y, x)
    hours = []
    tday, tpsum, nan_bad = [], 0, 0
    rng = {v: [np.inf, -np.inf] for v in VARS}
    for i, f in enumerate(fn):
        d = xr.open_dataset(f).load()
        nan_bad += int(sum(np.isnan(d[v].values[:, :, 0]).sum() + np.isnan(d[v].values[:, :N_IC2, 1]).sum()
                           for v in VARS))
        if i in sample:
            hours.append(d.time.values)
            for v in RAW:
                F[v].append(d[v].values)
        for v in VARS:
            x1 = d[v].values[:, :N_IC2, 1]
            rng[v] = [min(rng[v][0], np.nanmin(x1)), max(rng[v][1], np.nanmax(x1))]
        tday.append(d["t"].values.mean(0))     # (y, x)
        tpsum = tpsum + d["tp"].values.sum(0)
        d.close()
    check(nan_bad == 0, f"no NaN at active cells ({nan_bad} found)")
    hours = np.concatenate(hours)
    F = {v: np.concatenate(F[v], 0) for v in RAW}

    # ---- 2. identity with the TopoPyScale output (point order)
    for x, topo, n in [(0, TOPO_MODEL, N_MODEL), (1, TOPO_IC2.format(yy=yy), N_IC2)]:
        P = {v: np.empty((len(hours), n)) for v in RAW}
        for j, f in enumerate(sorted_points(topo, n)):
            with xr.open_dataset(f) as o:
                sl = o[RAW].sel(time=hours)
                for v in RAW:
                    P[v][:, j] = sl[v].values
        dif = {v: float(np.abs(F[v][:, :n, x] - P[v]).max()) for v in RAW}
        same = np.all([np.all(F[v][:, :n, x] == P[v], 0) for v in RAW], 0)   # per cell
        check(same.all(), f"x={x}: y == TopoPyScale point number for {same.sum()}/{n} cells "
              f"({len(sample)} days, {len(hours)} h, {len(RAW)} variables; max |diff| {max(dif.values()):.1e})")

    # ---- 3. ranges at x = 1
    for v, (lo, hi) in LIM.items():
        check(lo <= rng[v][0] and rng[v][1] <= hi,
              f"{v} range at x=1 {rng[v][0]:.4g} .. {rng[v][1]:.4g} (allowed {lo}..{hi})")

    # ---- 4. IC2 cells against the model cells
    tday = np.array(tday)                      # (day, y, x)
    tmean = tday.mean(0)
    pts_new = pd.read_csv(POINTS_IC2.format(yy=yy))
    pts_un = pd.read_csv(POINTS_MODEL)[:N_MODEL]
    check(np.array_equal(pts_un.name.values, np.arange(N_MODEL)) and np.array_equal(pts_new.name.values, np.arange(N_IC2)),
          f"point lists: names 0..{N_MODEL - 1} (model cells) and 0..{N_IC2 - 1} (IC2 cells) in row order")
    topo = xr.open_dataset(TOPO_NC)["Zs"]
    at = lambda p: topo.sel(x=xr.DataArray(p.x.values, dims="p"), y=xr.DataArray(p.y.values, dims="p"),  # noqa: E731
                            method="nearest").values
    z0, z1 = at(pts_un), at(pts_new)
    t0m, t1m = tmean[:, 0], tmean[:N_IC2, 1]
    tp0, tp1 = tpsum[:, 0], tpsum[:N_IC2, 1]
    ct = np.polyfit(z0, t0m, 2)
    cp = np.polyfit(z0, np.log(tp0), 2)
    rt = t1m - np.polyval(ct, z1)
    rp = tp1 / np.exp(np.polyval(cp, z1))
    rt0 = t0m - np.polyval(ct, z0)
    print(f"  annual mean t residual vs model-cell fit: IC2 cells p5/p50/p95 {np.percentile(rt, [5, 50, 95]).round(2)} K "
          f"(model cells {np.percentile(rt0, [5, 50, 95]).round(2)})")
    print(f"  annual tp ratio vs model-cell fit: IC2 cells p5/p50/p95 {np.percentile(rp, [5, 50, 95]).round(2)}")
    check((np.abs(rt) > 2).sum() <= 4, f"IC2 cells with |t residual| > 2 K: {(np.abs(rt) > 2).sum()}")
    check(((rp < 0.5) | (rp > 2)).sum() <= 4, f"IC2 cells with tp ratio outside 0.5-2: {((rp < 0.5) | (rp > 2)).sum()}")
    dist = (np.hypot(pts_new.x.values[:, None] - pts_un.x.values[None], pts_new.y.values[:, None] - pts_un.y.values[None]) / 1000
            + np.abs(z1[:, None] - z0[None]) / 100)
    nn = dist.argmin(1)
    cc = np.array([np.corrcoef(tday[:, i, 1], tday[:, nn[i], 0])[0, 1] for i in range(N_IC2)])
    check(np.quantile(cc, 0.01) > 0.95, f"daily t correlation with nearest model cell: min {cc.min():.3f}, median {np.median(cc):.4f}")

    if a.fig:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
        ax[0].scatter(z0, t0m - 273.15, s=2, c="#c9c8c2", label="model cells (x=0)")
        ax[0].scatter(z1, t1m - 273.15, s=6, c="#2a78d6", label="IC2 cells (x=1)")
        ax[0].set(xlabel="elevation (m)", ylabel="annual mean t (°C)", title=f"20{yy}: temperature")
        ax[0].legend(fontsize=8)
        ax[1].scatter(z0, tp0, s=2, c="#c9c8c2")
        ax[1].scatter(z1, tp1, s=6, c="#2a78d6")
        ax[1].set(xlabel="elevation (m)", ylabel="annual tp (forcing units, summed)", title="precipitation", yscale="log")
        fig.tight_layout()
        fig.savefig(a.fig, dpi=110)
    print(f"\n{'ALL CHECKS PASSED' if not fails else 'FAILED: ' + '; '.join(fails)}", flush=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
