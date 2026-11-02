"""Gaspari-Cohn (GC) prior correlation field of the 5400 model cells and the 400 ICESat-2 cells, per year.

Points: the 5400 model cells (indPTS_4, rows 0-5399) and the 400 observed cells
(rows 5400-5799) padded with NaN rows to 10800, all in the 7 scaled GP features.
d = Euclidean distance between points (length scales 1); d > 2c is set to NaN;
rhoGC1 = GC(d, c) with c = 5 (fifth-order piecewise rational function of Gaspari
and Cohn, 1999); entries with NaN distance (d > 2c or padded rows) are 0.
DistMaskGC_05 = 1 where rhoGC1 > 0.5, else NaN.
Existing output files are never overwritten.
Optional recipe check (--recipe-check): the same recipe applied to the cells of the
earlier IC2 selection must reproduce the GC field of the earlier data set.

Inputs:  <points>/IC2NP_<yr>_X.npy (s5_ic2_points.py), GP_models/5500_iter/indPTS_4.npy;
         for --recipe-check: GP_models/models_MatSel/IC2_kern5400_<yr>_400.npy and
         DATA_GP5400_400/Corr<yr>/rhoGC1.npy.
Outputs: <out>/Corr<yr>/rhoGC1.npy and DistMaskGC_05.npy (10800 x 10800 float64, ~0.9 GB each).
Environment: MuSAenv (module load anaconda3; source activate base; source activate MuSAenv).
Run:     sbatch sbatch_s8_gc_corr.sh <points dir> <out dir> [--years 23 24] [--recipe-check]
Original: /global/home/users/marcomaz/B/GP4MuSA/NP/np_gc_corr.py (recipe of
          B/GP4MuSA/4_designGC.ipynb cell 2); GC() copied from
          /global/home/users/marcomaz/MuSA_spatial/modules/spatialMuSA.py.
          Outputs in /global/scratch/users/marcomaz/DATA_NP/Corr<yr>/.
"""
import argparse
import os

import numpy as np
from scipy.spatial import distance

# ---- paths and settings ------------------------------------------------------
SCRATCH = "/global/scratch/users/marcomaz/"
MODEL_PTS = SCRATCH + "GP_models/5500_iter/indPTS_4.npy"                     # 5400 model cells
OLD_OBS_X = SCRATCH + "GP_models/models_MatSel/IC2_kern5400_{yr}_400.npy"     # --recipe-check only
OLD_GC = SCRATCH + "DATA_GP5400_400/Corr{yr}/rhoGC1.npy"                      # --recipe-check only
C = 5                                  # GC half-width (zero beyond 2c), in scaled-feature units
NY, N_OBS = 5400, 400
ACT = np.r_[np.arange(NY), NY + np.arange(N_OBS)]      # active rows: model cells + observed cells
# -------------------------------------------------------------------------------


def GC(d, c):
    """Gaspari-Cohn correlation of distance d with half-width c (copy of spatialMuSA.GC)."""
    # Pre-allocation
    rho = np.zeros(d.shape)

    # Correlation for nearby points
    sel_points = d[d < c]
    if len(sel_points != 0):
        sel_points = sel_points / c
        rho[d < c] = (-1/4) * (sel_points)**5 + (1/2) * (sel_points)**4 + \
            (5/8) * (sel_points)**3 - (5/3) * (sel_points)**2 + 1

    # Correlation for mid-range points
    sel_points = d[np.logical_and(d >= c, d <= 2*c)]
    if len(sel_points != 0):
        sel_points = sel_points/c
        rho[np.logical_and(d >= c, d <= 2*c)] = (1/12) * (sel_points)**5 - \
            (1/2) * (sel_points)**4 + (5/8) * (sel_points)**3 + (5/3) * \
            (sel_points)**2 - 5 * (sel_points) + 4 - (2/3) * \
            (1/sel_points)

    # Far points (d > 2c) and NaN distances stay 0 here
    return rho


def rho_gc(obs_X, model_pts):
    """GC field of model cells + observed cells padded with NaN to 5400 rows."""
    obs_pts = np.vstack((obs_X, np.full((NY - obs_X.shape[0], 7), np.nan)))
    pts = np.vstack((model_pts, obs_pts))
    d = distance.cdist(pts, pts, metric="euclidean")
    d[d > C * 2] = np.nan
    return GC(d, C)


p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--points", required=True, help="directory with IC2NP_<yr>_X.npy")
p.add_argument("--out", required=True, help="output data directory (Corr<yr>/)")
p.add_argument("--years", type=int, nargs="+", default=[23, 24], choices=[23, 24])
p.add_argument("--recipe-check", action="store_true",
               help="first reproduce the earlier GC field from the earlier IC2 cells; stop if it differs")
a = p.parse_args()

model_pts = np.load(MODEL_PTS)
for yr in a.years:
    print(f"===== 20{yr}", flush=True)
    if a.recipe_check:
        old_saved = np.load(OLD_GC.format(yr=yr), mmap_mode="r")
        old_new = rho_gc(np.load(OLD_OBS_X.format(yr=yr)), model_pts)
        na, nb = np.isnan(old_new), np.isnan(np.asarray(old_saved))
        diff = np.nanmax(np.abs(old_new - old_saved)) if (~na).any() else 0.0
        print(f"recipe check vs earlier rhoGC1: same NaN pattern {np.array_equal(na, nb)}, max |diff| {diff:.2e}", flush=True)
        if not (np.array_equal(na, nb) and diff < 1e-10):
            raise SystemExit("recipe does not reproduce the earlier field: stop")
        del old_new, na, nb

    cdir = os.path.join(a.out, f"Corr{yr}")
    os.makedirs(cdir, exist_ok=True)
    out_r, out_m = os.path.join(cdir, "rhoGC1.npy"), os.path.join(cdir, "DistMaskGC_05.npy")
    for f in (out_r, out_m):
        if os.path.exists(f):
            raise SystemExit(f"{f} exists: not overwriting")
    rho = rho_gc(np.load(os.path.join(a.points, f"IC2NP_{yr}_X.npy")), model_pts)
    np.save(out_r, rho)
    np.save(out_m, np.where(rho > 0.5, 1, np.nan))
    print(f"wrote {out_r} and {out_m}, shape {rho.shape}", flush=True)

    # checks on the active block: symmetry, unit diagonal, smallest eigenvalues, neighbourhood size
    R = rho[np.ix_(ACT, ACT)]
    del rho
    print(f"active 5800: symmetric {np.allclose(R, R.T, equal_nan=True)}, "
          f"diag {np.nanmin(np.diag(R)):.6f}-{np.nanmax(np.diag(R)):.6f}, NaN {np.isnan(R).sum()}")
    R0 = np.nan_to_num(R)
    ev_obs = np.linalg.eigvalsh(R0[NY:, NY:])
    ev_all = np.linalg.eigvalsh(R0)
    print(f"lambda_min: observed 400x400 {ev_obs[0]:.4f} ({(ev_obs < -1e-8).sum()} negative), "
          f"active 5800 {ev_all[0]:.4f} ({(ev_all < -1e-8).sum()} negative)")
    iu = np.triu_indices(N_OBS, 1)
    B = R0[:NY, NY:]
    n05 = (B > 0.5).sum(1)
    print(f"obs-obs median rho {np.median(R0[NY:, NY:][iu]):.3f}; observed neighbours (rho > 0.5) per model cell: "
          f"median {np.median(n05):.0f} ({np.percentile(n05, 10):.0f}-{np.percentile(n05, 90):.0f}), none {int((n05 == 0).sum())}",
          flush=True)
    del R, R0, B
