"""Build the data files of the interactive West-East strip website (docs/).

The website redraws the figure of B/Results/WE_strip_final.ipynb for any profile position, for the
two water years and the two experiments (GPE = GP prior correlation, GCE = Gaspari-Cohn).
This script turns the mapped ensembles (50 m grid, 100 members) into small files that the page
reads with HTTP range requests (GitHub Pages or any static host).

Inputs (per run, see RUNS):
    <D>/<run>/Post<yy>_mapped<yymmdd>_ens.nc, Prior<yy>_mapped<yymmdd>_ens.nc   mapped members
    <D>/<run>/Prior<yy>_mapped<yymmdd>.nc                                       mapped prior mean
    <D>/<run>/En_snd<yy>.nc, En_snd<yy>_Pr.nc                                   IC2-cell ensembles (x = 1)
    DATA_NP/points/IC2NP_<yy>.csv, DATA_NP/Obs<yy>_var/IC2_<yy-mm-dd>_var.nc    IC2 cells, obs and R
    all_data50from3_1105.nc (terrain Zs), all_data50from3_1702.nc (ASO 2023-04-01),
    ASO_EastRiver_2024Apr03_snowdepth_50m.tif (ASO 2024-04-03), shp/EastRiver_subbasins_proj.shp
    reanalyses/rean_50m.nc (optional): SNODAS, UA 800 m and WLDAS snow depth on the grid (web/get_reanalyses.py)

Outputs (in OUT):
    manifest.json             grid, runs, files, tile index, IC2 tracks and default settings per year
    mask.bin.gz               uint8 [ny, nx], 1 = cell with model values
    z.bin.gz                  float32 [ny, nx], terrain elevation (m)
    aso<yy>.bin.gz            int16 [ny, nx], ASO snow depth (mm), -32768 = missing
    rean_<prod><yy>.bin.gz    int16 [ny, nx], snow depth of a gridded product (mm), block-constant at its own
                              resolution; listed in manifest years[yr].products
    <id>_summary.bin.gz       int16 [4, ny, nx]: prior mean, prior SD, posterior mean, posterior SD (mm)
    <id>_ic2.json             IC2 cells: x, y, z, ASO, obs, R and the prior / posterior members (mm)
    <id>_pack<k>.bin          64 x 64-cell tiles, each gzip-compressed, concatenated (see TILE FORMAT)
    basins.geojson            sub-basin boundaries (UTM 13N, m)
    reference_<id>.json       notebook profiles, point values and two segments at the default settings
                              (full precision; for web/check_core.mjs only)

IC2 TRACKS. The IC2 cells lie on three near-north-south ICESat-2 tracks (beam pairs, the two beams
about 100 m apart). The cells are grouped by u = x - s (y - y_ref): the common slope s is the one
that minimises the spread of u within the groups, the groups being split where consecutive sorted
u values differ by more than TRACK_GAP. Each track gets a line x = a y + b fitted through its cells;
the track of the paper's profile keeps the notebook's own fit (cells with E in IC2P track_e), so the
default profile 2 is the paper's.

TILE FORMAT v2 (little endian). Cells of the tile with mask = 1, rows south to north, serpentine within
the rows (even rows west to east, odd rows east to west, counted from the tile's first row):
    uint32 n; then for the posterior and then the prior:
    uint8 lo[100 * n], uint8 hi[100 * n]: low and high bytes of int16 d[k, j] (member-major), the
    difference in cm between cell j and cell j - 1 of member k (d[k, 0] = value of the first cell).
    member value (cm) = cumulative sum of d[k, :]; error <= 5 mm. The mapped fields are smooth, so the
    differences are small and compress well (~52 MB per run; whole mm would need ~71 MB).

Grid rows run south to north (y ascending) and columns west to east (x ascending).

Run: sbatch web/sbatch_build_web.sh   (gpy-env, savio4_htc)
"""
import gzip
import json
import os
import time

import numpy as np
import pandas as pd
import xarray as xr
import rioxarray  # noqa: F401  (rasterio engine for the ASO tif)
import geopandas as gpd
import properscoring as ps
from scipy.stats import gaussian_kde

