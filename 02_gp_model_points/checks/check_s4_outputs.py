"""Consistency checks of the original point-selection outputs (no rerun of the selection).

1. Snapping (step 1 of s4, same lines): the 400 snapped cells must equal the first
   400 rows of indPTS_0.npy / indY_0.npy.
2. Nesting: indPTS_j[:400 + 1000 j] == indPTS_{j-1} and the same for indY_j.
3. model_j.npy (GPy param_array) = [indPTS_j (flattened), var_j, lnscale_j, noise]:
   inducing inputs, kernel variance and lengthscales equal the saved files, noise = 0.25.
4. Every row of indPTS_4 is a row of the standardised training cells (exact match),
   indY_4 holds log(sd+1) of those cells, and the number of distinct cells.
5. The lengthscales printed at the start of rounds 0-3 in the original log
   (pingSel.out) equal lnscale_{j-1}.npy (to the 8 printed decimals).

Inputs:  predictors NetCDF, nind400 model (s2), original iteration folder (5500_iter), original log.
Outputs: text on stdout.
Environment: module anaconda3/2024.02-1 + ~/.local (GPy 1.13.2), as s4.
Run:     python checks/check_s4_outputs.py <predictors.nc> <nind400.npy> <iter_dir> <pingSel.out>
Original: new check script; the data and snapping lines are copied from s4_select_points.py.
"""
import os
import re
import sys

import numpy as np
import xarray as xr
from sklearn.preprocessing import StandardScaler
import GPy

# ---- paths and settings ------------------------------------------------------
PREDICTORS_NC, MODEL_NPY, ITER_DIR, LOG = sys.argv[1:5]
sigma_y = 0.5
N_ROUNDS = 5


def load(name):
    return np.load(os.path.join(ITER_DIR, name))


# ---- training data (as s4) ------------------------------------------------------------
all_data = xr.open_dataset(PREDICTORS_NC)
all_data = all_data.drop_vars(['Sx200','Sx100','sinA','TPI1000','DAH'])
selected_data = all_data
selected_data = selected_data.assign_coords(n_ind= ("n_ind",[25,50,100,200,300,400]))
df = selected_data.drop(['spatial_ref']).to_dataframe().dropna(subset=["Xs"])
df0 = df.loc[df.index.get_level_values('date') == '2022-04-21']
df0 = df0.loc[df0.index.get_level_values('n_ind') ==25].reset_index(drop=True)
Y0 = np.array(df0.dropna()['snow_depth'])
Y0 = np.reshape(Y0, (-1, +1))
Y0t = np.log(Y0+1)
df0 = df0.dropna().drop(columns='snow_depth')
scaler = StandardScaler()
df0N = scaler.fit_transform(df0)
print('training cells:', df0N.shape, 'feature order:', list(df0.columns))

# ---- 1. snapping (step 1 of s4) ---------------------------------------------------------
kernel = GPy.kern.Matern52(input_dim=df0N.shape[1], ARD = True)
n_ind=400
model = GPy.models.SparseGPRegression(df0N,Y0t, kernel=kernel, num_inducing=n_ind, initialize=False)
model.update_model(False)
model.initialize_parameter()
model.Gaussian_noise.variance = sigma_y**2
model.Gaussian_noise.variance.fix()
model[:] = np.load(MODEL_NPY)
model.update_model(True)
y_ind_p = model.posterior.mean
x_ind_p = model.inducing_inputs.values
fake_ind = np.zeros_like(x_ind_p)
fake_y = np.zeros_like(y_ind_p)
coords = np.hstack([df0N,Y0t*5])
idxs = []
for i in range(x_ind_p.shape[0]):
    coords_i = np.hstack([x_ind_p[i],y_ind_p[i]*5])
    dists = ((coords-coords_i)**2).sum(axis=1)
    idxs.append(np.argmin(dists))
    fake_ind[i] = df0N[np.argmin(dists),:]
    fake_y[i] = Y0t[np.argmin(dists)]

ind0, y0 = load('indPTS_0.npy'), load('indY_0.npy')
print('\n1. snapping: indPTS_0[:400] identical:', np.array_equal(fake_ind, ind0[:400]),
      ' max abs diff:', np.max(np.abs(fake_ind - ind0[:400])),
      '| indY_0[:400] identical:', np.array_equal(fake_y, y0[:400]))
print('   snapped cells: distinct', len(set(idxs)), 'of', len(idxs))

# ---- 2.-3. nesting and model files -------------------------------------------------------
print('\n2./3. rounds')
for j in range(N_ROUNDS):
    P, Y = load(f'indPTS_{j}.npy'), load(f'indY_{j}.npy')
    ls, var, m = load(f'lnscale_{j}.npy'), load(f'var_{j}.npy'), load(f'model_{j}.npy')
    n_exp = 400 + 1000 * (j + 1)
    line = f'   j={j}: indPTS {P.shape}, expected rows {n_exp}: {P.shape[0] == n_exp}'
    if j > 0:
        Pp, Yp = load(f'indPTS_{j-1}.npy'), load(f'indY_{j-1}.npy')
        line += (f'; prefix == indPTS_{j-1}: {np.array_equal(P[:Pp.shape[0]], Pp)}'
                 f', indY prefix: {np.array_equal(Y[:Yp.shape[0]], Yp)}')
    nz = P.size
    line += (f'; model_{j}: Z == indPTS_{j}: {np.array_equal(m[:nz], P.ravel())}'
             f', var == var_{j}: {np.array_equal(m[nz:nz+1], var)}'
             f', lengthscales == lnscale_{j}: {np.array_equal(m[nz+1:nz+8], ls)}'
             f', noise: {m[nz+8]}, size ok: {m.size == nz + 9}')
    print(line)

# ---- 4. points are training cells -----------------------------------------------------------
P4, Y4 = load('indPTS_4.npy'), load('indY_4.npy')
row_of = {r.tobytes(): k for k, r in enumerate(df0N)}
rows = np.array([row_of.get(r.tobytes(), -1) for r in P4])
print('\n4. indPTS_4 rows found among the training cells:', np.sum(rows >= 0), 'of', len(rows),
      '| distinct cells:', len(set(rows[rows >= 0].tolist())),
      '| indY_4 == log(sd+1) of those cells:', np.array_equal(Y4[rows >= 0, 0], Y0t[rows[rows >= 0], 0]))

# ---- 5. printed lengthscales in the original log ------------------------------------------------
txt = open(LOG).read()
arrays = re.findall(r'^\[([^\]]+)\]', txt, flags=re.M)
print('\n5. lengthscale arrays printed in', LOG, ':', len(arrays))
for j, a in enumerate(arrays):
    printed = np.array([float(v) for v in a.split()])
    saved = load(f'lnscale_{j-1}.npy')
    print(f'   round {j}: printed == lnscale_{j-1} (abs. tol 1e-8, 8 printed decimals): '
          f'{np.allclose(printed, saved, rtol=0, atol=1e-8)}')
