# Technology Stack — New Dependencies

**Project:** TerraFlow (terraflow-agro)
**Scope:** Additions for Stage 3 (sensitivity analysis), spatial cross-validation, H3 export, CRS hardening, and JOSS packaging compliance
**Researched:** 2026-03-18
**Confidence note:** WebSearch, WebFetch, and shell tools were unavailable during research. All version assertions are based on training knowledge (cutoff August 2025) and the existing pyproject.toml. Versions MUST be verified with `pip index versions <package>` or PyPI before pinning in pyproject.toml.

---

## Existing Stack (Established — Do Not Replace)

| Technology | Pinned Floor | Role |
|------------|-------------|------|
| Python | 3.10+ | Runtime |
| Pydantic | 2.0+ | Config validation |
| rasterio | 1.2.0+ | Raster I/O |
| PyKrige | 1.7+ | Kriging interpolation |
| numpy | 1.21.0+ | Numerical core |
| scipy | 1.9.0+ | griddata, stats |
| pandas | 1.3.0+ | Tabular output |
| pyarrow | 14.0+ | Parquet serialization |
| shapely | 2.0.0+ | Geometry |
| pyproj | 3.0+ | CRS transformation |
| Typer | not pinned | CLI |
| pytest | 7.0+ | Testing |
| setuptools + build | 64+ | Packaging |

---

## New Dependencies — Recommended Stack

### 1. Sensitivity Analysis / Variance Decomposition

**Recommended: SALib**

| Library | Version Floor | License | Purpose |
|---------|--------------|---------|---------|
| SALib | 1.5.0+ | MIT | Sobol' indices (S1, ST), Morris screening, Saltelli sampler |

**Confidence: MEDIUM** — Version 1.4 was stable as of 2023; 1.5 was released with refactored API in 2023-2024. Training data supports this; version must be verified before pinning.

**Why SALib:**
- The canonical Python library for global sensitivity analysis (GSA). Cited in Saltelli et al. (2008) and Herman & Usher (2017, JOSS). Using SALib gives TerraFlow a citable, peer-reviewed SA method.
- Implements exactly the two methods in scope: Saltelli sampler + Sobol' analysis and Morris elementary effects screening.
- MIT license is compatible with TerraFlow's MIT license. No license friction.
- Pure Python over numpy/scipy. No GDAL or C extension dependencies. Safe install on all platforms.
- Actively maintained with JOSS paper (doi:10.21105/joss.00097) — reviewers will recognize the citation.
- The `SALib.analyze.sobol` + `SALib.sample.saltelli` workflow is stable and well-documented.

**Why not alternatives:**
- `chaospy`: Polynomial chaos expansion, not variance decomposition. Over-engineered for weight sensitivity.
- `sensitivity` (standalone): Unmaintained, no JOSS citation, not widely used in ag literature.
- Implementing Sobol from scratch: Violates the principle of standing on cited, reviewed implementations. A JOSS reviewer would flag home-grown SA.

**Version verification command (run before pinning):**
```
pip index versions SALib
```

**API surface TerraFlow will use:**
```python
from SALib.sample import saltelli
from SALib.analyze import sobol
# or for Morris:
from SALib.sample import morris as morris_sample
from SALib.analyze import morris as morris_analyze
```

**Note on SALib 1.5 API change:** SALib 1.4 → 1.5 introduced a problem-dict API change where `analyze()` returns a `ResultDict` with `.to_df()`. If the installed version is 1.5+, use the new API; if 1.4, use the old dict-based return. Pin to `>=1.4` and write version-conditional code, or pin to `>=1.5` and use the new API throughout. Recommend pinning `>=1.4.6` minimum, preferring `>=1.5` for the cleaner `.to_df()` output which maps well into `sensitivity_report.json`.

---

### 2. Spatial Cross-Validation for Kriging

**Recommended: No new library — implement LOOCV directly using PyKrige**

**Confidence: HIGH** — PyKrige's OrdinaryKriging already supports LOOCV via its `.execute()` call pattern. No external CV framework is needed for geostatistical LOOCV.

