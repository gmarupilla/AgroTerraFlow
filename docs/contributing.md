# Contributing

Thanks for helping improve TerraFlow! Here are the basics for v0.1.

## Local setup

```bash
make dev
```

This creates a virtual environment and installs development dependencies.

## Run tests

```bash
make test
```

## Linting

```bash
make lint
```

## Documentation

Install docs dependencies and run a local preview:

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

To validate the site:

```bash
mkdocs build --strict
```
