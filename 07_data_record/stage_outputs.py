"""Stage the files of the Zenodo data record as a folder tree (input data, DA experiments, website, documentation).

    input_data/DEM/srtm_eastriver_clipped.tif               the DEM of the downscaling (SRTM), unchanged
    input_data/points/GP_points.csv, IC2NP_23.csv, IC2NP_24.csv   the downscaled points (model cells, IC2 cells), unchanged
    input_data/GP_predictors/predictors_50m.nc              the 7 topographic / snow-cover predictors of the GP
    DA_experiments/<yy>_<GPE|GCE>/prior/                    En_snd<yy>_Pr.nc (prior ensemble at the model and IC2 cells),
                                                            Prior<yy>_mapped<date>[_ens].nc (mapped to the 50 m grid: members, mean)
    DA_experiments/<yy>_<GPE|GCE>/posterior/                En_snd<yy>.nc, Post<yy>_mapped<date>[_ens].nc (the same, posterior)
    website_data/<name>                                     data files of the website (docs/), see web/build_web_data.py
    documentation/README.md, md5sums.txt                    description of the record (RECORD_README.md), checksums
The file names inside the experiment folders are those written by 06_postprocessing. The ensembles at the
cells are copied unchanged (checked with md5). The mapped fields and the predictors are rewritten with
lossless zlib compression and checked value by value against the source files. Everything that contains
ASO snow depth goes to a separate folder that is never uploaded: aso_50m.nc, the website's ASO grids
(aso<yy>.bin.gz) and the website's IC2-cell files with their ASO values (the record gets a copy of these
with the ASO values removed). pack_record.py turns the tree into the files uploaded to Zenodo.

Inputs:  <D>/<run>/ (outputs of 06_postprocessing), all_data50from3_1702.nc, the website data folder,
         ASO_EastRiver_2024Apr03_snowdepth_50m.tif
Outputs: OUT/ (the record tree; documentation/md5sums.txt) and HOLD/ (aso_50m.nc, website_data/)
Environment: gpy-env (xarray, rioxarray, netCDF4)
Run: sbatch 07_data_record/sbatch_stage_outputs.sh
"""
import hashlib
import json
import os
import shutil

import numpy as np
import xarray as xr
import rioxarray  # noqa: F401  (rasterio engine for the ASO tif)

# ------------------------------------------------------------------ paths and settings
SCRATCH = "/global/scratch/users/marcomaz"
D = os.path.join(SCRATCH, "DATA_GP5400_400")
OUT = os.path.join(SCRATCH, "zenodo_outputs")
HOLD = os.path.join(SCRATCH, "zenodo_hold")
WEB = os.path.join(SCRATCH, "web_data")
ALLDATA = os.path.join(SCRATCH, "all_data50from3_1702.nc")
ASO24_TIF = os.path.join(SCRATCH, "ASO_EastRiver_2024Apr03_snowdepth_50m.tif")
DS = os.path.join(SCRATCH, "downscali3/inputs/dem")
POINTS = {"points": [os.path.join(DS, "GP_points.csv"),                       # the 5400 model cells
                     os.path.join(SCRATCH, "downscaliNP23/inputs/dem/IC2NP_23.csv"),
                     os.path.join(SCRATCH, "downscaliNP24/inputs/dem/IC2NP_24.csv")],
          "DEM": [os.path.join(DS, "srtm_eastriver_clipped.tif")]}          # same in all projects
# MuSA run (folder in D) -> water year, survey date, experiment folder of the record
RUNS = {"23GPpow2NPnbm_var": ("23", "230401", "23_GPE"), "23GCpow2NP_var": ("23", "230401", "23_GCE"),
        "24GPpow2NPnb_var": ("24", "240403", "24_GPE"), "24GCpow2NP_var": ("24", "240403", "24_GCE")}
FEATURES = ["Ys", "GSAfrac", "Xs", "Zs", "slope", "cosA", "TPI150"]   # order used by the GP
ZLIB = dict(zlib=True, complevel=4, shuffle=True)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def folder(*parts):
    d = os.path.join(*parts)
    os.makedirs(d, exist_ok=True)
    return d


def rel(path):
    return os.path.relpath(path, OUT)


def copy(src, dst):
    shutil.copy2(src, dst)
    assert md5(src) == md5(dst)
    print(f"{rel(dst)}: copied, md5 identical", flush=True)


def same(a, b):
    """Every variable and coordinate of two datasets identical (NaN == NaN)."""
    for k in list(a.variables):
        x, y = a[k].values, b[k].values
        if x.dtype.kind in "fc":
            ok = np.array_equal(x, y, equal_nan=True)
        else:
            ok = np.array_equal(x, y)
        if not ok:
            return False, k
    return True, None


