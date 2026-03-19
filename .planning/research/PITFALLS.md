# Domain Pitfalls

**Domain:** Research-grade geospatial / agricultural suitability Python library targeting JOSS
**Researched:** 2026-03-18
**Confidence note:** All pitfalls grounded in TerraFlow's actual code (verified) and established
geostatistical/JOSS domain knowledge (HIGH for items tied to code; MEDIUM for JOSS review
patterns from training data, not verified via live JOSS reviewer guides due to tool restrictions).

---

## Critical Pitfalls

Mistakes that cause JOSS rejection or require architectural rewrites.

---

### Pitfall 1: Sensitivity Analysis That Does Not Respect Sobol' Sample Size Requirements

**What goes wrong:**
The Sobol' method (SALib `sobol.analyze`) requires that the number of model evaluations be
`N * (2D + 2)` where N is a power of 2 and D is the number of input parameters. TerraFlow's
suitability model has 9 free parameters (w_v, w_t, w_r, v_min, v_max, t_min, t_max, r_min,
r_max). With D=9, even N=128 requires 2,432 evaluations; N=512 requires 9,728. Projects
commonly pick an arbitrary round number (e.g., n=1000) that does not satisfy `2^k` and then
interpret confidence intervals on the Sobol' indices as if they are reliable — producing
visually plausible but mathematically invalid sensitivity estimates.

**Why it happens:**
SALib will execute without error on non-power-of-2 samples; it does not enforce this
constraint. The resulting S1/ST indices are point estimates but their bootstrap confidence
intervals are meaningless. JOSS reviewers who know SALib will check the sample count.

**Consequences:**
- Sensitivity report published with `n_samples: 1000` — a red flag to any reviewer
- Sobol' confidence intervals mislead users about which parameters are actually dominant
- Cannot legitimately claim "w_v accounts for 62% of variance" if CI is unreliable

**Prevention:**
- Use `n_samples` as a power of 2: 512 or 1024 are the minimum practical choices for D=9
- Document the formula `N*(2D+2)` and the chosen N in `sensitivity_report.json`
- Add a validation in the `terraflow sensitivity` subcommand that rejects non-power-of-2 N
- Default: `n_samples: 1024` (produces 20,480 evaluations — fast for a pure Python scorer)

**Warning signs:**
- `n_samples` in config is not a power of 2
- ST confidence intervals span > 0.3 (suggesting insufficient samples)
- S1 + interaction terms do not sum close to ST for any parameter

**Phase:** Stage 3 (Sensitivity Analysis)

---

### Pitfall 2: Kriging LOOCV on Geographic Coordinates Conflates Units

**What goes wrong:**
PyKrige's `OrdinaryKriging` interprets the x/y inputs as distances when fitting the
variogram. TerraFlow's `_loocv` passes `lons` and `lats` in decimal degrees. This means
the variogram range parameter is expressed in degrees, not metres — producing a range that
is numerically meaningful only near the equator. At 45°N a degree of longitude is ~78 km
but a degree of latitude is ~111 km. The selected variogram model may be formally correct
but its range is uninterpretable and not comparable to published climate variogram ranges
in the literature.

**Why it happens:**
PyKrige does not enforce projected coordinates — it accepts whatever units you pass. The code
at `climate.py:374-393` passes raw lat/lon to `OrdinaryKriging` without coordinate
transformation. The LOOCV RMSE is still in the original variable units (°C, mm), so it
looks correct in `report.json`, but the fitted variogram range is ecologically meaningless.

**Consequences:**
- A JOSS reviewer familiar with geostatistics will ask "what units is the variogram range in?"
- The printed range in PyKrige's debug output will be ~0.5-5 degrees — implausible for any
  specific km-scale climate phenomenon
- Variogram model selection (spherical vs exponential vs Gaussian) may be systematically
  wrong because the nugget:sill:range ratio is distorted at non-equatorial latitudes

**Prevention:**
- Convert lat/lon to a local projected coordinate system (e.g., UTM or an equal-area
  projection) before passing to `OrdinaryKriging`; use `pyproj.Transformer` which is
  already a dependency
- Or document explicitly that coordinates are in degrees and that the variogram range is
  in degree-units, with a note on the limitation for high-latitude datasets
