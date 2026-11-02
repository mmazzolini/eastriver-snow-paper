# web — data and checks of the interactive figure

The page in [`docs/`](../docs/) is an interactive version of the paper figure with the West–East
(Longitudinal) profile and the ICESat-2 profile: terrain with snow depth drawn on it, the bias against
ASO, the ensemble distributions at a point or over a segment of each profile, and the map. Readers
choose the water year, the experiments (GPE, GCE or both; the map shows the one selected first), the
bands, the prior and three gridded snow products; they drag the longitudinal profile on the map and
slide the ICESat-2 profile along one of the three IC2 tracks of the year.

## Files

| File | What it does |
|---|---|
| `build_web_data.py`, `sbatch_build_web.sh` | Builds the data files of the page from the mapped ensembles, plus the IC2 tracks, the gridded products and the reference values of the notebook figure at the default settings (see the docstring for the formats) |
| `get_reanalyses.py`, `sbatch_get_reanalyses.sh` | Downloads UA 800 m, SNODAS and WLDAS for the two survey dates and puts them on the 50 m grid (each 50 m cell takes the value of the product cell around it; nothing is interpolated). WLDAS needs a NASA Earthdata token in `~/.edl_token` |
| `check_core.mjs`, `sbatch_check_core.sh` | Runs `docs/js/core.js` in Node.js on the built files and compares it with the reference |
| `site/` | Template of the public site repository: README, LICENSE and the GitHub Pages workflow |
| `export_site.sh`, `export_site_data.sh` | Copy the page into the site repository and the data files into the private data repository |

## Hosting

The site is published on GitHub Pages from a public repository that holds only the page
(`eastriver-snow-viewer`). Its workflow (`site/.github/workflows/pages.yml`) copies the data files from
a private repository (`eastriver-snow-viewer-data`, read with a read-only deploy key) into the
published site. The ASO files are only there: ASO snow depth is shown for visualisation and is not
redistributed (not in Zenodo, not in a public repository). GitHub Pages answers HTTP range requests,
so the page reads only the tiles it needs.

Every ensemble member is stored to the centimetre: 64 × 64-cell tiles, member-major, as differences
between neighbouring cells, gzip per tile, in pack files of at most 14.5 MB; about 56 MB per experiment
and year, 240 MB in total.

## Checks (2026-10-15)

- **Rebuilds:** apart from the manifest and the check references, every file of each new build is
  byte-identical to the previous one; the new files are the gridded products (UA 800 m and SNODAS for
  both dates, WLDAS for 2023).
- **IC2 tracks:** three per year (2023: 175 / 152 / 73 cells; 2024: 174 / 155 / 71). The paper's
  profile lies on track 2, whose line is the notebook's fit, so the default profile 2 is the paper's
  (end points identical).
- **Node check** (`check_core.mjs`, 265 checks, all passed), for the four experiments, with and without
  range requests: profile steps, cells and IC2 cells, every profile value, the field and IC2 points,
  scores, KDEs, profile 2 on its track, the products along both profiles, and one segment per
  profile (per-member means within 0.9 mm of full precision for profile 1, exact for the IC2 cells);
  the products within 0.5 mm (stored to the millimetre).
- **Paper numbers:** the default 2024 GPE view reproduces the figure: IC2 cell 92 prior 0.86 ± 0.99,
  posterior 1.35 ± 0.23, observation 1.23 m (σ 0.37), ASO 1.27 m; field cell E 327.19 km prior
  1.59 ± 1.54 (1.60 with the centimetre storage), posterior 1.51 ± 0.74, ASO 1.46 m.
- **Rounding:** at most 5.0 mm per member and on any profile value of the default views.
- **Browser** (headless Chromium, desktop light and dark, 1920 px, phone): no console errors, no
  horizontal overflow; scripted checks of the map following the experiment selected first, the track
  switch, dragging profile 2 along its track, segments in b) and e), their restoration from a shared
  link, Esc, the year dropdown, the product map layers, the map staying inside its box (pan limits),
  the + / − zoom buttons and Reset all.

## Running locally

```bash
sbatch web/sbatch_get_reanalyses.sh             # gridded products (optional)
sbatch web/sbatch_build_web.sh                  # data files into /global/scratch/users/marcomaz/web_data
sbatch web/sbatch_check_core.sh                 # checks
ln -s /global/scratch/users/marcomaz/web_data docs/data   # then serve docs/ (python -m http.server)
```

Without the private data, the Zenodo record's `website_data/` folder (link it as `docs/data`) runs the
page without ASO and without the gridded products.
