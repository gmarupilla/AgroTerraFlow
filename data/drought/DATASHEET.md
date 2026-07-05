# Datasheet — Drought-Impact Prediction Benchmark (v0)

Following Gebru et al., *Datasheets for Datasets* (2021).

## Motivation

- **Purpose.** Provide a prediction-ready, *impact-labeled* drought benchmark: predict realized
  **insured drought loss** from within-season climate/vegetation signal. Existing drought benchmarks
  target *severity* (USDM D2+) or crop *yield*; none uses drought-attributed insured loss.
- **Who built it.** The TerraFlow authors (see `CITATION.cff`), assembled with `terraflow.drought`.

## Composition

- **Instances.** One row per (county `GEOID`, corn crop-year). v0 = corn, 6-state Corn Belt
  (IL/IN/IA/MN/MO/NE), 2000–2023. **13,895 rows, 587 counties.**
- **Features.** 30 deseasonalized flashdry climate anomalies (`*_anom`) + `NDVI_anom_z` + USDM
  severity (`dm_gte_d2`, `dm_class`), each aggregated {mean, min, max, last} up to `cutoff_doy`
  (default ≈ Jul 31 — early-warning), plus `n_obs` and `n_stress_weeks`.
- **Labels.** `drought_loss_ratio` (regression; drought indemnity / true insured liability),
  `significant_drought_loss` (binary, positive rate **6.0%**), `drought_share` (bounded auxiliary),
  and raw `drought_indemnity` / `total_indemnity` / `total_liability`.
- **Coverage.** `insured_acres`, `total_premium`, `planted_acres`, and `insured_acre_fraction`
  (insured / planted acres; median ≈ 0.45) expose RMA's insured-only coverage bias.
- **Splits** (`splits.json`). Temporal (train ≤ 2015, test = 2012/2017/2022/2023), leave-one-state-out
  spatial, leave-one-year-out.

## Collection process

- **Labels** — USDA RMA *Cause of Loss* Summary-of-Business files (public, pipe-delimited, 1989–present).
  Drought-attributed indemnity (`Cause of Loss Description == "Drought"`) per county-crop-year.
- **Predictors** — the flashdry corpus (MODIS NDVI / ERA5-Land / Daymet / USDM / USDA-NASS), county-
  aggregated. See <https://github.com/gmarupilla/flashdry>.
- **Reproducibility** — `manifest.json` carries a SHA-256 build fingerprint over config + input hashes.

## Recommended uses

Drought-loss classification/regression under temporal and spatial distribution shift. Baseline
leaderboard (`leaderboard.csv`) covers naive, severity-only, and Ridge/RF/GBM climate models.

## Limitations & caveats

- **Insured-acre coverage.** RMA covers *insured* acres only; the `insured_acre_fraction` column
  (insured / NASS planted acres) documents this per county-year so users can filter or weight.
- **Denominator.** `drought_loss_ratio` uses the **true total insured liability** (RMA
  Summary-of-Business), so the loss-experience >1 artifact is essentially removed (4 of 13,895
  rows marginally exceed 1). Rank metrics and the binary target remain robust.
- **Scope.** v0 is corn + Corn Belt; soybean, CONUS, and additional predictors (e.g. GRACE) are future work.

## Distribution & license

- Benchmark table + splits + manifest + leaderboard are released on Zenodo:
  **DOI [10.5281/zenodo.21208651](https://doi.org/10.5281/zenodo.21208651)** (concept DOI — always latest version). Code: MIT (`terraflow`). Upstream data are public/open; cite the flashdry
  corpus and the upstream products.
