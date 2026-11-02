"""Fit the StandardScaler of the 7 topographic predictors on the ASO 2022-04-21 cells.

The predictors file (50 m grid, 809 x 995) holds the topographic predictors and the
ASO snow depth of four dates. The script keeps the cells where both the predictors
and the ASO snow depth of 2022-04-21 are defined (296,799 cells), fits a
scikit-learn StandardScaler on the 7 predictors in the order
Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150 and saves it with joblib.
The same fit is repeated inside s2, s3, s4 and s5 (as in the original scripts).

Inputs:  all_data50from3_1702.nc (predictors and ASO snow depth; see README.md).
Outputs: scaler file (joblib pickle; original name scaler.save).
Environment: conda env gpy-env (Python 3.11, scikit-learn 1.8.0, xarray 2026.2.0,
         pandas 3.0.1; see README.md).
Run:     python s1_fit_scaler.py --predictors <all_data50from3_1702.nc> --out <dir>/scaler.save
         (or sbatch sbatch_s1_fit_scaler.sh <all_data50from3_1702.nc> <out_file>)
Original: B/GP4MuSA/IC2_GP_indP_apr24.ipynb, cells 0, 2, 10 (scaler lines) and 11.
"""
import argparse
import os

import joblib
import numpy as np
import xarray as xr
from sklearn.preprocessing import StandardScaler

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC = '/global/scratch/users/marcomaz/all_data50from3_1702.nc'  # predictors and ASO snow depth (see README.md)
OUT_SCALER = './output/scaler.save'  # original: /global/scratch/users/marcomaz/GP_models/scaler.save
DROP_VARS = ['Sx200', 'Sx100', 'sinA', 'TPI1000', 'DAH']  # predictors not used by the GP
ASO_DATE = '2022-04-21'  # ASO flight used to fit the GP
N_IND_DUMMY = [25, 50, 100, 200, 300, 400]  # dummy coordinate kept from the original notebook

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--predictors', default=PREDICTORS_NC)
parser.add_argument('--out', default=OUT_SCALER)
args = parser.parse_args()

# ---- load predictors and ASO snow depth -----------------------------------------
all_data = xr.open_dataset(args.predictors)
all_data = all_data.drop_vars(DROP_VARS)

# The original notebook adds a dummy 'n_ind' dimension (left over from tests with
# several numbers of inducing points); to_dataframe() repeats the data along it and
# one copy is selected below. It does not change the values.
selected_data = all_data.assign_coords(n_ind=("n_ind", N_IND_DUMMY))

df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])

df0 = df.loc[df.index.get_level_values('date') == ASO_DATE]
df0 = df0.loc[df0.index.get_level_values('n_ind') == N_IND_DUMMY[0]].reset_index(drop=True)

# cells with all predictors and ASO snow depth defined; columns Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150
df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)

# ---- save ------------------------------------------------------------------------
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
joblib.dump(scaler, args.out)

print('cells used:', df0.shape[0])
print('feature order:', list(scaler.feature_names_in_))
print('mean_:', np.array2string(scaler.mean_, precision=17))
print('scale_:', np.array2string(scaler.scale_, precision=17))
print('saved', args.out)
