# CLI Usage

TerraFlow exposes a lightweight CLI for running the pipeline.

## Run with a config file

```bash
python -m terraflow.cli --config path/to/config.yml
```

The command will:

1. Load and validate the YAML config.
2. Run the pipeline.
3. Write outputs to the configured output directory.

## Common flags

| Flag | Description |
| --- | --- |
| `-c`, `--config` | Path to the YAML config file. |

### Example

```bash
python -m terraflow.cli --config examples/demo_config.yml
```
