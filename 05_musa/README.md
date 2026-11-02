# 05 — MuSA (eastriver-paper)

The experiments ran with MuSA `eastriver-paper`, kept in a fork of MuSA:

- **Code:** https://github.com/mmazzolini/MuSA/tree/eastriver-paper, tag `eastriver-paper-v1`
  (commit `075c336`)
- **Archive:** TODO Zenodo DOI

```bash
git clone --branch eastriver-paper-v1 https://github.com/mmazzolini/MuSA.git
```

It is MuSA (Alonso-González et al., 2022, https://github.com/ealonsogzl/MuSA) as of upstream commit
`e727116` (March 2025, between releases v2.2 and v2.3) with three changes, and the configurations and job
scripts of the four experiments in `eastriver/`:

1. **Prior and forcing constants** (`constants.py`): precipitation mean log error −2.05 and lower bound
   0.1; TopoPyScale precipitation (mm h⁻¹) converted to kg m⁻² s⁻¹; longwave error SD 20 W m⁻².
2. **Task synchronisation for HPC array runs**: atomic writes of the ensemble files and a flag written
   by task 0 after the last iteration; the prior ensembles are kept for post-processing.
3. **Prior correlations given directly** (`corr`, `loc_taper_power`, `loc_min_weight` in `config.py`):
   a cells × cells correlation matrix on the full grid draws the prior maps and localises the update.

| Config (`eastriver/`) | Water year | Prior correlation | MuSA run | Data record |
|---|---|---|---|---|
| `config23_GPpow2NPnbm_var.py` | 2023 | GP | `23GPpow2NPnbm_var` | `DA_experiments/23_GPE/` |
| `config23_GCpow2NP_var.py` | 2023 | Gaspari–Cohn | `23GCpow2NP_var` | `DA_experiments/23_GCE/` |
| `config24_GPpow2NPnb_var.py` | 2024 | GP | `24GPpow2NPnb_var` | `DA_experiments/24_GPE/` |
| `config24_GCpow2NP_var.py` | 2024 | Gaspari–Cohn | `24GCpow2NP_var` | `DA_experiments/24_GCE/` |

The inputs come from `03_ic2_cells_obs_corr` (observations, correlation matrices, mask) and
`04_forcing` (forcing). `eastriver/README.md` of the fork explains how to run an experiment
(`eastriver/run_experiment.sh`), which also calls the post-processing of `06_postprocessing` when
`POSTPROC_DIR` points to it. Environment: `MuSAenv` (`../environments/MuSAenv.yml`).

Licence: GPL-3.0 (MuSA); FSM2, included in MuSA, keeps its MIT licence.