def rewrite(src, dst, attrs=None):
    ds = xr.open_dataset(src)
    if attrs:
        ds.attrs.update(attrs)
    enc = {k: dict(ZLIB) for k in ds.data_vars}
    ds.to_netcdf(dst, encoding=enc)
    ok, bad = same(xr.open_dataset(src), xr.open_dataset(dst))
    assert ok, f"{dst}: {bad} differs from the source"
    print(f"{rel(dst)}: {os.path.getsize(src) / 1e6:.0f} -> {os.path.getsize(dst) / 1e6:.0f} MB, identical", flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(HOLD, exist_ok=True)
    # DA experiments: one folder per experiment, prior and posterior
    for run, (yy, tag, name) in RUNS.items():
        date = "2023-04-01" if yy == "23" else "2024-04-03"
        for kind, sub, cells in (("Prior", "prior", f"En_snd{yy}_Pr.nc"), ("Post", "posterior", f"En_snd{yy}.nc")):
            d = folder(OUT, "DA_experiments", name, sub)
            copy(os.path.join(D, run, cells), os.path.join(d, cells))
            for suffix in ("_ens", ""):
                f = f"{kind}{yy}_mapped{tag}{suffix}.nc"
                rewrite(os.path.join(D, run, f), os.path.join(d, f),
                        attrs={"experiment": name, "musa_run": run,
                               "note": "ensemble mapped to the 50 m grid (06_postprocessing/21_maptogrid_NP.py); "
                                       "the 'date' coordinate is a placeholder of the predictor set, the field is for " + date})
    # input data: predictors of the GP
    a = xr.open_dataset(ALLDATA)
    p = a[FEATURES + (["spatial_ref"] if "spatial_ref" in a else [])]
    p.attrs = {"title": "Predictors of the snow-depth Gaussian process, East River (CO), 50 m grid",
               "crs": "EPSG:32613 (WGS 84 / UTM zone 13N); x, y = cell centres (m)",
               "features": "Ys, Xs: distance (m) from the grid origin; Zs: elevation (m); slope; cosA: cosine of "
                           "aspect; TPI150: topographic position index (150 m) (Zs, slope, cosA, TPI150 derived "
                           "from DEM data); GSAfrac: annual ground snow-covered "
                           "area fraction from the USGS Landsat snow covered area products (Selkowitz et al. 2017)",
               "source": "all_data50from3_1702.nc (feature order as used by the GP: " + ", ".join(FEATURES) + ")"}
    dst = os.path.join(folder(OUT, "input_data", "GP_predictors"), "predictors_50m.nc")
    p.to_netcdf(dst, encoding={k: dict(ZLIB) for k in FEATURES})
    ok, bad = same(xr.open_dataset(ALLDATA)[FEATURES], xr.open_dataset(dst)[FEATURES])
    assert ok, f"predictors: {bad} differs"
    print(f"{rel(dst)}: {os.path.getsize(dst) / 1e6:.0f} MB, identical", flush=True)
    # input data: point files and DEM of the downscaling (the TopoPyScale configurations read them by these names)
    for sub, srcs in POINTS.items():
        d = folder(OUT, "input_data", sub)
        for src in srcs:
            copy(src, os.path.join(d, os.path.basename(src)))
    # website data (files with ASO values go to HOLD; the IC2 files also go to OUT without them)
    w_out, w_hold = folder(OUT, "website_data"), folder(HOLD, "website_data")
    for f in sorted(os.listdir(WEB)):
        src = os.path.join(WEB, f)
        if f.startswith("reference_") or f.startswith("rean_"):
            continue          # check files; third-party gridded products (web/get_reanalyses.py fetches them)
        if f.startswith("aso"):
            shutil.copy2(src, os.path.join(w_hold, f))
        elif f == "manifest.json":
            # the record's manifest marks ASO as absent; the full one is held back with the ASO files
            shutil.copy2(src, os.path.join(w_hold, f))
            m = json.load(open(src))
            for y in m["years"].values():
                y["aso"] = None
                y["products"] = []
            with open(os.path.join(w_out, f), "w") as fh:
                json.dump(m, fh, separators=(",", ":"))
        elif f.endswith("_ic2.json"):
            shutil.copy2(src, os.path.join(w_hold, f))
            d = json.load(open(src))
            d["aso"] = [None] * len(d["aso"])
            with open(os.path.join(w_out, f), "w") as fh:
                json.dump(d, fh, separators=(",", ":"))
        else:
            shutil.copy2(src, os.path.join(w_out, f))
    print(f"website files: {len(os.listdir(w_out))} in the record, {len(os.listdir(w_hold))} held back", flush=True)
    # ASO (never uploaded): the grids as used in the paper
    sd = a["snow_depth"]
    g24 = xr.open_dataset(ASO24_TIF, engine="rasterio")["band_data"].squeeze("band", drop=True)
    g24 = g24.interp(x=a.x, y=a.y)
    aso = xr.Dataset({
        "snow_depth_20220421": sd.sel(date="2022-04-21").drop_vars("date", errors="ignore"),
        "snow_depth_20230401": sd.sel(date="2023-04-01").drop_vars("date", errors="ignore"),
        "snow_depth_20240403": g24.drop_vars("spatial_ref", errors="ignore")})
    for k in aso.data_vars:
        aso[k].attrs = {"units": "m", "long_name": "ASO lidar snow depth, 50 m"}
    aso.attrs = {"title": "ASO snow depth on the 50 m grid of the East River experiments",
                 "source": "Airborne Snow Observatories; 2022-04-21 and 2023-04-01 from all_data50from3_1702.nc "
                           "(3 m depth aggregated to 50 m), 2024-04-03 from the 50 m ASO raster interpolated to the grid",
                 "crs": "EPSG:32613"}
    aso.to_netcdf(os.path.join(HOLD, "aso_50m.nc"), encoding={k: dict(ZLIB) for k in aso.data_vars})
    print("aso_50m.nc written to the hold folder", flush=True)
    # documentation: description of the record, then checksums of every other file (paths from the record root)
    doc = folder(OUT, "documentation")
    shutil.copy2(os.path.join(os.path.dirname(os.path.abspath(__file__)), "RECORD_README.md"), os.path.join(doc, "README.md"))
    files = sorted(rel(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
    files = [f for f in files if not f.startswith("documentation" + os.sep)]
    with open(os.path.join(doc, "md5sums.txt"), "w") as fh:
        for f in files:
            fh.write(f"{md5(os.path.join(OUT, f))}  {f}\n")
    tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in files)
    print(f"done: {len(files)} data files, {tot / 1e9:.2f} GB in {OUT}", flush=True)


if __name__ == "__main__":
    main()
