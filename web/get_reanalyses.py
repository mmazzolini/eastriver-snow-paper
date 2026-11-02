"""Download three gridded snow products for the two survey dates and put them on the 50 m web grid.

Products (snow depth and SWE; only the two survey dates are downloaded):
    SNODAS   NOAA NOHRSC Snow Data Assimilation System, 30 arc-second (~1 km), daily snapshot at
             06 UTC; NSIDC G02158 (masked CONUS files), open. Model with daily updates from ground,
             airborne and satellite observations.
    UA       University of Arizona daily SWE and snow depth, 800 m (Broxton et al. 2024), 'stable'
             files of climate.arizona.edu/data/UA_SWE/DailyData_800m; open. PRISM-driven snow model with
             SNOTEL and COOP station data assimilated.
    WLDAS    NASA Western Land Data Assimilation System, Noah-MP 3.6 driven by NLDAS-2, 0.01 deg, daily
             mean (WLDAS_NOAHMP001_DA1 D1.0, GES DISC); ends 2024-01-01, so 2023 only. Needs a NASA
             Earthdata token in ~/.edl_token (chmod 600); without it WLDAS is skipped.

On the 50 m grid every cell takes the value of the product cell that contains its centre, so the
products stay block-constant at their native resolution (nothing is interpolated).

Outputs (OUT):
    raw/                            downloaded files (WLDAS CONUS-West files are deleted after the subset)
    <prod>_<yyyymmdd>_subset.nc     the product around East River on its own lat/lon grid (m)
    rean_50m.nc                     <prod>_sd_<yyyymmdd>, <prod>_swe_<yyyymmdd> on the web grid (m)

Environment: gpy-env (xarray, netCDF4, pyproj, requests). Needs internet (compute nodes have it).
Run: sbatch web/sbatch_get_reanalyses.sh
"""
import gzip
import io
import os
import tarfile

import numpy as np
import requests
import xarray as xr
from pyproj import Transformer

# ------------------------------------------------------------------ paths and settings
SCRATCH = "/global/scratch/users/marcomaz"
OUT = os.path.join(SCRATCH, "reanalyses")
GRID_FILE = os.path.join(SCRATCH, "DATA_GP5400_400/23GPpow2NPnbm_var/Post23_mapped230401.nc")   # web grid
DATES = ["2023-04-01", "2024-04-03"]
WLDAS_DATES = ["2023-04-01"]                     # WLDAS ends 2024-01-01
TOKEN_FILE = os.path.expanduser("~/.edl_token")
MARGIN = 0.05                                    # degrees around the grid for the subsets
SNODAS_URL = "https://noaadata.apps.nsidc.org/NOAA/G02158/masked/{y}/{m:02d}_{mon}/SNODAS_{d}.tar"
UA_URL = "https://climate.arizona.edu/data/UA_SWE/DailyData_800m/WY{wy}/UA_SWE_Depth_800m_v1_{d}_stable.nc"
WLDAS_URL = "https://data.gesdisc.earthdata.nasa.gov/data/WLDAS/WLDAS_NOAHMP001_DA1.D1.0/{y}/{m:02d}/WLDAS_NOAHMP001_DA1_{d}.D10.nc"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def log(msg):
    print(msg, flush=True)


def fetch(url, path, headers=None):
    if os.path.exists(path):
        return path
    with requests.get(url, headers=headers or {}, stream=True, timeout=120) as r:
        r.raise_for_status()
        if "html" in r.headers.get("content-type", ""):
            raise RuntimeError(f"{url}: got an HTML page (login required?)")
        with open(path + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(path + ".part", path)
    log(f"downloaded {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.1f} MB)")
    return path


def web_grid():
    g = xr.open_dataset(GRID_FILE)
    gx, gy = np.sort(g.x.values.astype(float)), np.sort(g.y.values.astype(float))
    xx, yy = np.meshgrid(gx, gy)
    lon, lat = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True).transform(xx, yy)
    return gx, gy, lon, lat


def bbox(lon, lat):
    return lon.min() - MARGIN, lon.max() + MARGIN, lat.min() - MARGIN, lat.max() + MARGIN


