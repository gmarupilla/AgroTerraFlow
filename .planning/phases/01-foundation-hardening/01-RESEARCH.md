# Phase 1: Foundation Hardening - Research

**Researched:** 2026-03-26
**Domain:** Python geospatial pipeline hardening — CRS error handling, PyKrige diagnostics, test coverage, pyproject.toml packaging
**Confidence:** HIGH

## Summary

Phase 1 addresses four concrete, independently scoped changes to TerraFlow:
(1) replace broad `except Exception` and implicit failure modes with a custom `CRSMismatchError` that names both CRS strings; (2) surface PyKrige variogram parameters (nugget, sill, range, model) in `report.json`; (3) add targeted test coverage for three missing branch families (kriging fallback, MC zero-variance, MC single-sample); and (4) demote `plotly` from a core dependency to an optional `[viz]` extra and add PyPI packaging metadata.

The test suite is already at 87.32% branch coverage (above the 85% threshold), so HARD-02 is a targeted gap-fill, not a coverage sprint. The biggest implementation effort is HARD-01 because it requires defining a new exception class, wiring a CRS validation guard into the pipeline before interpolation begins, and adding test fixtures that exercise it. HARD-03 requires no code changes to PyKrige itself — only reading `ok.variogram_model_parameters` (which follows `[psill, range, nugget]` order for all three supported models) and writing those values into `report.json` at artifact-write time. HARD-04 is a `pyproject.toml`-only edit.

**Primary recommendation:** Implement in order HARD-04 (pure TOML, zero risk), HARD-03 (read parameters from `ok` object already in scope in `_interpolate_kriging`, pass back through `ClimateInterpolator`), HARD-02 (add three test functions targeting specific uncovered branches), then HARD-01 (new exception class + guard).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HARD-01 | Raise `CRSMismatchError` with informative message (including both CRS strings) when raster and climate CRS are incompatible — replace broad `except Exception` handlers | CRS guard must be added in `pipeline.py` before cell-coordinate reprojection; `CRSMismatchError` can subclass `pyproj.exceptions.CRSError`; both CRS strings are available at `raster_crs` and `CRS.from_epsg(4326)` |
| HARD-02 | Test suite covers kriging fallback (< MIN_KRIGING_STATIONS), MC zero-variance, and MC single-sample edge cases | Coverage gap confirmed at `climate.py:308-316` (fallback branch) and `pipeline.py` MC branches; fixtures needed: sparse climate CSV (2 stations), zero-std krig_std column, single-cell raster |
| HARD-03 | `report.json` includes `kriging_diagnostics` block with nugget, sill, range_, model when kriging used | PyKrige `ok.variogram_model_parameters` is `[psill, range, nugget]` (verified from source); sill = psill + nugget; must pass `ok` params through `_interpolate_kriging` return and up to `pipeline.py` report builder |
| HARD-04 | `plotly` moved to optional `[viz]` extra; trove classifiers and Documentation URL added to `pyproject.toml` | `plotly>=5.0.0` currently in core `dependencies`; must move to `[project.optional-dependencies]` `viz` key; `terraflow/viz.py` uses plotly — needs guard; trove classifiers and URL are pure TOML additions |
</phase_requirements>

## Standard Stack

### Core (all already installed, no new deps needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pykrige | 1.7.3 | Kriging interpolation | Already in use; `ok.variogram_model_parameters` is the stable attribute for variogram params |
| pyproj | 3.7.2 | CRS definitions and transformations | Standard in geospatial Python; `pyproj.exceptions.CRSError` is the canonical base class |
| pytest | 7.x+ | Test framework | Already configured in pyproject.toml |
| pytest-cov | 7.0.0 | Branch coverage | Already configured with `fail_under = 85` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| plotly | 5.24.1 | Optional visualization | Only when `terraflow[viz]` is installed; `viz.py` must guard the import |

### No New Dependencies Needed
All four requirements can be satisfied by modifying existing code and configuration. No `pip install` changes are needed except demoting plotly.

## Architecture Patterns

### Pattern 1: Custom Exception Subclassing `pyproj.exceptions.CRSError`

**What:** Define `CRSMismatchError(pyproj.exceptions.CRSError)` in `terraflow/geo.py` or a new `terraflow/exceptions.py`. Raise it proactively in `pipeline.py` when the raster CRS cannot be transformed to WGS84 for climate matching.

