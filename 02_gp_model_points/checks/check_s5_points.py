"""Compare the points CSV written by s5_make_points_csv.py with the original CSV files.

For GP_points3.csv and rows 0..5399 of GP_points3_B.csv: byte comparison of the text
lines, and value comparison (floats parsed exactly with float_precision='round_trip')
of index, x, y, name, lat and lon (equality and maximum absolute difference). Also
checks that every point is a distinct cell centre of the predictors grid, what the
extra rows 5400..5499 of GP_points3_B.csv hold (IC2indXY_5400.npy), and which point
set the original indXY_5400.npy holds (5500_iter/indPTS_4.npy or the older
models_MatSel/indPTS_5400.npy).

Inputs:  new output folder of s5; original CSV files; IC2indXY_5400.npy; indXY_5400.npy;
         models_MatSel/indPTS_5400.npy; predictors NetCDF.
Outputs: text on stdout.
Environment: module anaconda3/2024.02-1 + ~/.local, as s5.
Run:     python checks/check_s5_points.py <new dir> <GP_points3_B.csv> <GP_points3.csv> <IC2indXY_5400.npy> \
             <indXY_5400.npy> <models_MatSel/indPTS_5400.npy> <predictors.nc>
Original: new check script.
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.preprocessing import StandardScaler

# ---- paths and settings ------------------------------------------------------
NEW_DIR, CSV_B, CSV_3, XY_IC2, XY_ORIG, PTS_OLD, PREDICTORS_NC = sys.argv[1:8]
NEW_CSV = os.path.join(NEW_DIR, 'GP_points.csv')
N = 5400


def read(path):
    return pd.read_csv(path, index_col=0, float_precision='round_trip')


new = read(NEW_CSV)
new_lines = open(NEW_CSV).read().splitlines()
print('new CSV rows:', len(new), 'columns:', list(new.columns))

for path in (CSV_3, CSV_B):
    orig = read(path)
    o = orig.iloc[:N]
    lines = open(path).read().splitlines()[:N + 1]
    n_diff = sum(a != b for a, b in zip(lines, new_lines))
    print(f'\n== {path}: {len(orig)} rows; compare rows 0..{N-1}')
    print(f'   text lines (header + {N} rows) differing: {n_diff}')
    print('   columns identical:', list(o.columns) == list(new.columns),
          '| index identical:', np.array_equal(o.index.values, new.index.values))
    for c in ['x', 'y', 'name', 'lat', 'lon']:
        d = np.abs(o[c].values - new[c].values)
        print(f'   {c:4s} identical: {np.array_equal(o[c].values, new[c].values)}'
              f'  rows differing: {int(np.sum(d > 0))}  max abs diff: {d.max():.3e}')

# points on the grid
grid = xr.open_dataset(PREDICTORS_NC)
xy_new = new[['x', 'y']].values
print('\npoints on grid cell centres: x', int(np.isin(xy_new[:, 0], grid.x.values).sum()),
      'y', int(np.isin(xy_new[:, 1], grid.y.values).sum()), 'of', N,
      '| distinct (x, y):', len({(a, b) for a, b in xy_new}))

# extra rows of GP_points3_B.csv
orig_b = read(CSV_B)
extra = orig_b.iloc[N:]
ic2 = np.load(XY_IC2)
print(f'GP_points3_B.csv rows {N}..{len(orig_b)-1}: {len(extra)} rows, index {extra.index.min()}..{extra.index.max()};'
      f' x, y == IC2indXY_5400.npy {ic2.shape}:',
      ic2.shape[0] == len(extra) and np.array_equal(extra[['x', 'y']].values, ic2))

# origin of the original indXY_5400.npy (same scaler and conversion as s5)
all_data = xr.open_dataset(PREDICTORS_NC).drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])
selected_data = all_data.assign_coords(n_ind= ("n_ind",[25,50,100,200,300,400]))
df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])
df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==25].reset_index(drop=True)
df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
scaler.fit_transform(df0)
P = scaler.inverse_transform(np.load(PTS_OLD))
xy_old = np.vstack((P[:, 2] + 308089, 4322447 - P[:, 0])).T
xy_orig = np.load(XY_ORIG)
print(f'\noriginal indXY_5400.npy {xy_orig.shape}: == new points: {np.array_equal(xy_orig, xy_new)}'
      f' (rows equal in place: {int((xy_orig == xy_new).all(1).sum())});'
      f' == conversion of {os.path.basename(PTS_OLD)} (older selection): {np.array_equal(xy_orig, xy_old)};'
      f' distinct points: {len({tuple(r) for r in xy_orig})}')