# ------------------------------------------------------------------ paths and settings
SCRATCH = "/global/scratch/users/marcomaz"
D = os.path.join(SCRATCH, "DATA_GP5400_400")
OUT = os.environ.get("WEB_OUT", os.path.join(SCRATCH, "web_data"))
TOPO = os.path.join(SCRATCH, "all_data50from3_1105.nc")
ALLDATA = os.path.join(SCRATCH, "all_data50from3_1702.nc")
ASO24_TIF = os.path.join(SCRATCH, "ASO_EastRiver_2024Apr03_snowdepth_50m.tif")
BASINS = os.path.join(SCRATCH, "shp/EastRiver_subbasins_proj.shp")
REAN = os.path.join(SCRATCH, "reanalyses/rean_50m.nc")
# gridded snow products shown for comparison (web/get_reanalyses.py); order = legend order
PRODUCTS = {
    "ua": dict(label="UA 800 m", res="800 m", dash=None,
               desc="University of Arizona daily snow depth, 800 m; SNOTEL and COOP station data assimilated "
                    "into a PRISM-driven snow model (Broxton et al. 2024)"),
    "snodas": dict(label="SNODAS", res="1 km", dash="6 3",
                   desc="NOAA NOHRSC SNODAS, 1 km, snapshot at 06 UTC; snow model updated daily with ground, "
                        "airborne and satellite observations (NSIDC G02158)"),
    "wldas": dict(label="WLDAS", res="0.01°", dash="0.1 3.8",
                  desc="NASA WLDAS, Noah-MP 3.6 driven by NLDAS-2, 0.01°, daily mean; no snow data assimilation "
                       "(GES DISC WLDAS_NOAHMP001_DA1, ends 2024-01-01)"),
}

DATES = {2023: "2023-04-01", 2024: "2024-04-03"}
RUNS = [dict(id="23GP", year=2023, exp="GP", run="23GPpow2NPnbm_var"),
        dict(id="23GC", year=2023, exp="GC", run="23GCpow2NP_var"),
        dict(id="24GP", year=2024, exp="GP", run="24GPpow2NPnb_var"),
        dict(id="24GC", year=2024, exp="GC", run="24GCpow2NP_var")]
LABEL = {"GP": "GPE", "GC": "GCE"}
COLOR = {"GP": "#2a78d6", "GC": "#eb6834"}
TILE = 64
PACK_MAX = 14_500_000            # bytes per pack file (claude.ai preview limit 15 MB)
NODATA = -32768
Q = (25, 75)
MIN_CELLS = 1

# default settings = WE_strip_final.ipynb (Settings cell and the knobs of the last cell)
LONG = dict(n_min=4311.03e3, n_max=4311.06e3, e_min=None, e_max=None, k=300, bias_ylim=(-5.2, 5.2))
IC2P = dict(track_e=(339.0e3, 340.7e3), p0=4305.5e3, p1=4317.0e3, half_width=150, k=140,
            bias_ylim="sym", bias_fac=0.95)
PT_IC2 = dict(n=4313.99e3)
PT_FIELD = dict(e=326.2e3, snap=1.0e3)
# segments for the reference values of the segment distributions (web/check_core.mjs)
SEG_L = (325.0e3, 330.0e3)       # Easting range on the default profile 1
SEG_R = (4308.0e3, 4312.0e3)     # Northing range on the default profile 2
TRACK_GAP = 500.0                # m, gap in u that separates two tracks


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_gz(name, arr):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(gzip.compress(np.ascontiguousarray(arr).tobytes(), compresslevel=9, mtime=0))


def to_mm(a):
    """float metres -> int16 millimetres, NaN -> NODATA."""
    out = np.full(a.shape, NODATA, np.int16)
    ok = np.isfinite(a)
    out[ok] = np.clip(np.rint(a[ok] * 1000.0), -32767, 32767).astype(np.int16)
    return out


def jlist(a, nd=4):
    """numpy array -> JSON list with NaN -> None."""
    a = np.asarray(a, float)
    return [None if not np.isfinite(v) else round(float(v), nd) for v in a.ravel()]


def mapped(run, yy, tag, kind, ens):
    f = f"{kind}{yy}_mapped{tag}{'_ens' if ens else ''}.nc"
    var = "Posterior" if kind == "Post" else "Prior"
    da = xr.open_dataset(os.path.join(D, run, f))[var].isel(date=0).sortby("x").sortby("y")
    return da


