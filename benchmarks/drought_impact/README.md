# Drought-Impact Prediction Benchmark — v0 (corn, 6-state Corn Belt)

A prediction-ready benchmark whose target is **insured drought loss** (USDA RMA
Cause-of-Loss indemnity), not drought *severity* (USDM category) or *yield*. It asks a
question the field currently has no benchmark for: **from signal available by mid-season,
how large will this county's realized drought loss be?**

This is a self-contained, spin-out-ready sub-package of AgroTerraFlow: it has its own
`pyproject.toml` and no dependency on the parent `terraflow` package.

## Tasks

| Task | Target | Metrics |
|------|--------|---------|
| Regression | `drought_loss_cost` = drought indemnity / county liability | R², RMSE, Spearman ρ |
| Classification | `significant_loss` (loss-cost above threshold) | ROC-AUC, PR-AUC, Brier |

Unit of observation: **(`GEOID`, corn crop-year)**, annual. Scope: corn, 6-state Corn
Belt (IL/IN/IA/MN/MO/NE), 2000–2023.

## Data sources

| Role | Source | Notes |
|------|--------|-------|
| **Label** | USDA RMA Cause of Loss (COL, "Summary of Business with Month of Loss") | Public, free, county-level, 1989–2026; `Cause of Loss Description == "Drought"` |
| **Predictors** | flashdry `feature_table.parquet` | Weekly deseasonalized `_anom` features + NDVI, county-FIPS aligned, consumed as input |
| **Coverage** | NASS planted acres | For the `insured_acre_fraction` limitation column |
| **Severity baselines** | USDM D2+, VCI/TCI/VHI, flashdry WxCond detector | Probe *severity ≠ impact* |

All source locations are config values (`configs/v0_corn_6state.yaml`) — nothing is
hardcoded, so the pipeline runs on synthetic fixtures in CI and on the real
flashdry/RMA data locally.

## Quickstart

```bash
pip install -e benchmarks/drought_impact

# 1. Fetch RMA archives (needs network egress to rma.usda.gov)
python scripts/01_fetch_rma.py --config configs/v0_corn_6state.yaml
# 2. Assemble benchmark.parquet + manifest.json (needs flashdry feature_table_path set)
python scripts/02_assemble.py --config configs/v0_corn_6state.yaml
# 3. Write splits.json (temporal / spatial-block / LOYO)
python scripts/03_splits.py --config configs/v0_corn_6state.yaml
# 4. Fit baselines → leaderboard.csv
python scripts/04_run_baselines.py --config configs/v0_corn_6state.yaml
```

Run the tests (synthetic fixtures, no network / flashdry needed):

```bash
pytest benchmarks/drought_impact/tests -v
```

## `benchmark.parquet` schema

`GEOID`, `year`, `drought_loss_cost` (target), `significant_loss` (target),
`drought_indemnity`, `county_liability`, `total_premium_sum`, `total_indemnity`,
`insured_acres`, `planted_acres`, `insured_acre_fraction`, then the aggregated predictor
columns `{feature}_{mean,min,max,last,nstress}` for each flashdry `_anom` feature.

## Leaderboard

> **Pending real run.** The numbers below are filled by running the pipeline against the
> real RMA + flashdry data locally (the CI environment has neither network access to RMA
> nor the flashdry data). The synthetic-fixture end-to-end test proves the wiring.

| Baseline | Task | R² / ROC-AUC | RMSE / PR-AUC | Spearman / Brier |
|----------|------|-------------|---------------|------------------|
| naive_climatology | regression | _pending_ | _pending_ | _pending_ |
| naive_county | regression | _pending_ | _pending_ | _pending_ |
| index_wxcond_prob | regression | _pending_ | _pending_ | _pending_ |
| ridge / random_forest / gradient_boosting | regression | _pending_ | _pending_ | _pending_ |
| naive_prevalence | classification | _pending_ | _pending_ | _pending_ |
| index_wxcond_prob | classification | _pending_ | _pending_ | _pending_ |
| logistic / random_forest / gradient_boosting | classification | _pending_ | _pending_ | _pending_ |

**Headline hook:** a strong drought *severity* detector (WxCond) should be
informative-but-imperfect on the drought *loss* target — severity ≠ impact.

## Limitations

- **Coverage bias (first-class):** RMA covers *insured* acres only. Ship/consume the
  `insured_acre_fraction` column (RMA insured acres / NASS planted acres) to filter or
  weight county-years. See `datasheet.md`.
- **Denominator:** loss-cost uses indemnity / **liability**, not RMA's field-30 loss
  ratio (indemnity / **premium**); both are documented. Summed liability can over-count
  across causes — treated as an approximation.

See `datasheet.md` for the full Gebru et al. datasheet.
