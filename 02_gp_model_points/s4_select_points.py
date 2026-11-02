"""Select the 5400 simulation points: GP inducing points plus cells of largest unexplained prior variance.

Step 1 (snapping): each of the 400 inducing inputs of the fitted sparse GP (s2) is
replaced by the ASO 2022-04-21 cell closest to it in the space of the 7 standardised
predictors plus 5 x log(sd+1) (inducing input, GP mean at the inducing input).
Step 2 (5 rounds j = 0..4): in each round, 10 times, the prior variance not
explained by the current points, k(x,x) - k(x,Z) K(Z,Z)^-1 k(Z,x) (+ constant noise),
is computed at all 296,799 cells and the 100 cells with the largest value are added
(1000 cells per round). After each round the kernel variance and lengthscales are refitted
(L-BFGS-B, inducing inputs and noise fixed, starting from the previous kernel).
Result: 400 + 5 x 1000 = 5400 points in standardised predictor space (indPTS_4.npy).

Restart: the original run stopped with a MemoryError while building the round-3 model
(4400 inducing points). It was continued with a copy of the script (200B_selINDP.py),
first with j = 3 (fit of round 3, then selection and fit of round 4), then with j = 4
(fit of round 4 only). --restart-round J reproduces that copy: it loads indPTS_J and
indY_J, fits the round-J kernel starting from lnscale_{J-1}/var_{J-1}, saves it and
continues with the normal rounds J+1..4.

Inputs:  all_data50from3_1702.nc (predictors and ASO snow depth; see README.md);
         models_noP_Sparse_M52_2022_04_21_nind400.npy (s2); <iter_dir>/lnscale_-1.npy and
         var_-1.npy (s3). With --restart-round J also indPTS_J, indY_J, lnscale_{J-1}, var_{J-1}.
Outputs: in <iter_dir>, for each round j = 0..4: indPTS_j.npy (400 + 1000 (j+1) points x 7,
         standardised predictors), indY_j.npy (log(sd+1) of those cells), lnscale_j.npy,
         var_j.npy (refitted kernel), model_j.npy (GPy param_array).
Environment: module anaconda3/2024.02-1 (Python 3.11) + GPy 1.13.2, paramz 0.9.6,
         netCDF4 1.7.2 in ~/.local (see README.md). Needs a large-memory node
         (the round-4 model allocates several 296,799 x 5400 float64 arrays, ~13 GB each).
Run:     python s4_select_points.py --predictors <all_data50from3_1702.nc> --model <...nind400.npy> --iter-dir <iter_dir>
         python s4_select_points.py ... --restart-round 3    (continue after a failure)
         (or sbatch sbatch_s4_select_points.sh <all_data50from3_1702.nc> <...nind400.npy> <iter_dir> [J])
Original: B/GP4MuSA/200_selINDP.py (run on 2025-08-21; same code as 200_GP_indP.ipynb
         cells 0, 2, 4, 7, 9-11, 14, 15, 18, 20, 23) and, for the restart,
         B/GP4MuSA/200B_selINDP.py (2025-08-22). Original outputs in
         /global/scratch/users/marcomaz/GP_models/5500_iter/. Only the docstring, the
         paths/settings block, comments and the restart option were changed; unused
         imports, host-dependent paths, unused plot lines and bounds were removed.
"""
import argparse
import os

import xarray as xr
import numpy as np
from sklearn.preprocessing import StandardScaler
import GPy

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC = '/global/scratch/users/marcomaz/all_data50from3_1702.nc'  # predictors and ASO snow depth (see README.md)
MODEL_NPY = ('/global/scratch/users/marcomaz/GP_models/models_MatSel/'
             'models_noP_Sparse_M52_2022_04_21_nind400.npy')  # output of s2