# ------------------------------------------------------------------ notebook reference (verbatim logic)
def notebook_reference(ens_g, pri_ens_g, pri_g, aso_g, z_g, ok_g, gx, gy, oc, ens_o, pri_o, obs, r_obs, prods=None):
    """WE_strip_final.ipynb cells 5 and 9 (profile(), LONG / IC2P profiles, the two points).

    prods: {id: grid (m)} of the gridded products; their profile values use the same cells as ASO.
    """
    prods = prods or {}

    def profile(rows, cols_of_row):
        out = {k: [] for k in ("z", "aso", "mean", "prior", "lo", "hi", "memb", "plo", "phi", "pmemb")}
        out.update({f"prod_{p}": [] for p in prods})
        for r, cs in zip(rows, cols_of_row):
            rr, cc = np.meshgrid(np.atleast_1d(r), np.atleast_1d(cs), indexing="ij")
            m = ok_g[rr, cc]
            if m.sum() < MIN_CELLS:
                for k in out:
                    out[k].append(np.full(ens_g.shape[0], np.nan) if k in ("memb", "pmemb") else np.nan)
                continue
            rr, cc = rr[m], cc[m]
            for pid, pg in prods.items():
                out[f"prod_{pid}"].append(pg[rr, cc].mean())
            e = ens_g[:, rr, cc]
            lo, hi = np.percentile(e, Q, axis=0)
            out["z"].append(z_g[rr, cc].mean()); out["aso"].append(aso_g[rr, cc].mean())
            out["prior"].append(pri_g[rr, cc].mean()); out["mean"].append(e.mean())
            out["lo"].append(lo.mean()); out["hi"].append(hi.mean())
            out["memb"].append((e - aso_g[rr, cc]).mean(1))
            pe = pri_ens_g[:, rr, cc]
            plo, phi = np.percentile(pe, Q, axis=0)
            out["plo"].append(plo.mean()); out["phi"].append(phi.mean())
            out["pmemb"].append((pe - aso_g[rr, cc]).mean(1))
        return {k: np.array(v) for k, v in out.items()}

    rs = np.flatnonzero((gy >= LONG["n_min"]) & (gy <= LONG["n_max"]))
    cs = np.flatnonzero((gx >= -np.inf) & (gx <= np.inf))
    PL = profile([rs] * len(cs), [[c] for c in cs])
    sel_L = ((oc.y >= LONG["n_min"]) & (oc.y <= LONG["n_max"]) & oc.aso.notna()).to_numpy()

    trk = ((oc.x >= IC2P["track_e"][0]) & (oc.x <= IC2P["track_e"][1])).to_numpy()
    pfit = np.polyfit(oc.y[trk], oc.x[trk], 1)
    rp = np.flatnonzero((gy >= IC2P["p0"]) & (gy <= IC2P["p1"]))
    PR = profile([[r] for r in rp],
                 [np.flatnonzero(np.abs(gx - np.polyval(pfit, gy[r])) <= IC2P["half_width"]) for r in rp])
    sel_R = trk & ((oc.y >= IC2P["p0"]) & (oc.y <= IC2P["p1"]) & oc.aso.notna()).to_numpy()

    # points of the last cell
    cand = np.flatnonzero(sel_R)
    i_ic2 = int(cand[np.argmin(np.abs(oc.y.to_numpy()[cand] - PT_IC2["n"]))])
    with np.errstate(all="ignore"):
        zcol = np.nanmean(np.where(ok_g[rs], z_g[rs], np.nan), axis=0)
    win = np.flatnonzero(np.abs(gx - PT_FIELD["e"]) <= PT_FIELD["snap"])
    c_f = int(win[np.nanargmax(zcol[win])])
    r_f = rs[ok_g[rs, c_f]]
    post_f = ens_g[:, r_f, c_f].mean(1)
    pri_f = pri_ens_g[:, r_f, c_f].mean(1)

    def scores(cells_rc):
        """Bias, RMSE and CRPS (properscoring) over the profile cells with model and ASO."""
        rr, cc = cells_rc
        m = ok_g[rr, cc]
        rr, cc = rr[m], cc[m]
        a = aso_g[rr, cc]
        out = {"n": int(len(rr))}
        for lab, ens in (("Post", ens_g), ("Prior", pri_ens_g)):
            e = ens[:, rr, cc]
            out["bias" + lab] = float((e.mean(0) - a).mean())
            out["rmse" + lab] = float(np.sqrt(((e.mean(0) - a) ** 2).mean()))
            out["crps" + lab] = float(ps.crps_ensemble(a, e.T).mean())
        return out

    def kde_ref(v, grid):
        k = gaussian_kde(v, bw_method="scott")
        return jlist(np.where(grid >= 0, k(grid) + k(-grid), 0.0), 6)

    rr_L = np.repeat(rs, len(cs)); cc_L = np.tile(cs, len(rs))
    rr_R = np.concatenate([[r] * len(np.flatnonzero(np.abs(gx - np.polyval(pfit, gy[r])) <= IC2P["half_width"]))
                           for r in rp]).astype(int)
    cc_R = np.concatenate([np.flatnonzero(np.abs(gx - np.polyval(pfit, gy[r])) <= IC2P["half_width"])
                           for r in rp]).astype(int)
    kgrid = np.linspace(-0.05, 4.0, 9)

    # segments: per-member means over the profile-1 cells with E in SEG_L (cells with model and ASO)
    # and over the profile-2 IC2 cells with N in SEG_R
    cs_s = cs[(gx[cs] >= SEG_L[0]) & (gx[cs] <= SEG_L[1])]
    rr_s, cc_s = np.repeat(rs, len(cs_s)), np.tile(cs_s, len(rs))
    m_s = ok_g[rr_s, cc_s]
    rr_s, cc_s = rr_s[m_s], cc_s[m_s]
    seg_L = dict(e0=SEG_L[0], e1=SEG_L[1], c0=int(cs_s[0]), c1=int(cs_s[-1]), n=int(len(rr_s)),
                 post=jlist(ens_g[:, rr_s, cc_s].mean(1), 6), prior=jlist(pri_ens_g[:, rr_s, cc_s].mean(1), 6),
                 aso=float(aso_g[rr_s, cc_s].mean()), z=float(z_g[rr_s, cc_s].mean()),
                 prods={p: float(pg[rr_s, cc_s].mean()) for p, pg in prods.items()})
    yo = oc.y.to_numpy()
    i_s = cand[(yo[cand] >= SEG_R[0]) & (yo[cand] <= SEG_R[1])]
    seg_R = dict(n0=SEG_R[0], n1=SEG_R[1], idx=i_s.tolist(), n=int(len(i_s)),
                 post=jlist(ens_o[i_s].mean(0), 6), prior=jlist(pri_o[i_s].mean(0), 6),
                 obs=float(obs[i_s].mean()), r_mean=float(r_obs[i_s].sum() / len(i_s) ** 2),
                 aso=float(oc.aso.to_numpy()[i_s].mean()))

    def pdict(P):
        return {k: (jlist(v) if v.ndim == 1 else [jlist(row) for row in v]) for k, v in P.items()}

    return dict(
        PL=pdict(PL), PR=pdict(PR), xl=jlist(gx[cs], 1), yl=jlist(gy[rp], 1),
        pfit=[float(p) for p in pfit], sel_L=np.flatnonzero(sel_L).tolist(), sel_R=cand.tolist(),
        rows_L=rs.tolist(),
        ic2=dict(i=i_ic2, post=jlist(ens_o[i_ic2]), prior=jlist(pri_o[i_ic2]), obs=float(obs[i_ic2]),
                 r=float(r_obs[i_ic2]), aso=float(oc.aso[i_ic2]),
                 post_ms=[float(ens_o[i_ic2].mean()), float(ens_o[i_ic2].std())],
                 prior_ms=[float(pri_o[i_ic2].mean()), float(pri_o[i_ic2].std())]),
        field=dict(col=c_f, x=float(gx[c_f]), rows=r_f.tolist(), post=jlist(post_f), prior=jlist(pri_f),
                   aso=float(aso_g[r_f, c_f].mean()), z=float(z_g[r_f, c_f].mean()),
                   post_ms=[float(post_f.mean()), float(post_f.std())],
                   prior_ms=[float(pri_f.mean()), float(pri_f.std())]),
        scores=dict(L=scores((rr_L, cc_L)), R=scores((rr_R, cc_R))),
        kde=dict(grid=jlist(kgrid, 4), field_post=kde_ref(post_f, kgrid), ic2_post=kde_ref(ens_o[i_ic2], kgrid)),
        crps_ic2=float(ps.crps_ensemble(float(oc.aso[i_ic2]), ens_o[i_ic2])),
        seg=dict(L=seg_L, R=seg_R),
        note="full precision members; prior = mapped prior mean file")