- Add a warning when the ROI centroid latitude exceeds 55° (where distortion is >10%)

**Warning signs:**
- Variogram range in PyKrige debug output differs greatly between longitude and latitude units
- LOOCV RMSE is similar for all three variogram models (spherical/exponential/Gaussian) —
  may indicate the variogram fitting is not discriminating between models

**Phase:** Stage 1 (Kriging) — already shipped; consider a patch before JOSS submission

---

### Pitfall 3: Validation That Compares Scores to Labels Without Accounting for Spatial Autocorrelation

**What goes wrong:**
When TerraFlow scores are joined to FAO GAEZ or USDA NASS reference data and a confusion
matrix / Cohen's κ is computed, standard κ assumes observations are independent. Geospatial
raster cells are spatially autocorrelated — neighbouring cells have correlated errors.
This inflates the effective sample size and makes κ appear more significant than it is.
A JOSS reviewer doing spatial statistics will flag this immediately.

**Why it happens:**
Standard `sklearn.metrics.cohen_kappa_score` does not account for spatial autocorrelation.
Projects add validation metrics without reading the spatial statistics literature first.

**Consequences:**
- Paper states κ = 0.71 (substantial agreement) when the spatially-corrected effective N
  reduces significance below any defensible threshold
- If a reviewer runs Moran's I on the residuals and finds strong autocorrelation, the
  validation claim collapses
- JOSS may require a revision; worst case the validation section must be removed

**Prevention:**
- Report Moran's I on validation residuals alongside κ — this shows awareness of the issue
- Use block cross-validation (spatial CV) rather than random CV: hold out spatial blocks
  (e.g., 5-fold spatial k-fold) so training and test cells are not spatially proximate
- Alternatively, document the autocorrelation limitation explicitly in both code docstrings
  and the paper, citing Roberts et al. (2017) "Cross-validation strategies for data with
  temporal, spatial, hierarchical, or phylogenetic structure"
- At minimum: include `n_cells` in validation output and note that effective N < n_cells
  due to spatial autocorrelation

**Warning signs:**
- Validation code uses sklearn's train_test_split without a spatial blocking strategy
- High κ (>0.7) with very small ROI (spatial autocorrelation is more severe at fine scales)
- No Moran's I reported anywhere in validation output

**Phase:** Stage 4 (Validation)

---

### Pitfall 4: Sensitivity Analysis That Varies Parameters Independently When They Have Implicit Constraints

**What goes wrong:**
TerraFlow's ModelParams has 9 parameters but they are not all independent: the weights
`w_v + w_t + w_r` must sum to 1.0 for the score to remain in [0,1]. SALib's Saltelli
sampler treats each parameter as independently uniform over its bounds. If the sampler
produces `w_v=0.5, w_t=0.4, w_r=0.4` (sum=1.3), the suitability score will be clipped to
1.0 for many cells, destroying score variance and making the sensitivity analysis report
near-zero first-order indices — a false negative.

**Why it happens:**
Saltelli sampling is fully unconstrained. The simplex constraint on weights is not naturally
expressible in SALib's rectangular problem definition.

**Consequences:**
- Sobol' S1 and ST indices for w_v, w_t, w_r all appear near-zero
- Sensitivity report incorrectly concludes that weights don't matter
- Paper makes claims about parameter sensitivity that are artifacts of the clipping

**Prevention:**
- Option A (preferred): Use a simplex-constrained parameterisation — vary only w_v and w_t
  over [0,1] with the constraint w_v+w_t <= 1, and derive w_r = 1 - w_v - w_t. This reduces
  the effective parameter space from 9 to 8 and removes the illegal region.
- Option B: Normalise the sampled weight triplet before scoring: `w = [w_v, w_t, w_r] / sum`
  — but then document that the effective distribution is Dirichlet, not uniform.
- Add a pre-flight check in the sensitivity CLI that verifies weight bounds satisfy
  `w_v_max + w_t_max + w_r_max > 1` (the constraint can be violated) and warns the user.

**Warning signs:**
- sensitivity_report.json shows S1 indices < 0.05 for all three weight parameters
- Mean score across MC samples is near 1.0 (clipping artefact)
- Weight bounds in config each reach 1.0: e.g., `w_v: [0, 1], w_t: [0, 1], w_r: [0, 1]`