def cell_index(centres, values):
    """Index of the regular-grid cell (given by its centres, ascending or descending) holding each value."""
    c = np.asarray(centres, float)
    step = c[1] - c[0]
    i = np.floor((values - (c[0] - step / 2)) / step).astype(int)
    i[(i < 0) | (i >= len(c))] = -1
    return i


def to_grid(da, lon, lat):
    """Product on a regular lat/lon grid (dims lat, lon) -> web grid, value of the containing cell."""
    ilat, ilon = cell_index(da.lat.values, lat), cell_index(da.lon.values, lon)
    v = da.values
    out = np.where((ilat >= 0) & (ilon >= 0), v[np.clip(ilat, 0, None), np.clip(ilon, 0, None)], np.nan)
    return out


# ------------------------------------------------------------------ SNODAS
def snodas_header(txt):
    h = {}
    for line in txt.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip()] = v.strip()
    return h


def snodas(date, box):
    d = date.replace("-", "")
    y, m = int(d[:4]), int(d[4:6])
    tar = fetch(SNODAS_URL.format(y=y, m=m, mon=MON[m - 1], d=d), os.path.join(OUT, "raw", f"SNODAS_{d}.tar"))
    out = {}
    with tarfile.open(tar) as t:
        names = t.getnames()
        for code, var in (("1036", "sd"), ("1034", "swe")):
            dat = next(n for n in names if f"ssmv1{code}tS__T0001TTNATS{d}05HP001.dat.gz" in n)
            hdr = dat.replace(".dat.gz", ".txt.gz")
            h = snodas_header(gzip.decompress(t.extractfile(hdr).read()).decode("latin-1"))
            ncol, nrow = int(h["Number of columns"]), int(h["Number of rows"])
            raw = np.frombuffer(gzip.decompress(t.extractfile(dat).read()), dtype=">i2").reshape(nrow, ncol)
            dx, dy = float(h["X-axis resolution"]), float(h["Y-axis resolution"])
            x0, y1 = float(h["Minimum x-axis coordinate"]), float(h["Maximum y-axis coordinate"])
            bx = float(h["Benchmark x-axis coordinate"])
            assert abs(x0 + dx / 2 - bx) < 1e-6, "SNODAS header: unexpected corner convention"
            nod = float(h["No data value"])
            slope, icpt = float(h.get("Data slope", 1)), float(h.get("Data intercept", 0))
            v = np.where(raw == nod, np.nan, raw * slope + icpt) / 1000.0           # mm -> m
            lon = x0 + dx * (np.arange(ncol) + 0.5)
            lat = y1 - dy * (np.arange(nrow) + 0.5)
            da = xr.DataArray(v, dims=("lat", "lon"), coords=dict(lat=lat, lon=lon))
            out[var] = da.sel(lon=slice(box[0], box[1]), lat=slice(box[3], box[2]))
            log(f"SNODAS {date} {var}: units {h.get('Data units')}, slope {slope}; " +
                ", ".join(f"{k}: {v}" for k, v in h.items() if "time" in k.lower() or "hour" in k.lower()))
    return out


# ------------------------------------------------------------------ UA 800 m
def ua(date, box):
    d = date.replace("-", "")
    wy = int(d[:4]) + (1 if int(d[4:6]) >= 10 else 0)
    f = fetch(UA_URL.format(wy=wy, d=d), os.path.join(OUT, "raw", f"UA_800m_{d}.nc"))
    ds = xr.open_dataset(f)
    log(f"UA {date}: variables {list(ds.data_vars)}; " +
        "; ".join(f"{k} [{ds[k].attrs.get('units', '?')}]" for k in ds.data_vars))
    lat_n = next(n for n in ds.coords if n.lower().startswith("lat"))
    lon_n = next(n for n in ds.coords if n.lower().startswith("lon"))
    ds = ds.rename({lat_n: "lat", lon_n: "lon"})
    out = {}
    for var, key in (("sd", "DEPTH"), ("swe", "SWE")):
        name = next(k for k in ds.data_vars if k.upper() == key)
        da = ds[name].squeeze(drop=True)
        units = da.attrs.get("units", "mm").lower()      # "millimeters snow thickness", "millimeters h20"
        da = da / 1000.0 if units.startswith("mm") or units.startswith("millimet") else da
        lat = da.lat.values
        out[var] = da.sel(lon=slice(box[0], box[1]),
                          lat=slice(box[2], box[3]) if lat[1] > lat[0] else slice(box[3], box[2]))
    return out


