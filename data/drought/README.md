# Drought-impact benchmark — data provenance

This directory holds inputs for the `terraflow.drought` benchmark. **No large data is committed** —
files land here at build time (the directory is git-ignored except this README).

## Label — USDA RMA Cause of Loss (public, free)

- Source: <https://www.rma.usda.gov/tools-reports/summary-of-business/cause-loss>
- Pipe-delimited flat files, one ZIP per commodity year, 1989–present (30-field record layout).
- Fetched by `terraflow drought fetch --rma-dir data/drought/rma` into `rma/colsom_YYYY.zip`.
- The impact label is drought-attributed insured indemnity per county-crop-year
  (`Cause of Loss Description == "Drought"`), normalized by loss-experience liability.
- **Known limitation:** Cause of Loss covers *insured* acres only; participation varies by
  crop/region/year, and the loss-experience liability denominator can push `drought_loss_ratio`
  above 1 in catastrophic county-years. Rank metrics + the binary target are the robust headlines.

## Predictors — flashdry corpus (separate repo, cite; do not vendor)

- Repo: <https://github.com/gmarupilla/flashdry> (own Zenodo DOI / `CITATION.cff`).
- `feature_table.parquet` — county × growing-season climate/vegetation anomalies + USDM severity,
  6-state Corn Belt, 2000–2023, keyed on 5-digit `GEOID`. Point `feature_table:` in the config at it.
- Upstream sources (all public): MODIS NDVI (NASA LP DAAC), ERA5-Land (Copernicus CDS), Daymet
  (ORNL), USDM (droughtmonitor.unl.edu), USDA-NASS QuickStats.

## Reproducibility

Every `terraflow drought build` writes `manifest.json` with a SHA-256 build fingerprint over the
config + input file hashes, so identical inputs reproduce a byte-identical benchmark table.