# ------------------------------------------------------------------ IC2 tracks
def ic2_tracks(x, y, pfit, sel):
    """Group the IC2 cells into tracks (see IC2 TRACKS above).

    x, y: cell coordinates (m); pfit: the notebook's fit of the paper track; sel: indices of the
    notebook's track cells. Returns the track index of every cell (west to east) and the tracks.
    """
    y_ref = 4311.0e3

    def groups(s):
        u = x - s * (y - y_ref)
        o = np.argsort(u)
        cut = np.flatnonzero(np.diff(u[o]) > TRACK_GAP) + 1
        return u, np.split(o, cut)

    def spread(s):
        u, gs = groups(s)
        return sum(((u[g] - u[g].mean()) ** 2).sum() for g in gs)

    slopes = np.linspace(-0.3, 0.3, 1201)
    s = slopes[int(np.argmin([spread(v) for v in slopes]))]
    u, gs = groups(s)
    gs = sorted(gs, key=lambda g: u[g].mean())
    track = np.empty(len(x), int)
    for k, g in enumerate(gs):
        track[g] = k
    paper = int(np.bincount(track[sel]).argmax())
    assert (track[sel] == paper).all(), "the notebook's track cells fall on more than one track"
    out = []
    for k, g in enumerate(gs):
        a, b = (pfit if k == paper else np.polyfit(y[g], x[g], 1))
        out.append(dict(id=k, label=f"Track {k + 1} (E {(a * y_ref + b) / 1000:.1f} km)", a=float(a), b=float(b),
                        ymin=float(y[g].min()), ymax=float(y[g].max()), n=int(len(g)), paper=k == paper))
    return track, out, float(s)