# ------------------------------------------------------------------ WLDAS
def wldas(date, box):
    if not os.path.exists(TOKEN_FILE):
        log(f"WLDAS {date}: no {TOKEN_FILE}, skipped")
        return None
    token = open(TOKEN_FILE).read().strip()
    hdr = {"Authorization": f"Bearer {token}"}
    # LIS daily means: the file named after day D+1 holds the mean of day D; check with time_bnds
    day = np.datetime64(date)
    for cand in (day, day + 1):
        d = str(cand).replace("-", "")
        # the file of day D+1 at 00 UTC sits in the folder of day D
        folder = cand - 1
        f = os.path.join(OUT, "raw", f"WLDAS_{d}.nc")
        fetch(WLDAS_URL.format(y=int(str(folder)[:4]), m=int(str(folder)[5:7]), d=d), f, hdr)
        ds = xr.open_dataset(f)
        tb = ds["time_bnds"].values.ravel() if "time_bnds" in ds else None
        log(f"WLDAS {d}: time {ds.time.values}, time_bnds {tb}")
        if tb is not None and np.datetime64(tb[0], "D") == day and np.datetime64(tb[-1], "D") == day + 1:
            break
        ds.close()
    else:
        raise RuntimeError("no WLDAS file holds the mean of " + date)
    ds = ds.rename({n: n.lower() for n in ("lat", "lon") if n in ds.coords})
    out = {}
    for var, name in (("sd", "SnowDepth_tavg"), ("swe", "SWE_tavg")):
        da = ds[name].squeeze(drop=True)
        log(f"WLDAS {date} {name} [{da.attrs.get('units')}]")
        da = da / 1000.0 if da.attrs.get("units", "").lower() in ("kg m-2", "kg/m2", "mm") else da
        out[var] = da.sel(lon=slice(box[0], box[1]), lat=slice(box[2], box[3])).load()
    ds.close()
    for cand in (day, day + 1):     # the CONUS-West files are ~0.9 GB each
        p = os.path.join(OUT, "raw", f"WLDAS_{str(cand).replace('-', '')}.nc")
        if os.path.exists(p):
            os.remove(p)
    return out


def main():
    os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
    gx, gy, lon, lat = web_grid()
    box = bbox(lon, lat)
    log(f"web grid {len(gy)} x {len(gx)}; lon {box[0]:.3f}..{box[1]:.3f}, lat {box[2]:.3f}..{box[3]:.3f}")
    res = xr.Dataset(coords=dict(y=gy, x=gx))
    prods = [("snodas", snodas, DATES), ("ua", ua, DATES), ("wldas", wldas, WLDAS_DATES)]
    for prod, fn, dates in prods:
        for date in dates:
            d = date.replace("-", "")
            sub = fn(date, box)
            if sub is None:
                continue
            xr.Dataset({k: v for k, v in sub.items()}).to_netcdf(os.path.join(OUT, f"{prod}_{d}_subset.nc"))
            for var, da in sub.items():
                g = to_grid(da, lon, lat)
                res[f"{prod}_{var}_{d}"] = (("y", "x"), g)
                res[f"{prod}_{var}_{d}"].attrs = dict(units="m", product=prod, date=date,
                                                      native_cells=int(da.size))
                log(f"{prod} {var} {date}: native {da.shape}, on the grid: {np.isfinite(g).mean() * 100:.0f} % "
                    f"finite, mean {np.nanmean(g):.3f} m, range {np.nanmin(g):.3f}..{np.nanmax(g):.3f} m")
    res.attrs = dict(note="each 50 m cell holds the value of the product cell containing its centre (no "
                          "interpolation); see web/get_reanalyses.py", crs="EPSG:32613")
    res.to_netcdf(os.path.join(OUT, "rean_50m.nc"))
    log(f"wrote rean_50m.nc: {sorted(res.data_vars)}")


if __name__ == "__main__":
    main()