**When to use:** The climate CSV always carries WGS84 lat/lon (no CRS metadata). The raster can be in any CRS. The pipeline already reprojects cell coordinates to WGS84 at `pipeline.py:475-483`. The guard should sit before that block — validate that `raster_crs` can produce a valid `Transformer` to EPSG:4326 and that the raster CRS is not None/invalid.

**Exact trigger scenario:** A raster with `raster.crs = None` or a broken/incompatible CRS (e.g., a local engineering CRS with no well-defined relationship to WGS84) would silently produce garbage lat/lon values. The `CRSMismatchError` message must include both CRS strings.

**Example:**
```python
# In terraflow/exceptions.py (new file) or terraflow/geo.py
from pyproj.exceptions import CRSError

class CRSMismatchError(CRSError):
    """Raised when raster CRS and climate data CRS are incompatible."""
    pass
```

```python
# In pipeline.py — after raster_crs is read, before coordinate reprojection
_climate_crs = CRS.from_epsg(4326)  # climate CSV is always WGS84
if raster.crs is None:
    raise CRSMismatchError(
        f"Raster has no CRS. Cannot reproject to climate CRS "
        f"(EPSG:4326). Raster CRS: None, climate CRS: EPSG:4326"
    )
try:
    Transformer.from_crs(raster_crs, _climate_crs, always_xy=True)
except CRSError as exc:
    raise CRSMismatchError(
        f"Raster CRS '{raster_crs.to_wkt()}' is incompatible with climate CRS "
        f"'{_climate_crs.to_wkt()}': {exc}"
    ) from exc
```

**Important note:** `geo.py` already has a bare `except Exception as e` at line 88 wrapping `from_bounds()`. That specific handler wraps a `rasterio` operation (window calculation), not a CRS operation — it should be narrowed to specific rasterio exceptions but is not the primary CRS mismatch target. The main CRS guard belongs in `pipeline.py`.

### Pattern 2: Surfacing Variogram Parameters in report.json (HARD-03)

**What:** PyKrige `OrdinaryKriging.variogram_model_parameters` is always `[psill, range, nugget]` for spherical, exponential, and gaussian models (confirmed from source). The sill (total variance) equals `psill + nugget`.

**Where the ok object lives:** `_interpolate_kriging` in `climate.py` creates `ok` per variable (lines 521-528). The variogram parameters are the same for all variables because the same `self._krig_variogram_model` is used. Parameters are read from the FIRST `ok` object constructed.

**How to surface:** Extend `ClimateInterpolator` to store variogram params after the first `ok` construction, then have `pipeline.py` read them and write to `report.json`.

**Option A (clean):** Add `self.variogram_params: dict` attribute to `ClimateInterpolator`. Populate it in `_interpolate_kriging` on first iteration:
```python
ok = OrdinaryKriging(...)
if not hasattr(self, '_variogram_params_extracted'):
    p = ok.variogram_model_parameters  # [psill, range, nugget]
    self.variogram_params = {
        "nugget": float(p[2]),
        "psill": float(p[0]),
        "sill": float(p[0]) + float(p[2]),
        "range_": float(p[1]),
        "model": self._krig_variogram_model,
    }
    self._variogram_params_extracted = True
```

**Alternative (simpler):** Expose params from `_init_kriging` using a full-data ok fit (no LOOCV overhead since we already call LOOCV per variable). The init already selects the best model and calls LOOCV — just store params then.

**Recommendation:** Option B — fit one full `ok` in `_init_kriging` after model selection and read params once. Avoids coupling `_interpolate_kriging` to a side-effectful attribute population.

**report.json block target:**
```json
"kriging_diagnostics": {
    "model": "spherical",
    "nugget": 0.383,
    "psill": 7.292,
    "sill": 7.676,
    "range_": 0.0158,
    "range_units": "degrees"
}
```

**Range units note:** PyKrige in `euclidean` mode (the default, which is what this codebase uses) computes distances in the same units as the input coordinates. Since inputs are WGS84 decimal degrees, `range_` is in degrees. This is a known limitation that should be documented in `report.json` with a `range_units` field (e.g., `"degrees_geographic"`) and in the README/paper Methods. The STATE.md explicitly flags this as a blocker: "Variogram range units (degrees vs UTM reproject) must be resolved before Phase 1 closes." The research recommendation is: document the degree-unit limitation in `report.json` and the paper; do NOT reproject to UTM in Phase 1 (that is a v2 enhancement per REQUIREMENTS.md GEO-03).

### Pattern 3: Optional Dependency Guard for viz.py (HARD-04)

