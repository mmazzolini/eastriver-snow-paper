"""Convert the 5400 selected points from standardised predictors to UTM and lat/lon (CSV).

Refits the StandardScaler of the 7 predictors (same fit as s1), back-transforms
indPTS_4.npy (output of s4) to predictor units and takes the grid coordinates
Xs and Ys (m, measured from the centre of the upper-left cell of the 50 m grid):
x = Xs + 308089, y = 4322447 - Ys (WGS 84 / UTM zone 13N, EPSG:32613). The points
are converted to WGS 84 lat/lon (EPSG:4326) with geopandas and written as a CSV
with the columns (index), x, y, name, lat, lon; name = row number (0..5399), in the
order of indPTS_4.npy. The original GP_points3.csv is the point file of the
TopoPyScale configuration downscali3/config_GP2.yml (method 'points', 2022-10-01 to
2024-10-01).

The original CSV GP_points3_B.csv has 100 more rows (5400..5499, index and name
0..99) with earlier ICESat-2 cells (IC2indXY_5400.npy), which are not used; they are
not written here. The notebook also saved the x, y array as indXY_5400.npy (cell 19);
the file now at that path was written before indPTS_4.npy existed and holds the
conversion of an older selection (models_MatSel/indPTS_5400.npy), so it is not
reproduced here.

Inputs:  all_data50from3_1702.nc (predictors and ASO snow depth; see README.md);
         indPTS_4.npy (s4).
Outputs: <out_dir>/GP_points.csv, the point file of the downscaling (01_era5_downscaling,
         config_GP_points.yml; also in the data record, input_data/points/). Original:
         GP_points3.csv; the same as rows 0..5399 of GP_points3_B.csv up to 1.4e-14 deg in
         lat/lon, which TopoPyScale does not read (it recomputes lat/lon from x, y).
Environment: module anaconda3/2024.02-1 (Python 3.11) + geopandas 1.0.1, pyproj 3.6.1
         (PROJ 9.3.0), shapely 2.0.6, netCDF4 1.7.2 in ~/.local (see README.md).
Run:     python s5_make_points_csv.py --predictors <all_data50from3_1702.nc> --points <iter_dir>/indPTS_4.npy --out-dir <dir>
         (or sbatch sbatch_s5_make_points_csv.sh <all_data50from3_1702.nc> <indPTS_4.npy> <dir>)
Original: B/GP4MuSA/sample_forcing.ipynb cells 0-2 (data and scaler), 9 and 15
         (back-transform), 19 (x, y array), 24 and 28-34 (lat/lon) and 39 (CSV).
         The notebook was later edited for other point sets (cell 9 now loads
         IC2_kern5400_23_400.npy, cell 39 writes GP_points23_400.csv); this script
         follows the indPTS_4.npy path that is commented out in cell 9.
"""
import argparse
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from sklearn.preprocessing import StandardScaler

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC = '/global/scratch/users/marcomaz/all_data50from3_1702.nc'  # predictors and ASO snow depth (see README.md)
POINTS_NPY = '/global/scratch/users/marcomaz/GP_models/5500_iter/indPTS_4.npy'  # output of s4
OUT_DIR = './output/'  # original: /global/scratch/users/marcomaz/downscali3/inputs/dem/
OUT_CSV = 'GP_points.csv'
X0 = 308089     # x (EPSG:32613) of the centre of the first grid column (Xs = 0)
Y0 = 4322447    # y (EPSG:32613) of the centre of the top grid row (Ys = 0)
CRS_UTM = 'EPSG:32613'
CRS_LATLON = 'EPSG:4326'

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--predictors', default=PREDICTORS_NC)
parser.add_argument('--points', default=POINTS_NPY)
parser.add_argument('--out-dir', default=OUT_DIR)
args = parser.parse_args()
os.makedirs(args.out_dir, exist_ok=True)

# ---- scaler (cells 0-2; same fit as s1) ---------------------------------------------
all_data = xr.open_dataset(args.predictors)
all_data = all_data.drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])

# dummy 'n_ind' dimension: to_dataframe() repeats the data along it and one copy is kept
selected_data = all_data
selected_data = selected_data.assign_coords(n_ind= ("n_ind",[25,50,100,200,300,400]))

df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])

df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==25].reset_index(drop=True)

df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)

# ---- back-transform and grid -> UTM (cells 9, 15, 19) ----------------------------------
fake_indN = np.load(args.points)
fake_ind = scaler.inverse_transform(fake_indN)   # columns Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150

fake_ind[:, 0] = Y0 - fake_ind[:, 0]   # Ys -> y
fake_ind[:, 2] += X0                   # Xs -> x

ind_pts = np.vstack((fake_ind[:, 2], fake_ind[:, 0])).T   # columns x, y

# ---- lat/lon and CSV (cells 24, 28-34, 39) ---------------------------------------------
pts = pd.DataFrame(ind_pts, columns=['x', 'y'])
pts['name'] = pts.index
gdf = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts['x'], pts['y']), crs=CRS_UTM)
gdf = gdf.to_crs(CRS_LATLON)
gdf['lat'] = gdf.geometry.y
gdf['lon'] = gdf.geometry.x
pts = gdf.drop(columns='geometry')

pts.to_csv(os.path.join(args.out_dir, OUT_CSV))
print(pts.shape[0], 'points written to', os.path.join(args.out_dir, OUT_CSV))
