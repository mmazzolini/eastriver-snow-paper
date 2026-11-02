"""Download hourly ERA5 single-level (SURF) and pressure-level (PLEV) data as the monthly files TopoPyScale 0.2.2 reads.

For every month of the period one SURF request and one PLEV request per pressure level
are sent to the CDS with cdsapi (several requests in parallel; the CDS refuses a PLEV
request with all six levels and variables of a month, "cost limits exceeded"). The CDS
returns a zip when instant and accumulated SURF fields are mixed; it is unpacked and
the two files are merged. The per-level PLEV files of a month are joined along
pressure_level. The files are then renamed and cleaned as TopoPyScale's remap_CDSbeta
did (valid_time -> time, pressure_level -> level in increasing pressure, number/expver
and four unused SURF variables dropped). Months whose SURF/PLEV file already exists are
skipped, and finished downloads are kept until their month is written, so an
interrupted or partly failed run can be restarted with the same command.

Inputs:  config_era5.yml (period, extent, grid, variables, levels, output folder);
         CDS credentials in ~/.cdsapirc, read by cdsapi (new CDS, url .../api).
Outputs: <output_dir>/SURF_YYYYMM.nc (z, d2m, sp, t2m, strd, ssrd, tp) and
         <output_dir>/PLEV_YYYYMM.nc (z, t, u, v, q, r on 500..1000 hPa), 5 x 5 grid,
         dims (time, [level,] latitude, longitude).
Environment: conda env `downscaling` (Python 3.9, cdsapi 0.7.5, xarray 2023.4.1, netCDF4).
Run:     sbatch sbatch_s1_download_era5.sh [config_era5.yml]
         (python s1_download_era5.py [config]; needs outbound internet, which the
         savio4_htc compute nodes have)
Original: requests of TopoPyScale 0.2.7 fetch_era5.py (env `downi`, locally edited:
         era5_request_surf, era5_request_plev, process_SURF_file, remap_CDSbeta), run from
         /global/scratch/users/marcomaz/downscali3/finish_downscalin_new_approach.ipynb
         cells 17 (get_era5), 19 (join of per-level PLEV files), 21 (process_SURF_file),
         22 (remap_netcdf). The PLEV files were downloaded in pieces (600-1000 hPa without r,
         r alone, 500 hPa alone) and joined in
         /global/scratch/users/marcomaz/downscali3/merge_plev_vars.ipynb cells 2-5 and 7-9;
         here each level is one request with all six variables.
"""
import os
import shutil
import sys
import zipfile
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path

import cdsapi
import pandas as pd
import xarray as xr
import yaml

# ---- paths and settings ------------------------------------------------------
HERE = Path(__file__).resolve().parent
CONFIG_FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "config_era5.yml"
SURF_FILE = "SURF_{:04d}{:02d}.nc"     # TopoPyScale globs inputs/climate/SURF*.nc and PLEV*.nc
PLEV_FILE = "PLEV_{:04d}{:02d}.nc"
RAW_SUBDIR = "raw"                     # CDS downloads; a sub-folder is not matched by that glob
SURF_DATASET = "reanalysis-era5-single-levels"
PLEV_DATASET = "reanalysis-era5-pressure-levels"
TIME_STEPS = {"1H": ["%02d:00" % h for h in range(24)],
              "3H": ["%02d:00" % h for h in range(0, 24, 3)],
              "6H": ["%02d:00" % h for h in range(0, 24, 6)]}
DAYS = ["%02d" % d for d in range(1, 32)]   # the CDS ignores days a month does not have
# -------------------------------------------------------------------------------


def log(msg):
    print(msg, flush=True)


def month_list(start, end):
    """Months to download, as TopoPyScale's retrieve_era5 builds them."""
    dates = pd.date_range(start, pd.Timestamp(end) - pd.offsets.Day() + pd.offsets.MonthEnd(),
                          freq="M", inclusive="both")
    return [(d.year, d.month) for d in dates]


def cds_area(cfg):
    """[N, W, S, E] strings: project extent widened by buffer_deg, as TopoPyScale's get_era5."""
    latN, latS, lonW, lonE = cfg["extent"]
    b = cfg["buffer_deg"]
    return [str(latN + b), str(lonW - b), str(latS - b), str(lonE + b)]


def surf_request(cfg, year, month):
    return {"variable": cfg["surf_variables"],
            "product_type": [cfg["product_type"]],
            "area": cds_area(cfg),
            "year": str(year),
            "month": "%02d" % month,
            "day": DAYS,
            "time": TIME_STEPS[cfg["timestep"]],
            "grid": cfg["grid"],
            "data_format": "netcdf",
            "download_format": "unarchived"}


def plev_request(cfg, year, month, level):
    return {"product_type": [cfg["product_type"]],
            "area": cds_area(cfg),
            "variable": cfg["plev_variables"],
            "pressure_level": [level],
            "year": str(year),
            "month": "%02d" % month,
            "day": DAYS,
            "time": TIME_STEPS[cfg["timestep"]],
            "grid": cfg["grid"],
            "data_format": "netcdf",
            "download_format": "unarchived"}


def download(job):
    """Retrieve one request into raw/<name>; written as .part first so a crash leaves no
    file that looks complete. Returns True on success."""
    dataset, request, target = job
    if target.exists():
        log(f"{target.name}: raw download present")
        return True
    part = target.with_name(target.name + ".part")
    log(f"{target.name}: requesting {dataset}")
    try:
        cdsapi.Client().retrieve(dataset, request, str(part))
    except Exception as e:   # keep the other requests going; a rerun retries this one
        log(f"{target.name}: FAILED: {e}")
        return False
    os.replace(part, target)
    log(f"{target.name}: downloaded")
    return True