**What:** `plotly` must become an optional `[viz]` extra. `terraflow/viz.py` currently uses plotly at module level. The guard must prevent `ImportError` at import time when plotly is not installed.

**Pattern:**
```python
# In terraflow/viz.py — top of file
try:
    import plotly.graph_objects as go  # type: ignore[import]
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

def plot_suitability_map(df, ...):
    if not _PLOTLY_AVAILABLE:
        raise ImportError(
            "plotly is required for visualization. "
            "Install with: pip install terraflow[viz]"
        )
    ...
```

**pyproject.toml changes needed:**
1. Remove `"plotly>=5.0.0"` from `dependencies`
2. Add `[project.optional-dependencies]` `viz = ["plotly>=5.0.0"]`
3. Add `classifiers` array with PyPI trove classifiers
4. Add `Documentation` URL to `[project.urls]`

**Standard trove classifiers for a scientific Python geospatial library:**
```toml
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: GIS",
    "Topic :: Scientific/Engineering :: Information Analysis",
    "Operating System :: OS Independent",
]
```

**Documentation URL:** The project uses MkDocs (`mkdocs.yml` present). The published docs URL should be `https://gmarupilla.github.io/AgroTerraFlow/` (GitHub Pages convention). Confirm actual URL before writing.

### Pattern 4: MC Edge Case Tests (HARD-02)

**What:** Three specific test families are needed to close coverage branches:

| Edge Case | Target Branch | File:Line |
|-----------|--------------|-----------|
| Kriging fallback (< MIN_KRIGING_STATIONS) | `climate.py:308-316` | `_init_kriging` early-return |
| MC with zero-variance krig_std | `pipeline.py` MC block (all stds = 0) | MC normal draw degenerates to point estimate |
| MC with single-sample (n_mc=1) | `pipeline.py` MC block | `np.percentile` with 1 sample |

**Fixtures needed:**
- `synthetic_climate_csv_sparse`: 2-station CSV (< MIN_KRIGING_STATIONS=5) — already absent from conftest.py
- `synthetic_raster` already exists in conftest.py
- No new fixture needed for zero-variance and single-sample — just use existing `synthetic_climate_csv_dense` with `uncertainty_samples=1` and mock or craft a config with zero-std output

**Zero-variance scenario:** MC branch `_temp_std = np.maximum(df["mean_temp_krig_std"].to_numpy(), 0.0)` with all-zero std means `rng.normal(mean, 0, shape)` → all draws equal mean → CI width = 0. Test: assert `score_ci_low == score_ci_high == score` element-wise.

**Single-sample scenario:** `uncertainty_samples=1` → `np.percentile(scores_mc, 5, axis=1)` and `95, axis=1)` with shape `(n_cells, 1)` → both return the single value → CI width = 0. Test: assert `(df["score_ci_high"] - df["score_ci_low"]).abs().max() < 1e-9`.

### Anti-Patterns to Avoid

- **Widening the custom exception hierarchy:** `CRSMismatchError` should subclass `pyproj.exceptions.CRSError`, not `Exception`. JOSS reviewers and downstream users can then catch `CRSError` generically.
- **Reading variogram params from LOOCV sub-objects:** LOOCV creates throwaway `ok` objects fitted on n-1 points — their variogram params are slightly different from the full-data fit. Always read params from a full-data `ok` fit.
- **Storing ok object on self:** `OrdinaryKriging` objects are large (~MB). Store only the extracted param dict, not the full `ok` object.
- **Removing `except Exception` from the atomic I/O cleanup blocks:** Those catch-alls (lines 236, 269) are intentional cleanup guards for the `tempfile` cleanup path. They are not the target of HARD-01.
- **Moving plotly import to a function call:** Module-level try/except is cleaner and avoids repeated `ImportError` on every call. The `_PLOTLY_AVAILABLE` flag pattern is standard (same as optional deps in scipy).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CRS validation | Custom CRS string parser | `pyproj.CRS` + `pyproj.Transformer` | pyproj handles all edge cases in CRS authority lookup |
| Variogram parameter extraction | Custom variogram fitting | `ok.variogram_model_parameters` | Already computed by PyKrige during `OrdinaryKriging()` init |
| Test fixture rasters | Real GeoTIFFs in repo | `rasterio.open(..., "w")` in conftest | Already established pattern in existing conftest.py |
| PyPI trove classifiers | Custom lookup | Copy from established geospatial libs | Classifiers are stable vocabulary; no discovery needed |

## Common Pitfalls

### Pitfall 1: PyKrige variogram_model_parameters order

