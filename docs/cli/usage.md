---
title: CLI Usage
description: How to run TerraFlow from the command line — flags, config resolution, and output locations.
icon: material/console
tags:
  - CLI
  - Reference
---

# CLI Usage

TerraFlow exposes a lightweight CLI for running the pipeline.

## Run with a config file

=== "Direct CLI"

    ```bash
    terraflow run --config path/to/config.yml
    ```

    The command will:

    1. Load and validate the YAML config
    2. Run the pipeline
    3. Write outputs to the configured output directory

=== "Python Module"

    ```python
    from terraflow.pipeline import run_pipeline

    # Run the pipeline programmatically
    run_pipeline("path/to/config.yml")
    ```

=== "Without Install"

    ```bash
    # Use python -m fallback (no install required)
    python -m terraflow.cli run --config path/to/config.yml
    ```

!!! tip "Portable Configs"
    Relative paths in the config file are resolved relative to the config file's own directory, not the current working directory. This means configs are portable — you can run `terraflow run -c /any/dir/config.yml` from any location.

## Common flags

| Flag | Description |
| --- | --- |
| `-c`, `--config` | Path to the YAML config file. |

### Example

```bash
# From the project root — paths in examples/demo_config.yml use ../data/
terraflow run --config examples/demo_config.yml

# Alternative: python -m fallback (no install required)
python -m terraflow.cli run --config examples/demo_config.yml
```

## Sensitivity analysis

Run Sobol' and Morris sensitivity analysis over `ModelParams` weights to understand which parameters drive score variance most:

```bash
terraflow sensitivity -c config.yml
```

Requires a `sensitivity:` block in your config:

```yaml
sensitivity:
  method: sobol          # sobol | morris | both (default: both)
  n_samples: 512         # Sobol' sample count (must be power of 2)
  morris_trajectories: 10
```

Output is written to `outputs/runs/<fingerprint>/sensitivity_report.json`.

```json
{
  "sobol": {
    "w_v": {"S1": 0.42, "ST": 0.51},
    "w_t": {"S1": 0.31, "ST": 0.38},
    "w_r": {"S1": 0.27, "ST": 0.35}
  },
  "morris": {
    "w_v": {"mu_star": 0.19, "sigma": 0.04},
    ...
  }
}
```

See [`notebooks/02_sensitivity_analysis.ipynb`](../notebooks/02_sensitivity_analysis.ipynb) for a worked example.

## Model validation

Validate the pipeline output against spatial structure and an optional reference dataset:

```bash
terraflow validate -c config.yml
```

Requires a `validation:` block in your config:

```yaml
validation:
  n_blocks_side: 4        # splits bounding box into n×n spatial blocks
  buffer_deg: 0.1         # degrees of buffer excluded between train/test folds
  reference_csv: data/reference_labels.csv   # optional; columns: lat, lon, label
```

Results are appended to the existing `report.json` under the `"validation"` key:

```json
{
  "validation": {
    "method": "spatial_block_cv",
    "citation": "Roberts et al. 2017, Ecography",
    "n_folds": 12,
    "mean_fold_accuracy": 0.74,
    "cohen_kappa": 0.61,
    "morans_i_residuals": 0.08,
    "kriging_loocv_rmse": {"mean_temp": 0.42, "total_rain": 12.1}
  }
}
```

!!! note "What fold accuracy means here"
    TerraFlow's suitability model has no free parameters — scores are deterministic given the config. Fold accuracy reflects how spatially consistent the label distribution is across your study area, not model generalization.

See [`notebooks/03_model_validation.ipynb`](../notebooks/03_model_validation.ipynb) for a worked example.

## H3 export

Re-index pipeline output to H3 hexagonal cells for interop with DeckGL, Kepler.gl, and h3pandas. Requires the optional `[h3]` extra:

```bash
pip install terraflow-agro[h3]
terraflow export --format h3 -c config.yml
# or pass an explicit resolution override:
terraflow export --format h3 -c config.yml --resolution 8
```

The output `h3_resolution_N.parquet` lands in the run directory alongside `features.parquet`. The H3 resolution participates in the run fingerprint, so different resolutions produce distinct cached artifacts.

See [`notebooks/04_h3_export.ipynb`](../notebooks/04_h3_export.ipynb) and the [H3 export guide](../h3-export.md) for a worked example.