**Why no new library:**
- PyKrige `OrdinaryKriging` can be run in leave-one-out mode by withholding one point at a time and predicting at its location. This is 10–20 lines of Python using existing dependencies.
- Adding `scikit-learn` or `scikit-gstat` for LOOCV would add a large transitive dependency (scikit-learn pulls in `joblib`, `threadpoolctl`, etc.) for a task that PyKrige already enables.
- JOSS reviewers expect simple, auditable implementations. A hand-rolled LOOCV loop over stations is more transparent than a framework's cross-validation machinery.

**LOOCV implementation pattern (no new dependency):**
```python
import numpy as np
from pykrige.ok import OrdinaryKriging

def loocv_kriging(x, y, z, variogram_model="spherical"):
    errors = []
    for i in range(len(z)):
        mask = np.ones(len(z), dtype=bool)
        mask[i] = False
        ok = OrdinaryKriging(x[mask], y[mask], z[mask],
                             variogram_model=variogram_model)
        pred, _ = ok.execute("points", [x[i]], [y[i]])
        errors.append(float(pred[0]) - z[i])
    return np.array(errors)
```

**Optional addition: scikit-gstat** (only if variogram diagnostics beyond PyKrige are needed)

| Library | Version Floor | License | Purpose |
|---------|--------------|---------|---------|
| scikit-gstat | 1.0.0+ | MIT | Variogram fitting diagnostics, nugget/sill/range decomposition, directional variogram |

**Confidence: LOW** — scikit-gstat is an active library but niche. Version confirmed as active through 2024; exact current version not verified. Only add if PyKrige's variogram report output is insufficient for reviewers.

**Decision rule:** Start without scikit-gstat. If JOSS reviewers ask for richer variogram diagnostic output (directional variograms, variogram model goodness-of-fit plots), add it in a follow-up PR.

---

### 3. H3 Hexagonal Grid Indexing and Export

**Recommended: h3**

| Library | Version Floor | License | Purpose |
|---------|--------------|---------|---------|
| h3 | 3.7.0+ | Apache-2.0 | H3 cell indexing, lat/lon to H3 cell ID, H3 cell to GeoJSON polygon |

**Confidence: MEDIUM** — h3-py 3.x was the stable series as of 2024; h3-py 4.0 was in development with a breaking API change. Version floor and which series to target must be verified before pinning.