**What goes wrong:** Misidentifying parameter order as `[nugget, range, psill]` (the order used in some textbooks) instead of PyKrige's actual `[psill, range, nugget]`.

**Why it happens:** The Cressie (1993) convention and PyKrige differ. Most online examples show the Cressie convention.

**How to avoid:** Read directly from source: `spherical_variogram_model(m, d)` docstring says "m is [psill, range, nugget]". Confirmed from `/opt/anaconda3/lib/python3.13/site-packages/pykrige/variogram_models.py`. sill = p[0] + p[2], range_ = p[1], nugget = p[2].

**Warning signs:** If nugget > sill after computation, the order is wrong.

### Pitfall 2: `ok` object params reflect full-data fit, not LOOCV sub-fits

**What goes wrong:** Reading variogram params from the throwaway `ok` objects inside `_loocv()` gives params fitted on n-1 points, not the final model.

**How to avoid:** Fit one additional full-data `ok` object in `_init_kriging` after model selection (all n points) and read `variogram_model_parameters` from that. Alternatively read params from the first `ok` in `_interpolate_kriging` (which uses all n points).

### Pitfall 3: `raster.crs is None` passes silently through Transformer

**What goes wrong:** `Transformer.from_crs(None, epsg4326)` raises `pyproj.exceptions.CRSError` but only at construction time. If the raster CRS is a valid but geographically incompatible CRS, the transform silently produces wrong coordinates.

**How to avoid:** The CRS guard only needs to catch `None` CRS and CRSError at Transformer construction. Geographic vs projected CRS mismatch (the coordinates are wrong but numerically valid) is a harder problem — document as known limitation.

### Pitfall 4: plotly import breaks test suite when removed from core deps

**What goes wrong:** Removing plotly from core deps without adding the try/except guard in `viz.py` causes `test_viz.py` to fail with `ImportError` since the test environment may not have `[viz]` installed.

**How to avoid:** Add the guard in `viz.py` first. Then update `test_viz.py` to either (a) install `[viz]` in CI, or (b) mark viz tests with `pytest.importorskip("plotly")`. The existing `dev` extra in pyproject.toml does not include `[viz]`, so `test_viz.py` must use `pytest.importorskip`.

### Pitfall 5: `fail_under = 85` in pyproject.toml causes CI failure if new tests reduce coverage

**What goes wrong:** Adding test files that import covered-but-not-executed code paths can reduce effective coverage.

**How to avoid:** Run `pytest --cov --cov-branch` after each change. Current baseline is 87.32% — there is a 2.32 percentage point buffer before breaching the threshold.

### Pitfall 6: Sparse-station fixture triggers kriging fallback AND changes interpolation_method

**What goes wrong:** When `_init_kriging` falls back to `"linear"`, `self.interpolation_method` is mutated. The test must assert the fallback happened (by checking `interpolator.interpolation_method == "linear"`) not that it raised an error.

**How to avoid:** Test the kriging fallback branch by asserting `interpolator.interpolation_method == "linear"` after constructing `ClimateInterpolator` with sparse data and `interpolation_method="kriging"`.

## Code Examples

Verified patterns from codebase and library source:

### Reading PyKrige Variogram Parameters (HIGH confidence — verified from source)
```python
# From pykrige/variogram_models.py — all three models use [psill, range, nugget]
ok = OrdinaryKriging(lons, lats, vals, variogram_model=model, verbose=False, enable_plotting=False)
p = ok.variogram_model_parameters  # np.ndarray of length 3
kriging_diagnostics = {
    "model": ok.variogram_model,
    "psill": float(p[0]),
    "nugget": float(p[2]),
    "sill": float(p[0]) + float(p[2]),   # total variance = psill + nugget
    "range_": float(p[1]),
    "range_units": "degrees_geographic",  # WGS84 euclidean mode
}
```

### CRSMismatchError Definition (MEDIUM confidence — standard pattern)
```python
# terraflow/exceptions.py
from pyproj.exceptions import CRSError

class CRSMismatchError(CRSError):
    """Raised when raster CRS and climate data CRS are incompatible.

    Attributes
    ----------
    raster_crs : str
        WKT or authority string of the raster CRS.
    climate_crs : str
        WKT or authority string of the expected climate CRS.
    """
    pass
```

