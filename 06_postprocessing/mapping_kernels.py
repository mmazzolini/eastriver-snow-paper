"""Kernels of the mapping of the MuSA ensembles to the 50 m grid (imported by 21_maptogrid_NP.py).

map_one_ensemble_gp: GP regression (GPy, Matern 5/2 with ARD, fixed variance and length scales,
    Gaussian noise variance sigma_y**2) of log(snow depth + 1) on the 5400 model cells, predicted
    on the grid cells; returns exp(mean) - 1 (m).
map_one_ensemble_gc: the same with the Gaspari-Cohn kernel (class GaspariCohn, compactly supported,
    zero beyond 2 length scales), solved directly with a Cholesky factor that each worker process
    caches; the prediction is computed in chunks of MUSA_PRED_CHUNK grid cells (default 2000).
Both take one tuple (member index, 5400 snow depths in mm, training features, prediction features,
variance, length scale(s), sigma_y) and return (member index, values on the grid cells).

Inputs: none (functions only). Outputs: none.
Environment: gpy-env (../environments/gpy-env.yml); MUSA_PRED_CHUNK (optional, GC only).
Run: imported, not run (see 21_maptogrid_NP.py).
Original: map_one_ensemble of B/Post/21_maptogridGP_ensembles_all_20230401.py (here
    map_one_ensemble_gp), GaspariCohn and map_one_ensemble of
    B/Post/21_maptogridGC_ensembles_all_onedate.py (here map_one_ensemble_gc); copied verbatim,
    only the function names (and the GC function's reference to its own cache) changed.
"""
import os

import numpy as np
import GPy
from scipy.linalg import cho_factor, cho_solve
from GPy.kern import Kern
from GPy.core.parameterization import Param
from paramz.transformations import Logexp


# ---- GP (Matern 5/2), from 21_maptogridGP_ensembles_all_20230401.py
def map_one_ensemble_gp(args):
    en_idx, all_ptsY, all_ptsT, pred_features, var, lengthscales, sigma_y = args

    all_ptsYT = np.log(all_ptsY / 1000 + 1)[:, np.newaxis]

    kernel = GPy.kern.Matern52(
        input_dim=all_ptsT.shape[1],
        ARD=True,
        lengthscale=lengthscales,
        variance=var,
    )

    model = GPy.models.GPRegression(all_ptsT, all_ptsYT, kernel=kernel)
    model.update_model(False)
    model.initialize_parameter()
    model.Gaussian_noise.variance = sigma_y**2
    model.Gaussian_noise.variance.fix()
    model.update_model(True)

    y, _ = model.predict(pred_features, full_cov=False, include_likelihood=False, Y_metadata=None)
    posterior = np.exp(y[:, 0]) - 1
    return en_idx, posterior