# ------------------------------------------------------------------ tiles
def tile_cells(mask, r0, c0):
    """Rows and columns of the cells of a tile in storage order (rows S->N, serpentine)."""
    rr, cc = [], []
    for r in range(r0, min(r0 + TILE, mask.shape[0])):
        cs = np.flatnonzero(mask[r, c0:c0 + TILE]) + c0
        if (r - r0) % 2 == 1:
            cs = cs[::-1]
        rr += [r] * len(cs)
        cc += list(cs)
    return np.array(rr, int), np.array(cc, int)


def encode(e):
    """e: [n_mem, n_cell] (m) -> (bytes, decoded values in m, max error in m)."""
    cm = np.rint(e * 100.0).astype(np.int64)
    assert np.abs(cm).max() < 32768, "member value outside the int16 cm range"
    d = np.diff(cm, axis=1, prepend=0)
    assert np.abs(d).max() < 32768, "difference outside the int16 range"
    u = d.astype(np.int16).view(np.uint16)
    lo, hi = (u & 0xFF).astype(np.uint8), (u >> 8).astype(np.uint8)
    dec = cm / 100.0
    return lo.tobytes() + hi.tobytes(), dec, float(np.abs(dec - e).max())


def build_tiles(rid, post, prior, mask):
    """Write <rid>_pack<k>.bin and return the tile index, the pack names and the decoded members."""
    ny, nx = mask.shape
    ntr, ntc = -(-ny // TILE), -(-nx // TILE)
    index, packs, buf, k, err = [None] * (ntr * ntc), [], bytearray(), 0, 0.0
    dec_post = np.full(post.shape, np.nan)
    dec_pri = np.full(prior.shape, np.nan)

    def flush():
        nonlocal buf, k
        if buf:
            name = f"{rid}_pack{k}.bin"
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(bytes(buf))
            packs.append(name)
            buf, k = bytearray(), k + 1

    for tr in range(ntr):
        for tc in range(ntc):
            r0, c0 = tr * TILE, tc * TILE
            if not mask[r0:r0 + TILE, c0:c0 + TILE].any():
                continue
            rr, cc = tile_cells(mask, r0, c0)
            parts = [np.uint32(len(rr)).tobytes()]
            for ens, dec in ((post, dec_post), (prior, dec_pri)):
                e = ens[:, rr, cc]
                assert np.isfinite(e).all(), f"{rid}: non-finite member in tile {tr},{tc}"
                blob, d, mx = encode(e)
                err = max(err, mx)
                dec[:, rr, cc] = d
                parts.append(blob)
            blob = gzip.compress(b"".join(parts), compresslevel=9, mtime=0)
            if len(buf) + len(blob) > PACK_MAX:
                flush()
            index[tr * ntc + tc] = [k, len(buf), len(blob)]
            buf += blob
    flush()
    return index, packs, err, dec_post, dec_pri


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    topo = xr.open_dataset(TOPO)

    # grid from the first run; every run must share it
    g0 = mapped(RUNS[0]["run"], "23", "230401", "Post", ens=False)
    gx, gy = g0.x.values.astype(float), g0.y.values.astype(float)
    ny, nx = len(gy), len(gx)
    log(f"grid {ny} x {nx}, x {gx[0]:.0f}-{gx[-1]:.0f}, y {gy[0]:.0f}-{gy[-1]:.0f}")
    z_g = topo["Zs"].reindex(x=gx, y=gy, method="nearest", tolerance=1).values.astype(float)

    # ASO per year (as WE_strip_final for 2024, figureNP_GPGC.load_ground for 2023)
    g24 = xr.open_dataset(ASO24_TIF, engine="rasterio").rename({"band_data": "snow_depth"})
    g24 = g24.squeeze("band", drop=True)["snow_depth"]
    a = xr.open_dataset(ALLDATA).drop_vars(["Sx200", "Sx100", "sinA", "TPI1000", "DAH", "spatial_ref"],
                                           errors="ignore")
    df = a.to_dataframe().dropna(subset=["Xs"])
    g23 = df.loc[df.index.get_level_values("date") == DATES[2023], "snow_depth"].to_xarray()
    g23 = g23.squeeze("date", drop=True) if "date" in g23.dims else g23
    g23 = g23.sortby("x").sortby("y")             # the data frame round trip leaves x unsorted
    ground = {2023: g23, 2024: g24}
    aso_grid = {2023: g23.reindex(x=gx, y=gy, method="nearest", tolerance=1).values.astype(float),
                2024: g24.interp(x=gx, y=gy).values.astype(float)}

    # gridded snow products on the grid, per year (only the products that cover the survey date)
    rean = xr.open_dataset(REAN) if os.path.exists(REAN) else None
    prod_grid = {}
    for yr, date in DATES.items():
        prod_grid[yr] = {}
        for pid in PRODUCTS:
            v = f"{pid}_sd_{date.replace('-', '')}"
            if rean is not None and v in rean:
                g = rean[v].reindex(x=gx, y=gy, method="nearest", tolerance=1).values.astype(float)
                prod_grid[yr][pid] = g
        log(f"{yr}: products {list(prod_grid[yr])}")

    mask = None
    manifest_runs, years = {}, {}
    for R in RUNS:
        rid, yr, run = R["id"], R["year"], R["run"]
        yy, tag = str(yr)[2:], DATES[yr][2:].replace("-", "")
        log(f"{rid}: loading {run}")
        post = mapped(run, yy, tag, "Post", ens=True)
        assert np.array_equal(post.x.values, gx) and np.array_equal(post.y.values, gy), "grid differs"
        ens_g = post.transpose("en", "y", "x").values.astype(float)
        pri_ens_g = (mapped(run, yy, tag, "Prior", ens=True).transpose("en", "y", "x")
                     .reindex(x=gx, y=gy).values.astype(float))
        pri_g = mapped(run, yy, tag, "Prior", ens=False).transpose("y", "x").reindex(x=gx, y=gy).values
        m = np.isfinite(ens_g).all(0)
        assert np.array_equal(m, np.isfinite(pri_ens_g).all(0)), "prior / posterior masks differ"
        assert np.array_equal(m, np.isfinite(ens_g[0])), "partly missing members"
        if mask is None:
            mask = m
            write_gz("mask.bin.gz", mask.astype(np.uint8))
            write_gz("z.bin.gz", np.where(np.isfinite(z_g), z_g, np.nan).astype(np.float32))
            log(f"valid cells {int(mask.sum())}")
        assert np.array_equal(mask, m), f"{rid}: mask differs from the first run"

        # map summary
        summ = np.stack([pri_ens_g.mean(0), pri_ens_g.std(0), ens_g.mean(0), ens_g.std(0)])
        write_gz(f"{rid}_summary.bin.gz", to_mm(summ))

        # tiles
        index, packs, qerr, dec_post, dec_pri = build_tiles(rid, ens_g, pri_ens_g, mask)
        log(f"{rid}: {len(packs)} packs, {sum(i is not None for i in index)} tiles, max rounding error "
            f"{qerr * 1000:.2f} mm")

        # IC2 cells
        pts = pd.read_csv(os.path.join(SCRATCH, f"DATA_NP/points/IC2NP_{yy}.csv"))
        xs, ys = xr.DataArray(pts.x.to_numpy(), dims="p"), xr.DataArray(pts.y.to_numpy(), dims="p")
        oc = pd.DataFrame({"x": pts.x.to_numpy(), "y": pts.y.to_numpy(),
                           "z": topo["Zs"].sel(x=xs, y=ys, method="nearest").to_numpy(),
                           "aso": ground[yr].interp(x=xs, y=ys).to_numpy()})
        snd = lambda f: (xr.open_dataset(os.path.join(D, run, f))["snd"].sel(x=1, t=DATES[yr])  # noqa: E731
                         .sel(y=slice(0, 399)).transpose("y", "en").values.astype(float) / 1000.0)
        ens_o, pri_o = snd(f"En_snd{yy}.nc"), snd(f"En_snd{yy}_Pr.nc")
        assert ens_o.shape[0] == len(oc) and np.isfinite(ens_o).all() and np.isfinite(pri_o).all()
        obs_ds = xr.open_dataset(os.path.join(SCRATCH, f"DATA_NP/Obs{yy}_var", f"IC2_{DATES[yr][2:]}_var.nc"))
        obs_ds = obs_ds.isel(time=0, x=1)
        obs = obs_ds["snow_depth"].values[:len(oc)].astype(float)
        r_obs = obs_ds["sd"].values[:len(oc)].astype(float)
        ic2 = dict(x=oc.x.round(1).tolist(), y=oc.y.round(1).tolist(), z=jlist(oc.z, 1),
                   aso=jlist(oc.aso, 4), obs=jlist(obs, 4), r=jlist(r_obs, 4),
                   post=np.rint(ens_o * 1000).astype(int).tolist(), prior=np.rint(pri_o * 1000).astype(int).tolist())
        with open(os.path.join(OUT, f"{rid}_ic2.json"), "w") as f:
            json.dump(ic2, f, separators=(",", ":"))

        # notebook reference at the default settings, full precision and from the rounded members
        aso_g = aso_grid[yr]
        ok_g = np.isfinite(aso_g) & mask
        ref = notebook_reference(ens_g, pri_ens_g, pri_g, aso_g, z_g, ok_g, gx, gy, oc, ens_o, pri_o, obs, r_obs,
                                 prods=prod_grid[yr])
        refq = notebook_reference(dec_post, dec_pri, dec_pri.mean(0), aso_g, z_g, ok_g, gx, gy, oc, ens_o,
                                  pri_o, obs, r_obs)
        for P in ("PL", "PR"):
            for k in ("mean", "prior", "lo", "hi", "plo", "phi", "memb", "pmemb"):
                d = np.nanmax(np.abs(np.array(ref[P][k], float) - np.array(refq[P][k], float)))
                log(f"{rid}: {P}.{k} max |rounded - full| = {d * 1000:.3f} mm")
        with open(os.path.join(OUT, f"reference_{rid}.json"), "w") as f:
            json.dump(ref, f, separators=(",", ":"))
        f_, i_ = ref["field"], ref["ic2"]
        log(f"{rid}: IC2 cell #{i_['i']}: prior {i_['prior_ms'][0]:.2f}±{i_['prior_ms'][1]:.2f}, post "
            f"{i_['post_ms'][0]:.2f}±{i_['post_ms'][1]:.2f}, obs {i_['obs']:.2f} (σ {np.sqrt(i_['r']):.2f}), "
            f"ASO {i_['aso']:.2f} m; field E {f_['x']:.0f} m: prior {f_['prior_ms'][0]:.2f}±{f_['prior_ms'][1]:.2f}, "
            f"post {f_['post_ms'][0]:.2f}±{f_['post_ms'][1]:.2f}, ASO {f_['aso']:.2f} m; "
            f"{len(ref['sel_L'])} / {len(ref['sel_R'])} IC2 cells in the profiles")

        # default profile 2 of this year: the notebook's fitted track line; IC2 capture distance that
        # selects exactly the notebook's cells
        pfit = np.array(ref["pfit"])
        p0, p1 = IC2P["p0"], IC2P["p1"]
        res = np.abs(oc.x.to_numpy() - np.polyval(pfit, oc.y.to_numpy()))
        inside = (oc.y >= p0).to_numpy() & (oc.y <= p1).to_numpy() & oc.aso.notna().to_numpy()
        sel = np.array(ref["sel_R"], int)
        cap = float(np.ceil((res[sel].max() + 1.0) / 10.0) * 10.0)
        extra = np.flatnonzero(inside & (res <= cap) & ~np.isin(np.arange(len(oc)), sel))
        log(f"{rid}: profile-2 capture {cap:.0f} m, {len(sel)} track cells, {len(extra)} other cells within it")
        if yr not in years:
            trk_of, tracks, slope = ic2_tracks(oc.x.to_numpy(), oc.y.to_numpy(), pfit, sel)
            log(f"{yr}: IC2 tracks (common slope dx/dy {slope:.4f}): " +
                ", ".join(f"{t['label']} {t['n']} cells N {t['ymin'] / 1e3:.1f}-{t['ymax'] / 1e3:.1f} km"
                          + (" [paper]" if t["paper"] else "") for t in tracks))
            paper_track = next(t["id"] for t in tracks if t["paper"])
            years[yr] = dict(date=DATES[yr], aso=f"aso{yy}.bin.gz", runs=[], tracks=tracks,
                             ic2_track=trk_of.tolist(), defaults=dict(
                p1=dict(row0=int(ref["rows_L"][0]), nrows=len(ref["rows_L"]), e0=None, e1=None, k=LONG["k"],
                        bias=list(LONG["bias_ylim"])),
                p2=dict(track=paper_track, x0=float(np.polyval(pfit, p0)), y0=p0, x1=float(np.polyval(pfit, p1)),
                        y1=p1, hw=IC2P["half_width"], k=IC2P["k"], bias="sym", bias_fac=IC2P["bias_fac"], cap=cap),
                field=dict(e=PT_FIELD["e"], snap=PT_FIELD["snap"]), ic2=dict(i=i_["i"], n=PT_IC2["n"]),
                q=list(Q), min_cells=MIN_CELLS))
            write_gz(f"aso{yy}.bin.gz", to_mm(aso_g))
            plist = []
            for pid, pg in prod_grid[yr].items():
                name = f"rean_{pid}{yy}.bin.gz"
                write_gz(name, to_mm(np.where(mask, pg, np.nan)))
                plist.append(dict(id=pid, file=name, **PRODUCTS[pid]))
            years[yr]["products"] = plist
        years[yr]["runs"].append(rid)
        manifest_runs[rid] = dict(year=yr, exp=R["exp"], label=LABEL[R["exp"]], run=run, color=COLOR[R["exp"]],
                                  summary=f"{rid}_summary.bin.gz", ic2=f"{rid}_ic2.json", packs=packs,
                                  tiles=index, n_mem=int(ens_g.shape[0]), max_quant_error_m=round(qerr, 5))
        del ens_g, pri_ens_g, dec_post, dec_pri

    # sub-basin boundaries
    b = gpd.read_file(BASINS).boundary.simplify(25)
    feats = []
    for geom in b:
        lines = getattr(geom, "geoms", [geom])
        feats.append(dict(type="Feature", properties={}, geometry=dict(
            type="MultiLineString", coordinates=[[[round(x), round(y)] for x, y in ln.coords] for ln in lines])))
    with open(os.path.join(OUT, "basins.geojson"), "w") as f:
        json.dump(dict(type="FeatureCollection", features=feats), f, separators=(",", ":"))

    manifest = dict(
        title="West-East strip and ICESat-2 profiles, East River (CO)", created=time.strftime("%Y-%m-%d"),
        tile_format=2, tile_unit_m=0.01,
        grid=dict(nx=nx, ny=ny, x=[round(float(v), 1) for v in gx], y=[round(float(v), 1) for v in gy],
                  dx=50, tile=TILE, ntr=-(-ny // TILE), ntc=-(-nx // TILE), crs="EPSG:32613"),
        files=dict(mask="mask.bin.gz", z="z.bin.gz", basins="basins.geojson"),
        nodata_i16=NODATA, years={str(k): v for k, v in years.items()}, runs=manifest_runs,
        colors=dict(COLOR, prior="#8c8c8c", aso="#0b0b0b", ic2="#d62728", terrain="#8c5a2b"))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, separators=(",", ":"))
    tot = sum(os.path.getsize(os.path.join(OUT, n)) for n in os.listdir(OUT))
    log(f"done: {len(os.listdir(OUT))} files, {tot / 1e6:.1f} MB in {OUT}")


if __name__ == "__main__":
    main()