### Guard in pipeline.py (MEDIUM confidence)
```python
# After: raster_crs = raster.crs  (line 394 of pipeline.py)
from pyproj.exceptions import CRSError as _PyProjCRSError
from .exceptions import CRSMismatchError

_climate_crs_str = "EPSG:4326"
if raster_crs is None:
    raise CRSMismatchError(
        f"Raster '{cfg.raster_path}' has no CRS (raster_crs=None). "
        f"Expected a raster reprojectable to climate CRS '{_climate_crs_str}'."
    )
try:
    Transformer.from_crs(raster_crs, CRS.from_epsg(4326), always_xy=True)
except _PyProjCRSError as exc:
    raise CRSMismatchError(
        f"Raster CRS '{raster_crs.to_string()}' is incompatible with "
        f"climate CRS '{_climate_crs_str}': {exc}"
    ) from exc
```

### Test for Kriging Fallback (HARD-02)
```python
def test_kriging_fallback_sparse_stations():
    """With < MIN_KRIGING_STATIONS stations, interpolation_method falls back to linear."""
    from terraflow.climate import ClimateInterpolator, MIN_KRIGING_STATIONS

    sparse_df = pd.DataFrame({
        "lat": [40.0, 40.1],   # only 2 stations, < MIN_KRIGING_STATIONS=5
        "lon": [-100.0, -99.9],
        "mean_temp": [18.0, 20.0],
        "total_rain": [100.0, 120.0],
    })
    interpolator = ClimateInterpolator(
        climate_df=sparse_df, strategy="spatial", interpolation_method="kriging"
    )
    assert interpolator.interpolation_method == "linear"
```

### Test for MC Single-Sample (HARD-02)
```python
def test_mc_single_sample_ci_width_zero(
    tmp_path, synthetic_raster, synthetic_climate_csv_dense
):
    """uncertainty_samples=1 → score_ci_low == score_ci_high."""
    from terraflow.pipeline import run_pipeline
    cfg = _write_kriging_config(
        tmp_path / "cfg.yml", synthetic_raster, synthetic_climate_csv_dense,
        tmp_path / "out", uncertainty_samples=1,
    )
    df = run_pipeline(cfg)
    assert "score_ci_low" in df.columns
    np.testing.assert_array_almost_equal(df["score_ci_low"], df["score_ci_high"])
```

### pyproject.toml optional viz dependency (HARD-04)
```toml
[project.optional-dependencies]
viz = ["plotly>=5.0.0"]
dev = [
    # ... existing dev deps without plotly ...
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `except Exception` broad catch | Named exception types + custom error class | Phase 1 | JOSS reviewers can see specific failure modes |
| No variogram diagnostics in output | `kriging_diagnostics` block in report.json | Phase 1 | Paper can cite variogram model; reproducibility |
| plotly as core dep | plotly as optional `[viz]` | Phase 1 | Reduces install footprint; avoids JOSS reviewer friction |

**Deprecated/outdated in this codebase:**
- `_aggregate_climate()` in pipeline.py: already marked deprecated; not touched in Phase 1

## Open Questions

1. **CRS mismatch exact scenario for `CRSMismatchError`**
   - What we know: Climate CSV is always WGS84 (lat/lon degrees). The guard needs to fire when a raster has `crs=None` or a CRS that can't be transformed to WGS84.
   - What's unclear: Should the error also fire when raster CRS is valid but the raster extent in WGS84 does not overlap the climate station extent? That's a data quality issue, not a CRS mismatch.
   - Recommendation: Scope the error strictly to "can't transform raster CRS to WGS84" — None CRS and `CRSError` during Transformer construction. Spatial extent overlap is already handled by the existing `ValueError` in `clip_raster_to_roi`.

2. **Variogram range units in report.json**
   - What we know: PyKrige in euclidean mode returns range in degree-units when inputs are WGS84.
   - What's unclear: STATE.md says "decision deferred to Phase 1 planning." The research recommendation is to document degree-units with a `range_units: "degrees_geographic"` field and a comment in report.json, without UTM reprojection. UTM reprojection is GEO-03 (v2 scope).
   - Recommendation: Document limitation now (Phase 1), defer fix to v2.

3. **Documentation URL for pyproject.toml**
   - What we know: mkdocs.yml exists; the GitHub repo is `gmarupilla/AgroTerraFlow`.
   - What's unclear: Whether GitHub Pages has been enabled and the docs are live at `https://gmarupilla.github.io/AgroTerraFlow/`.
   - Recommendation: Use the GitHub Pages URL. If not yet live, it is still the correct canonical URL to register.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pyproj | HARD-01 (CRSMismatchError) | Yes | 3.7.2 | — |