**Why h3 (Uber's H3 library):**
- The canonical Python binding for Uber's H3 hierarchical hexagonal geospatial indexing. No competitor exists — H3 is the standard for hex-indexed geospatial exports.
- Apache-2.0 license is compatible with TerraFlow's MIT license.
- Maps cleanly to TerraFlow's use case: each pixel centroid (lat/lon) → `h3.geo_to_h3(lat, lon, resolution)` → H3 cell ID string added as a column in `features.parquet`.
- The H3 cell ID column enables direct interop with DeckGL's `H3HexagonLayer`, `pandas-h3`, `duckdb` spatial functions, and any H3-native tool.

**Critical API version decision:**

h3-py 3.x uses the legacy API:
```python
import h3
cell_id = h3.geo_to_h3(lat, lon, resolution)       # returns string
boundary = h3.h3_to_geo_boundary(cell_id)           # returns polygon vertices
```

h3-py 4.x uses a new API:
```python
import h3
cell_id = h3.latlng_to_cell(lat, lon, resolution)   # renamed
boundary = h3.cell_to_boundary(cell_id)              # renamed
```

**Recommendation:** Pin to `>=3.7.0,<4.0` if h3 4.0 is not yet stable on PyPI, or pin to `>=4.0` if it has been released with stable API. Verify with `pip index versions h3` before committing to either. Use a thin adapter function inside TerraFlow so that only one module needs to change if h3 4.x is adopted later.

**Why not alternatives:**
- `h3pandas`: A pandas extension for H3. Adds a layer on top of h3-py. Unnecessary — TerraFlow can call h3 directly in the export module. Adding h3pandas adds a dependency without adding functionality beyond what 5 lines of pandas code achieves.
- Custom hex grids: Not H3-compatible. Defeats the interop purpose.

**Integration pattern for TerraFlow:**
```python
# In terraflow/export.py or appended in pipeline.py artifact write
import h3

H3_RESOLUTION = 7  # ~1.2 km edge length; configurable via pipeline config

def add_h3_index(df: pd.DataFrame, resolution: int = H3_RESOLUTION) -> pd.DataFrame:
    df["h3_index"] = df.apply(
        lambda row: h3.geo_to_h3(row["lat"], row["lon"], resolution), axis=1
    )
    return df
```

The `h3_index` column goes into `features.parquet` alongside existing suitability columns, with resolution stored in `manifest.json` for provenance.

---

### 4. CRS Validation — No New Library

**Recommended: Harden pyproj usage — no additional dependency**

**Confidence: HIGH** — pyproj 3.0+ already provides all the CRS comparison and introspection primitives needed. The gap is usage patterns, not missing library functionality.

**Why no new library:**
pyproj's `CRS` class already supports:
- `CRS.from_user_input()` for safe parsing of EPSG codes, WKT, proj strings
- `CRS.equals()` for semantic CRS equality (not string comparison)
- `CRS.is_geographic` / `CRS.is_projected` for axis type checks
- `CRS.axis_info` for unit introspection (meters vs degrees)
- `Transformer.from_crs(src, dst, always_xy=True)` for safe reprojection

The real fix is replacing the broad `except Exception` handlers in `geo.py` and `pipeline.py` with `pyproj.exceptions.CRSError` catches and informative error messages that include the mismatched CRS strings.

**Pattern for informative CRS errors:**
```python
from pyproj import CRS
from pyproj.exceptions import CRSError

def validate_crs_match(raster_crs: CRS, config_crs: CRS, source: str) -> None:
    if not raster_crs.equals(config_crs):
        raise ValueError(
            f"CRS mismatch in {source}: "
            f"raster has '{raster_crs.to_epsg() or raster_crs.name}', "
            f"config expects '{config_crs.to_epsg() or config_crs.name}'. "
            f"Reproject the raster or update the config CRS."
        )
```

---

### 5. JOSS-Compliant Scientific Python Packaging

**Recommended: No new tooling — harden existing setup**

**Confidence: HIGH** — TerraFlow's existing setuptools + pyproject.toml + build stack already meets JOSS requirements. The gaps are configuration completeness, not missing tools.

**What JOSS actually requires (per JOSS submission guidelines):**
1. Software installable via standard means (`pip install terraflow-agro`) — already done.
2. Tests runnable by an independent reviewer (`pip install .[dev] && pytest`) — already done.
3. Documentation accessible — MkDocs site already exists.
4. License file present — MIT, present.
5. `CITATION.cff` present — added in PR #24.
6. Archive on Zenodo or similar — must be done at submission time (separate from code).

**What to harden (no new libraries needed):**

| Gap | Fix | Confidence |
|-----|-----|------------|
| `pyproject.toml` version floors are permissive (e.g., `numpy>=1.21`) | Tighten to reflect what is actually tested in CI matrix | HIGH |
| `[project.optional-dependencies]` has `dev` but no `test` extra | Split into `test` extra so reviewers can install just test deps | HIGH |
| `plotly` is in core `dependencies` but is a visualization tool | Move to `[optional-dependencies].viz` — reviewers doing headless installs will not want plotly | MEDIUM |
| No `classifiers` in `pyproject.toml` | Add PyPI trove classifiers (Programming Language :: Python :: 3.10, etc.) | MEDIUM |
| `project.urls` only has Homepage and Bug Tracker | Add `Documentation` and `Changelog` URLs | LOW |

**On build backend:** setuptools 64+ is fine. Do not switch to Hatchling, Flit, or Poetry for this project. The migration cost is not justified, and setuptools is the most widely understood by JOSS reviewers.

**On `uv` as package manager:** uv is a build tool accelerator, not a packaging format. The published package is a standard wheel/sdist. JOSS reviewers use pip. Ensure `pip install terraflow-agro[dev]` works without uv present. This is currently true — preserve it.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Sensitivity analysis | SALib | chaospy | chaospy is PCE/quadrature, not global SA; no JOSS paper to cite |
| Sensitivity analysis | SALib | Home-grown Sobol | No citable implementation; JOSS reviewer will flag |
| Spatial CV | PyKrige LOOCV (custom) | scikit-learn cross_val_score | Adds large dependency for a 15-line LOOCV loop; not geostatistical-aware |
| Spatial CV | PyKrige LOOCV (custom) | scikit-gstat | Adds dependency; only needed if variogram diagnostics are insufficient |
| H3 export | h3 | h3pandas | h3pandas adds dependency without adding functionality TerraFlow needs |
| H3 export | h3 | Custom hex grid | Not H3-compatible; defeats interop purpose |
| CRS validation | pyproj (existing) | fiona CRS utilities | fiona is already a rasterio dependency but not directly used; no gain |
| Packaging | setuptools (existing) | Hatchling / Flit | Migration cost unjustified; setuptools is well-understood by reviewers |

---

## Installation

```bash
# Core additions (add to pyproject.toml [project.dependencies])
pip install "SALib>=1.4.6"
pip install "h3>=3.7.0"   # verify current series before pinning

# No new dev/test additions needed for these features
```

**pyproject.toml additions:**
```toml
[project.dependencies]
# ... existing ...
"SALib>=1.4.6",
"h3>=3.7.0",          # verify exact floor and upper bound before release

[project.optional-dependencies]
dev = [
  # ... existing ...
]
# New: move plotly out of core
viz = [
  "plotly>=5.0.0",
]
```

---

## Dependency Size and Safety Assessment

| Library | Transitive deps | License | Install size (approx) | Safety |
|---------|----------------|---------|----------------------|--------|
| SALib | numpy (already present) | MIT | ~3 MB | Safe; no C extensions beyond numpy |
| h3 | C extension (H3 C library compiled) | Apache-2.0 | ~5–10 MB | Safe; ships compiled wheels for all major platforms |

h3 ships binary wheels on PyPI for Linux/macOS/Windows x86_64 and arm64. It should install cleanly in TerraFlow's Docker image (python:3.11-slim) without GDAL or other native library prerequisites.

---

## Version Verification Checklist

Run these before updating pyproject.toml:

```bash
pip index versions SALib         # verify >=1.4.6 is current; confirm 1.5 API
pip index versions h3             # verify which major version series is stable (3.x vs 4.x)
pip index versions scikit-gstat   # verify only if adding for variogram diagnostics
```

Specific things to check:
- **SALib**: Is 1.5.x the stable release? If yes, pin `>=1.5` and use `.to_df()` API.
- **h3**: Is 4.0 released and stable? If yes, use `latlng_to_cell` / `cell_to_boundary` API. If 4.0 is still pre-release, pin `>=3.7.0,<4.0`.

---

## Sources

**Confidence levels:**
- SALib method: HIGH — backed by Saltelli et al. (2008) GSA textbook; Herman & Usher (2017) JOSS paper doi:10.21105/joss.00097; library in continuous use across scientific computing community since 2015.
- SALib version: MEDIUM — training knowledge through August 2025; must verify current release.
- H3 library identity: HIGH — Uber H3 is the only hex indexing standard; h3-py is the canonical Python binding; no competitor.
- H3 version series: MEDIUM — 3.x → 4.x transition was underway as of training cutoff; must verify current stable series.
- LOOCV via PyKrige: HIGH — PyKrige's API is stable and the LOOCV pattern is standard geostatistical practice (Cressie 1993).
- CRS hardening via pyproj: HIGH — pyproj 3.0+ CRS primitives are well-documented and stable.
- JOSS packaging requirements: HIGH — based on JOSS submission guidelines (joss.theoj.org/about#submission_requirements), stable since 2018.
- scikit-gstat as optional: LOW — niche library; version and maintenance status must be verified independently.