ITER_DIR = './output/5500_iter/'  # original: /global/scratch/users/marcomaz/GP_models/5500_iter/
sigma_y = 0.5   # noise standard deviation of the selection models (variance 0.25, fixed)

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--predictors', default=PREDICTORS_NC)
parser.add_argument('--model', default=MODEL_NPY)
parser.add_argument('--iter-dir', default=ITER_DIR, help='holds lnscale_-1/var_-1 (s3); receives all outputs')
parser.add_argument('--restart-round', type=int, default=None, choices=[0, 1, 2, 3, 4],
                    help='restart at round J from indPTS_J/indY_J (as 200B_selINDP.py)')
args = parser.parse_args()
ITER_DIR = args.iter_dir

# ---- training data ----------------------------------------------------------------
all_data = xr.open_dataset(args.predictors)
all_data = all_data.drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])

# dummy 'n_ind' dimension: to_dataframe() repeats the data along it and one copy is kept
selected_data = all_data#.sel(x=slice(xmin, xmax), y=slice(ymax, ymin)).drop_sel(date='2022-05-18')
selected_data = selected_data.assign_coords(n_ind= ("n_ind",[25,50,100,200,300,400]))

df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])
n = df.shape[1]-1


df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==25].reset_index(drop=True)
Y0 = np.array(df0.dropna()['snow_depth'])
Y0 = np.reshape(Y0, (-1, +1))
Y0t = np.log(Y0+1)
df0_all = df0.copy()
df0_all.drop(columns='snow_depth', inplace=True)
df0_all = df0_all.dropna()


# standardised predictors Ys, GSAfrac, Xs, Zs, slope, cosA, TPI150 of the 296,799 cells
df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)


def compute_gp_prior_variance_vectorized_constant_diag(kernel, new_Z, df0N, noise_var, knn_diag_val):
    # prior variance not explained by the points Z at every cell:
    # k(x,x) - k_xZ Kzz^-1 k_Zx + noise (noise and k(x,x) are constants); the
    # selection depends only on the kernel and on Z, not on the snow depths.
    # Kmm: [M, M], new_Z are inducing points
    Kmm = kernel.K(new_Z, new_Z) + 1e-6 * np.eye(new_Z.shape[0])
    Kmm_inv = np.linalg.inv(Kmm)
    # Kmn: [M, N] where N is num test points
    Kmn = kernel.K(new_Z, df0N)
    # Each reduction[i] = Kmn[:, i].T Kmm_inv Kmn[:, i]
    reduction = np.sum((Kmm_inv @ Kmn) * Kmn, axis=0)
    # All diagonal values the same
    var_pred_diag = knn_diag_val - reduction + noise_var
    return var_pred_diag


if args.restart_round is None:
    # ---- step 1: snap the 400 inducing inputs of the s2 model to ASO cells ----------
    kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], ARD = True)
    n_ind=400

    model = GPy.models.SparseGPRegression(df0N,Y0t, kernel=kernel, num_inducing=n_ind, initialize=False)

    model.update_model(False) # do not call the underlying expensive algebra on load
    model.initialize_parameter() # Initialize the parameters (connect the parameters up)
    model.Gaussian_noise.variance = sigma_y**2
    model.Gaussian_noise.variance.fix()
    model[:] = np.load(args.model) # Load the parameters (the noise variance is overwritten too)

    model.update_model(True) # Call the algebra only once

    y_ind_p = model.posterior.mean       # GP mean at the inducing inputs
    x_ind_p = model.inducing_inputs.values


    fake_ind = np.zeros_like(x_ind_p)
    fake_y = np.zeros_like(y_ind_p)

    # nearest cell in (7 standardised predictors, 5 x log(sd+1)) space
    coords = np.hstack([df0N,Y0t*5])

    idxs = []
    for i in range(x_ind_p.shape[0]):

        ind = x_ind_p[i,:][np.newaxis,:]/model.kern.lengthscale.values  # not used

        coords_i = np.hstack([x_ind_p[i],y_ind_p[i]*5])
        dists = ((coords-coords_i)**2).sum(axis=1)
        idxs.append(np.argmin(dists))
        fake_ind[i] = df0N[np.argmin(dists),:]
        fake_y[i] = Y0t[np.argmin(dists)]


    # ---- model for round 0: kernel of s3 (lnscale_-1, var_-1), snapped points fixed ----
    j=-1

    lnscale = np.load(os.path.join(ITER_DIR, f'lnscale_{j}.npy'))
    var = np.load(os.path.join(ITER_DIR, f'var_{j}.npy'))

    kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], lengthscale=lnscale, variance=var,ARD = True)

    modelN = GPy.models.SparseGPRegression(df0N,Y0t, kernel,Z = fake_ind)
    modelN.Gaussian_noise.variance = sigma_y**2
    modelN.Gaussian_noise.variance.fix()
    modelN.inducing_inputs.fix()
    # Fix the lengthscales (this model is not optimised; only its kernel is used in round 0)
    modelN.kern.lengthscale.fix()

    first_round = 0
