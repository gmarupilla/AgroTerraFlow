# External Integrations

**Analysis Date:** 2026-03-18

## APIs & External Services

**None configured.** TerraFlow is a standalone scientific workflow with no remote API dependencies. All data comes from local files (rasters, CSVs).

## Data Storage

**Databases:**
- None — data is persisted as local files only

**File Storage:**
- **Local filesystem only**
  - Input: GeoTIFF rasters (`rasterio.open()`) and CSV climate data
  - Output: Parquet (`features.parquet`), JSON (`manifest.json`, `report.json`), CSV (`results.csv`)
  - All files written to `output_dir/runs/<run_fingerprint>/`

**Caching:**
- None — no caching layer; computation is deterministic and reproducible

## Authentication & Identity

**Auth Provider:**
- None — no user authentication required
- Single-user CLI application with local file access
- All pipeline runs identified by content-based fingerprint (SHA256), not user credentials

## Monitoring & Observability

**Error Tracking:**
- None — errors logged to stderr and captured in pipeline exception handling

**Logs:**
- **Framework:** Python `logging` module (`terraflow.utils.logger`)
- **Destination:** Console (stdout/stderr) during CLI execution
- **No remote log aggregation**
- Structured JSON output in `report.json` and `manifest.json` for audit/provenance

## CI/CD & Deployment

**Hosting:**
- Not applicable — TerraFlow is a command-line package distributed via PyPI
- Package published to Python Package Index (PyPI) via GitHub Actions workflow
- See: `.github/workflows/publish-pypi.yml`

**CI Pipeline:**
- **GitHub Actions** (`.github/workflows/`)
  - `ci.yml` - Python 3.10/3.11/3.12 testing on Ubuntu, Docker end-to-end test
  - `quality.yml` - Type checking, linting, formatting
  - `license-check.yml` - Dependency license audit
  - `docs.yml` - MkDocs site generation
  - `security.yml` - Vulnerability scanning
  - `docs-preview.yml` - Preview builds for PRs touching docs/
  - `manuscript.yml` - JOSS paper compilation via Docker
  - `publish-pypi.yml` - Release automation to PyPI
  - `.github/dependabot.yml` - Automated dependency updates

**Deployment:**
- CLI: `pip install terraflow-agro` — users run locally
- Docker: `docker build -t terraflow:latest` + `docker run` for reproducible environments
- Source distribution: `pyproject.toml` → setuptools → wheel + sdist

## Environment Configuration

**Required env vars:**
- None — TerraFlow requires no environment variables to function
- All configuration is explicit in YAML files supplied via `-c/--config` CLI flag

**Secrets location:**
- No secrets management — TerraFlow is designed for scientific reproducibility without API keys/tokens
- All inputs are local files; all outputs are local files

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Data Format Specifications

**Input Rasters:**
- Format: GeoTIFF (COG-compatible preferred)
- Supported by: `rasterio.open()` (via GDAL)
- CRS: Any EPSG code or WKT string (auto-transformed to match ROI CRS)
- Multi-band: Band 1 read only
- Nodata handling: Respects raster's nodata sentinel value

**Input Climate CSV:**
- Format: Plain CSV (pandas-readable)
- Required columns: `lat`, `lon`, `mean_temp`, `total_rain`
- Coordinate system: WGS84 (EPSG:4326) — lat/lon in degrees

**Output Features (Parquet):**
- Format: Apache Parquet (via PyArrow backend)
- Columns (schema v1): run_id, cell_id, lat, lon, v_index, mean_temp, total_rain, score, label
- Optional columns with kriging: `mean_temp_krig_std`, `total_rain_krig_std`
- Optional uncertainty columns: `score_ci_low`, `score_ci_high` (with Monte Carlo)
- Compression: Snappy (default PyArrow)

**Output Manifest (JSON):**
- Config snapshot (canonical JSON)
- Run identity (fingerprint, start/end time)
- Input provenance (file paths, SHA256 hashes, sizes)
- Provenance sources: `DataCatalog.to_provenance()` in `terraflow/ingest.py`

**Output Report (JSON):**
- QA metrics (coverage %, valid cell counts)
- Climate interpolation CV metrics (if kriging used)
- Step timings (raster load, interpolation, suitability, write)
- Schema version, timestamp

## Integration Boundaries

**Filesystem Read:**
- `rasterio.open(raster_path)` — reads GeoTIFF with metadata
- `pd.read_csv(climate_csv_path)` — reads climate CSV
- `yaml.safe_load()` — parses YAML config

**Filesystem Write:**
- `features_df.to_parquet()` — via PyArrow
- `json.dump()` — manifest and report
- Backward compat: `results.csv` via pandas

**Geospatial Transforms:**
- `pyproj.Transformer` — CRS conversions
- `rasterio.transform` — pixel-to-geographic coordinate mapping
- `shapely.geometry.box()` — ROI geometry creation

**Scientific Computation:**
- `scipy.interpolate.griddata()` — linear interpolation (default)
- `pykrige.OrdinaryKriging()` — kriging (optional, requires ≥5 stations)
- Variogram models: spherical, exponential, gaussian (auto-selected via LOOCV)

---

*Integration audit: 2026-03-18*
