"""Observation error standard deviations of the ICESat-2 cells by terrain-slope class (0.37 / 0.84 / 1.40 m).

Each selected 50 m cell stands for n = 11 IC2 cells (4461 candidate cells in
2023 / 400 selected). The error of one IC2 50 m cell (NMAD of IC2 snow depth by
slope class, values as entered in the original notebook) is scaled as the
standard deviation of a mean of n correlated errors:
    sd = nmad * sqrt((1 + (n - 1) * rho_mean) / n),
with rho_mean the mean Matern 5/2 correlation (variance 1) between all 2023
candidate cells in the scaled GP features. The rounded values (0.37, 0.84, 1.40)
are those written by s7_obs_and_gp_corr.py.

Inputs:  IC2_synt50from3_23.feather, GP_models/scaler.save,
         GP_models/models_MatSel/lengthscales_noP_Sparse_M52_2022_04_21_nind5400.npy.
Outputs: printed values only.
Environment: gpy-env (GPy).
Run:     sbatch sbatch_s6_obs_error_classes.sh   (python s6_obs_error_classes.py)
Original: /global/home/users/marcomaz/B/GP4MuSA/IC2_GP_indP.ipynb cells 0, 5, 8, 11-13, 19, 22-28
          (rho_mean printed there: 0.886555579941265).
"""
import GPy
import joblib
import numpy as np
import pandas as pd

# ---- paths and settings ------------------------------------------------------
SCRATCH = "/global/scratch/users/marcomaz/"
FEATHER_23 = SCRATCH + "IC2_synt50from3_23.feather"
SCALER = SCRATCH + "GP_models/scaler.save"
LENGTHSCALES = SCRATCH + "GP_models/models_MatSel/lengthscales_noP_Sparse_M52_2022_04_21_nind5400.npy"
N_OBS = 400
N = 11                       # IC2 cells per observed cell (4461 / 400 = 11.15, cell 13)
NMAD = {                     # NMAD of one IC2 50 m cell (m), notebook cells 26-28
    "slope < 10 deg": 0.39,
    "10 <= slope <= 40 deg": 0.6 * 1.48,   # MAD 0.6 m x 1.48
    "slope > 40 deg": 1.48,
}
# -------------------------------------------------------------------------------

scaler = joblib.load(SCALER)
COLS = list(scaler.feature_names_in_)      # = df0.columns of the notebook

# 2023 candidate cells: median columns + Xs, Ys, rows without NaN (cells 5 and 8)
IC2_23 = pd.read_feather(FEATHER_23)
IC2_sel23 = IC2_23.loc[:, (slice(None), 'median')].reset_index(col_level=1)
IC2_sel23[['Xs', 'Ys']] = IC2_23[['Xs', 'Ys']]
IC2_sel23.dropna(inplace=True)
IC2_sel23.drop(columns=['x', 'y', 'pair'], inplace=True)
IC2_sel23.drop(columns=['snow_depth'], inplace=True)
IC2_N23 = scaler.transform(IC2_sel23[COLS])
size_IC2 = IC2_sel23.shape[0]
print(f"2023 IC2 candidate cells {size_IC2}; per observed cell {size_IC2 / N_OBS:.2f} (n = {N})")

# mean correlation between all candidate cells (cells 19, 22-24)
lengthscales = np.load(LENGTHSCALES)
kernel3 = GPy.kern.Matern52(input_dim=IC2_N23.shape[1], ARD=True, lengthscale=lengthscales, variance=1)
corr = kernel3.K(IC2_N23, IC2_N23)
corr_ = corr.mean()
print(f"mean correlation rho_mean = {corr_!r}")

# standard deviation of the mean of N correlated errors (cells 26-28)
for name, nmad in NMAD.items():
    ind_pt_std = nmad * ((1 + (N - 1) * corr_) / N) ** (1 / 2)
    print(f"{name:22s} nmad {nmad:.3f} m -> sd {ind_pt_std:.4f} m (rounded {ind_pt_std:.2f}; variance {round(ind_pt_std, 2) ** 2:.4f} m2)")