**Phase:** Stage 3 (Sensitivity Analysis)

---

## Moderate Pitfalls

---

### Pitfall 5: JOSS Reviewer Cannot Reproduce Results Without Downloading External Data

**What goes wrong:**
JOSS requires that reviewers be able to run the software. If the demo config requires
downloading a multi-GB raster from CropScape or FAO GAEZ — which requires account
registration, has rate limits, or simply takes too long — the reviewer will fail
installation verification and flag the software as not installable/runnable.

**Why it happens:**
Real ag datasets are large and proprietary or gated. Projects use them in demos without
providing a deterministic synthetic fallback.

**Consequences:**
- JOSS checklist item "Does the software have a test suite that the reviewer can run?" fails
- Reviewer marks "Functionality" as not verified
- Rejection or major revision request

**Prevention:**
TerraFlow already has `scripts/make_demo_raster.py` and `make get-demo-data`. Ensure:
- The `make get-demo-data` path produces a usable demo raster unconditionally (synthetic
  fallback is always available, external download is optional)
- Smoke test passes on CI without any external download
- `README.md` quickstart section completes in under 2 minutes on a cold machine
- Paper figures are reproducible from the synthetic demo, not from the real raster

**Warning signs:**
- `pytest` skips smoke tests because the raster is absent
- Quickstart section says "download from X" before saying "run the demo"

**Phase:** Ongoing; verify before JOSS submission

---

### Pitfall 6: Monte Carlo Normality Assumption Is Violated When kriging_std Is Near Zero

**What goes wrong:**
The current Monte Carlo implementation samples `Normal(krig_mean, krig_std)` for climate
variables. At or very near a station location, `krig_std` is ~0 by construction of ordinary
kriging (interpolation is exact at data points). This produces degenerate samples (all
identical to the mean). The CI collapse to a point (`score_ci_low == score_ci_high ==
score`), which is technically correct but visually misleading — a reviewer may interpret
"CI width = 0" as "uncertainty analysis failed" rather than "this is a station location".

**Why it happens:**
Exact interpolation is a feature of ordinary kriging, but it produces a discontinuity in
the CI width surface — zeros at station locations, positive values elsewhere. This is
rarely documented in the uncertainty output.

**Prevention:**
- Document the exact-interpolation property in the `uncertainty` section of `report.json`
- Add `n_cells_zero_ci_width` to `report.json["uncertainty"]` so the phenomenon is
  visible in the output rather than silent
- Include a comment in `pipeline.py` near the `np.maximum(krig_std, 0.0)` clip explaining
  why zero std is valid at station locations, not a bug

**Warning signs:**
- `mean_ci_width` in report.json is anomalously small relative to the number of stations
- User-reported bug: "CI is always 0 for some cells"

**Phase:** Stage 2 (Monte Carlo) — already shipped; add documentation now

---

### Pitfall 7: H3 Export Introduces a Projection Step That Breaks Reproducibility Fingerprinting

**What goes wrong:**
H3 cell IDs are deterministic given a resolution and WGS84 lat/lon. However, if H3 export
is added as a pipeline step that modifies `features.parquet` schema or output path structure,
the `run_fingerprint` may or may not incorporate the H3 resolution setting. If the H3
resolution is in the config but not in the fingerprint hash, two runs with different H3
resolutions will produce the same fingerprint and different artifacts — breaking the
no-op rerun detection.

**Why it happens:**
New output stages are sometimes bolted onto the pipeline after the fingerprint computation
without updating the fields that feed `compute_run_fingerprint`.

**Consequences:**
- No-op rerun detection incorrectly serves cached results from a different H3 resolution
- Silent corruption: user gets resolution-5 H3 cells when they configured resolution-8

**Prevention:**
- Any new config key that affects output must be included in the canonicalized config that
  feeds `compute_run_fingerprint`
- Write a determinism regression test for H3: run with resolution=5, assert fingerprint
  differs from resolution=8 run
- Keep H3 export as a separate post-processing step that does not alter `features.parquet`
  schema — write to a separate `h3_export.parquet` so the schema contract is preserved

**Warning signs:**
- New config key added but not reflected in a new determinism test
- H3 resolution change does not change `run_fingerprint`

**Phase:** H3 Export feature