else:
    # ---- restart (200B_selINDP.py): fit round J from saved points, then continue ----
    j = args.restart_round

    lnscale = np.load(os.path.join(ITER_DIR, f'lnscale_{j-1}.npy'))
    var = np.load(os.path.join(ITER_DIR, f'var_{j-1}.npy'))

    kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], lengthscale=lnscale, variance=var,ARD = True)

    fake_ind = np.load(os.path.join(ITER_DIR, f'indPTS_{j}.npy'))
    fake_y= np.load(os.path.join(ITER_DIR, f'indY_{j}.npy'))


    modelN = GPy.models.SparseGPRegression(df0N,Y0t, kernel,Z = fake_ind)
    modelN.Gaussian_noise.variance = sigma_y**2
    modelN.Gaussian_noise.variance.fix()
    modelN.inducing_inputs.fix()
    modelN.optimize()

    np.save(os.path.join(ITER_DIR, f'lnscale_{j}.npy'),kernel.lengthscale.values)
    np.save(os.path.join(ITER_DIR, f'var_{j}.npy'),kernel.variance.values)

    np.save(os.path.join(ITER_DIR, f'model_{j}.npy'), modelN.param_array)

    first_round = j + 1

# ---- step 2: 5 rounds of 10 x 100 cells of largest predictive variance ----------------
size = 100
for j in range(first_round, 5):


    print(modelN.kern.lengthscale.values)


    for i in range(10):
        # variance with the current points as inducing inputs and the kernel of the last fit
        var_uncertainty = compute_gp_prior_variance_vectorized_constant_diag(modelN.kern, fake_ind, df0N, modelN.likelihood.variance[0], modelN.kern.K(df0N[0:1,:],df0N[0:1,:])[0,0])
        order = np.argsort(var_uncertainty,axis=0,kind='stable')
        # cells with variance >= the 100th largest (kept in cell order)
        new_ind = df0N[(var_uncertainty>=var_uncertainty[order][-size]),:]
        new_indt = Y0t[(var_uncertainty>=var_uncertainty[order][-size]),:]

        fake_ind = np.vstack((fake_ind,new_ind))
        fake_y = np.vstack((fake_y,new_indt))

    np.save(os.path.join(ITER_DIR, f'indPTS_{j}.npy'),fake_ind)
    np.save(os.path.join(ITER_DIR, f'indY_{j}.npy'),fake_y)

    modelN= None

    # refit kernel variance and lengthscales with all points as fixed inducing inputs,
    # starting from the kernel of the previous round
    lnscale = np.load(os.path.join(ITER_DIR, f'lnscale_{j-1}.npy'))
    var = np.load(os.path.join(ITER_DIR, f'var_{j-1}.npy'))

    kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], lengthscale=lnscale, variance=var,ARD = True)

    modelN = GPy.models.SparseGPRegression(df0N,Y0t, kernel,Z = fake_ind)
    modelN.Gaussian_noise.variance = sigma_y**2
    modelN.Gaussian_noise.variance.fix()
    modelN.inducing_inputs.fix()

    modelN.optimize()

    np.save(os.path.join(ITER_DIR, f'lnscale_{j}.npy'),kernel.lengthscale.values)
    np.save(os.path.join(ITER_DIR, f'var_{j}.npy'),kernel.variance.values)

    np.save(os.path.join(ITER_DIR, f'model_{j}.npy'), modelN.param_array)
