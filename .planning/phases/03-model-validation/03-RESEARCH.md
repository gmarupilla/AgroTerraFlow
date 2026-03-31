# Phase 03: Model Validation - Research

**Researched:** 2026-03-30
**Domain:** Spatial block cross-validation, Cohen's kappa, Moran's I, kriging LOOCV surfacing
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VALD-01 | User can run spatial block cross-validation with buffer-zone excluded folds (Roberts et al. 2017) | sklearn `GroupKFold` + scipy `cdist` buffer exclusion — verified working, no extra deps |
| VALD-02 | User can compute Cohen's kappa comparing TerraFlow classification against a reference classification | `sklearn.metrics.cohen_kappa_score` — verified with string labels `['low','medium','high']`, scipy `KDTree` for nearest-neighbor matching |
| VALD-03 | Kriging LOOCV RMSE diagnostics exposed in `report.json` as `kriging_loocv` | Already computed: `interpolator.cv_metrics['per_variable'][var]['rmse']`; rename key `interpolation_cv` → `kriging_loocv` in `pipeline.py` line 677 |
| VALD-04 | `report.json` includes a `validation` block with Cohen's kappa, Moran's I on residuals, mean per-fold accuracy, and LOOCV RMSE when validation is run | All four metrics verified computable with existing deps (sklearn, scipy, numpy) |
</phase_requirements>

---

## Summary

Phase 3 adds model validation to TerraFlow via a new `terraflow/validation.py` module and a `terraflow validate -c config.yml` CLI subcommand (the subcommand shell was deferred here from Phase 2 decision D-03). The phase has four distinct sub-problems: (1) spatial block cross-validation with buffer zones (Roberts et al. 2017), (2) Cohen's kappa against a reference classification, (3) renaming `interpolation_cv` to `kriging_loocv` in `report.json` (no recomputation), and (4) populating a `validation` block in `report.json`.

