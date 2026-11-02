"""Fit the sparse GP model of ASO snow depth (2022-04-21) on the 7 topographic predictors.

Target y = log(snow_depth + 1) of the ASO flight of 2022-04-21 at the 296,799 cells
where the predictors and the snow depth are defined; inputs are the 7 predictors
(Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150) standardised with a StandardScaler.
Model: GPy SparseGPRegression, Matern 5/2 kernel with ARD (one lengthscale per
predictor), Gaussian noise fixed to sigma_y = 0.25 m (log units), L-BFGS-B
optimisation of kernel variance, lengthscales and inducing inputs, for 300, 400
and 500 inducing points. The model with 400 inducing points is used downstream.
No random seed is set: GPy starts the inducing inputs from a random subset of the
cells, so a rerun gives a different local optimum. The original output folder has
the files for 300 and 400 inducing points only (no file for 500).

Inputs:  all_data50from3_1702.nc (predictors and ASO snow depth; see README.md).
Outputs: <model_dir>/models_noP_Sparse_M52_2022_04_21_nind{300,400,500}.npy
         (GPy param_array: inducing inputs (n_ind x 7), kernel variance,
         7 lengthscales, noise variance).
Environment: module anaconda3/2024.02-1 (Python 3.11) + GPy 1.13.2, paramz 0.9.6,
         netCDF4 1.7.2 in ~/.local (see README.md).
Run:     python s2_fit_sparse_gp.py --predictors <all_data50from3_1702.nc> --model-dir <dir>
         (or sbatch sbatch_s2_fit_sparse_gp.sh <all_data50from3_1702.nc> <dir>)
Original: B/GP_sno/100.py (run from /global/scratch/users/marcomaz/GP_models, so
         ./models_MatSel/ = /global/scratch/users/marcomaz/GP_models/models_MatSel/).
         Only the docstring, the paths/settings block and comments were changed;
         unused imports, host-dependent paths, two unused ICESat-2 tables and
         commented-out code were removed.
"""
import argparse
import os

import xarray as xr
import numpy as np
from sklearn.preprocessing import StandardScaler
import GPy

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC = '/global/scratch/users/marcomaz/all_data50from3_1702.nc'  # predictors and ASO snow depth (see README.md)
MODEL_DIR = './output/models_MatSel/'  # original: ./models_MatSel/ in /global/scratch/users/marcomaz/GP_models
sigma_y = 0.25             # fixed noise standard deviation (log(sd+1) units)
n_inds = [300, 400, 500]   # numbers of inducing points fitted one after the other

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--predictors', default=PREDICTORS_NC)
parser.add_argument('--model-dir', default=MODEL_DIR)
args = parser.parse_args()
MODEL_DIR = args.model_dir
os.makedirs(MODEL_DIR, exist_ok=True)

# ---- load predictors and ASO snow depth -----------------------------------------
all_data = xr.open_dataset(args.predictors)
all_data = all_data.drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])

# dummy 'n_ind' dimension left over from earlier tests: to_dataframe() repeats the
# data along it and one copy (n_ind == 20) is selected below; values are unchanged
selected_data = all_data
selected_data = selected_data.assign_coords(n_ind= ("n_ind",[8,20, 45, 64, 100,150,200, 500]))

df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])
n = df.shape[1]-1


df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==20].reset_index(drop=True)
# target: log(snow depth + 1) at cells with all predictors and ASO snow depth defined
Y0 = np.array(df0.dropna()['snow_depth'])
Y0 = np.reshape(Y0, (-1, +1))
Y0t = np.log(Y0+1)
df0_all = df0.copy()
df0_all.drop(columns='snow_depth', inplace=True)
df0_all = df0_all.dropna()


# predictors in the order Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150, standardised
df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)

df0_allN = scaler.transform(df0_all)  # not used below

def fit_models(n_ind):

    print(n_ind)
    kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], ARD = True)

    # inducing inputs start from a random subset of the cells (no seed)
    model = GPy.models.SparseGPRegression(df0N,Y0t, kernel=kernel, num_inducing=n_ind)
    model.Gaussian_noise.variance = sigma_y**2
    model.Gaussian_noise.variance.fix()

    model.optimize()
    np.save(os.path.join(MODEL_DIR, f'models_noP_Sparse_M52_2022_04_21_nind{n_ind}.npy'), model.param_array)
    print(model)

for n_ind in n_inds:
    fit_models(n_ind)
