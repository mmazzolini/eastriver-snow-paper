"""Selection of the 400 ICESat-2 (IC2) observed cells for one year ("B_K30" selection).

Candidates are the 50 m IC2 cells of s3_ic2_to_50m.py with complete median values.
Stage 0: a sparse GP (Matern 5/2, 30 inducing points) is fitted on the candidates
in the 7 scaled GP features with target log(snow depth + 1); each inducing point
is snapped to the nearest free candidate in [features, target].
Stage 1: cells are added one at a time up to 400, each time the candidate that most
reduces the summed GP predictive variance over the 5400 model cells (indPTS_4).
For 2024 the GP is fitted on the May (2024-05-20) depths and the observation is the
April (2024-04-03) depth; cells without an April value are not candidates.

Inputs:  IC2_synt50from3_<yr>.feather (+ IC2_synt50from3_24april.feather for 2024),
         GP_models/scaler.save, GP_models/5500_iter/{lnscale_4,var_4,indPTS_4}.npy,
         GP_models/models_MatSel/lengthscales_noP_Sparse_M52_2022_04_21_nind5400.npy
         (GP model of the 5400 model cells, made outside this folder).
Outputs: <out>/IC2cand_<yr>.npz (X, y_fit, y_obs, x, y, xg, yg, cols of all candidates)
         <out>/IC2sel_<yr>_B_K30.npz (idx, X, y_obs, y_fit, x, y, xg, yg, stage of the 400 cells)
Environment: gpy-env (GPy 1.13.2).
Run:     sbatch sbatch_s4_select_ic2_cells.sh 23 <out dir>   (and 24; ~3-5 min per year)
Original: /global/home/users/marcomaz/B/GP4MuSA/IC2_selINDP.py (+ sbatch_IC2_selINDP.sh);
          the original also wrote the variants A_K10/A_K30/A_K100/old400, not used later.
"""
import argparse
import os
import time

import GPy
import joblib
import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular

# ---- paths and settings ------------------------------------------------------
SCRATCH = "/global/scratch/users/marcomaz/"
FEATHER = SCRATCH + "IC2_synt50from3_{yr}.feather"            # 2023-04-01 / 2024-05-20 depths
FEATHER_APR24 = SCRATCH + "IC2_synt50from3_24april.feather"    # 2024-04-03 depths
SCALER = SCRATCH + "GP_models/scaler.save"
IT = SCRATCH + "GP_models/5500_iter/"                          # lnscale_4, var_4, indPTS_4
LS_STAGE0 = SCRATCH + "GP_models/models_MatSel/lengthscales_noP_Sparse_M52_2022_04_21_nind5400.npy"
SIGMA_Y = 0.5          # GP noise standard deviation (log space)
N_TOT = 400            # observed cells
K = 30                 # stage-0 inducing points (seed = K)
Y0_UTM, X0_UTM = 4322447, 308089      # y = Y0_UTM - Ys, x = Xs + X0_UTM (grid centre in UTM 13N)
# -------------------------------------------------------------------------------

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("year", type=int, choices=[23, 24])
p.add_argument("out", help="output directory")
a = p.parse_args()
YEAR, OUT = a.year, os.path.join(a.out, "")
os.makedirs(OUT, exist_ok=True)

scaler = joblib.load(SCALER)
COLS = list(scaler.feature_names_in_)
print("features", COLS, flush=True)


def median_table(f):
    """Median columns of a 50 m feather plus the grid coordinates Xs, Ys."""
    d = pd.read_feather(f)
    cols = [c for c, s in d.columns if s == "median"]
    t = pd.DataFrame({c: d[(c, "median")].to_numpy() for c in cols})
    t["Xs"], t["Ys"] = d[("Xs", "")].to_numpy(), d[("Ys", "")].to_numpy()
    return t


# candidates: median columns + Xs, Ys without NaN
tab = median_table(FEATHER.format(yr=YEAR)).dropna().reset_index(drop=True)
y_fit = np.log(tab["snow_depth"].to_numpy() + 1)
if YEAR == 24:
    apr = median_table(FEATHER_APR24)[["x", "y", "snow_depth"]]
    apr = apr[apr["snow_depth"] > -1].rename(columns={"snow_depth": "sd_apr"})
    tab = tab.merge(apr, on=["x", "y"], how="left")
    y_obs = np.log(tab["sd_apr"].to_numpy() + 1)
