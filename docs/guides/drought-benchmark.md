# Drought-impact prediction benchmark

`terraflow.drought` assembles and evaluates an **impact-labeled** drought benchmark: predict
**insured drought loss** from within-season climate and vegetation signal. The label is USDA RMA
*Cause of Loss* indemnity attributed to drought — a decision-relevant economic *impact* target,
distinct from drought *severity* (USDM D2+) and crop *yield* benchmarks (CY-Bench, SustainBench).

## Why this benchmark

Existing drought benchmarks predict how *dry* it is (severity) or how much a crop *yields*. Neither
answers the question insurers, agencies, and adaptation planners actually face: **where will drought
translate into realized loss this season?** RMA Cause of Loss is the public, county-level record of
that realized loss, back to 1989 — but it has never been packaged as a prediction-ready ML benchmark.

## Task

- **Unit:** (county `GEOID`, crop-year), corn, 6-state Corn Belt (IL/IN/IA/MN/MO/NE), 2000–2023.
- **Targets:** `drought_loss_ratio` (regression) and `significant_drought_loss` (binary), plus a
  bounded `drought_share` auxiliary.
- **Predictors:** the 30 deseasonalized flashdry `*_anom` climate features + `NDVI_anom_z` + USDM
  severity, aggregated {mean, min, max, last} up to `cutoff_doy` (default ≈ Jul 31) — an
  **early-warning** framing (predict end-of-season loss from mid-season signal).
- **Splits:** temporal (held-out years incl. the 2012 extreme + recent 2022/2023), leave-one-state-out
  spatial, and leave-one-year-out.

## Quickstart

```bash
terraflow drought fetch    --rma-dir data/drought/rma --year-min 2000 --year-max 2023
terraflow drought build    -c examples/drought_v0_corn_6state.yml
terraflow drought evaluate -c examples/drought_v0_corn_6state.yml
```

`build` writes `benchmark.parquet` + `manifest.json` (deterministic build fingerprint) + `splits.json`;
`evaluate` writes `evaluate_report.json` + `leaderboard.csv`.

## Reference results (v0, 587 counties, 13,895 county-years, 18.5% positive)

Temporal split (train ≤ 2015, test = 2012/2017/2022/2023):

| Task | Model | Headline |
|---|---|---|
| Classification | LogReg [climate] | ROC-AUC **0.93**, PR-AUC **0.78** |
| Classification | LogReg [severity] | ROC-AUC 0.92, PR-AUC 0.73 |
| Classification | RandomForest [climate] | ROC-AUC 0.27 (temporal extrapolation collapse) |
| Regression | Ridge [climate] | Spearman **0.65** |
| Spatial LOSO | RandomForest [climate] | mean ROC-AUC **0.91** |

Findings: (1) within-season signal predicts insured drought loss well (AUC ≈ 0.91–0.93);
(2) USDM severity is a *strong* baseline — within-season climate anomalies match/slightly beat it and
are available earlier in the season; (3) **temporal extrapolation to extreme years is the open
challenge** — tree models collapse under distribution shift while linear models hold. That model-class
gap is the benchmark's most interesting result.

## Limitations (datasheet notes)

- RMA Cause of Loss covers **insured acres only**; participation varies by crop/region/year.
- The loss-experience liability denominator can push `drought_loss_ratio` above 1 in catastrophic
  years — prefer rank metrics (Spearman) and the binary target.
- v0 is corn + Corn Belt; soybean, CONUS, and a coverage-bias column are planned follow-ups.

## Provenance & citation

The predictor corpus comes from the separate [flashdry](https://github.com/gmarupilla/flashdry) repo
(cite its Zenodo DOI; not vendored here). See `data/drought/README.md` for upstream sources and
licenses.
