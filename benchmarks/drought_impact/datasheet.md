# Datasheet — Drought-Impact Prediction Benchmark (v0)

Following Gebru et al., *Datasheets for Datasets* (2021). This documents the v0 corn,
6-state Corn Belt release.

## Motivation

- **For what purpose was the dataset created?** Existing drought benchmarks label
  *severity* (USDM category) or *yield* (CY-Bench, SustainBench). None targets insured
  drought **loss** (impact attribution). This benchmark fills that gap: predict realized,
  county-level insured drought loss from pre-cutoff climate signal, enabling models to be
  evaluated on impact rather than a severity proxy.
- **Who created it and for whom?** Assembled as a self-contained sub-package of the
  open-source AgroTerraFlow project for the research community (target venues: ESSD,
  Scientific Data, NeurIPS Datasets & Benchmarks).

## Composition

- **What do instances represent?** One instance = a (`GEOID`, corn crop-year) — a US
  county in a given year.
- **How many instances?** v0 scope: corn, 6 states (IL/IN/IA/MN/MO/NE), 2000–2023, ~587
  counties → on the order of 10–14k county-years (exact count set at build time).
- **What data does each instance contain?** The target(s) (`drought_loss_cost`,
  `significant_loss`), provenance/label components (indemnity, liability, premium), the
  coverage-bias column (`insured_acre_fraction`), and aggregated `_anom` climate
  predictors summarized over the growing-season window up to `cutoff_doy`.
- **Is any information missing?** County-years with no RMA liability are absent (not
  insured / not reported). County-years with liability but no drought cause row are
  **present as true negatives** (`drought_loss_cost == 0`), not missing.
- **Are there labels/targets?** Yes — regression (`drought_loss_cost`) and binary
  (`significant_loss`).
- **Recommended splits.** Official `splits.json`: temporal held-out years (incl. the 2012
  extreme + recent 2022/2023), spatial-block CV (contiguous county blocks), and
  leave-one-year-out. Use the temporal split as the headline.

## Collection process

- **Labels** — USDA RMA Cause of Loss ("Summary of Business with Month of Loss"), a
  public, free, 30-field pipe-delimited yearly archive. Filtered to the 6 states + corn;
  drought rows selected by `Cause of Loss Description == "Drought"` (no code-table lookup).
- **Predictors** — flashdry `feature_table.parquet` (weekly deseasonalized `_anom`
  features + NDVI), aggregated per county-year over `[season_start_doy, cutoff_doy]`.
- **Join key** — 5-digit `GEOID` (FIPS state + county), shared across all sources.

## Preprocessing / labeling

- `drought_loss_cost` = Σ drought indemnity / county liability (per GEOID×year).
- `significant_loss` = `drought_loss_cost` above a configured threshold (fixed default, or
  county-historical-baseline mode).
- Predictor aggregation: `{mean, min, max, last, n_stress_weeks}` per `_anom` feature,
  with `n_stress_weeks` = weeks below −1σ.
- **Provenance:** every build writes `manifest.json` with a deterministic
  `build_fingerprint` over the config + input file SHA-256s → reproducible datasets.

## Uses & limitations

- **Coverage bias (primary limitation).** RMA covers *insured* acres only. Loss is not
  observed on uninsured acres. The `insured_acre_fraction` column (RMA insured acres /
  NASS planted acres) lets users filter/weight; county-years below a coverage floor should
  be treated cautiously.
- **Denominator choice.** Loss-cost = indemnity/liability (not RMA's indemnity/premium
  field-30 loss ratio). Summed liability across cause rows can over-count when a
  county-year has multiple loss causes; `total_premium_sum` ships as a cross-check.
- **Not for:** attributing loss to specific farms, real-time operational payout
  decisions, or non-corn / non-Corn-Belt use in v0.

## Distribution & maintenance

- Code + config + datasheet are versioned in the AgroTerraFlow repo under
  `benchmarks/drought_impact/`. Raw RMA archives and built artifacts are not committed
  (regenerable from source); a `build_fingerprint` pins each release.
- Follow-ups: soybean, CONUS expansion, GRACE/TWS predictors, and a TerraFlow baseline
  adapter.
