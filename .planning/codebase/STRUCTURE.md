# STRUCTURE.md — TerraFlow Directory Layout

## Top-Level Layout

```
TerraFlow/
├── terraflow/              # Main Python package
│   ├── __init__.py         # Package entry point, version export
│   ├── cli.py              # Typer CLI entry point
│   ├── pipeline.py         # Pipeline orchestrator
│   ├── config.py           # Pydantic config models (TerraFlowConfig, ModelParams, etc.)
│   ├── ingest.py           # Raster/CSV ingestion utilities
│   ├── geo.py              # Geospatial operations (reprojection, masking, sampling)
│   ├── climate.py          # Climate interpolation (IDW + kriging)
│   ├── model.py            # Suitability scoring + Monte Carlo uncertainty
│   ├── stats.py            # Raster statistics + QA summaries
│   ├── utils.py            # Shared utilities (bbox, CRS helpers, nodata)
│   ├── viz.py              # Visualization helpers
│   └── core/
│       ├── __init__.py
│       └── run_identity.py # Deterministic run fingerprinting
│
├── tests/                  # pytest test suite
│   ├── conftest.py         # Shared fixtures (synthetic raster, climate CSV)
│   ├── data/               # Small static test data (README.md)
│   ├── smoke_test.py       # Real-data smoke tests (skipped if data absent)
│   ├── test_artifacts.py   # Artifact contract tests (parquet, JSON schemas)
│   ├── test_cli.py         # CLI command tests
│   ├── test_climate.py     # ClimateInterpolator unit + integration tests
│   ├── test_config.py      # Config validation tests
│   ├── test_determinism.py # Determinism regression tests
│   ├── test_e2e_smoke.py   # End-to-end smoke tests (synthetic data)
│   ├── test_geo.py         # Geo operations tests
│   ├── test_ingest.py      # Ingest tests
│   ├── test_model.py       # Model scoring tests
│   ├── test_pipeline.py    # Pipeline integration tests
│   ├── test_run_identity.py # Run fingerprint tests
│   ├── test_stats.py       # Stats tests
│   ├── test_uncertainty.py # MC uncertainty propagation tests
│   ├── test_utils.py       # Utility tests
│   └── test_viz.py         # Visualization tests
│
├── docs/                   # MkDocs documentation
│   ├── index.md            # Landing page
│   ├── quickstart.md
│   ├── field-guide.md
│   ├── ROADMAP.md
│   ├── DEVELOPMENT.md
│   ├── contributing.md
│   ├── api/                # API reference stubs
│   │   ├── climate.md
│   │   ├── core.md
│   │   └── ingest.md
│   ├── architecture/       # ADRs and architecture docs
│   │   ├── adr-001-band-selection.md
│   │   ├── adr-002-bbox-roi.md
│   │   ├── adr-003-climate-interpolation.md
│   │   ├── adr-004-crs-reprojection.md
│   │   ├── adr-005-kriging-interpolation.md
│   │   ├── artifacts.md
│   │   ├── boundaries.md
│   │   ├── overview.md
│   │   └── run-identity.md
│   ├── cli/
│   │   └── usage.md
│   ├── config/
│   │   ├── examples.md
│   │   └── schema.md
│   ├── notebooks/          # Marimo + Jupyter demonstration notebooks
│   └── stylesheets/
│       └── extra.css
│
├── paper/                  # JOSS paper submission
│   ├── paper.md            # Main manuscript
│   ├── biblio.bib          # Bibliography
│   ├── figure1.jpeg        # Architecture figure
│   ├── figure2.jpeg        # Pipeline figure
│   ├── figure3.png         # Results figure
│   ├── figure1_architecture.mmd  # Mermaid source
│   ├── figure2_pipeline.mmd
│   ├── mermaid-config.json
│   └── plots.py            # Figure generation script
│
├── data/                   # Demo input data
│   ├── README.md           # Instructions for downloading USDA CDL raster
│   └── demo_climate.csv    # Sample climate station data
│
├── examples/
│   └── demo_config.yml     # Example TerraFlow config
│
├── outputs/
│   └── demo_run/
│       └── results.csv     # Demo output
│
├── test_outputs/           # Exploratory test artifacts (not in pytest suite)
│   ├── climate_comparison_v0.1_vs_v0.2.0.png
│   ├── climate_index_matching_results.csv
│   ├── climate_spatial_interpolation_results.csv
│   ├── climate_variables.png
│   ├── raster_bands_overview.png
│   └── test_data/
│       └── kansas_climate_stations.csv
│
├── scripts/
│   └── make_demo_raster.py # Script to generate synthetic demo raster
│
├── .github/
│   └── workflows/          # CI/CD GitHub Actions
│
├── .planning/              # GSD planning artifacts
│   └── codebase/           # This directory
│
├── pyproject.toml          # Project metadata, deps, tool configs (Ruff, mypy, pytest)
├── Makefile                # Common dev tasks (test, lint, docs, demo)
├── mkdocs.yml              # MkDocs site config
├── Dockerfile              # Container image definition
├── .dockerignore
├── .pre-commit-config.yaml # Pre-commit hooks (Ruff, Black, mypy)
├── sonar-project.properties # SonarCloud config
├── CHANGELOG.md
├── CITATION.cff            # Software citation metadata
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── LICENSE
├── README.md
└── license-report.md
```

## Key Locations by Function

| Purpose | Location |
|---|---|
| Add a new pipeline stage | `terraflow/pipeline.py` — insert into `Pipeline.run()` |
| Add a CLI command | `terraflow/cli.py` — add Typer command |
| Add config parameters | `terraflow/config.py` — extend Pydantic models |
| Add geospatial operations | `terraflow/geo.py` |
| Add climate interpolation methods | `terraflow/climate.py` — `ClimateInterpolator` |
| Add scoring methods | `terraflow/model.py` |
| Add statistics/QA | `terraflow/stats.py` |
| Add output artifacts | `terraflow/pipeline.py` + `terraflow/core/run_identity.py` |
| Write tests | `tests/test_<module>.py` |
| Write shared fixtures | `tests/conftest.py` |
| Add architecture docs | `docs/architecture/` |
| Update CLI docs | `docs/cli/usage.md` |
| Update config docs | `docs/config/schema.md` |

## Naming Conventions

- **Modules**: `snake_case.py` matching their functional domain (`climate.py`, `geo.py`)
- **Test files**: `test_<module>.py` mirroring the module they test
- **Classes**: `PascalCase` (e.g., `ClimateInterpolator`, `TerraFlowConfig`, `Pipeline`)
- **Functions**: `snake_case` (e.g., `load_climate_csv`, `reproject_raster`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MIN_KRIGING_STATIONS`)
- **Type aliases**: `PascalCase` or descriptive names (e.g., `BBox`, `CRSLike`)
- **Test classes**: `TestFeatureName` grouping related test functions
- **Test functions**: `test_<behaviour>_<condition>` (e.g., `test_init_spatial_strategy_valid`)

## Special Directories

- `tests/data/` — small, committed static test data only; large/binary data downloaded via `make get-demo-data`
- `.planning/codebase/` — GSD codebase map (this directory); not shipped to users
- `paper/` — JOSS manuscript; figures generated by `paper/plots.py`
- `test_outputs/` — exploratory outputs from manual testing; not part of automated suite
- `outputs/` — default pipeline output directory; `.gitignore`d except demo results
