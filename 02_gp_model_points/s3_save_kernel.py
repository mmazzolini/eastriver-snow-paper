"""Load the fitted sparse GP (400 inducing points) and save its Matern 5/2 kernel parameters.

Rebuilds the standardised ASO 2022-04-21 training data as in s2, creates a
SparseGPRegression with 400 inducing points without initialising it, loads the
parameter array saved by s2 into it and writes the kernel lengthscales (7, in the
predictor order Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150) and the kernel variance.
These are the starting kernel ('round -1') of the point selection in s4.

Inputs:  all_data50from3_1702.nc (predictors and ASO snow depth; see README.md);
         models_noP_Sparse_M52_2022_04_21_nind400.npy (output of s2).
Outputs: <out_dir>/lnscale_-1.npy (7 lengthscales), <out_dir>/var_-1.npy (kernel variance).
Environment: module anaconda3/2024.02-1 (Python 3.11) + GPy 1.13.2, paramz 0.9.6,
         netCDF4 1.7.2 in ~/.local (see README.md).
Run:     python s3_save_kernel.py --predictors <all_data50from3_1702.nc> --model <...nind400.npy> --out-dir <iter_dir>
         (or sbatch sbatch_s3_save_kernel.sh <all_data50from3_1702.nc> <...nind400.npy> <iter_dir>)
Original: B/GP4MuSA/200_GP_indP.ipynb, cells 0, 2, 4, 7 (model loading lines), 15 and 16
         (original outputs in /global/scratch/users/marcomaz/GP_models/5500_iter/).
"""
import argparse
import os

import numpy as np
import xarray as xr
from sklearn.preprocessing import StandardScaler
import GPy

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC = '/global/scratch/users/marcomaz/all_data50from3_1702.nc'  # predictors and ASO snow depth (see README.md)
MODEL_NPY = ('/global/scratch/users/marcomaz/GP_models/models_MatSel/'
             'models_noP_Sparse_M52_2022_04_21_nind400.npy')  # output of s2
OUT_DIR = './output/5500_iter/'  # original: /global/scratch/users/marcomaz/GP_models/5500_iter/
n_ind = 400      # inducing points of the loaded model
j = -1           # file tag: lnscale_{j}.npy, var_{j}.npy
sigma_y = 0.5    # set before loading; the loaded parameter array overwrites the noise variance

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--predictors', default=PREDICTORS_NC)
parser.add_argument('--model', default=MODEL_NPY)
parser.add_argument('--out-dir', default=OUT_DIR)
args = parser.parse_args()
os.makedirs(args.out_dir, exist_ok=True)

# ---- training data (cells 0, 2, 4) ----------------------------------------------
all_data = xr.open_dataset(args.predictors)
all_data = all_data.drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])

# dummy 'n_ind' dimension: to_dataframe() repeats the data along it and one copy is kept
selected_data = all_data
selected_data = selected_data.assign_coords(n_ind= ("n_ind",[25,50,100,200,300,400]))

df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])
n = df.shape[1]-1

df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==25].reset_index(drop=True)
Y0 = np.array(df0.dropna()['snow_depth'])
Y0 = np.reshape(Y0, (-1, +1))
Y0t = np.log(Y0+1)

df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)

# ---- load the fitted model (cell 7) -------------------------------------------------
kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], ARD = True)

model = GPy.models.SparseGPRegression(df0N,Y0t, kernel=kernel, num_inducing=n_ind, initialize=False)

model.update_model(False) # do not call the underlying expensive algebra on load
model.initialize_parameter() # Initialize the parameters (connect the parameters up)
model.Gaussian_noise.variance = sigma_y**2
model.Gaussian_noise.variance.fix()
model[:] = np.load(args.model) # Load the parameters (inducing inputs, kernel, noise)

model.update_model(True) # Call the algebra only once

print(model)

# ---- save the kernel parameters (cells 15, 16) --------------------------------------
np.save(os.path.join(args.out_dir, f'lnscale_{j}.npy'),kernel.lengthscale.values)
np.save(os.path.join(args.out_dir, f'var_{j}.npy'),kernel.variance.values)
print('lengthscales:', kernel.lengthscale.values)
print('variance:', kernel.variance.values)
print('saved', os.path.join(args.out_dir, f'lnscale_{j}.npy'), os.path.join(args.out_dir, f'var_{j}.npy'))
