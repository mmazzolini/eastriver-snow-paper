# 07 — Data record (Zenodo)

Builds and uploads the data record that goes with the paper: the input data that are not available
elsewhere (DEM, point files, the 50 m predictor grid of the GP model), the outputs of the four
experiments and the data files of the website in `docs/`. The record's own description is
`RECORD_README.md` (copied into the record as `documentation/README.md`).

Published record: https://doi.org/10.5281/zenodo.23894419

## Steps

1. Stage the record as a folder tree and pack it for Zenodo (compute node, ~1 h):
   ```bash
   sbatch 07_data_record/sbatch_stage_outputs.sh
   ```
   `stage_outputs.py` writes the tree to `/global/scratch/users/marcomaz/zenodo_outputs/`
   (`input_data/`, `DA_experiments/<yy>_<GPE|GCE>/{prior,posterior}/`, `website_data/`,
   `documentation/` with `md5sums.txt`) and the files with ASO values to
   `/global/scratch/users/marcomaz/zenodo_hold/`. The mapped ensembles and the predictors are rewritten
   with lossless compression and checked value by value against the source files; the other files are
   copied and checked with md5. Zenodo records have no folders, so `pack_record.py` then writes
   `/global/scratch/users/marcomaz/zenodo_upload/`: `README.md`, `md5sums.txt` and one zip per folder
   (`input_data.zip`, `DA_experiments_<yy>_<G*E>.zip`, `website_data.zip`), each read back and checked.
2. Check `zenodo_metadata.json` (title, authors, affiliations, the code repository URL; the paper DOI is
   added to the published record later, by editing its metadata).
3. Upload to a draft and review it on zenodo.org (the script never publishes):
   ```bash
   export ZENODO_TOKEN=...                       # personal token with deposit:write and deposit:actions
   sbatch 07_data_record/sbatch_upload_zenodo.sh --dry-run    # lists the files
   sbatch 07_data_record/sbatch_upload_zenodo.sh              # or --deposition <id> for an existing draft
   ```
   The job log (`web_logs/slurm-upload_zenodo-<job>.out`) gives the draft's address.
4. Publish the record on zenodo.org. GMD requires the record to be public when the paper is submitted.
   The website does not read from it: it is served by GitHub Pages with its data from a private
   repository (see `web/README.md`). The record's `website_data/` (without ASO and without the
   third-party gridded products) lets anyone run the page locally.

## ASO snow depth

ASO snow depth is not redistributed, so the files that contain it stay in `zenodo_hold/` and are never
uploaded: `aso_50m.nc` (the grids used in the paper: GP training on 2022-04-21, evaluation on 2023-04-01
and 2024-04-03) and, in `website_data/`, the website's ASO grids (`aso23.bin.gz`, `aso24.bin.gz`), its
IC2-cell files with their ASO values and its full manifest. The record gets the IC2-cell files with the
ASO values removed and a manifest that marks ASO as absent. Without ASO the website shows the model
profiles and distributions, but no ASO line, no comparison panels and no scores.

`predictors_50m.nc` holds no ASO values: the terrain predictors (elevation, slope, aspect, TPI) are
derived from DEM data, and `GSAfrac` comes from the USGS Landsat snow covered area products.