else:
    y_obs = y_fit.copy()
print(f"IC2 cells {len(tab)}, with observation {np.isfinite(y_obs).sum()}", flush=True)
ok = np.isfinite(y_obs)
tab, y_fit, y_obs = tab[ok].reset_index(drop=True), y_fit[ok][:, None], y_obs[ok][:, None]
X = scaler.transform(tab[COLS])
xg = tab["Xs"].to_numpy() + X0_UTM
yg = Y0_UTM - tab["Ys"].to_numpy()
np.savez(OUT + f"IC2cand_{YEAR}.npz", X=X, y_fit=y_fit, y_obs=y_obs, x=tab["x"].to_numpy(),
         y=tab["y"].to_numpy(), xg=xg, yg=yg, cols=np.array(COLS))

# kernel of the prior correlation (Corr.npy) used in stage 1
kern_sel = GPy.kern.Matern52(input_dim=X.shape[1], ARD=True,
                             lengthscale=np.load(IT + "lnscale_4.npy"),
                             variance=np.load(IT + "var_4.npy"))
kvar = float(kern_sel.variance.values[0])


def stage0(K, seed):
    """Sparse GP with K inducing points on the IC2 cells, snapped to IC2 cells."""
    np.random.seed(seed)
    k = GPy.kern.Matern52(input_dim=X.shape[1], ARD=True,
                          lengthscale=np.load(LS_STAGE0),
                          variance=np.load(IT + "var_4.npy"))
    m = GPy.models.SparseGPRegression(X, y_fit, kernel=k, num_inducing=K)
    m.Gaussian_noise.variance = SIGMA_Y ** 2
    m.Gaussian_noise.variance.fix()
    m.optimize()
    xz, yz = m.inducing_inputs.values, np.asarray(m.posterior.mean)
    coords = np.hstack([X, y_fit])
    idx = []
    for i in range(K):
        d = ((coords - np.hstack([xz[i], yz[i]])) ** 2).sum(axis=1)
        d[idx] = np.inf                      # no duplicates: next nearest free cell
        idx.append(int(np.argmin(d)))
    return idx


def fill_B(idx, T):
    """Candidate that most reduces sum over the model cells T of the predictive
    variance (noisy observation, variance SIGMA_Y**2), one per step."""
    idx = list(idx)
    Ktc = kern_sel.K(T, X)
    while len(idx) < N_TOT:
        Z = X[idx]
        L = np.linalg.cholesky(kern_sel.K(Z, Z) + 1e-6 * np.eye(len(idx)))
        Ac = solve_triangular(L, kern_sel.K(Z, X), lower=True)
        At = solve_triangular(L, kern_sel.K(Z, T), lower=True)
        C = Ktc - At.T @ Ac
        score = np.sum(C ** 2, axis=0) / (kvar - np.sum(Ac ** 2, axis=0) + SIGMA_Y ** 2)
        score[idx] = -np.inf
        idx.append(int(np.argmax(score)))
    return idx


def save(name, idx, n0):
    idx = np.asarray(idx)
    assert len(idx) == N_TOT and len(np.unique(idx)) == N_TOT, name
    stage = np.r_[np.zeros(n0, int), np.ones(N_TOT - n0, int)]
    np.savez(OUT + f"IC2sel_{YEAR}_{name}.npz", idx=idx, X=X[idx], y_obs=y_obs[idx], y_fit=y_fit[idx],
             x=tab["x"].to_numpy()[idx], y=tab["y"].to_numpy()[idx], xg=xg[idx], yg=yg[idx], stage=stage)
    print(f"saved {name}: elevation median {np.median(tab['Zs'].to_numpy()[idx]):.0f} m", flush=True)


T = np.load(IT + "indPTS_4.npy")          # 5400 model cells (scaled features)
t = time.time()
i0 = stage0(K, seed=K)
print(f"stage 0 K={K}: {len(i0)} cells, {time.time() - t:.0f} s", flush=True)
t = time.time()
save(f"B_K{K}", fill_B(i0, T), K)
print(f"stage 1: {time.time() - t:.0f} s", flush=True)
