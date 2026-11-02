# Data record: East River ICESat-2 snow-depth assimilation

Data of the paper *Leveraging probabilistic machine learning to enable large scale assimilation of
ICESat-2 snow depth observations* (Mazzolini, Aalstad, Cowherd, Alonso-González, Girotto and Treichler):
the input data of the experiments that are not available elsewhere, the outputs of the four
data-assimilation (DA) experiments and the data files of the interactive website. Code: see the related
code repository. Licence: CC BY 4.0.

## Structure

```
input_data/
  DEM/srtm_eastriver_clipped.tif
  points/GP_points.csv, IC2NP_23.csv, IC2NP_24.csv
  GP_predictors/predictors_50m.nc
DA_experiments/
  23_GPE/ prior/  En_snd23_Pr.nc, Prior23_mapped230401_ens.nc, Prior23_mapped230401.nc
          posterior/  En_snd23.nc, Post23_mapped230401_ens.nc, Post23_mapped230401.nc
  23_GCE/ (as 23_GPE)
  24_GPE/ prior/  En_snd24_Pr.nc, Prior24_mapped240403_ens.nc, Prior24_mapped240403.nc
          posterior/  En_snd24.nc, Post24_mapped240403_ens.nc, Post24_mapped240403.nc
  24_GCE/ (as 24_GPE)
website_data/
documentation/
  README.md, md5sums.txt
```

On Zenodo each folder is one zip file (`input_data.zip`, `DA_experiments_<yy>_<G*E>.zip`,
`website_data.zip`) that keeps these paths; `README.md` and `md5sums.txt` are plain files. Unzip the
files you need in one folder and check them with `md5sum -c md5sums.txt` (the paths in it start at the
top of the tree).

## DA experiments

| Folder | Water year | Prior correlation | Survey date (ASO) | MuSA run (config in `eastriver/` of MuSA eastriver-paper) |
|---|---|---|---|---|
| `23_GPE` | 2022-10-01 to 2023-09-30 | Gaussian process (GPE) | 2023-04-01 | `23GPpow2NPnbm_var` |
| `23_GCE` | 2022-10-01 to 2023-09-30 | Gaspari–Cohn (GCE) | 2023-04-01 | `23GCpow2NP_var` |
| `24_GPE` | 2023-10-01 to 2024-09-30 | Gaussian process (GPE) | 2024-04-03 | `24GPpow2NPnb_var` |
| `24_GCE` | 2023-10-01 to 2024-09-30 | Gaspari–Cohn (GCE) | 2024-04-03 | `24GCpow2NP_var` |

MuSA with the FSM2 snow model, 100 members, iterative ensemble smoother (4 iterations), ICESat-2 (IC2)
snow depth at 400 cells assimilated on the survey date and spread to 5400 model cells. The file names are
those written by the post-processing of the code repository (`06_postprocessing`).

| File (in `prior/` and `posterior/`) | Content |
|---|---|
| `En_snd<yy>.nc` (posterior), `En_snd<yy>_Pr.nc` (prior) | snow depth `snd` (mm, int64, fill −9999), dims `y` (5400) × `x` (2) × `t` (daily) × `en` (100). `x = 0`: the 5400 model cells; `x = 1`: the IC2 cells in `y = 0…399` |
| `Post<yy>_mapped<yymmdd>_ens.nc`, `Prior<yy>_mapped<yymmdd>_ens.nc` | the members mapped to the 50 m grid on the survey date (`Posterior` / `Prior`, m; dims `en`, `y`, `x`, `date`; the `date` coordinate is a placeholder carried over from the predictor set) |
| `Post<yy>_mapped<yymmdd>.nc`, `Prior<yy>_mapped<yymmdd>.nc` | ensemble mean of the above |

## Input data

| File | Content |
|---|---|
| `DEM/srtm_eastriver_clipped.tif` | the SRTM elevation model used by TopoPyScale for the downscaling (clipped to the basin) |
| `points/GP_points.csv` | the 5400 model cells, in the order of the `y` dimension above (the point file of the TopoPyScale downscaling). Columns: index, x, y (m, EPSG:32613), name, lat, lon |
| `points/IC2NP_23.csv`, `points/IC2NP_24.csv` | the 400 IC2 cells of each water year, in the order of the IC2 cells above (same columns) |
| `GP_predictors/predictors_50m.nc` | the 7 GP predictors on the 50 m grid (EPSG:32613): `Ys`, `GSAfrac`, `Xs`, `Zs`, `slope`, `cosA`, `TPI150` (the order used by the GP). `Xs`, `Ys`: distances (m) from the grid origin; `Zs`: elevation (m), `slope`, `cosA`: cosine of the aspect and `TPI150`: topographic position index (150 m), derived from DEM data; `GSAfrac`: annual ground snow-covered area fraction from the USGS Landsat snow covered area products (Selkowitz et al. 2017) |

The point files and the DEM go into `inputs/dem/` of the TopoPyScale projects (`01_era5_downscaling` of
the code repository). The code that selects the points is in `02_gp_model_points` and
`03_ic2_cells_obs_corr`. The other inputs (ERA5, ICESat-2 ATL03) are public and are downloaded by the
code.

## Website data

The data files of the interactive website (manifest, terrain, map summaries, IC2 cells and ensemble tiles;
format described in `web/build_web_data.py` of the code repository). Members are stored to the
centimetre. Link the folder as `docs/data` of the code repository and serve `docs/` to run the page.

## Not included

ASO lidar snow depth (Airborne Snow Observatories, Inc.), used to train the GP and to evaluate the
experiments, cannot be redistributed; it is available from ASO, Inc. The website files therefore hold no
ASO values (the page then shows no ASO line and no scores), and no third-party gridded snow products.

## Coordinates

UTM zone 13N (EPSG:32613), cell centres in metres. The mapped files and the predictors were rewritten
with lossless zlib compression; their values are identical to the files used in the paper. The `En_snd`
files are unchanged copies.
