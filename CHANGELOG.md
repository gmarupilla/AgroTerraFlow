# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Climate-impact pipeline integration in `run_pipeline` (#138f).** `terraflow.pipeline.run_pipeline` now auto-invokes the `terraflow.climate_impact` orchestrator when the loaded config declares both `climate.temporal_aggregations` and `climate.scenarios`. After `features.parquet` is written the pipeline calls `run_climate_impact_features(cfg, run_dir, df[["cell_id", "lat", "lon"]])`, producing a sibling `climate_features.parquet` (cell-indexed; one column per `<rule>__<scenario>` pair). The new artifact is appended to `manifest.json` `output_files`, the cached-run early-return now requires `climate_features.parquet` when the climate-impact path is configured, and `climate.timeseries_csv` is registered as an input path so its hash factors into the run fingerprint (changing the CSV invalidates the cache). The `NotImplementedError` gate added in #138e is removed: `PipelineConfig.validate_all()` returns cleanly for the full climate-impact shape. New `examples/demo_config_climate_impact.yml` exercises the path end-to-end with three scenarios (historical + SSP2-4.5 + SSP5-8.5) and seven aggregation rules including the four WMO/ETCCDI-aligned hazard kinds. 2 new tests in `tests/test_pipeline.py` cover (a) the auto-invoke happy path with two scenarios × two rules and (b) cache-correctness when `climate_features.parquet` is removed but `features.parquet` survives.
- **Climate-impact pipeline orchestration (#138e).** New `terraflow.climate_impact` module with two public functions: `load_timeseries_csv(path)` parses and validates the long-format station daily CSV (columns: `station_id, lat, lon, date, temperature_c, precipitation_mm`); `run_climate_impact_features(cfg, run_dir, cells_df)` orchestrates the full pipeline — compute per-station aggregations via `terraflow.temporal.compute_per_station_aggregations`, kriging-interpolate each `<rule>__<scenario>` column to cell centroids via `terraflow.climate.ClimateInterpolator`, and write a new `climate_features.parquet` artifact to the run directory. `ClimateConfig` gains a `timeseries_csv: Optional[str]` field. The historical single-period `features.parquet` artifact contract is unchanged — climate-impact columns live in a separate sibling artifact so downstream tools merge them on `cell_id`. The `PipelineConfig.validate_all()` `NotImplementedError` gate from #138a is removed: replaced with a clean `ValueError("requires climate.timeseries_csv")` when `temporal_aggregations` is set without the new input field. 9 new tests in `tests/test_climate_impact.py` cover the schema validator, happy-path single-scenario, two-scenario equality test, missing-input error path, and the gate update. `run_climate_impact_features` is currently a standalone callable; full integration into `run_pipeline` (auto-invoke when both lists are populated) + demo + notebook land in #138f.
- **Hazard indicators — GDD / frost days / heat-stress days / SPEI (#138d).** New `terraflow.hazard` module implementing the four crop-hazard `TemporalAggregation` kinds previously gated as `NotImplementedError` in `terraflow.temporal`: `growing_degree_days(df, base_temp_c)` = `sum_d max(0, T - base)` per station; `frost_days(df, threshold_c)` and `heat_stress_days(df, threshold_c)` count days at or beyond the threshold (matches WMO ETCCDI FD0/TX35 conventions when the threshold is set canonically); `spei(df, timescale_months)` returns a simplified Thornthwaite-PET-based Standardised Precipitation-Evapotranspiration Index at the final month of the input window. The SPEI simplifications relative to the canonical R-package implementation are documented in the module docstring (no daylight-hour correction; per-station heat-index fit; z-score standardisation rather than log-logistic CDF). The `terraflow.temporal.aggregate_per_station` dispatcher now routes the four hazard kinds into the new module instead of raising. 20 new tests in `tests/test_hazard.py` cover GDD additive correctness, threshold-equality semantics for frost/heat days, SPEI dry/wet sign tests with anomaly windows, edge cases (empty input, window-too-short, non-positive timescale), and dispatcher integration. The `PipelineConfig` `NotImplementedError` gate from #138a still holds — pipeline wiring activates in #138e.
- **CMIP6 NetCDF scenario ingest (#138c).** New `terraflow.cmip6` module behind an optional `[cmip6]` install extra (`xarray>=2024.1`, `netcdf4>=1.7`). Four public functions: `cmip6_metadata(path)` returns sha256 + size_bytes + the CMIP6 global attrs (`variant_label`, `source_id`, `experiment_id`, `institution_id`, `table_id`) that will fold into the run fingerprint in #138e; `load_cmip6_scenario(path, variable, period)` opens a NetCDF lazily via xarray and slices the time axis by a year-inclusive period window; `extract_station_timeseries(da, stations, output_variable)` samples a CMIP6 DataArray at station (lat, lon) coordinates using vectorised nearest-neighbour selection and returns the long-format DataFrame shape `terraflow.temporal` expects (`station_id, lat, lon, date, <output_variable>`); `cmip6_to_station_timeseries(...)` is a one-call wrapper around the previous two. xarray is imported lazily inside each callable so users on the historical CSV path never pay the import cost. Tolerates both `lat`/`lon` and `latitude`/`longitude` coord names commonly seen across CMIP6 sources. 12 new tests in `tests/test_cmip6.py` build synthetic CF-compliant NetCDFs with `xarray.DataArray.to_netcdf`, then assert: SHA-256/size hashing, CMIP6 global attribute extraction, time-window filtering, exact nearest-neighbour sampling on a deterministic value grid, and the optional-extra ImportError path. The module is wired into the package but the pipeline (#138e) and demo (#138e) follow after #138d.
- **Multi-temporal aggregation engine (#138b).** New `terraflow.temporal` module: `filter_scenario(df, scenario)` slices a long-format station time-series to a `Scenario.period` year window; `aggregate_per_station(df, rule)` dispatches a `TemporalAggregation` to its kind-specific implementation; `compute_per_station_aggregations(df, rules, scenarios)` returns the outer-product matrix indexed by `station_id` with columns `<rule_label>__<scenario_name>`. Three non-hazard kinds implemented: `annual_mean` (long-run mean of `temperature_c`), `seasonal_mean` (mean of `temperature_c` over `months: [1..12]`), `precip_percentile` (Nth percentile of `precipitation_mm`). Four hazard kinds (`growing_degree_days`, `frost_days`, `heat_stress_days`, `spei`) raise `NotImplementedError` pointing at `terraflow.hazard` (#138d). Stations with no rows after a filter resolve to `NaN` rather than being dropped, so downstream kriging LOOCV sees missing values cleanly. 18 new tests in `tests/test_temporal.py` cover all three implemented kinds plus the dispatcher, scenario filter, outer-product helper, and edge cases (empty scenarios, empty rules, missing columns, NaN propagation across stations missing in a scenario window). Wired into the pipeline behind the existing `NotImplementedError` gate; the gate lifts in #138e once CMIP6 ingest (#138c) and hazard module (#138d) ship.
- **Climate-impact configuration schema (#138a).** `TemporalAggregation` Pydantic model accepting `kind` ∈ {`annual_mean`, `seasonal_mean`, `growing_degree_days`, `frost_days`, `heat_stress_days`, `precip_percentile`, `spei`} with kind-specific validation (`months: [1..12]`, `base_temp_c: float`, `threshold_c: float`, `percentile: 0..100`, `timescale_months: int > 0`). `Scenario` Pydantic model with `name: non-empty str` + `period: [year_min, year_max]` (years 1800-2200, year_min ≤ year_max). `ClimateConfig` gains `temporal_aggregations: list[TemporalAggregation] = []` and `scenarios: list[Scenario] = []`. Cross-field validation: non-empty `temporal_aggregations` requires non-empty `scenarios`; scenario names must be unique. Defaults are empty lists so existing configs continue to work unchanged. Schema page (`docs/config/schema.md`) extended with the full flagship example block. **Pipeline-level gate:** `PipelineConfig.validate_all()` raises `NotImplementedError` when either list is non-empty, so users do not silently get single-period output while the engine (#138b), CMIP6 ingest (#138c), and hazard module (#138d) are still in flight. The Pydantic models themselves accept the full shape and are introspectable for tooling and docs. Aggregation engine + scenario fan-out land in #138b/c/d.

### Changed
- **Rebrand to climate-impact-on-agriculture flagship (#137).** Title locked to "TerraFlow: A Reproducible Geospatial Suitability Framework" with Tier-2 pitch "reproducible climate-impact assessment of agricultural suitability — including climate-induced crop hazards (drought, flood, heat stress, growing-degree-day shifts) under historical and projected future climate." Methodology extends to habitat suitability, land-use planning, and conservation siting as adjacent expansion chapters. Updated: `README.md` headline + lede, `paper/paper.md` title + Summary + Statement of Need, `paper/paper.md` frontmatter `title` + `tags` (adds `climate impact` + `crop suitability`), `pyproject.toml` `description`, `CITATION.cff` `title` + `abstract`, `mkdocs.yml` `site_description`, `docs/index.md` headline + lede, `docs/quickstart.md` framing. PyPI package name (`terraflow-agro`), license, authors, ORCIDs, and repo URL unchanged.
- `terraflow.validation` narrowed to spatial-block cross-validation only. The `_compute_kappa()` and `_morans_i()` helpers and the `reference_csv` field on `ValidationConfig` are removed; the validation block in `report.json` no longer carries `cohen_kappa`, `morans_i_residuals`, `reference_dataset`, or `n_reference_points`. Downstream users that want Cohen's κ should call `sklearn.metrics.cohen_kappa_score` directly; spatial autocorrelation diagnostics belong to `esda.Moran` on the exported `features.parquet`. Reason: both wrappers failed the Methods-section citation test (downstream papers cite `esda` / `sklearn` not TerraFlow); keeping them added maintenance burden without earning citations. Strategy decision in issue #123/#136. Paper, README, mkdocs docs (`api/validation.md`, `cli/usage.md`, `architecture/overview.md`, `config/schema.md`, `reproducibility.md`) and `cli.py` validate docstring updated to reflect the narrowed surface.

### Removed
- GeoAI engine: `terraflow/geoai_engine.py`, `terraflow geoai {fields,landcover,canopy}` CLI sub-app, `GeoAIConfig` Pydantic block, `compute_geoai_fingerprint`, ADR-007, `docs/geoai.md`, `docs/api/geoai_engine.md`, `06_geoai_engine.ipynb`, `tests/test_geoai_engine.py`, `[geoai]` extra (`geoai-py` + `torch`), and `geoai-integration.yml` workflow. Engine bodies were `NotImplementedError` stubs; the module did not earn Methods-section citations (downstream users go to `geoai-py` directly). Strategy decision in issue #123/#134 — reintroduce as a separate `terraflow-geoai` package post-JOSS if interest materializes. Paper, README, CITATION.cff, mkdocs nav, and reproducibility docs updated to drop GeoAI mentions; `wu2026geoai` removed from `paper/biblio.bib`.
- H3 export: `terraflow/export.py` (`to_h3`, `run_export`), `terraflow export --format h3` CLI subcommand, `ExportConfig` Pydantic block, `terraflow.to_h3` re-export, `[h3]` optional extra (`h3>=4.0,<5`), `docs/h3-export.md`, `docs/api/export.md`, `docs/notebooks/04_h3_export.ipynb`, `tests/test_export.py`, the `TestExportCLI` class in `tests/test_cli.py`, the H3 section in `docs/cli/usage.md`, the `export.py` + `h3_resolution_N.parquet` rows in `docs/architecture/overview.md`, the `export` config row in `docs/config/schema.md`, the H3 rows in `README.md`, and the `[h3]` mention in `docs/install/homebrew.md`. Module was a thin `h3-py` + pandas-groupby wrapper; downstream users can call `h3-py` directly in 5 lines on `features.parquet`. Strategy decision in issue #123/#135. No spillover into the locked flagship (reproducible climate-impact assessment of agricultural suitability).

### Changed
- All seven notebooks under `docs/notebooks/` re-executed against v0.4.0 so the rendered docs site shows live output for every cell. `05_extended_variogram_mode.ipynb` (previously checked in unexecuted) and `06_geoai_engine.ipynb` (just created) now have execution counts and outputs; `terraflow_v0_2_0_comprehensive_test.ipynb` re-executed so the inline outputs and execution counts are in sync. `kriging_uncertainty_demo.ipynb` header bumped from v0.2.1 → v0.4.0; `terraflow_v0_2_0_comprehensive_test.ipynb` header now frames the notebook as a v0.2.0 → v0.4.0 backward-compatibility regression check.
- `docs/notebooks/06_geoai_engine.ipynb` stub cell now patches the helper functions (`_device`, `_torch_major_minor`, `_geoai_major_minor`, `_seed_torch`) so the notebook executes cleanly without the `[geoai]` extra installed (previously only `_GEOAI_AVAILABLE` and `_do_fields` were patched, which left `torch.cuda.is_available()` to dereference `None`).
- `docs/contributing.md` "for v0.2.0+" → "for v0.4.0+" and the citation example in `docs/reproducibility.md` updated from `terraflow-agro==0.2.2` to `terraflow-agro==0.4.0`.

### Fixed
- `paper/biblio.bib` `wu2026geoai` entry replaced: it was a placeholder `@misc` with `note = "Manuscript in preparation for JOSS"` and a GitHub URL, but the GeoAI JOSS paper was actually **published 2026-02-03** as Wu, Q. (2026), *GeoAI: A Python package for integrating artificial intelligence with geospatial data analysis and visualization*, Journal of Open Source Software, 11(118), 9605, [doi:10.21105/joss.09605](https://doi.org/10.21105/joss.09605). The bib entry is now a proper `@article` with the real DOI, volume, issue, page, ISSN, and publisher. All five `[@wu2026geoai]` citations in `paper/paper.md` continue to resolve to the same key (no in-body text changes).
- `paper/biblio.bib` `terraflow_zenodo` entry **removed**. It was uncited (no `[@terraflow_zenodo]` anywhere in `paper/paper.md`) and carried the same stale v0.1.5 DOI (`10.5281/zenodo.18490119`) and stale title that were already cleaned out of `CITATION.cff` and the paper frontmatter. The repository URL is the citation handle until JOSS mints the v0.4.0 archive on acceptance.

### Added
- `# AI usage disclosure` section in `paper/paper.md` (now a **required** section per the JOSS review criteria). The section discloses that AI tools were used as a coding assistant during implementation and manuscript drafting, that AI-assisted code is human-reviewed before commit, and that the 289 automated tests on Python 3.10/3.11/3.12 verify correctness (#111).
- `.github/ISSUE_TEMPLATE/bug_report.yml` (YAML-form bug report including TerraFlow version, Python version, OS, config YAML, repro command, expected vs actual, optional `run_fingerprint`) and `feature_request.yml` (problem / proposal / alternatives / subsystem). `.github/ISSUE_TEMPLATE/config.yml` disables blank issues and surfaces the docs site, reproducibility page, security advisory flow, and contributing guide (#113).
- `.github/SUPPORT.md` documenting all support channels (docs, discussions, bug reports, reproducibility help, security disclosures, contributing) so the JOSS "seek support" community-guidelines item is closed (#114).
- `.github/pull_request_template.md` with the project's PR checklist (lint / typecheck / coverage / CHANGELOG / docs / notebook / mkdocs nav / reproducibility-impact section) so new contributors see the gate at PR-open time (#114).

### Changed
- `CITATION.cff` refreshed: `version: 0.4.0`, `date-released: 2026-06-08`, title now matches the JOSS paper subtitle ("…and Foundation-Model Inference"), abstract mentions the v0.4.0 GeoAI engine, and keyword list adds `kriging`, `sensitivity-analysis`, `uncertainty-quantification`, `geoai`, `foundation-models`, `pytorch` (#112). The `doi:` field is removed for now: the previously recorded `10.5281/zenodo.18490119` actually resolves to the v0.1.5 archive, and no v0.4.0 Zenodo record has been minted (GitHub→Zenodo integration not yet enabled). JOSS archives the accepted version itself on publication, so the citation handle is the repository URL until then.
- `paper/paper.md` AI usage disclosure section expanded to name the specific AI tools and model versions used (Anthropic Claude Code with `claude-opus-4-7` for v0.4.0 GeoAI / paper revisions, earlier Claude Sonnet 4.x / Opus 4.x for v0.2.x – v0.3.0 climate-pipeline work; OpenAI Codex GitHub App for automated PR review), per the JOSS criterion that AI disclosures must be specific rather than generic.
- `paper/paper.md` frontmatter `repository-artifact` + `identifiers` removed (same v0.1.5-vs-v0.4.0 mismatch reason as the CITATION.cff DOI removal). In-body citation-graph mention reworded to point at the Zenodo archive that will be minted on JOSS acceptance.
- GitHub repo About sidebar: description now references the GeoAI engine; topics gained `geoai`, `foundation-models`, `pytorch` (within GitHub's 20-topic cap, dropping `opengeos`) (#115; metadata-only change, no code diff).

## [0.4.0] — 2026-06-08

### Added
- Optional `[geoai]` extra (`pip install terraflow-agro[geoai]`) bringing in `geoai-py` and `torch` for the upcoming `terraflow geoai` subcommand (#91, epic #90).
- `GeoAIConfig` Pydantic block accepted under `geoai:` in pipeline configs, with validation for engine name (`fields`/`landcover`/`canopy`), power-of-two `chip_size` (≥ 32), `confidence_threshold` in [0, 1], and positive `batch_size`.
- Internal `terraflow.core.run_identity.compute_geoai_fingerprint()` for deterministic GeoAI-run identity. Hashes config, inputs (`{sha256, size_bytes}` shape now enforced), and `name`/`weights_sha256`/`geoai_major_minor`; optionally also `device` and `torch_major_minor`.
- `terraflow.geoai_engine` module with `run_fields()`, `run_landcover()`, `run_canopy()` orchestrators (#92). Validates `config.geoai.engine`, fingerprints inputs + device/torch, writes artifacts to `<output_dir>/runs/<geoai_fingerprint>/geoai/`, emits `geoai_manifest.json` and `report.json`, seeds `torch.manual_seed` from the fingerprint, and skips inference on cache hits. Engine bodies are placeholders that land in #94.
- `terraflow geoai {fields,landcover,canopy}` CLI subcommands wired via a Typer sub-app, sharing a single error-handling helper with the rest of the CLI for uniform exit codes and log labels (#93).
- New `ADR-007: GeoAI Engine Adapter` (`docs/architecture/adr-007-geoai-engine.md`), GeoAI user guide (`docs/geoai.md`), API reference page (`docs/api/geoai_engine.md`), and demo notebook (`docs/notebooks/06_geoai_engine.ipynb`) covering the orchestrator, cache-hit behaviour, and fingerprint sensitivity (#95).
- Annotated GeoAI configuration example block appended to `docs/config/examples.md` and a GeoAI section added to `docs/reproducibility.md` documenting the device + torch-minor fingerprint contributions and known CUDA-determinism limits (#96, #46).
- Opt-in `.github/workflows/geoai-integration.yml` workflow gated on `terraflow/geoai_engine.py`, `tests/test_geoai_engine.py`, `terraflow/core/run_identity.py`, and the workflow file itself; installs the `[geoai,dev]` extras and runs the GeoAI + fingerprint tests under Python 3.12 (#97).
- `paper/paper.md` now describes the v0.4.0 GeoAI engine and cites `geoai-py` via a new `wu2026geoai` entry in `paper/biblio.bib` (#94).
- `terraflow.compute_geoai_fingerprint` and `terraflow.compute_run_fingerprint` re-exported at the package level for direct import.

### Changed
- `terraflow.cli` refactored: extracted a `_config_option()` annotated alias and an `_invoke()` exception-translation helper so every subcommand (`run`, `sensitivity`, `validate`, `export`, `geoai *`) shares one error ladder. Eliminates the SonarCloud duplication that gated PR #107.

### Removed
- AI usage disclosure section removed from `paper/paper.md`.

## [0.3.0] — 2026-04-23

### Added
- `climate.variogram_mode` config for kriging. The default `standard` mode keeps the existing spherical/exponential/Gaussian candidate set; `extended` mode also evaluates nested variogram candidates and records LOOCV candidate scores in `report.json`.
- Notebook `05_extended_variogram_mode.ipynb` demonstrating extended kriging variogram selection with synthetic station data.
- `raster_band` top-level config field (default `1`): selects the 1-based rasterio band for multi-band inputs (CDL stacks, Sentinel rasters) so users no longer need to pre-extract bands (#42). Out-of-range values raise `ValueError` at pipeline start-up; the selected band is captured in `manifest.json` via the config snapshot.
- `report.json` now includes an `interpolation_fallback` block with per-variable fallback-to-mean counts (`fallback_cells_by_variable`) plus the aggregate total, whenever `fallback_to_mean` is enabled (#38). A WARNING is logged for any variable whose fallback ratio exceeds 10 % of sampled cells, flagging poor spatial coverage before users read the report.
- `docs/reproducibility.md`: consolidated documentation of what the run fingerprint covers, what it excludes, known sources of non-determinism (pykrige variogram fit across scipy versions, qhull triangulation tie-breaking, BLAS-dependent summation order), cache-invalidation behaviour, and a reviewer-oriented citation and verification checklist (#46). Linked from the README and the MkDocs nav.
- `paper/biblio.bib`: added `herman2017salib` (SALib JOSS paper, doi:10.21105/joss.00097), `saltelli2008global` (Global Sensitivity Analysis: The Primer), and `cressie1993spatial` (Statistics for Spatial Data) BibTeX entries (#65). Cited in `paper/paper.md` alongside descriptions of the Ordinary Kriging climate path and the Sobol'/Morris sensitivity and spatial-validation analyses.
- `make docker-smoke` target that builds the Docker image and runs the demo pipeline with `--network none`, asserting `features.parquet`, `manifest.json`, and `report.json` land under the mounted output directory (#67). Added as a dedicated `docker-smoke-offline` job in `.github/workflows/ci.yml` so every push verifies air-gapped reproducibility.
- `paper/paper.md` rewritten to comply with the 2026 JOSS structural requirements: required sections now include Summary, Statement of Need, State of the Field, Software Design, Research Impact Statement, AI Usage Disclosure, Acknowledgements, and References (#66). The submission date is synced to the current v0.2.2 release, kriging and uncertainty quantification are described as shipped features rather than Future Work, and the JOSS-required AI usage disclosure is provided.
- `paper/paper.md` "Research impact statement" now includes a quantitative results table produced by a full end-to-end run on the bundled demo (`terraflow run`, `sensitivity`, `validate`): kriging LOOCV RMSE per climate variable, MC confidence-interval widths, Sobol' S1 / ST indices, spatial-block-CV accuracy, Cohen's κ, and Moran's I on residuals (#64). Numbers are reproducible with `make get-demo-data && terraflow run/sensitivity/validate -c examples/demo_config.yml`.

### Changed
- `examples/demo_config.yml` now uses kriging interpolation with 200-sample Monte-Carlo uncertainty propagation and samples 2 000 cells, so the demo exercises the uncertainty and sensitivity pipelines end-to-end and produces the metrics table in `paper.md` (#64).
- `data/demo_climate.csv` expanded from 5 clustered stations to 20 stations distributed across the full demo ROI, with a plausible west-to-east temperature and precipitation gradient.
- `scripts/make_demo_raster.py` now generates a 609×234 raster at 1 km pixels covering the full demo ROI (western Kansas, lon -101..-94, lat 38..40) in EPSG:5070. Previous version produced a 779×779 patch at 30 m pixels that spanned only ~23 km × 23 km in eastern Kansas — inconsistent with the configured ROI.

### Fixed
- `terraflow sensitivity` now resolves `output_dir` relative to the config file's parent directory, matching `terraflow run` (#64 discovery). Previously, a relative `output_dir` was evaluated against the caller's working directory, so `sensitivity_report.json` could land outside the project tree when invoked from the repo root with a config that used `output_dir: ../outputs/...`.

### Changed
- Removed decorative section-banner comments and self-evident inline comments throughout `pipeline.py`, `ingest.py`, `geo.py`, and `climate.py`; comments now appear only at genuinely complex logic.
- Refactored `run_pipeline()` into four extracted helpers (`_project_cells_to_wgs84`, `_score_cells`, `_apply_monte_carlo`, `_build_report`) reducing the function from 425 lines to ~130 lines of orchestration and cutting cognitive complexity below SonarQube thresholds.
- Moved `import math` inline call in `geo.py` to module-level import.

### Fixed
- ROI clipping now snaps requested bounds to an intersecting pixel window so very small ROIs avoid oversized raster reads.
- Closed resolved issues: H3-01 (#60), H3-02 (#61), H3-03 (#62), H3-04 (#63), and #40 (all implemented in prior phases).
- `ClimateInterpolator` now resolves duplicate station coordinates by averaging numeric values at initialisation instead of only warning (#43). This prevents the singular-covariance failure mode in Ordinary Kriging when input CSVs contain repeated lat/lon entries (common with aggregated NOAA summaries); resolution count is logged at INFO.
- Pipeline cache hits now verify the `terraflow_schema_version` embedded in `features.parquet` against the current `FEATURES_SCHEMA_VERSION` and re-run instead of silently returning stale artifacts when the version is mismatched or missing (#39). A WARNING log is emitted when invalidation occurs.

### Tests
- Added `TestMaxCellsBoundary` regression coverage in `tests/test_determinism.py` for `max_cells == n_valid_cells` and `max_cells > n_valid_cells`, pinning the seeded-sampling contract at the boundary (#37).

## [0.2.2] — 2026-04-12

### Added
- **H3-indexed export** (`terraflow export --format h3 -c config.yml`): re-indexes suitability results by H3 hexagonal cell for interop with DeckGL, Kepler.gl, and h3pandas. Output written to `h3_resolution_N.parquet` in the run directory. New `to_h3()` function in `terraflow.export` and `run_export()` orchestrator. Optional `[h3]` extra: `pip install terraflow-agro[h3]`.
- `ExportConfig` Pydantic model with `h3_resolution` field (validated 0–15) in `terraflow.config`.
- `export` CLI subcommand with `--format` (required), `--config`/`-c`, and optional `--resolution`/`-r` override.
- Notebook `04_h3_export.ipynb` demonstrating H3 export with synthetic data.
- **Sensitivity analysis** (`terraflow sensitivity -c config.yml`): Sobol' first-order / total-order indices and Morris elementary effects for all `ModelParams` weights via SALib. Results written to `sensitivity_report.json` in the run directory. New `sensitivity:` config block; `SensitivityConfig` in `terraflow.config`.
- **Model validation** (`terraflow validate -c config.yml`): spatial block cross-validation (Roberts et al. 2017), Cohen's kappa against an optional reference CSV, and Moran's I on score residuals. Results appended to `report.json` under `"validation"` key. New `validation:` config block; `ValidationConfig` in `terraflow.config`.
- `terraflow/sensitivity.py` — `run_sensitivity()` public API.
- `terraflow/validation.py` — `run_validation()`, `_spatial_block_cv()`, `_morans_i()`, `_compute_kappa()` public/internal API.
- `pipeline.resolve_run_dir(config_path)` — deterministic run-directory lookup without re-running the pipeline.
- `scikit-learn>=1.0` runtime dependency (BSD-3-Clause); used for `cohen_kappa_score` and `GroupKFold`.
- `SALib>=1.5` runtime dependency (MIT); used for Sobol' and Morris sampling/analysis.
- Notebooks: `02_sensitivity_analysis.ipynb`, `03_model_validation.ipynb` (also rendered in docs).
- **CRS error handling**: `CRSMismatchError` raised with both CRS strings when raster and ROI CRS disagree.
- **Variogram diagnostics block** in `report.json` (`kriging_diagnostics`) when kriging is used: model name, psill, nugget, sill, range, range units.
- **Kriging LOOCV RMSE** in `report.json` (`kriging_loocv`) per climate variable when kriging is configured.
- **Monte Carlo uncertainty coverage** in `report.json` when `uncertainty_samples` is set.
- `plotly` moved to optional `[viz]` extra (`pip install terraflow-agro[viz]`).

- **Ordinary Kriging interpolation** (`interpolation_method: "kriging"` in climate
  config): uses `pykrige.ok.OrdinaryKriging` with automatic variogram model selection
  (spherical / exponential / Gaussian) via Leave-One-Out Cross-Validation.  Requires
  ≥ 5 stations; falls back to `"linear"` with a warning for sparse networks.
- **Per-cell kriging uncertainty**: `features.parquet` gains `{var}_krig_std` columns
  (kriging prediction standard deviation) when `interpolation_method: "kriging"`.
- **Interpolation cross-validation**: `report.json` gains an `interpolation_cv` section
  with LOOCV RMSE and MAE per climate variable when kriging is configured.
- **IDW interpolation** (`interpolation_method: "idw"`): inverse distance weighting
  (power=2) as a lightweight no-dependency spatial alternative.
- `climate.interpolation_method` config field (choices: `linear` [default],
  `kriging`, `idw`); existing configs without the field default to `"linear"`.
- `pykrige>=1.7` runtime dependency (BSD-3-Clause).
- ADR-005 documenting the kriging design decision.
- Determinism regression test suite (`tests/test_determinism.py`): four tests covering
  seeded cell-set stability, score stability, fingerprint presence, and fingerprint
  stability across independent runs.
- `synthetic_climate_csv_dense` pytest fixture (8 stations) for kriging tests.
- **Homebrew tap**: `brew tap gmarupilla/terraflow && brew install terraflow` for macOS — handles GDAL and PROJ system-library installation automatically. Formula at `packaging/homebrew/Formula/terraflow.rb`.
- `publish-homebrew.yml`: auto-updates `gmarupilla/homebrew-terraflow` formula (url + sha256) on every `v*.*.*` tag push. ADR-006 documents the tap-vs-Core decision.

### Fixed
- **Reproducibility**: cell sampling in `run_pipeline` now uses a
  `numpy.random.default_rng` seeded from the SHA-256 of the run fingerprint.
  Identical inputs always produce the same cell set, closing the known limitation
  acknowledged in v0.2.1.

### Changed
- `ClimateInterpolator.__init__` accepts a new `interpolation_method` keyword argument
  (default `"linear"`, fully backward compatible).
- `paper/paper.md` reproducibility section updated: removed the "known limitation"
  paragraph, added seeded-sampling bullet; "Future Work" seeded-sampling bullet removed.

## [0.2.1] — 2026-03-15

### Fixed
- Broadened Python support floor from 3.13 to **3.10** (`requires-python`, mypy target, CI matrix now tests 3.10/3.11/3.12).
- `rasterio.CRS` has no `.equals()` method — replaced with `==` / `!=` in `geo.py` and `pipeline.py`.
- Docker build: added missing `curl` to apt deps; fixed `uv` install path (`UV_INSTALL_DIR=/usr/local/bin`); copied `data/` and `scripts/` into image; generate synthetic demo raster at build time so container runs end-to-end with no external data.

### Added
- `CITATION.cff` with both authors and ORCIDs for Zenodo/GitHub citation support.
- Deterministic run fingerprinting: `core/run_identity` module (`compute_run_fingerprint`, `hash_roi_geometry`, `fingerprint_file`).
- Shapely dependency for geometry normalisation in ROI hashing.
- Run identity tests and documentation.
- `[tool.ruff]` configuration in `pyproject.toml`; notebooks and scripts excluded from linting.
- `.dockerignore` to keep build context lean.
- CI `docker-e2e` job: builds image, runs demo pipeline, verifies `features.parquet`, `manifest.json`, `report.json`.
- Demo notebook converted from broken marimo iframe to a 30-cell Jupyter `.ipynb` rendered via `mkdocs-jupyter`.

### Changed
- README: corrected test count (127), Python badge (3.10+), CLI invocation (`terraflow --config`, not `terraflow run --config`).
- Demo raster (`data/usda_cdl.tif`) removed from git; now downloaded from USDA CropScape or generated synthetically via `make get-demo-data`.
- Removed `fly.toml` (unrelated web deployment config) and aspirational `docs/joss-readiness.md` / `docs/ard-readiness.md`.
- `.gitignore`: added `.vscode/`, `.claude/`, `.cursor/`, `.aider*`, `__marimo__/`, `test_outputs/`.

## [0.2.0] — 2026-02-24

### Added
- `DataCatalog` abstraction in `ingest`: collects CRS, bounds, nodata, dtype, shape, and SHA-256 fingerprint for each input layer without performing pixel reads.
- Schema-versioned output artifacts: `features.parquet` (v1), `manifest.json`, `report.json` written atomically under `<output_dir>/runs/<fingerprint>/`.
- `features.parquet` schema contract enforced in tests: columns `run_id`, `cell_id`, `lat`, `lon`, `v_index`, `mean_temp`, `total_rain`, `score`, `label` with stable dtypes.
- `manifest.json` records config snapshot, input fingerprints, `DataCatalog` metadata, code version, git SHA, and UTC timestamp.
- `report.json` records per-layer coverage fraction, nodata cell counts, raster and climate statistics, and per-step wall-clock timings.
- `stats` module: `RasterSummary`, `ClimateSummary`, `RunReport` Pydantic models; `summarize_raster`, `compare_rasters`, `batch_summarize` functions.
- End-to-end smoke tests using fully synthetic rasters and climate data (no external data dependency).
- Artifact contract tests covering column presence, dtype stability, label cardinality, and `run_id` linkage across artifacts.
- Architecture Decision Records: ADR-001 (band selection), ADR-002 (bbox ROI), ADR-003 (climate interpolation), ADR-004 (CRS reprojection).
- MkDocs documentation site with Material theme, deployed to GitHub Pages.
- `docs/architecture/artifacts.md` and `docs/architecture/run-identity.md` documenting output contracts.

### Changed
- `pipeline` refactored to use `DataCatalog` for metadata collection, separating ingest metadata from orchestration.
- Atomic artifact writes: each file is written to a temp path and renamed on success to prevent partial outputs.
- CRS enforcement: output cell coordinates are always WGS84 geographic degrees regardless of input raster projection.
- Pydantic v2 throughout: `PipelineConfig`, `ModelParams`, `ROI`, all stats models.

## [0.1.2] — 2025-11-29

### Fixed
- CI workflow: refined virtualenv setup, linting targets, and dependency installation steps.
- PyPI publish action updated to latest release; metadata verification disabled for initial publish.

## [0.1.1] — 2025-11-29

### Fixed
- CI workflow and Makefile: separated linting and testing steps; corrected `src` vs `terraflow` target paths.
- Removed deprecated `create_raster.py` script.

## [0.1.0] — 2025-11-25

### Added
- Initial release of TerraFlow.
- Config-driven pipeline: YAML configuration loaded and validated with Pydantic.
- Raster ingestion via `rasterio`: single-band GeoTIFF loading with nodata masking.
- ROI clipping: bounding-box windowed reads with CRS reprojection via `pyproj`.
- Climate CSV loading via `pandas`: tabular temperature and rainfall observations.
- Spatial interpolation of climate observations to raster cell centroids (`scipy.interpolate.griddata`) with nearest-neighbour fallback.
- Parametric suitability model: normalised weighted composite of vegetation index, mean temperature, and total rainfall.
- `results.csv` output with per-cell scores and categorical labels.
- CLI entry point: `terraflow -c config.yml`.
- GitHub Actions CI: lint (ruff + black) and test on push and pull request.
- Automated PyPI publishing on version tags.
- MIT License.
