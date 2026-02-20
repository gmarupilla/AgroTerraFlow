---
title: Contributing Guidelines
description: How to set up locally, run tests and linting, preview docs, and submit a pull request to TerraFlow.
icon: material/source-pull
tags:
  - Development
  - Contributing
---

# Contributing

Thanks for helping improve TerraFlow! Here are the basics for v0.2.0+.

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
uv pip install -r docs/requirements.txt
mkdocs serve
```

To validate the site:

```bash
mkdocs build --strict
```
