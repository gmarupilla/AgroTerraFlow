# Drought-impact prediction benchmark

`terraflow.drought` assembles and evaluates an **impact-labeled** drought benchmark: predict
**insured drought loss** from within-season climate and vegetation signal. The label is USDA RMA
*Cause of Loss* indemnity attributed to drought — a decision-relevant economic *impact* target,
distinct from drought *severity* (USDM D2+) and crop *yield* benchmarks (CY-Bench, SustainBench).

**Dataset:** Zenodo DOI [10.5281/zenodo.21208651](https://doi.org/10.5281/zenodo.21208651) (CC-BY-4.0).

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

## Reference results (v0.2, 587 counties, 13,895 county-years, 6.0% positive)

Temporal split (train ≤ 2015, test = 2012/2017/2022/2023):

| Task | Model | Headline |
|---|---|---|
| Classification | GradientBoost [climate] | ROC-AUC **0.95**, PR-AUC **0.66** |
| Classification | LogReg [severity] | ROC-AUC 0.93, PR-AUC 0.62 |
| Classification | RandomForest [climate] | ROC-AUC 0.56 (temporal-extrapolation collapse) |
| Spatial LOSO | GradientBoost [climate] | mean ROC-AUC **0.91** |

Findings: (1) within-season signal predicts realised insured drought loss well (best temporal
ROC-AUC ≈ 0.95; spatial ≈ 0.91); (2) USDM severity is a *strong* baseline that within-season climate
models match/beat while arriving earlier in the season; (3) **model choice matters sharply under
temporal extrapolation** — a random forest collapses to near-chance (≈0.56) on held-out extreme
years while gradient-boosting and linear models stay strong (0.80–0.95). The positive class is rare
(6%), so PR-AUC is the honest headline.

## Limitations (datasheet notes)

- RMA Cause of Loss covers **insured acres only**; the benchmark ships an `insured_acre_fraction`
  column (insured acres / NASS planted acres; median ≈ 0.45) so users can filter/weight by coverage.
- `drought_loss_ratio` uses the **true total insured liability** (RMA Summary-of-Business), removing
  the loss-experience >1 artifact (4 of 13,895 rows marginally exceed 1). Rank metrics and the binary
  target remain robust.
- v0.2 is corn + Corn Belt; soybean, CONUS, and additional predictors (e.g. GRACE) are planned.

## Provenance & citation

The predictor corpus comes from the separate [flashdry](https://github.com/gmarupilla/flashdry) repo
(cite its Zenodo DOI; not vendored here). See `data/drought/README.md` for upstream sources and
licenses.
