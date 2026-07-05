# Drought-Impact Prediction Benchmark

A self-contained, spin-out-ready sub-package under `benchmarks/drought_impact/` that
defines a prediction-ready benchmark whose target is **insured drought loss** (USDA RMA
Cause-of-Loss indemnity) — not drought *severity* (USDM category) or *yield*.

!!! note "Relationship to TerraFlow"
    The benchmark is *methodologically separate* from the TerraFlow pipeline: it has its
    own `pyproject.toml` and does **not** import `terraflow`. It reuses one idea from the
    parent project — the deterministic build fingerprint (`terraflow/core/run_identity.py`),
    vendored so the package can spin out cleanly.

## Why a new benchmark

Existing drought benchmarks label *severity* (USDM category — what drought detectors
predict) or *yield* (CY-Bench, SustainBench). None uses insured drought **loss** as the
target. The label source — USDA RMA Cause of Loss — is public, free, county-level,
1989–2026, with drought as a distinct cause. The headline scientific hook: a strong
drought *severity* detector only partially predicts drought *loss* → **severity ≠
impact** → the benchmark measures something the field currently can't.

## Tasks & unit of observation

Unit of observation: **(`GEOID`, corn crop-year)**, annual — matching the RMA grain.

| Task | Target | Metrics |
|------|--------|---------|
| Regression | `drought_loss_cost` = drought indemnity / county liability | R², RMSE, Spearman ρ |
| Classification | `significant_loss` (loss-cost above threshold) | ROC-AUC, PR-AUC, Brier |

v0 scope: corn, 6-state Corn Belt (IL/IN/IA/MN/MO/NE), 2000–2023.

## Pipeline

```
RMA COL zips ──rma.py──▶ tidy frame ──labels.py──▶ loss-cost + binary flag
flashdry feature_table ──predictors.py──▶ aggregated _anom vector @cutoff_doy
                        └─coverage.py──▶ insured_acre_fraction
                                              │
   labels ⋈ predictors ⋈ coverage ──assemble.py──▶ benchmark.parquet + manifest(fingerprint)
                                              ├─splits.py──▶ splits.json (temporal / spatial-block / LOYO)
                                              └─baselines.py + metrics.py──▶ leaderboard
```

Every external location is a config value in `configs/v0_corn_6state.yaml`, so the same
code runs on synthetic fixtures in CI and on the real flashdry/RMA data locally.

## Splits

`splits.json` ships three official evaluation protocols, keyed by `"{GEOID}:{year}"`:

- **Temporal held-out** — train on early years, test on held-out years including the 2012
  extreme and recent 2022/2023. The headline split.
- **Spatial block** — contiguous county blocks (mirrors
  `terraflow/validation.py::_assign_block_ids`) to guard against autocorrelation leakage.
- **Leave-one-year-out** — one fold per year.

## Baselines

Three tiers: **naive** (county historical loss rate, climatology), **index** (USDM D2+,
VCI/TCI/VHI, flashdry WxCond probability — the severity≠impact probes), and **ML** (Ridge,
RandomForest, GradientBoosting on the aggregated `_anom` predictors).

## Reproducibility

Each build writes `manifest.json` with a deterministic `build_fingerprint` over the config
plus SHA-256s of every input file — identical inputs reproduce identical datasets.

## Limitations

- **Coverage bias:** RMA covers *insured* acres only. The `insured_acre_fraction` column
  (RMA insured acres / NASS planted acres) lets users filter or weight county-years.
- **Denominator:** loss-cost = indemnity/liability, not RMA's field-30 indemnity/premium;
  both are documented. See the [datasheet](https://github.com/gmarupilla/AgroTerraFlow/blob/main/benchmarks/drought_impact/datasheet.md).

## Running it

```bash
pip install -e benchmarks/drought_impact
python scripts/01_fetch_rma.py     --config configs/v0_corn_6state.yaml   # needs network
python scripts/02_assemble.py      --config configs/v0_corn_6state.yaml   # needs flashdry paths
python scripts/03_splits.py        --config configs/v0_corn_6state.yaml
python scripts/04_run_baselines.py --config configs/v0_corn_6state.yaml

pytest benchmarks/drought_impact/tests -v   # synthetic fixtures, no network/flashdry
```

See the [demo notebook](../notebooks/08_drought_impact_benchmark.ipynb) for an end-to-end
walk-through on synthetic data.
