"""Synthetic ICESat-2 snow depth at 3 m: ASO snow depth and terrain sampled along the ICESat-2 tracks.

The ATL03 photons of 2023-04-01 (rgt 173) are binned on the 3 m ASO grid per
beam (spot); each bin keeps the mean photon position and the median beam pair.
At each bin the 3 m terrain variables and the ASO snow depth of one ASO date
are read from the nearest grid cell. The track positions are always those of
2023-04-01; only the ASO date of the snow depth changes between files.

Inputs:  ATL03 photons (ATL03_yapc.feather, s1_download_atl03.py);
         3 m stack all_data3_new.nc (terrain + ASO snow depth on 2022-04-21,
         2022-05-18, 2023-04-01, 2024-04-03, 2024-05-20; the 2024-04-03 layer was
         appended in 0_IC2_synth3.ipynb cell 3).
Outputs: feather with one row per (3 m cell, spot): Xg, Yg, spot, x, y, pair,
         Zs, slope, cosA, sinA, DAH, TPI150, TPI1000, Sx200, Sx100, snow_depth,
         GSAfrac. Files used later: IC2_synt3_24_new.feather (ASO 2024-04-03);
         IC2_synt3_.feather (2023-04-01) and IC2_synt3_24.feather (2024-05-20)
         are earlier files of the same layout.
Environment: anaconda3 base (module load anaconda3; conda activate base), the kernel of the
         original notebook.
Run:     sbatch sbatch_s2_ic2_synth3.sh 2024-04-03 /path/to/IC2_synt3_24_new.feather
         (python s2_ic2_synth3.py --aso-date 2024-04-03 --out <file>; ~2 h,
         the nearest-cell lookup is done row by row as in the original)
Original: /global/home/users/marcomaz/B/GP_sno/0_IC2_synth3.py
          (same code as 0_IC2_synth3.ipynb cells 0-1, 4-5, 7, 9, 11, 13-15).
"""
import argparse
import datetime

import pandas as pd
import pyarrow.feather as feather
import xarray as xr

# ---- paths and settings ------------------------------------------------------
ATL03_FEATHER = "/global/home/groups/fc_mgirotto/East_River_Data/IS2/ATL03_yapc.feather"
ALL_DATA_3M = "/global/scratch/users/marcomaz/all_data3_new.nc"
TRACK_DATE = datetime.date(2023, 4, 1)   # ICESat-2 overpass whose photon positions are used
RES = 3                                  # grid resolution (m)
VARS = ['Zs', 'slope', 'cosA', 'sinA', 'DAH', 'TPI150', 'TPI1000', 'Sx200', 'Sx100',
        'snow_depth', 'GSAfrac']
# -------------------------------------------------------------------------------

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--aso-date", default="2024-04-03", help="ASO date of the snow depth layer")
p.add_argument("--out", required=True, help="output feather file")
a = p.parse_args()

all_data = xr.open_dataset(ALL_DATA_3M)
IC2 = pd.DataFrame(feather.read_feather(ATL03_FEATHER))
IC2_april = IC2[IC2.index.date == TRACK_DATE].copy()

all_data_date = all_data.sel(date=a.aso_date, band=1).drop_vars('spatial_ref')

# 3 m bin index of every photon; one row per (bin, spot)
# (.values added: newer pandas/xarray do not subtract a 0-d DataArray from a Series; same numbers)
IC2_april.loc[:, 'Xg'] = ((IC2_april.loc[:, 'x'] - all_data.coords['x'].min().values - RES / 2) // RES).astype(int)
IC2_april.loc[:, 'Yg'] = ((IC2_april.loc[:, 'y'] - all_data.coords['y'].min().values - RES / 2) // RES).astype(int)
IC2_april_synt = IC2_april.groupby(['Xg', 'Yg', 'spot']).agg({'x': 'mean',
                                                             'y': 'mean',
                                                             'pair': 'median'}).reset_index()

# nearest 3 m grid value at the mean photon position of each bin
for var in VARS:
    print(var, flush=True)
    var_val = []
    for index, row in IC2_april_synt.iterrows():
        var_val.append(all_data_date[var].sel({'x': row['x'], 'y': row['y']}, method='nearest').values)
    IC2_april_synt[var] = var_val

for var in VARS:
    IC2_april_synt[var] = IC2_april_synt[var].astype(float)

IC2_april_synt.to_feather(a.out)
print(f"wrote {a.out}: {len(IC2_april_synt)} rows", flush=True)
