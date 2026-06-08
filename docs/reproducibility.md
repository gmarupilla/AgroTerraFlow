# Reproducibility Guarantees

TerraFlow is designed so that a researcher can cite a specific `run_fingerprint`
and reviewers, collaborators, or auditors can regenerate byte-identical outputs
from the same inputs and configuration. This page documents **exactly** what
that guarantee covers, what it does not cover, and how to cite a run.

## What the run fingerprint includes

A `run_fingerprint` is a deterministic SHA-256 hex digest computed from:

1. **The entire YAML configuration**, canonicalised as JSON (keys sorted,
   booleans/floats normalised). This means every field — `raster_path`,
   `raster_band`, `max_cells`, every `model_params` weight, the complete
   `climate` block (including `interpolation_method` and `variogram_mode`),
   the `roi` block, and any optional `sensitivity` / `validation` / `export`
   config — contributes to the fingerprint.
2. **The SHA-256 content hash of the input raster** (GeoTIFF bytes).
3. **The SHA-256 content hash of the climate CSV** (file bytes).
4. **The optional reference CSV hash** for `terraflow validate`, when present.

The fingerprint is the directory name under `<output_dir>/runs/` where all
artifacts land. Identical inputs and config ⇒ identical fingerprint ⇒ the
cache hit path returns the previously computed `features.parquet`,
`manifest.json`, and `report.json` without recomputation.

## What the run fingerprint excludes (by design)

These are intentionally **not** part of the fingerprint:

- **File mtimes.** Copying a file across machines rewrites the mtime; only
  the content hash is load-bearing.
- **Absolute paths.** Two users with inputs at different paths but the same
  content get the same fingerprint.
- **Wall-clock time.** `manifest.json` records `created_at_utc` for audit,
  but it does not feed back into the hash.
- **Host metadata.** Hostname, username, git SHA of the working tree are
  recorded in `manifest.json` for provenance but never influence the hash.
- **Installed package versions.** See the **limits** section below — this is
  a *known* non-guarantee, not an oversight.

## What is strongly reproducible (bit-identical)

Under the same Python version, same `numpy` / `scipy` / `pykrige` wheels, and
same OS/architecture:

- The sampled set of ROI cells (`rng.choice` is seeded from the fingerprint).
- The per-cell `lat`, `lon`, `v_index`, `mean_temp`, `total_rain`, `score`,
  and `label` values.
- The per-cell Monte Carlo confidence-interval columns (`score_ci_low`,
  `score_ci_high`) when `uncertainty_samples > 0`.
- All Sobol' and Morris indices from `terraflow sensitivity`.
- All spatial-block CV, kappa, and Moran's-I values from `terraflow validate`.

The sampling path is exercised across the `max_cells == n_valid_cells` and
`max_cells > n_valid_cells` boundaries by the regression tests in
`tests/test_determinism.py::TestMaxCellsBoundary`.

## Known sources of non-determinism and their limits

Reproducibility is a floor, not a ceiling. These are the documented
departures:

### Variogram fitting (`pykrige` extended mode)

`terraflow`'s **extended** `variogram_mode` fits nested variogram families
using `scipy.optimize.curve_fit`, which invokes the Levenberg–Marquardt
solver. `curve_fit` is deterministic given identical inputs and initial
guesses, but across **different** `scipy` versions the solver's convergence
path can shift by a few ULPs, producing very small differences in
variogram parameters (`psill`, `range_`, `nugget`). Standard-mode
variograms (spherical / exponential / Gaussian) are selected by LOOCV RMSE
and are not affected.

### Delaunay triangulation tie-breaking (scipy)

Linear and nearest-neighbour interpolation via `scipy.interpolate.griddata`
use `scipy.spatial.Delaunay` under the hood. When four or more stations
lie on a common circle, the triangulation is ambiguous and the specific
triangulation chosen depends on the underlying `qhull` version. In
practice this manifests only with degenerate station layouts; real-world
networks rarely trigger it.

### Floating-point summation order