---

### Pitfall 8: Variogram Model Selection Uses Only the First Climate Variable

**What goes wrong:**
`_init_kriging` at `climate.py:321-323` selects the best variogram model by running LOOCV
on only the first climate variable (`primary_var = self.climate_columns[0]`). It then
applies that same model to all climate variables. If mean_temp has a spherical variogram
structure but total_rain has an exponential structure (common in reality — precipitation
and temperature have different correlation length scales), the model applied to total_rain
may be suboptimal.

**Why it happens:**
Running LOOCV on all variables × all models is O(3N²) per variable, which is expensive.
Selecting on one variable is a reasonable computational shortcut — but it is not documented
as a limitation.

**Consequences:**
- If a reviewer asks "how was the variogram model selected for each variable?", the honest
  answer is "it was selected on the first variable only" — which is not standard practice
- Interpolation quality for secondary variables (total_rain) may be worse than reported

**Prevention:**
- Document the single-variable selection strategy in the climate module docstring and in
  the paper's Methods section: "variogram model is selected by LOOCV on the primary
  climate variable and applied uniformly across all variables"
- Add a per-variable RMSE comparison note in `report.json["interpolation_cv"]` — it
  already reports per-variable RMSE, so a reviewer can see if one variable has much
  higher RMSE (suggesting a different model would be better for it)
- Consider adding an optional `per_variable_variogram: true` config flag as a future
  enhancement, with the computationally cheaper single-variable strategy as the default

**Warning signs:**
- `total_rain` LOOCV RMSE significantly higher than `mean_temp` RMSE in report.json

**Phase:** Stage 1 (Kriging) — already shipped; add documentation now

---

## Minor Pitfalls

---

### Pitfall 9: Climate Column Auto-Detection Silently Includes Non-Climate Numeric Columns

**What goes wrong:**
`ClimateInterpolator._validate_columns()` auto-detects numeric columns in the climate CSV
excluding lat/lon. If the CSV contains an `id`, `year`, `station_id`, or `elevation` column
that happens to be numeric, it will be treated as a climate variable, interpolated, and
added to `features.parquet`. The suitability model ignores it (it only reads `mean_temp`
and `total_rain`), but the extra column inflates storage and confuses downstream users.

**Prevention:**
- Add a `climate.variables: [mean_temp, total_rain]` explicit config key (already identified
  in CONCERNS.md); auto-detect only if the key is absent for backward compatibility
- Emit a warning when more than 2 numeric non-coordinate columns are auto-detected,
  listing which columns will be treated as climate variables

**Phase:** Stage 1 / ongoing

---

### Pitfall 10: H3 Resolution Mismatch With Raster Pixel Size

**What goes wrong:**
H3 resolution 8 cells are ~0.74 km² and resolution 9 cells are ~0.11 km². If the source
raster has 30 m pixels (Landsat-scale), multiple H3 cells at resolution 12 fit within a
single pixel — producing many H3 cells with identical scores (because they all sample the
same pixel). At coarser resolutions (5-6), one H3 cell spans thousands of pixels and the
single assigned score (from nearest sampled cell) does not represent the spatial average.

**Why it happens:**
H3 resolution is often chosen for downstream tooling compatibility (e.g., DeckGL's default
resolution) without checking alignment with the source raster resolution.

**Consequences:**
- Users report "many cells have identical scores" at fine H3 resolutions — looks like a bug
- At coarse resolutions, users expect an aggregated score but get a point sample

**Prevention:**
- Add a resolution recommendation table in docs: map typical raster resolutions (30 m,
  250 m, 1 km, 10 km) to appropriate H3 resolutions
- Emit a warning when H3 cell area < 4× raster pixel area (too-fine risk) or when H3 cell
  area > 1000× raster pixel area (aggregation risk)
- Default H3 export to aggregate (mean) over all sampled cells within an H3 cell, not
  nearest-cell assignment

**Phase:** H3 Export feature

---

### Pitfall 11: paper.md Quantitative Claims Not Updated After Each Stage

