"""Collect the MuSA ensembles of one run into a netCDF file of daily snow depth (mm).

MuSA saves one compressed pickle per cell with the hourly FSM2 states of every member.
For each cell and member this script takes the daily mean of the snow depth `snd`,
converts it to mm and casts it to int64 (truncation toward zero), and writes all cells
to one array. Posterior (default) or prior ensembles (--prior). Run settings (ensemble
folder, mask, dates, members) come from config.py of the MuSA folder MUSA_DIR.

Inputs:
    $MUSA_DIR/config.py   save_ensemble_path, nc_maks_path, date_ini, date_end, ensemble_members
    <save_ensemble_path>/ensbl_<y>_<x>.pkl.blp                posterior ensembles (default)
    <save_ensemble_path>/0pri_ensbl_<y>_<x>_obs<b>.pkl.blp    prior ensembles (--prior)
    <nc_maks_path>        mask (y, x); gives the output y, x coordinates
    The MuSA package (modules/) must be importable from MUSA_DIR to unpickle the ensembles.
Outputs:
    <save_ensemble_path>/../$MUSA_POST_OUTDIR/En_snd<yy>.nc     (posterior)
    <save_ensemble_path>/../$MUSA_POST_OUTDIR/En_snd<yy>_Pr.nc  (prior)
    variable snd (y 5400, x 2, t 365/366, en 100), int64, mm, fill -9999 (no cell file),
    zlib level 9. <yy> = characters 3-4 of date_end. MUSA_POST_OUTDIR may be absolute.
Environment: MuSAenv (../environments/MuSAenv.yml); MUSA_DIR (MuSA folder whose config.py
    describes the run), MUSA_POST_OUTDIR (output folder), MUSA_POST_NWORKERS (processes).
Run (from 06_postprocessing):
    export MUSA_DIR=<MuSA folder>/ MUSA_POST_OUTDIR=<run>
    sbatch sbatch_20b_save_netEN.sh     # posterior: python 20b_save_netEN.py
    sbatch sbatch_20b_save_netEN2.sh    # prior:     python 20b_save_netEN.py --prior
Original: B/Post/20b_savePost_netEN.py and B/Post/20b_savePrior2_netEN.py (identical except
    for the file pattern and the output name, selected here by --prior).
"""
import argparse
import datetime as dt
import glob
import os
import pickle
import sys
import time
from multiprocessing import Pool

import blosc
import numpy as np
import xarray as xr

# ---- paths and settings
MUSA_DIR = os.environ["MUSA_DIR"]                   # MuSA folder with the run's config.py
OUTDIR = os.environ["MUSA_POST_OUTDIR"]             # output folder, relative to <save_ensemble_path>/..
NWORKERS = int(os.environ.get("MUSA_POST_NWORKERS", os.environ.get("SLURM_CPUS_PER_TASK", "1")))
PATTERN = {False: "e*", True: "0pri_ensbl_*"}       # posterior / prior ensemble files
SUFFIX = {False: "", True: "_Pr"}                   # output name En_snd<yy><suffix>.nc

sys.path.append(MUSA_DIR)
import config as cfg  # noqa: E402
if cfg.numerical_model == 'FSM2':
    # not used directly: importing the MuSA modules in this order lets pickle load the
    # ensemble objects (unpickling modules.internal_class first fails on a circular import)
    import modules.fsm_tools as model  # noqa: E402,F401

ens_path = cfg.save_ensemble_path

# time axis of the run (hourly states, daily output)
date_ini = dt.datetime.strptime(cfg.date_ini, "%Y-%m-%d %H:%M")
date_end = dt.datetime.strptime(cfg.date_end, "%Y-%m-%d %H:%M")
del_t = np.asarray([date_ini + dt.timedelta(hours=x)
                    for x in range(int((date_end - date_ini).total_seconds() / 3600) + 1)])
dates = (np.datetime64(date_ini)
         + np.arange(0, ((date_end - date_ini).days) + 1, 1).astype("timedelta64[D]"))
tsize = dates.shape[0]
nsize = cfg.ensemble_members

mask = xr.open_dataarray(cfg.nc_maks_path)
northing = mask.y
easting = mask.x
mask = mask.values
xsize = mask.shape[1]
ysize = mask.shape[0]


def _parse_cell_from_filename(filename):
    if filename[0] == '0':
        y = int(filename.split('.')[-3].split('_')[2])
        x = int(filename.split('.')[-3].split('_')[3])
        return y, x, False

    y = int(filename.split('.')[-3].split('_')[-2])
    x = int(filename.split('.')[-3].split('_')[-1])
    return y, x, False


def get_daily_result_en(task, time_step='24h'):
    filename, pathe = task
    y, x, should_skip = _parse_cell_from_filename(filename)
    if should_skip:
        return None

    with open(os.path.join(pathe, filename), "rb") as f:
        compressed_pickle = f.read()
        depressed_pickle = blosc.decompress(compressed_pickle)
        data = pickle.loads(depressed_pickle)

    try:
        ensembles = data[0].state_membres
    except:  # noqa: E722  (the file holds the ensemble object itself, not a list)
        ensembles = data.state_membres

    cell_values = np.full((tsize, nsize), -9999, dtype=np.int64)
    for i, member in enumerate(ensembles):
        member.index = del_t
        series = member.resample(time_step).mean().snd * 1000      # daily mean, m -> mm
        cell_values[:, i] = np.asarray(series.values, dtype=np.int64)

    return y, x, cell_values


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prior", action="store_true", help="prior ensembles (0pri_ensbl_*) instead of posterior")
    prior = ap.parse_args().prior

    data = np.empty((ysize, xsize, tsize, nsize), dtype='int')
    data.fill(-9999)
    results = xr.DataArray(data=data,
                           coords=dict(
                               y=northing,
                               x=easting,
                               t=(["t"], dates),
                               en=(["en"], range(nsize))),
                           name='snd',
                           attrs={'_FillValue': -9999,
                                  'unit': 'mm'},
                           )

    pathe = ens_path
    filelist = [os.path.basename(file_path)
                for file_path in glob.glob(os.path.join(pathe, PATTERN[prior]))]

    workers = max(1, min(NWORKERS, len(filelist)))

    start = time.time()
    processed = 0
    progress_step = max(1, len(filelist) // 20)
    with Pool(processes=workers) as pool:
        for output in pool.imap_unordered(get_daily_result_en,
                                          [(filename, pathe) for filename in filelist],
                                          chunksize=32):
            processed += 1
            if output is None:
                continue
            y, x, cell_values = output
            results.values[y, x, :, :] = cell_values

            if processed % progress_step == 0 or processed == len(filelist):
                elapsed = time.time() - start
                frac = processed / len(filelist)
                eta = (elapsed / frac - elapsed) if frac > 0 else np.nan
                print(f'Progress: {processed}/{len(filelist)} '
                      f'({100*frac:.1f}%) elapsed={elapsed:.1f}s eta={eta:.1f}s',
                      flush=True)

    end = time.time()
    print(f'Processed {len(filelist)} files with {workers} workers in {end - start:.2f} s')
    out_dir = os.path.join(ens_path, '..', OUTDIR)
    yy = cfg.date_end[2:4]  # year of the run, e.g. '24'
    os.makedirs(out_dir, exist_ok=True)
    results.to_netcdf(os.path.join(out_dir, f'En_snd{yy}{SUFFIX[prior]}.nc'),
                      encoding={"snd": {'zlib': True, 'complevel': 9}})


if __name__ == "__main__":
    main()