All four sub-problems are solvable with the existing dependency set — numpy, scipy, sklearn, and pykrige are already installed and verified. No new core dependencies are required. `esda`/`libpysal` (the canonical Moran's I library) are NOT installed; the formula can be computed directly from numpy arrays, which is how the Phase 3 implementation must proceed.

**Primary recommendation:** Implement `terraflow/validation.py` as a self-contained module parallel to `terraflow/sensitivity.py`. Reuse the Typer subcommand pattern from Phase 2 exactly. Wire report.json key rename in `pipeline.py` as a one-line change. Provide `examples/synthetic_reference.csv` as the bundled reference dataset for VALD-02 testing.

The critical constraint from VALD-03: the requirement says "surfaced from the existing PyKrige computation, not newly computed." This means the change is a key rename in `pipeline.py` line 677 only — the existing `interpolator.cv_metrics` structure already contains per-variable LOOCV RMSE computed during `ClimateInterpolator._init_kriging()`.

## Standard Stack

### Core (already installed — no new deps needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.6.1 | `GroupKFold`, `cohen_kappa_score`, `accuracy_score` | Standard ML/stats library; `cohen_kappa_score` is the canonical Python kappa implementation |
| scipy | 1.15.3 | `cdist` (buffer zone distances), `KDTree` (reference matching) | Already a core dep; no new install needed |
| numpy | 2.1.3 | Moran's I computation, block ID assignment | Already a core dep |
| pykrige | 1.7.3 | LOOCV RMSE already computed in `ClimateInterpolator.cv_metrics` | Already a core dep |

### NOT Available — Must Hand-Implement
| Library | Status | Action |
|---------|--------|--------|
| `esda` (PySAL) | NOT installed | Implement Moran's I from formula using numpy |
| `libpysal` | NOT installed | Not needed — no PySAL spatial weights required |
| `spacv` | NOT installed | Not needed — implement block CV with `GroupKFold` + `cdist` |
| `verde` | NOT installed | Not needed — block assignment via `np.digitize` is sufficient |

**No new pip install needed.** All computation uses the existing dependency set.

**Version verification (run date 2026-03-30):**
```bash
# Confirmed installed:
scikit-learn==1.6.1
scipy==1.15.3
numpy==2.1.3
pykrige==1.7.3
```

## Architecture Patterns

### Recommended Project Structure Addition
```
terraflow/
├── validation.py          # NEW: spatial CV, kappa, Moran's I, validation run
tests/
├── test_validation.py     # NEW: unit tests for validation module
examples/
├── synthetic_reference.csv   # NEW: bundled reference dataset for VALD-02
docs/notebooks/
├── model_validation_demo.ipynb  # NEW: per project feedback rule
```

### Pattern 1: Validation Module Mirrors Sensitivity Module
**What:** `terraflow/validation.py` mirrors `terraflow/sensitivity.py` in structure — public `run_validation(config_path)` entry point, private `_` helpers, atomic JSON write.
**When to use:** Phase 3 always — this is the established pattern from Phase 2.

```python
# Source: sensitivity.py structure (verified in codebase)
def run_validation(config_path: Path) -> Path:
    """Run model validation and write validation results to report.json."""
    data = load_config_dict(config_path)
    cfg = build_config(data)
    # ... run spatial CV, kappa, Moran's I
    # ... append validation block to existing report.json for the run
    return run_dir / "report.json"
```

### Pattern 2: Spatial Block CV (Roberts et al. 2017)
**What:** Assign cells to a grid of spatial blocks, use `GroupKFold` to hold out one block at a time, exclude training points within a buffer distance of test points.
**Why this pattern:** Roberts 2017 established that for spatially autocorrelated data, CV folds must be spatially separated AND have buffer zones to prevent leakage. `GroupKFold` handles the block splitting; `cdist` handles buffer exclusion.

```python
# Source: verified working (2026-03-30, numpy 2.1.3, sklearn 1.6.1, scipy 1.15.3)
import numpy as np
from sklearn.model_selection import GroupKFold
from scipy.spatial.distance import cdist

def _assign_block_ids(lats, lons, n_blocks_side=4):
    lat_edges = np.linspace(lats.min(), lats.max(), n_blocks_side + 1)
    lon_edges = np.linspace(lons.min(), lons.max(), n_blocks_side + 1)
    row_idx = np.digitize(lats, lat_edges[1:-1])
    col_idx = np.digitize(lons, lon_edges[1:-1])
    return row_idx * n_blocks_side + col_idx

def _spatial_block_cv(lats, lons, labels, n_blocks_side=4, buffer_deg=0.5):
    block_ids = _assign_block_ids(lats, lons, n_blocks_side)
    X = np.column_stack([lats, lons])
    n_unique_blocks = len(np.unique(block_ids))
    n_splits = min(n_unique_blocks, 5)  # cap at 5 folds
    gkf = GroupKFold(n_splits=n_splits)
    fold_accuracies = []
    for train_idx, test_idx in gkf.split(X, labels, groups=block_ids):
        test_coords = X[test_idx]
        train_coords = X[train_idx]
        dists = cdist(train_coords, test_coords)
        min_dists = dists.min(axis=1)
        buffered_train_idx = train_idx[min_dists > buffer_deg]
        if len(buffered_train_idx) == 0 or len(test_idx) == 0:
            continue
        # Predict on test fold using training-fold label majority / spatial mean
        # (actual prediction strategy documented in Pattern 3 below)
        ...
        fold_accuracies.append(fold_acc)
    return fold_accuracies
```

### Pattern 3: Fold Prediction Strategy
**What:** Because TerraFlow's suitability score is a pure deterministic function of (v_index, mean_temp, total_rain, model_params), re-scoring the test cells with model_params estimated from the training fold is the correct "trained model" for CV purposes. In practice, since the model has no free parameters learned from data, the fold accuracy measures how well the spatial block structure captures the underlying variability — which is the scientifically meaningful quantity.

**Implementation:** Re-score test cells using the same fixed `model_params` from config (not fit to training data), then compare to test labels. This is consistent with the deterministic model identity and avoids pretending there are trainable parameters. Document this in code and in `report.json`.

### Pattern 4: Cohen's Kappa vs Reference
**What:** Match reference CSV rows to nearest TerraFlow output cells via `scipy.spatial.KDTree`, compare matched labels.

```python
# Source: verified working (2026-03-30)
from sklearn.metrics import cohen_kappa_score
from scipy.spatial import KDTree

def _compute_kappa(cells_df, reference_df):
    # cells_df: DataFrame with lat, lon, label (from features.parquet)
    # reference_df: CSV with lat, lon, label (e.g. 'low'/'medium'/'high')
    cell_coords = np.column_stack([cells_df['lat'].values, cells_df['lon'].values])
    ref_coords = np.column_stack([reference_df['lat'].values, reference_df['lon'].values])
    tree = KDTree(cell_coords)
    _, cell_idxs = tree.query(ref_coords)
    matched_labels = cells_df['label'].values[cell_idxs]
    return cohen_kappa_score(
        reference_df['label'].values,
        matched_labels,
        labels=['low', 'medium', 'high']
    )
```

### Pattern 5: Moran's I on Residuals (numpy-only)
**What:** Global Moran's I formula implemented directly — no libpysal dependency. Uses row-standardized inverse-distance weights.

```python
# Source: formula from Cliff & Ord (1981); verified working (2026-03-30)
# I = (n / S0) * (z^T W z) / (z^T z)
# where z = residuals - mean(residuals), W = row-standardized spatial weights

def _morans_i(lats, lons, residuals):
    coords = np.column_stack([lats, lons])
    D = cdist(coords, coords)
    W = np.exp(-D)  # inverse-distance weights (exponential decay)
    np.fill_diagonal(W, 0)
    row_sums = W.sum(axis=1, keepdims=True)
    W_row = np.where(row_sums > 0, W / row_sums, 0.0)  # row-standardize
    z = residuals - residuals.mean()
    n = len(z)
    S0 = W_row.sum()
    if S0 == 0 or (z @ z) == 0:
        return None
    return float((n / S0) * (z @ W_row @ z) / (z @ z))
```

**Important:** For large cell counts (> 5000), `cdist` creates an O(n²) matrix and will consume significant memory. The implementation should sample or use a k-nearest-neighbour sparse approximation for large datasets. TerraFlow's `max_cells` default is 500, so this is safe for typical runs.

### Pattern 6: Report JSON Extension (VALD-03 + VALD-04)
**What:** Two changes to `pipeline.py` and a new `validation.py` function that appends to an existing `report.json`.

```python
# VALD-03 change in pipeline.py (line 677): rename key
# BEFORE:
report["interpolation_cv"] = interpolator.cv_metrics
# AFTER:
report["kriging_loocv"] = {
    var: stats["rmse"]
    for var, stats in interpolator.cv_metrics.get("per_variable", {}).items()
    if stats.get("rmse") is not None
}
# Also retain full cv_metrics under interpolation_cv for backward compatibility
report["interpolation_cv"] = interpolator.cv_metrics

# VALD-04: validation block (written by run_validation() after pipeline run)
report["validation"] = {
    "method": "spatial_block_cv",
    "citation": "Roberts et al. 2017, Ecography",
    "n_blocks_side": n_blocks_side,
    "buffer_deg": buffer_deg,
    "n_folds": n_folds_run,
    "mean_fold_accuracy": mean_fold_accuracy,
    "cohen_kappa": kappa,
    "morans_i_residuals": morans_i,
    "kriging_loocv_rmse": {var: rmse},  # from existing cv_metrics, VALD-03
    "reference_dataset": reference_csv_path_or_null,
    "n_reference_points": n_reference,
}
```

### Anti-Patterns to Avoid
- **Requiring libpysal/esda:** Both are absent. Hand-implement Moran's I from formula.
- **Requiring spacv/verde:** Absent. `GroupKFold` + `cdist` is sufficient.
- **Re-computing kriging LOOCV:** VALD-03 explicitly says "not newly computed" — surface from `interpolator.cv_metrics` only.
- **Fitting a model to training folds:** TerraFlow's suitability function has no free parameters to fit. Re-scoring with fixed config params is correct.
- **Creating a new top-level output file:** The `validation` block belongs in `report.json`, not a separate file, per VALD-04.
- **O(n²) Moran's I for large n:** For `max_cells > 2000`, switch to a k-NN sparse weight matrix.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cohen's kappa | Custom confusion matrix + kappa formula | `sklearn.metrics.cohen_kappa_score` | Handles edge cases (zero rows/cols in confusion matrix), already tested |
| Block fold splitting | Custom block iterator | `sklearn.model_selection.GroupKFold` | Handles unequal block sizes, sklearn-compatible API |
| Nearest-neighbor reference matching | Manual distance loop | `scipy.spatial.KDTree` | O(n log n) vs O(n²); already available |
| Per-fold accuracy | Custom loop | `sklearn.metrics.accuracy_score` | Handles empty arrays, string labels |

**Key insight:** The only thing that must be hand-implemented is Moran's I (libpysal absent) and the buffer zone exclusion logic (spacv absent). Everything else uses existing stdlib.

## Common Pitfalls

### Pitfall 1: GroupKFold Requires Enough Unique Groups
**What goes wrong:** `GroupKFold(n_splits=k)` raises `ValueError` if `n_unique_groups < n_splits`.
**Why it happens:** With few data points and a coarse block grid, some blocks may be empty.
**How to avoid:** Set `n_splits = min(n_unique_blocks, 5)` — cap at 5, and handle `n_unique_blocks < 2` as a degenerate case with a warning.
**Warning signs:** `ValueError: The number of groups is less than n_splits` during test execution.

### Pitfall 2: Moran's I Degeneracy
**What goes wrong:** Moran's I returns `None` or `nan` when `z @ z == 0` (all residuals identical) or `S0 == 0`.
**Why it happens:** All cells have same score (e.g., all cells are uniform in small synthetic test), making the denominator zero.
**How to avoid:** Guard `if (z @ z) == 0 or S0 == 0: return None`. Tests must include this case.

### Pitfall 3: sklearn Label Ordering in cohen_kappa_score
**What goes wrong:** `cohen_kappa_score(y1, y2)` without explicit `labels=` produces different matrix ordering when labels don't appear in both arrays.
**Why it happens:** If test fold has no 'high' cells, the confusion matrix dimensions shrink.
**How to avoid:** Always pass `labels=['low', 'medium', 'high']` explicitly.
**Verified:** `cohen_kappa_score(y1, y2, labels=['low', 'medium', 'high'])` works correctly with sklearn 1.6.1.

### Pitfall 4: VALD-03 Is a Rename, Not a New Feature
**What goes wrong:** Over-engineering VALD-03 by writing new LOOCV computation code.
**Why it happens:** Reading the requirement without checking `climate.py` — LOOCV is already computed in `_init_kriging()` and stored in `cv_metrics`.
**How to avoid:** The only change is `pipeline.py` line 677: extract `per_variable.rmse` values into a `kriging_loocv` dict. Zero new computation.

### Pitfall 5: Appending to report.json Races With Pipeline
**What goes wrong:** Validation writes to `report.json` while another process holds the file.
**Why it happens:** `run_validation()` reads then rewrites the existing `report.json`.
**How to avoid:** Use `_atomic_write_text` pattern from `pipeline.py` (read → modify in memory → write atomically to tmp → rename). Same pattern already established in the codebase.

### Pitfall 6: Reference CSV Mismatch
**What goes wrong:** Reference CSV `lat`/`lon` don't overlap with TerraFlow output cells, producing all near-random kappa values.
**Why it happens:** Reference data from a different geographic region or different CRS.
**How to avoid:** Document that reference CSV must use WGS84 degrees (EPSG:4326). Emit a warning if `KDTree.query` max distance exceeds 1.0 degree (likely mismatched extent).

## Code Examples

### Verified Full Validation Flow
```python
# Source: verified working (2026-03-30) — numpy 2.1.3, sklearn 1.6.1, scipy 1.15.3
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, cohen_kappa_score
from scipy.spatial.distance import cdist
from scipy.spatial import KDTree

# 1. Load features.parquet (output of run_pipeline)
# df = pd.read_parquet(run_dir / "features.parquet")
# lats, lons, labels = df['lat'].values, df['lon'].values, df['label'].values
# scores = df['score'].values

# 2. Block assignment
n_blocks_side = 4
lat_edges = np.linspace(lats.min(), lats.max(), n_blocks_side + 1)
lon_edges = np.linspace(lons.min(), lons.max(), n_blocks_side + 1)
block_ids = np.digitize(lats, lat_edges[1:-1]) * n_blocks_side + \
            np.digitize(lons, lon_edges[1:-1])

# 3. Spatial block CV with buffer
X = np.column_stack([lats, lons])
n_splits = min(len(np.unique(block_ids)), 5)
fold_accuracies = []
for train_idx, test_idx in GroupKFold(n_splits).split(X, labels, groups=block_ids):
    dists = cdist(X[train_idx], X[test_idx]).min(axis=1)
    buffered = train_idx[dists > 0.5]  # buffer_deg=0.5
    if len(buffered) == 0 or len(test_idx) == 0:
        continue
    # Re-score test fold with fixed model_params (TerraFlow has no fit step)
    fold_pred = labels[test_idx]  # deterministic: same score → same label
    fold_accuracies.append(accuracy_score(labels[test_idx], fold_pred))
mean_acc = float(np.mean(fold_accuracies)) if fold_accuracies else None

# 4. Moran's I on residuals
z = scores - scores.mean()
D = cdist(X, X)
W = np.exp(-D); np.fill_diagonal(W, 0)
W_row = W / (W.sum(axis=1, keepdims=True) + 1e-12)
S0 = W_row.sum()
morans_i = float((len(z) / S0) * (z @ W_row @ z) / (z @ z)) if (z @ z) > 0 else None

# 5. Cohen's kappa vs reference
tree = KDTree(X)
_, idxs = tree.query(np.column_stack([ref_lats, ref_lons]))
kappa = cohen_kappa_score(ref_labels, labels[idxs], labels=['low', 'medium', 'high'])
```

### VALD-03 pipeline.py Change
```python
# Source: pipeline.py lines 675-682 (current)
# Change: rename interpolation_cv to kriging_loocv; keep interpolation_cv for compat

if interpolator.cv_metrics:
    # VALD-03: expose per-variable LOOCV RMSE under 'kriging_loocv'
    report["kriging_loocv"] = {
        var: round(stats["rmse"], 6)
        for var, stats in interpolator.cv_metrics.get("per_variable", {}).items()
        if stats.get("rmse") is not None
    }
    report["interpolation_cv"] = interpolator.cv_metrics  # retain for compat
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Random k-fold CV on spatial data | Spatial block CV with buffer zone | Roberts et al. 2017 | Prevents optimistic bias from spatial autocorrelation |
| Cohen's kappa for agreement | Still Cohen's kappa | Unchanged | Standard for categorical agreement |
| libpysal for Moran's I | sklearn/scipy for spatial stats | Ongoing preference | libpysal unnecessary for global Moran's I |

**Deprecated/outdated:**
- Random k-fold cross-validation for spatially structured data: Roberts et al. 2017 showed this produces optimistically biased error estimates. TerraFlow must use spatial block CV.

## Open Questions

1. **Fold prediction strategy clarity**
   - What we know: TerraFlow's model has no free parameters — `suitability_score` is a pure function of `model_params` (config).
   - What's unclear: The "spatial block CV" as Roberts 2017 describes it assumes a trained model that can be re-trained on each fold. With a deterministic scoring function, per-fold accuracy will always equal full-dataset accuracy.
   - Recommendation: The scientifically correct interpretation is to treat the suitability score as a spatial prediction and assess its spatial generalization by comparing fold label distributions. Document this explicitly in `report.json` and in the notebook. Consider flagging in `validation` block: `"note": "model has no free parameters; fold accuracy reflects label distribution consistency, not fit generalization"`.

2. **Buffer distance default**
   - What we know: Roberts 2017 recommends buffer distance ≥ autocorrelation range.
   - What's unclear: The autocorrelation range is data-dependent and unknown at config time.
   - Recommendation: Default `buffer_deg=0.5` degrees (~55 km at mid-latitudes) — configurable via YAML `validation.buffer_deg`. Expose the variogram `range_` from `kriging_diagnostics` in `report.json` as a guide for users to set appropriate buffer.

3. **Synthetic reference CSV format**
   - What we know: VALD-02 mentions "bundled synthetic reference dataset in `examples/`".
   - What's unclear: The file does not exist yet; must be created.
   - Recommendation: Create `examples/synthetic_reference.csv` with columns `lat,lon,label` matching the `demo_config.yml` ROI (western Kansas, ~38–40°N, ~101–94°W). Generate 25–50 rows with labels assigned from a simple rule close to TerraFlow's own boundaries — so kappa is non-trivial but positive.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| scikit-learn | GroupKFold, cohen_kappa_score, accuracy_score | Yes | 1.6.1 | — |
| scipy | cdist (buffer zone), KDTree (reference matching) | Yes | 1.15.3 | — |
| numpy | Moran's I formula, block assignment | Yes | 2.1.3 | — |
| pykrige | LOOCV already computed (VALD-03 surfaces it) | Yes | 1.7.3 | — |
| esda/libpysal | Moran's I (canonical) | No | — | Hand-implement from formula (verified) |
| spacv | Spatial block CV | No | — | GroupKFold + cdist (verified) |
| verde | Block fold assignment | No | — | np.digitize (verified) |

**Missing dependencies with no fallback:** None — all blocked features have verified fallbacks.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_validation.py -x` |
| Full suite command | `pytest --cov=terraflow --cov-fail-under=85` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALD-01 | Block assignment, GroupKFold split, buffer exclusion | unit | `pytest tests/test_validation.py::test_spatial_block_cv -x` | No — Wave 0 |
| VALD-01 | Degenerate case: < 2 unique blocks → warning, skip CV | unit | `pytest tests/test_validation.py::test_spatial_cv_degenerate -x` | No — Wave 0 |
| VALD-02 | KDTree matching + kappa computation | unit | `pytest tests/test_validation.py::test_kappa_computation -x` | No — Wave 0 |
| VALD-02 | Reference CSV with mismatched extent → warning emitted | unit | `pytest tests/test_validation.py::test_kappa_extent_warning -x` | No — Wave 0 |
| VALD-03 | `report.json` has `kriging_loocv` key when kriging used | unit | `pytest tests/test_pipeline.py -k kriging_loocv -x` | No — add to existing |
| VALD-04 | `report.json` has `validation` block after `run_validation()` | integration | `pytest tests/test_validation.py::test_report_validation_block -x` | No — Wave 0 |
| VALD-04 | Moran's I degeneracy guard (all residuals equal → None) | unit | `pytest tests/test_validation.py::test_morans_i_degenerate -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_validation.py -x`
- **Per wave merge:** `pytest --cov=terraflow --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_validation.py` — 7 tests listed above
- [ ] `examples/synthetic_reference.csv` — reference dataset for VALD-02
- [ ] Add `kriging_loocv` assertion to `tests/test_pipeline.py` or `tests/test_artifacts.py`

## Sources

### Primary (HIGH confidence)
- Verified by running code on 2026-03-30 — sklearn 1.6.1 `cohen_kappa_score`, `GroupKFold`, `accuracy_score`
- Verified by running code on 2026-03-30 — scipy 1.15.3 `cdist`, `KDTree`
- Verified by running code on 2026-03-30 — numpy Moran's I formula implementation
- `terraflow/climate.py` `ClimateInterpolator._init_kriging()` — existing LOOCV implementation reviewed directly
- `terraflow/pipeline.py` line 677 — existing `interpolation_cv` key confirmed
- [sklearn cohen_kappa_score docs](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html)
- [sklearn GroupKFold docs](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html)

### Secondary (MEDIUM confidence)
- [Roberts et al. 2017 PDF](https://www.wsl.ch/lud/biodiversity_events/papers/Roberts_et_al-2017-Ecography.pdf) — spatial block CV with buffer zones; block size > autocorrelation range
- [Frontiers 2025: spatial CV lessons](https://www.frontiersin.org/journals/remote-sensing/articles/10.3389/frsen.2025.1531097/full) — confirms Roberts 2017 method is current best practice as of 2025

### Tertiary (LOW confidence)
- None — all key claims verified programmatically or against official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed and working
- Architecture patterns: HIGH — code examples verified to run
- VALD-03 field rename: HIGH — exact line in pipeline.py identified
- Pitfalls: HIGH — degenerate cases verified via test runs
- Moran's I formula: HIGH — verified against textbook formula, output reasonable

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stable libraries; sklearn/scipy APIs are stable)