def unpack(raw, work):
    """Return the CDS download as one netCDF file (TopoPyScale's process_SURF_file).

    With instant and accumulated fields (SURF) the CDS sends a zip of two netCDF files
    (stepType-instant, stepType-accum), which are merged with xr.merge. The instant file
    goes first: in the original run it came first, so the global attributes and the
    variable order of the merged file are those of the instant file. A plain netCDF
    download (PLEV) is returned unchanged."""
    if not zipfile.is_zipfile(raw):
        return raw
    unzip_dir = work / (raw.stem + "_unzip")
    with zipfile.ZipFile(raw, "r") as zf:
        zf.extractall(unzip_dir)
    nc_files = sorted(str(unzip_dir / f) for f in os.listdir(unzip_dir) if f.endswith(".nc"))
    nc_files.sort(key=lambda f: "instant" not in os.path.basename(f))
    merged = work / (raw.stem + "_merged.nc")
    datasets = [xr.open_dataset(f) for f in nc_files]
    try:
        xr.merge(datasets).to_netcdf(merged)
    finally:
        for ds in datasets:
            ds.close()
    shutil.rmtree(unzip_dir)
    return merged


def join_levels(level_files, out):
    """Join the per-level PLEV downloads along pressure_level (cell 19 of the original
    notebook). They are joined from 1000 to 500 hPa, the order of a multi-level CDS file,
    so that remap_plev() gives increasing pressure as in the files used."""
    datasets = [xr.open_dataset(f) for f in level_files]
    try:
        xr.concat(datasets, dim="pressure_level").to_netcdf(out, mode="w", format="NETCDF4")
    finally:
        for ds in datasets:
            ds.close()


def remap_surf(src, out, drop):
    """remap_CDSbeta for SURF: valid_time -> time; drop unused variables, number, expver."""
    with xr.open_dataset(src) as ds:
        ds = ds.rename({"valid_time": "time"})
        ds = ds.drop_vars(drop, errors="ignore")
        ds = ds.drop_vars(["number", "expver"], errors="ignore")
        ds.to_netcdf(out, mode="w")


def remap_plev(src, out):
    """remap_CDSbeta for PLEV: pressure_level -> level, valid_time -> time, levels reversed
    (the CDS sends 1000..500 hPa; TopoPyScale takes level=-1 as the lowest level), drop
    number and expver."""
    with xr.open_dataset(src) as ds:
        ds = ds.rename({"pressure_level": "level", "valid_time": "time"})
        ds = ds.isel(level=slice(None, None, -1))
        ds = ds.drop_vars(["number", "expver"], errors="ignore")
        ds.to_netcdf(out, mode="w")


def main():
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f)
    out_dir = Path(cfg["output_dir"])
    raw_dir = out_dir / RAW_SUBDIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    months = month_list(cfg["start"], cfg["end"])
    log(f"config {CONFIG_FILE}\noutput {out_dir}\nmonths {months[0]} .. {months[-1]} ({len(months)})")
    log(f"area [N, W, S, E] = {cds_area(cfg)}, grid {cfg['grid']}")

    # 1) downloads (only months without a final file)
    jobs, todo = [], []
    for year, month in months:
        final = out_dir / SURF_FILE.format(year, month)
        if final.exists():
            log(f"{final.name}: present, skipped")
        else:
            raw = raw_dir / ("cds_" + SURF_FILE.format(year, month))
            jobs.append((SURF_DATASET, surf_request(cfg, year, month), raw))
            todo.append(("surf", [raw], final))
        final = out_dir / PLEV_FILE.format(year, month)
        if final.exists():
            log(f"{final.name}: present, skipped")
        else:
            raws = []
            for level in sorted(cfg["plevels"], reverse=True):   # 1000 .. 500 hPa
                raw = raw_dir / ("cds_" + PLEV_FILE.format(year, month).replace(".nc", "_%04d.nc" % level))
                jobs.append((PLEV_DATASET, plev_request(cfg, year, month, level), raw))
                raws.append(raw)
            todo.append(("plev", raws, final))
    if jobs:
        pool = ThreadPool(cfg["download_threads"])
        pool.map(download, jobs)
        pool.close()
        pool.join()

    # 2) post-processing, one month at a time (netCDF/HDF5 writes are not thread safe)
    missing = 0
    for kind, raws, final in todo:
        if not all(r.exists() for r in raws):
            log(f"{final.name}: downloads incomplete, not written (rerun to retry)")
            missing += 1
            continue
        part = final.with_name("." + final.name + ".part")   # hidden: not read by TopoPyScale
        if kind == "surf":
            src = unpack(raws[0], raw_dir)
            remap_surf(src, part, cfg["surf_drop"])
        else:
            src = raw_dir / ("joined_" + final.name)
            join_levels(raws, src)
            remap_plev(src, part)
        if src not in raws:
            src.unlink()
        os.replace(part, final)
        if not cfg.get("keep_raw", False):
            for r in raws:
                r.unlink()
        log(f"{final.name}: written")
    if missing:
        sys.exit(f"{missing} monthly file(s) not written; rerun the same command")
    log("done")


if __name__ == "__main__":
    main()
