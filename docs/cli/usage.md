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
    terraflow --config path/to/config.yml
    ```

    The command will:

    1. Load and validate the YAML config
    2. Run the pipeline
    3. Write outputs to the configured output directory

=== "Python Module"

    ```python
    from terraflow.pipeline import main
    
    # Run the pipeline programmatically
    main("path/to/config.yml")
    ```

=== "Without Install"

    ```bash
    # Use python -m fallback (no install required)
    python -m terraflow.cli --config path/to/config.yml
    ```

!!! tip "Portable Configs"
    Relative paths in the config file are resolved relative to the config file's own directory, not the current working directory. This means configs are portable — you can run `terraflow -c /any/dir/config.yml` from any location.

## Common flags

| Flag | Description |
| --- | --- |
| `-c`, `--config` | Path to the YAML config file. |

### Example

```bash
# From the project root — paths in examples/demo_config.yml use ../data/
terraflow --config examples/demo_config.yml

# Alternative: python -m fallback (no install required)
python -m terraflow.cli --config examples/demo_config.yml
```
