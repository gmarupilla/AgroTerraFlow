# H3 Export

TerraFlow can re-index suitability results by [H3](https://h3geo.org/) hexagonal cells,
enabling direct interop with H3-native toolchains such as DeckGL, Kepler.gl, and
`h3pandas`.

## Installation

H3 support is an optional extra:

```bash
pip install terraflow-agro[h3]
```

This adds `h3-py>=4.0` as a dependency. The core `terraflow` install remains lean.

## Python API

```python
from terraflow.export import to_h3

# features is a DataFrame from features.parquet with columns:
# lat, lon, score, v_index, mean_temp, total_rain, label
h3_df = to_h3(features, resolution=8)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `features` | `pd.DataFrame` | — | Pipeline output with lat/lon and score columns |
| `resolution` | `int` | `8` | H3 resolution 0-15 (8 ≈ 0.74 km² per cell) |

**Returns** a `pd.DataFrame` indexed by `h3_cell` with aggregated columns:
`score`, `v_index`, `mean_temp`, `total_rain`, `label` (label by mode per cell).

**Raises**

- `ImportError` — if `h3-py` is not installed
- `ValueError` — if resolution is outside 0–15 or required columns are missing

## CLI

Run the export subcommand after a successful pipeline run:

```bash
terraflow export --format h3 -c config.yml
```

Override the resolution from the command line:

```bash
terraflow export --format h3 --resolution 4 -c config.yml
```

Options:

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--config` | `-c` | yes | Path to YAML config file |
| `--format` | `-f` | yes | Export format. Currently: `h3` |
| `--resolution` | `-r` | no | H3 resolution override (0–15) |

## Config

Add an `export:` section to your YAML config:

```yaml
export:
  h3_resolution: 8   # default resolution for CLI and run_export()
```

`h3_resolution` is validated by the `ExportConfig` Pydantic model (must be 0–15).
The CLI `--resolution` flag overrides this value for a single invocation without
modifying the config file.

## Output

The H3 parquet artifact is written alongside the other pipeline artifacts:

```
outputs/runs/<fingerprint>/
  features.parquet              — original pixel-level results
  h3_resolution_8.parquet       — H3-indexed results at resolution 8
  manifest.json
  report.json
  results.csv
```

Schema of `h3_resolution_N.parquet`:

| Column | Type | Description |
|--------|------|-------------|
| `h3_cell` | `str` | H3 cell identifier at the requested resolution |
| `score` | `float` | Mean suitability score across pixels in cell |
| `v_index` | `float` | Mean vegetation index |
| `mean_temp` | `float` | Mean temperature |
| `total_rain` | `float` | Mean total rainfall |
| `label` | `str` | Majority suitability label in cell |

## Example

See the [H3 Export Demo notebook](notebooks/04_h3_export.ipynb) for a worked example
using synthetic data.