# ---- Gaspari-Cohn, from 21_maptogridGC_ensembles_all_onedate.py
class GaspariCohn(Kern):
    def __init__(self, input_dim, variance=1.0, lengthscale=1.0,
                 active_dims=None, name='gaspari_cohn'):
        super(GaspariCohn, self).__init__(input_dim, active_dims, name)
        self.variance = Param('variance', float(variance), Logexp())
        self.lengthscale = Param('lengthscale', float(lengthscale), Logexp())
        self.link_parameters(self.variance, self.lengthscale)

    def _scaled_dist(self, X, X2=None):
        if X2 is None:
            X2 = X
        X = np.asarray(X)
        X2 = np.asarray(X2)
        diff = X[:, None, :] - X2[None, :, :]
        d = np.sqrt(np.sum(diff**2, axis=2))
        return d / float(self.lengthscale)

    @staticmethod
    def _gc_rho(r):
        r = np.asarray(r)
        out = np.zeros_like(r, dtype=float)

        m1 = (r >= 0.0) & (r <= 1.0)
        x = r[m1]
        out[m1] = (((-0.25*x + 0.5)*x + 0.625)*x - 5.0/3.0)*x*x + 1.0

        m2 = (r > 1.0) & (r < 2.0)
        x = r[m2]
        out[m2] = ((((x/12.0 - 0.5)*x + 0.625)*x + 5.0/3.0)*x - 5.0)*x \
                  + 4.0 - 2.0/(3.0*x)

        return out
    
    def K(self, X, X2=None):
        r = self._scaled_dist(X, X2)
        return self.variance * self._gc_rho(r)

    def Kdiag(self, X):
        return np.full(X.shape[0], float(self.variance))

    def update_gradients_full(self, dL_dK, X, X2=None):
        if X2 is None:
            X2 = X

        X = np.asarray(X)
        X2 = np.asarray(X2)

        diff = X[:, None, :] - X2[None, :, :]
        d = np.sqrt(np.sum(diff**2, axis=2))

        ell = float(self.lengthscale)
        var = float(self.variance)

        r = d / ell

        rho = np.zeros_like(r)
        drho_dr = np.zeros_like(r)

        m1 = (r >= 0.0) & (r <= 1.0)
        x = r[m1]
        rho[m1] = 1.0 - (5.0/3.0)*x**2 + (5.0/8.0)*x**3 + 0.5*x**4 - 0.25*x**5
        drho_dr[m1] = -(10.0/3.0)*x + (15.0/8.0)*x**2 + 2.0*x**3 - (5.0/4.0)*x**4

        m2 = (r > 1.0) & (r < 2.0)
        x = r[m2]
        rho[m2] = 4.0 - 5.0*x + (5.0/3.0)*x**2 + (5.0/8.0)*x**3 - 0.5*x**4 + (1.0/12.0)*x**5 - 2.0/(3.0*x)
        drho_dr[m2] = -5.0 + (10.0/3.0)*x + (15.0/8.0)*x**2 - 2.0*x**3 + (5.0/12.0)*x**4 + 2.0/(3.0*x**2)

        dK_dvar = rho
        dK_dell = var * drho_dr * (-r / ell)

        self.variance.gradient = np.sum(dL_dK * dK_dvar)
        self.lengthscale.gradient = np.sum(dL_dK * dK_dell)
            
    def update_gradients_diag(self, dL_dKdiag, X):
        self.variance.gradient = np.sum(dL_dKdiag)
        self.lengthscale.gradient = 0.0

    def gradients_X(self, dL_dK, X, X2=None):
        raise NotImplementedError("gradients_X not implemented for this kernel yet")

    def gradients_X_diag(self, dL_dKdiag, X):
        return np.zeros_like(X)


def map_one_ensemble_gc(args):
    en_idx, all_ptsY, all_ptsT, pred_features, var, lengthscale, sigma_y = args
    # per-process cache to avoid recomputing the same kernel matrix and cholesky
    if not hasattr(map_one_ensemble_gc, "_cache"):
        map_one_ensemble_gc._cache = {}

    # key depends on training / prediction shapes and kernel params
    key = (all_ptsT.shape[0], pred_features.shape[0], float(var), float(lengthscale), float(sigma_y))
    cache = map_one_ensemble_gc._cache

    if key not in cache:
        kernel = GaspariCohn(
            input_dim=all_ptsT.shape[1],
            lengthscale=lengthscale,
            variance=var,
        )
        # keep kernel parameters fixed
        kernel.variance.fix()
        kernel.lengthscale.fix()

        # training covariance + noise
        K_tt = kernel.K(all_ptsT, all_ptsT)
        K_tt[np.diag_indices_from(K_tt)] += sigma_y**2

        # Cholesky factorization (stored via cho_factor/cho_solve)
        cho = cho_factor(K_tt, lower=True, check_finite=False)

        # store only cho factor and kernel object (do not compute full K_pt)
        cache[key] = {
            'cho': cho,
            'kernel': kernel,
        }

    # now compute posterior for this ensemble using cached factors
    cached = cache[key]
    kernel = cached['kernel']

    all_ptsYT = np.log(all_ptsY / 1000 + 1)[:, np.newaxis]
    # solve alpha = K_tt^{-1} * y using cho_solve
    alpha = cho_solve(cached['cho'], all_ptsYT, check_finite=False)

    # compute K_pt in chunks to avoid large temporary arrays
    n_pred = pred_features.shape[0]
    chunk = int(os.environ.get('MUSA_PRED_CHUNK', '2000'))
    y_pred_parts = []
    for i in range(0, n_pred, chunk):
        Xs = pred_features[i:i+chunk]
        K_chunk = kernel.K(Xs, all_ptsT)
        y_chunk = K_chunk.dot(alpha)
        y_pred_parts.append(y_chunk)

    y_pred = np.vstack(y_pred_parts)
    posterior = np.exp(y_pred[:, 0]) - 1
    return en_idx, posterior