Across OS / BLAS combinations (Accelerate on macOS, OpenBLAS on Linux,
MKL on Intel), `numpy`'s internal summation order for large reductions
can differ in the last bit. Score values will match to ~1e-12 across
platforms, not bit-identical.

### Cache invalidation on schema bump

Running an older TerraFlow against a newer `features.parquet` (or vice
versa) is handled: the pipeline reads the embedded
`terraflow_schema_version` on cache hit and invalidates the cache,
logging a WARNING, when the version does not match the current
`FEATURES_SCHEMA_VERSION`. See
`tests/test_pipeline.py::TestCacheSchemaVersionInvalidation`.

### Station-coordinate deduplication

If the climate CSV contains duplicate lat/lon rows (common with
aggregated NOAA summaries), TerraFlow averages them at
`ClimateInterpolator` construction. The merge is deterministic and
bit-identical, but it does mean the underlying input CSV and the
effective station set used for kriging are different objects. The
averaging step is logged at INFO level with the before/after station
counts.

## GeoAI runs: a separate fingerprint

Starting with v0.4.0, the optional `terraflow geoai` runners use their own
`geoai_fingerprint` (computed by
`terraflow.core.run_identity.compute_geoai_fingerprint`) that hashes:

1. **The canonicalised YAML configuration** (same canonicaliser as the core
   pipeline, so the `geoai:` block, `raster_path`, and `roi` all
   participate).
2. **The sorted SHA-256 + size of every input raster.**
3. **A `model_metadata` payload**: `name`, `weights_sha256`,
   `geoai_major_minor` (patch deliberately excluded so bug-fix releases of
   `geoai-py` do not invalidate caches), plus the runtime-detected
   `device` (`cpu` / `cuda` / `mps`) and `torch_major_minor`.

Device and torch minor version *are* part of the GeoAI fingerprint because
GPU kernels and torch-minor releases can shift the last few bits of
inference outputs. Two consequences:

- Re-running the same config on a different device legitimately yields a
  *different* fingerprint and a fresh cache directory — outputs may differ
  bit-for-bit.
- `torch.manual_seed` is set from the fingerprint before each runner
  invocation, so the seeded code path is deterministic. CUDA non-determinism
  in unseeded kernels (e.g. atomic reductions) is the documented limit;
  enable `torch.use_deterministic_algorithms(True)` in your environment if
  you need stronger guarantees, at a performance cost.

Each GeoAI run writes `<output_dir>/runs/<geoai_fingerprint>/geoai/{
geoai_manifest.json, report.json, <engine artifacts>}`. The manifest
captures the full payload listed above and is sufficient to recreate the
cached run on the same hardware.

`compute_geoai_fingerprint` treats `device` and `torch_major_minor` as
**optional** keys in `model_metadata` — they are folded into the hash
only when supplied. The in-tree `terraflow.geoai_engine._run` always
populates them, so the CLI runners and the Python wrappers behave as
documented above. Bypassing the engine module (e.g. calling
`compute_geoai_fingerprint` directly from a custom adapter) and omitting
those keys yields a different fingerprint than the engine's — pin both
keys explicitly if you need cross-tool fingerprint agreement.

## How to cite a specific run

For a publication, cite the run the way you would cite a software version:

```
Results produced by TerraFlow v0.2.2
(https://pypi.org/project/terraflow-agro/0.2.2),
run_fingerprint=<hex>, inputs sha256:<raster>, <climate>.
```

All three fields — the package version, the fingerprint, and the input
hashes — are recorded in the `manifest.json` of every run. The raw
payload can be pasted verbatim into supplementary materials.

## Reproducibility check-list for reviewers

1. Install the exact version: `pip install terraflow-agro==0.2.2`.
2. Recompute the input hashes: `sha256sum <raster.tif> <climate.csv>`.
3. Point the config at those paths and run `terraflow run -c cfg.yml`.
4. Verify that the resulting directory name under `runs/` matches the
   published `run_fingerprint`.
5. Open `manifest.json` and confirm the `input_fingerprints.sha256`
   values match your step-2 hashes.

If all four match, the artifacts are byte-identical to the cited run
(within the known floating-point limits above).