**What goes wrong:**
The paper states that TerraFlow "produces reproducible results" but the specific quantitative
claims (LOOCV RMSE values, MC mean CI width, Sobol' indices) must be updated manually after
each new stage ships. Projects commonly ship Stages 3 and 4 and then submit the paper with
Stage 1 numbers still in the results table.

**Prevention:**
- Maintain a `paper/results_snapshot.json` that is generated by running the demo pipeline
  and is committed alongside each new stage
- CI should verify that `paper/results_snapshot.json` was updated when `terraflow/` modules
  change (a linting rule comparing last-modified dates)
- Assign explicit ownership: whoever merges a stage milestone reviews `paper.md` before
  the PR merges

**Phase:** All stages; especially before JOSS submission

---

## JOSS-Specific Rejection Patterns (Geospatial Tools)

The following are rejection or revision request patterns seen in geospatial/scientific Python
tools reviewed by JOSS. Confidence: MEDIUM (based on training data from JOSS review threads;
not verified via live JOSS reviewer guidelines due to tool access restrictions).

| Rejection Reason | TerraFlow Risk | Mitigation Already In Place |
|-----------------|---------------|------------------------------|
| "Software not installable by reviewer" | LOW — CI green, PyPI published | `make get-demo-data` synthetic fallback; Docker e2e job |
| "No test suite or tests don't run" | LOW — 127 tests, 85% coverage | CI matrix on 3.10/3.11/3.12 |
| "Paper claims not supported by software" | HIGH — kriging LOOCV range units, weight justification gap | Stages 3+4 must close this |
| "Software duplicates existing packages without adding novelty" | MEDIUM — must argue that the pipeline integration is the contribution, not kriging or SALib alone | Statement of need in paper.md |
| "Insufficient documentation for independent use" | MEDIUM — quickstart exists but no worked examples with real data | 2-3 more config examples needed |
| "Scientific methodology is not citable or not standard" | HIGH — linear model weights are uncited; FAO GAEZ not integrated | Stages 3+4 address this |
| "Outputs are not interpretable without deep domain knowledge" | MEDIUM — labels are interpretable; CI bounds are not explained to non-geostatisticians | Docs + report.json uncertainty explanation |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Stage 3: Sensitivity Analysis | Sobol' sample size not a power of 2 | Validate N is 2^k in CLI; document formula |
| Stage 3: Sensitivity Analysis | Weight simplex constraint violated during sampling | Use constrained parameterisation (Pitfall 4) |
| Stage 4: Validation | Standard κ ignores spatial autocorrelation | Report Moran's I; use spatial block CV |
| Stage 4: Validation | Reference dataset requires account registration | Use synthetic FAO-derived labels in demo |
| H3 Export | H3 resolution not in fingerprint hash | Regression test: different resolution = different fingerprint |
| H3 Export | Resolution / pixel mismatch | Warn when mismatch exceeds threshold; aggregate rather than point-sample |
| All stages | paper.md quantitative results stale | Commit results_snapshot.json with each stage |
| JOSS submission | Kriging variogram range in degree-units | Document limitation; consider projected-coordinate option |
| JOSS submission | MC CI collapse at station locations | Document in report.json; not a bug |

---

## Sources

**HIGH confidence (verified in TerraFlow codebase):**
- `terraflow/climate.py` lines 289-393: kriging initialisation, LOOCV, single-variable model selection
- `terraflow/pipeline.py` lines 540-583: Monte Carlo implementation, krig_std assumption
- `terraflow/model.py` lines 41-47, 84-89: weight combination, clipping
- `terraflow/geo.py` lines 62-105: CRS handling, 4-corner reprojection, NaN guard

**MEDIUM confidence (established geostatistical literature, not re-verified 2026):**
- Cressie, N. (1993) "Statistics for Spatial Data" — variogram unit requirements
- Roberts et al. (2017) "Cross-validation strategies for data with temporal, spatial,
  hierarchical, or phylogenetic structure" — spatial CV blocking
- Saltelli, A. et al. (2010) "Variance based sensitivity analysis of model output.
  Design and estimator for the total sensitivity index" — Sobol' sample size requirements
- SALib documentation: `N * (2D + 2)` evaluation count formula

**MEDIUM confidence (JOSS review community knowledge, training data):**
- JOSS reviewer guidelines (https://joss.readthedocs.io/en/latest/reviewer_guidelines.html)
- Common JOSS review threads for geospatial tools (github.com/openjournals/joss-reviews)
