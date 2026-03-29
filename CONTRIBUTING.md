# Contributing to TerraFlow

TerraFlow is a solo-maintained research software project. Contributions are welcome
but should align with the project's scope: reproducible geospatial pipelines for
agricultural modeling.

## Dev Setup

```bash
git clone https://github.com/gmarupilla/AgroTerraFlow
cd AgroTerraFlow
pip install -e ".[dev]"
pytest
```

The test suite requires no external data — synthetic rasters are generated automatically.
To run with coverage: `pytest --cov=terraflow --cov-report=term-missing`

## Code Style

- Formatter: `black` (line length 88)
- Linter: `ruff`
- Type hints: required on all public functions
- Run both before opening a PR: `ruff check . && black --check .`

## Pull Requests

- Keep PRs small and focused on a single concern
- All new behavior must include tests
- Update `CHANGELOG.md` under `[Unreleased]`
- CI must pass before review

## Issues

Use issues to:
- Report bugs with a reproducible config + stack trace
- Propose targeted improvements with clear motivation
- Discuss changes before writing code for non-trivial work

Feature requests are evaluated against project scope (see README). Requests that
require significant maintenance burden or diverge from the core pipeline design
may be declined.

## Scope

TerraFlow is not a general geospatial framework. Before contributing, read the
"Project Scope" section in the README to avoid building something that won't be merged.

## Questions

Open a GitHub issue with the `question` label. Response is best-effort.