| pykrige | HARD-03 (variogram params) | Yes | 1.7.3 | — |
| pytest-cov | HARD-02 (coverage) | Yes | 7.0.0 | — |
| plotly | HARD-04 (demote to optional) | Yes | 5.24.1 | Becomes optional |
| rasterio | All | Yes | 1.5.0 | — |

No missing dependencies. All tools available.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-cov 7.0.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` and `[tool.coverage]` |
| Quick run command | `pytest tests/test_climate.py tests/test_uncertainty.py -x --cov=terraflow --cov-branch -q` |
| Full suite command | `pytest tests/ --cov=terraflow --cov-branch --cov-report=term-missing -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARD-01 | `CRSMismatchError` raised with both CRS strings on None raster CRS | unit | `pytest tests/test_geo.py tests/test_pipeline.py -x -k crs_mismatch` | Partial — `test_geo.py` and `test_pipeline.py` exist but lack CRS mismatch tests |
| HARD-01 | `CRSMismatchError` raised on incompatible CRS | unit | `pytest tests/test_pipeline.py -x -k crs_mismatch` | Partial |
| HARD-02 | kriging fallback to linear when < MIN_KRIGING_STATIONS | unit | `pytest tests/test_climate.py -x -k kriging_fallback` | Not present |
| HARD-02 | MC zero-variance: CI width = 0 when all krig_std = 0 | integration | `pytest tests/test_uncertainty.py -x -k zero_variance` | Not present |
| HARD-02 | MC single-sample: CI width = 0 when uncertainty_samples=1 | integration | `pytest tests/test_uncertainty.py -x -k single_sample` | Not present |
| HARD-03 | `report.json` contains `kriging_diagnostics` block with correct keys | integration | `pytest tests/test_uncertainty.py tests/test_pipeline.py -x -k kriging_diagnostics` | Not present |
| HARD-04 | `import terraflow` succeeds without plotly installed | unit | `pytest tests/test_viz.py -x -k no_plotly` | Partial — `test_viz.py` exists, no optional-dep test |
| HARD-04 | `pip install terraflow` doesn't pull in plotly | packaging | Manual / checked via `pip show plotly` after bare install | Manual check |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --cov=terraflow --cov-branch -q`
- **Per wave merge:** Full suite with `--cov-report=term-missing`
- **Phase gate:** Total branch coverage >= 87% (current baseline), suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_climate.py` — add `test_kriging_fallback_sparse_stations` covering `climate.py:308-316`
- [ ] `tests/test_uncertainty.py` — add `test_mc_zero_variance_ci_collapsed` and `test_mc_single_sample_ci_width`
- [ ] `tests/test_pipeline.py` or `tests/test_geo.py` — add `test_crs_mismatch_error_raised` with synthetic None-CRS raster fixture
- [ ] `tests/test_pipeline.py` — add `test_kriging_diagnostics_in_report_json`
- [ ] `tests/test_viz.py` — add `pytest.importorskip("plotly")` guard so viz tests skip cleanly when plotly is not installed
- [ ] `tests/conftest.py` — add `synthetic_climate_csv_sparse` fixture (2 stations, < MIN_KRIGING_STATIONS)

## Sources

### Primary (HIGH confidence)
- PyKrige source `pykrige/variogram_models.py` — confirmed `[psill, range, nugget]` parameter order for spherical, exponential, gaussian models
- `terraflow/climate.py` (read directly) — confirmed `_krig_variogram_model`, `_init_kriging`, `_interpolate_kriging` structure
- `terraflow/pipeline.py` (read directly) — confirmed `except Exception` locations, MC block, report.json builder
- `pyproject.toml` (read directly) — confirmed plotly in core deps, missing classifiers/Documentation URL
- `pytest --cov` run output — confirmed 87.32% branch coverage, specific missing branches

### Secondary (MEDIUM confidence)
- `pyproj.exceptions.CRSError` as base class for custom exception — standard pyproj usage pattern; pyproj 3.x ships `pyproj.exceptions` module

### Tertiary (LOW confidence)
- Trove classifier recommendations — standard set for scientific Python; specific to this library's topic area

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed, versions confirmed
- Architecture: HIGH for HARD-03 (param order confirmed from source), MEDIUM for HARD-01 (exception placement is design choice, not verifiable fact)
- Pitfalls: HIGH for variogram param order (source-verified), MEDIUM for others

**Research date:** 2026-03-26
**Valid until:** 2026-05-26 (stable PyKrige API; pyproj API very stable)
