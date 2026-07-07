# An impact-labeled, prediction-ready drought benchmark for the US Corn Belt: predicting insured drought loss from within-season climate signal

**Authors:** Gnaneswara Marupilla¹, Chandhini Bayina²
**Affiliations:** ¹ Independent Researcher & Software Engineer (Scientific Computing); ² University of Central Missouri, Warrensburg, Missouri, United States
**Correspondence:** Gnaneswara Marupilla (gnaneswara@marupilla.dev)

> Target journal: **Earth System Science Data (ESSD)** — article type: *Data description paper*.
> Markdown review copy; the submission artifact is `manuscript.tex` (copernicus class). Every
> quantitative result below was produced by `terraflow drought build/evaluate` on the real RMA +
> flashdry inputs (no synthetic data) and verified against a fresh `evaluate_report.json` on
> 2026-07-05: corn 6.0% positive (temporal ROC-AUC 0.954, spatial LOSO 0.915); soybean 4.8% positive
> (temporal 0.927, spatial LOSO 0.898).

---

## Abstract

Drought benchmarks in machine learning predict how *dry* a season is (drought severity, e.g. the US
Drought Monitor D2+ category) or how much a crop *yields*. Neither answers the question insurers,
agencies, and adaptation planners actually face: **where will drought translate into realized economic
loss this season?** We present the first prediction-ready, *impact-labeled* drought benchmark, whose
target is **realized insured drought loss** derived from the public USDA Risk Management Agency (RMA)
Cause of Loss records. The benchmark pairs this label with a within-season predictor stack of
deseasonalized climate and vegetation anomalies aggregated to a mid-season cutoff, framing an
**early-warning** task: predict end-of-season insured loss from signal available by late July. Version 0
covers corn and soybean across the 6-state Corn Belt (Illinois, Indiana, Iowa, Minnesota, Missouri,
Nebraska), 2000–2023, at county–crop-year resolution (13,895 county-years, 587 counties per crop). We
release the assembled benchmark table, official temporal / leave-one-state-out / leave-one-year-out
splits, a deterministic build manifest, and a baseline leaderboard, alongside the open-source
`terraflow.drought` pipeline that reproduces every artifact from public inputs. A tiered baseline
evaluation shows that within-season climate signal predicts realized insured drought loss well (best
temporal ROC-AUC ≈ 0.95, spatial ROC-AUC ≈ 0.91), that US Drought Monitor severity is a strong but
beatable baseline that arrives later in the season, and that model choice matters sharply under
temporal extrapolation to extreme years. The dataset is archived on Zenodo
(https://doi.org/10.5281/zenodo.21208651, CC-BY-4.0).

## 1. Introduction

Drought is the costliest recurrent climate hazard for US agriculture, and quantifying *where and when*
it will cause loss is central to crop insurance, disaster response, and adaptation planning. Machine
learning has been applied extensively to two adjacent framings. The first is **drought severity
detection** — predicting a categorical dryness index such as the US Drought Monitor (USDM) D2+
class from meteorological and remote-sensing inputs. The second is **crop-yield prediction** — the
target of benchmarks such as CY-Bench and SustainBench. Both are valuable, but neither is the
economic-impact quantity that risk managers act on. Severity measures the *hazard*; yield measures a
*biophysical outcome*; neither is the *realized insured loss* that determines indemnity payouts,
program cost, and where mitigation has the highest return.

The USDA RMA Cause of Loss Summary-of-Business files are the public, county-level record of exactly
this quantity — indemnities paid, attributed to a specific cause of loss (including "Drought"), back
to 1989. Despite being open and long-running, these records have never been packaged as a
prediction-ready ML benchmark: they are distributed as large pipe-delimited loss-experience files that
require careful joining to the true insured liability and to a coverage denominator before they can
serve as an honest supervised target.

We close that gap. Our contributions are:

1. **An impact label.** A defensible, reproducible per-(county, crop, year) drought-loss target
   derived from RMA Cause of Loss, using the true total insured liability (from the RMA
   Summary-of-Business coverage files) as the denominator so the loss-experience ">1" artifact is
   removed, plus a documented insured-acre coverage-bias column.
2. **A prediction-ready benchmark.** The label joined to a within-season predictor stack of
   deseasonalized climate and vegetation anomalies and USDM severity aggregates, with regression and
   classification targets and three official evaluation splits (temporal, leave-one-state-out spatial,
   leave-one-year-out).
3. **A reproducible pipeline.** `terraflow.drought`, an open-source (MIT) sub-package that fetches the
   public inputs, assembles the benchmark, and runs a baseline leaderboard, writing a SHA-256 build
   fingerprint so identical inputs reproduce byte-identical artifacts.

The benchmark is deliberately *lean* in v0 — it uses only established, openly licensed data products
and standard estimators — so that its value is the **task and the labeled data**, not a modeling
apparatus. Deep sequence models, additional predictors (e.g. GRACE terrestrial water storage),
soybean-masked vegetation indices, and CONUS coverage are explicit future work.

## 2. Data and methods

### 2.1 Study domain and unit

The instance is one row per **(county FIPS `GEOID`, crop, crop-year)**. Version 0 covers **corn** and
**soybean** over the 6-state Corn Belt — Illinois (FIPS 17), Indiana (18), Iowa (19), Minnesota (27),
Missouri (29), Nebraska (31) — for crop-years **2000–2023**. This yields **13,895 county-years across
587 counties** per crop. The annual grain matches the native resolution of the RMA loss records, and
the county grain matches both the RMA and the predictor corpus join key.

### 2.2 Label construction (RMA Cause of Loss)

Labels derive from the USDA RMA **Cause of Loss** Summary-of-Business files (public, pipe-delimited,
1989–present). For each county-crop-year we compute:

- `drought_indemnity` = Σ indemnity where the *Cause of Loss Description* equals `"Drought"` (a literal
  text match on the official field — no code-table lookup);
- `total_indemnity` = Σ indemnity over all causes;
- `drought_share` = `drought_indemnity / total_indemnity`, a bounded auxiliary target in [0, 1].

The primary regression target is the **drought loss ratio**

`drought_loss_ratio = drought_indemnity / total_liability`,

where the denominator `total_liability` is taken from the RMA **Summary-of-Business coverage** files —
the true total insured liability across *all* policies (the pipeline falls back to the Cause-of-Loss
loss-experience liability `col_liability` only when the coverage file is absent). Using this denominator (rather than the loss-experience liability of
only loss-incurring policies, which is present in the Cause of Loss file) removes the artifact whereby
the ratio can exceed 1: after this correction only 4 of 13,895 corn rows marginally exceed 1, and both
the rank metrics and the binary target are robust to them. The binary target is

`significant_drought_loss = (drought_loss_ratio ≥ τ)`, with default threshold `τ = 0.10`.

County-years that appear in the predictor panel but have **no** Cause of Loss record are genuine
zero-loss negatives (`drought_loss_ratio = 0`, not significant) and are retained and filled, rather
than dropped — an omission that would otherwise inflate the positive rate. The resulting positive rate
is **6.0% for corn** and **4.8% for soybean**; the positive class is rare, which is why we treat PR-AUC
(average precision) as the honest classification headline.

### 2.3 Predictors (within-season, early-warning)

Predictors come from the openly documented **flashdry** corpus
(https://github.com/gmarupilla/flashdry), a county-aggregated stack built from MODIS NDVI, ERA5-Land,
Daymet, the US Drought Monitor, and USDA-NASS. We aggregate the growing-season time series **up to a
configurable day-of-year cutoff** (`cutoff_doy`, default 212 ≈ 31 July) to enforce an **early-warning**
framing: predict end-of-season realized loss from signal available only by mid-season. For each
county-year the predictor vector comprises:

- the **30 deseasonalized climate anomalies** (`*_anom`), each summarized as {mean, min, max, last};
- `NDVI_anom_z`, the standardized NDVI anomaly (same four summaries);
- **USDM severity** aggregates (`dm_gte_d2`, `dm_class`) — the severity baseline signal;
- `n_obs` and `n_stress_weeks` (season coverage and count of stress weeks).

An end-of-season variant (`cutoff_doy = 273`, 30 September) is available by configuration.

### 2.4 Coverage bias

Because RMA covers **insured acres only**, the benchmark ships coverage columns — `insured_acres`,
`total_premium`, `planted_acres` (USDA-NASS), and `insured_acre_fraction` (insured / planted acres,
median ≈ 0.70) — so users can filter or weight by insurance penetration rather than silently treating
uninsured acreage as zero-loss. This is stated as a first-class limitation, not a footnote.

### 2.5 Benchmark assembly and reproducibility

`terraflow drought build` performs: parse RMA Cause of Loss → build per-(GEOID, year) numerator labels
→ join the true Summary-of-Business liability and NASS planted acres → aggregate the flashdry
predictors to the cutoff → left-join predictors ⋈ labels on (GEOID, year) → finalize the loss-ratio,
binary, and coverage targets. It writes `benchmark.parquet`, `splits.json`, and `manifest.json`. The
manifest records a **SHA-256 build fingerprint** over the canonicalized configuration plus the hashes
of every input file (and of the fetched NASS acreage, since NASS is a live source), so identical inputs
reproduce a byte-identical fingerprint — the dataset's reproducibility contract.

### 2.6 Evaluation splits

Three official splits are released in `splits.json`:

- **Temporal** — test on the held-out years **2012, 2017, 2022, 2023** (the 2012 extreme drought and
  the recent 2022/2023 seasons); train on the *remaining* crop-years up to 2015 (i.e. 2000–2015 with
  2012 removed). The held-out years are excluded from training, so no test year — including the 2012
  extreme, which is ≤ 2015 — leaks into the train set. This is the primary, operationally realistic
  split (forecast the future from the past).
- **Leave-one-state-out (spatial)** — hold out each state in turn to measure spatial transfer.
- **Leave-one-year-out** — per-year generalization.

## 3. Technical validation

We provide a tiered baseline leaderboard (`terraflow drought evaluate` → `evaluate_report.json`,
`leaderboard.csv`) to characterize the task, not to propose a state-of-the-art method. Three tiers:
**naive** (train-mean and per-county historical-mean), **severity-only** (a model on the USDM
aggregates alone), and **climate ML** (Ridge / RandomForest / GradientBoosting on the within-season
anomaly features). All estimators are seeded (`random_state = 0`, `n_jobs = 1`) so the leaderboard is
deterministic. Regression is scored by R², RMSE, and Spearman ρ (the rank metric is the robust
headline given the heavy-tailed ratio); classification by ROC-AUC, average precision (PR-AUC), and
Brier score.

**Corn, temporal split** (train = non-test crop-years ≤ 2015; test = 2012/2017/2022/2023):

| Task | Model | Headline |
|---|---|---|
| Classification | GradientBoost [climate] | ROC-AUC **0.95**, PR-AUC **0.66** |
| Classification | LogReg [severity]       | ROC-AUC 0.93, PR-AUC 0.62 |
| Classification | RandomForest [climate]  | ROC-AUC 0.56 (temporal-extrapolation collapse) |
| Spatial LOSO   | GradientBoost [climate] | mean ROC-AUC **0.91** |

Three findings characterize the benchmark:

1. **Within-season signal predicts realized insured drought loss well** — best temporal ROC-AUC ≈ 0.95,
   spatial leave-one-state-out ≈ 0.91 — establishing that the task is learnable from mid-season data.
2. **USDM severity is a strong baseline that within-season climate models match or beat while arriving
   earlier in the season.** Severity alone reaches ROC-AUC ≈ 0.93; climate anomalies to the July cutoff
   reach ≈ 0.95 with a several-week lead time. Severity and impact are correlated but not identical —
   the benchmark measures the impact quantity directly.
3. **Model choice matters sharply under temporal extrapolation.** On held-out extreme years a random
   forest collapses to near-chance (ROC-AUC ≈ 0.56) while gradient-boosting and linear models remain
   strong (0.80–0.95). Because the positive class is rare (6%), PR-AUC is the honest headline and
   naive baselines are correspondingly weak.

The **soybean** benchmark (built identically via the crop-parameterized config) covers 13,895
county-years at 4.8% positive, with best temporal ROC-AUC ≈ 0.93 and spatial LOSO ≈ 0.90. Caveat: the
flashdry NDVI layer is corn-masked, so for soybean `NDVI_anom_z` acts as a regional vegetation-stress
proxy rather than a crop-specific signal; the weather anomalies and USDM severity are crop-agnostic.

## 4. Data availability

The benchmark table, official splits, build manifest, and baseline leaderboard are archived on Zenodo:
**https://doi.org/10.5281/zenodo.21208651** (concept DOI — resolves to the latest version), released
under **CC-BY-4.0**. The upstream inputs are public: USDA RMA Cause of Loss and Summary-of-Business
files, USDA-NASS QuickStats, and the flashdry predictor corpus (which itself derives from MODIS NDVI,
ERA5-Land, Daymet, and the US Drought Monitor — cite each upstream product). `data/drought/README.md`
and `data/drought/DATASHEET.md` (following Gebru et al., *Datasheets for Datasets*, 2021) document
provenance, licenses, and known limitations.

## 5. Code availability

The pipeline is the open-source (MIT) `terraflow.drought` sub-package of TerraFlow. The exact release
used to build this dataset is tagged on GitHub (https://github.com/gmarupilla/AgroTerraFlow) and
archived alongside the data. Reproduction is a three-command sequence:

```bash
terraflow drought fetch    --rma-dir data/drought/rma --sob-dir data/drought/sob --year-min 2000 --year-max 2023
terraflow drought build    -c examples/drought_v0_corn_6state.yml
terraflow drought evaluate -c examples/drought_v0_corn_6state.yml
```

`build` emits the deterministic `manifest.json` fingerprint; `evaluate` emits the leaderboard.

## 6. Limitations

- **Insured-acre coverage.** RMA records insured acres only; the `insured_acre_fraction` column
  (median ≈ 0.70) exposes this per county-year so users can filter or weight rather than mistake
  uninsured acreage for zero loss.
- **Denominator.** The loss ratio uses the true Summary-of-Business insured liability; 4 of 13,895
  corn rows marginally exceed 1, and rank metrics and the binary target are robust to them.
- **Attribution.** The label counts indemnity attributed to the literal "Drought" cause of loss; a
  heat-inclusive variant (`["Drought", "Heat", "Hot Wind"]`) is available by configuration.
- **Scope.** v0 is corn + soybean over the 6-state Corn Belt. CONUS coverage, additional predictors
  (e.g. GRACE terrestrial water storage), deep sequence models, and a crop-masked NDVI layer for
  non-corn crops are planned follow-ups.

## 7. Conclusions

We release the first prediction-ready, impact-labeled drought benchmark, targeting realized insured
drought loss from public RMA records and pairing it with an early-warning within-season predictor
stack, official splits, a reproducible build pipeline, and a baseline leaderboard. Baselines show the
task is learnable (temporal ROC-AUC ≈ 0.95), that drought severity is a strong but beatable and later
signal, and that robustness to temporal extrapolation is a discriminating axis for methods. By
packaging an economic-impact target that the field has not previously benchmarked, the dataset opens a
concrete evaluation surface for drought early-warning and agricultural risk modeling.

## References

*(to be completed in the copernicus `.bib`)*

- Gebru, T., et al. (2021). Datasheets for Datasets. *Communications of the ACM*.
- USDA Risk Management Agency. Cause of Loss and Summary of Business files. https://www.rma.usda.gov/
- USDA National Agricultural Statistics Service. QuickStats. https://quickstats.nass.usda.gov/
- US Drought Monitor. https://droughtmonitor.unl.edu/
- Muñoz-Sabater, J., et al. (2021). ERA5-Land. *Earth System Science Data*.
- Thornton, P. E., et al. Daymet: Daily Surface Weather Data.
- flashdry predictor corpus. https://github.com/gmarupilla/flashdry (cite Zenodo DOI).
- Marupilla, G., et al. TerraFlow / `terraflow.drought`. https://github.com/gmarupilla/AgroTerraFlow
