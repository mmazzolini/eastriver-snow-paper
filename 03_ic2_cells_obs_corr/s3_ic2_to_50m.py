"""Synthetic ICESat-2 snow depth at 50 m: median and standard deviation of the 3 m track samples per 50 m cell.

The 3 m samples of s2_ic2_synth3.py are binned on the 50 m model grid per beam
(spot); every column is reduced to its median and standard deviation within the
bin. The grid coordinates Xs, Ys of the 50 m cell nearest to the median
position are added. The result has two-level columns, e.g. ('snow_depth',
'median'), ('Xs', '').

Inputs:  3 m feather from s2_ic2_synth3.py; 50 m stack all_data50from3_1702.nc
         (only its x, y coordinates and the Xs, Ys variables are used).
Outputs: 50 m feather. Files used later: IC2_synt50from3_23.feather (ASO 2023-04-01),
         IC2_synt50from3_24.feather (ASO 2024-05-20) and
         IC2_synt50from3_24april.feather (ASO 2024-04-03); all three use the
         2023-04-01 track positions.
Environment: gpy-env.
Run:     sbatch sbatch_s3_ic2_to_50m.sh /path/IC2_synt3_24_new.feather /path/IC2_synt50from3_24april.feather
         (python s3_ic2_to_50m.py --in <3 m feather> --out <50 m feather>)
Original: /global/home/users/marcomaz/B/GP_sno/20_IC2_synth3vsAllData.ipynb
          cells 0, 36, 39-43 (input IC2_synt3_24_new.feather, output IC2_synt50from3_24april.feather).
"""
import argparse

import numpy as np
import pandas as pd
import pyarrow.feather as feather
import xarray as xr

# ---- paths and settings ------------------------------------------------------
ALL_DATA_50M = "/global/scratch/users/marcomaz/all_data50from3_1702.nc"
RES = 50                                  # model grid resolution (m)
# -------------------------------------------------------------------------------

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--in", dest="inp", required=True, help="3 m feather (s2_ic2_synth3.py)")
p.add_argument("--out", required=True, help="output 50 m feather")
a = p.parse_args()

all_data3to50 = xr.open_dataset(ALL_DATA_50M)
IC2_synth = pd.DataFrame(feather.read_feather(a.inp))

# 50 m bin index (replaces the 3 m Xg, Yg); median and std of every column per (bin, spot)
IC2_synth.loc[:, 'Xg'] = ((IC2_synth.loc[:, 'x'] - all_data3to50.coords['x'].min().values - RES / 2) // RES).astype(int)
IC2_synth.loc[:, 'Yg'] = ((IC2_synth.loc[:, 'y'] - all_data3to50.coords['y'].min().values - RES / 2) // RES).astype(int)
IC2_synth3to50 = IC2_synth.groupby(['Xg', 'Yg', 'spot']).agg(['median', 'std'])

# grid coordinates of the nearest 50 m cell (outer selection, then its diagonal = paired x, y)
for var in ['Xs', 'Ys']:
    print(var, flush=True)
    IC2_synth3to50[var] = np.diagonal(all_data3to50[var].sel({'x': IC2_synth3to50['x', 'median'].values,
                                                              'y': IC2_synth3to50['y', 'median'].values},
                                                             method='nearest').values)

IC2_synth3to50 = IC2_synth3to50.reset_index().drop(columns=['Xg', 'Yg'])
IC2_synth3to50.to_feather(a.out)
print(f"wrote {a.out}: {len(IC2_synth3to50)} rows", flush=True)
