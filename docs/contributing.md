---
title: Contributing Guidelines
description: How to set up locally, run tests and linting, preview docs, and submit a pull request to TerraFlow.
icon: material/source-pull
tags:
  - Development
  - Contributing
---

# Contributing

Thanks for helping improve TerraFlow! Here are the basics for v0.5.0+.

## Contribution Workflow

```mermaid
flowchart LR
    A[Fork Repository] --> B[Clone & Setup]
    B --> C[Create Branch]
    C --> D[Make Changes]
    D --> E[Run Tests]
    E --> F{Tests Pass?}
    F -->|No| D
    F -->|Yes| G[Run Linting]
    G --> H{Lint Pass?}
    H -->|No| D
    H -->|Yes| I[Commit Changes]
    I --> J[Push to Fork]
    J --> K[Create PR]
    K --> L[Code Review]
    L --> M[Merge]
    
    style E fill:#00b0ff,stroke:#0091ea,color:#fff
    style G fill:#00b0ff,stroke:#0091ea,color:#fff
    style M fill:#2d8a55,stroke:#1e5c3a,color:#fff
```

## Local setup

```bash title="Quick Setup"
make dev
```

This creates a virtual environment and installs development dependencies.

!!! tip "Prerequisites"
    - Python 3.9 or higher
    - `make` command (or run commands from Makefile manually)
    - Git for version control

## Run tests

```bash title="Test Suite"
make test
```

!!! success "Test Coverage"
    Aim for >80% coverage for new features. Check coverage report in `htmlcov/index.html`

## Linting

```bash title="Code Quality"
make lint
```

!!! warning "Pre-commit Requirement"
    All code must pass `black` formatting and `ruff` linting before PR approval.

## Documentation

Install docs dependencies and run a local preview:

=== "Preview Docs"

    ```bash
    uv pip install -r docs/requirements.txt
    mkdocs serve
    ```
    
    Open http://127.0.0.1:8000 in your browser

=== "Build & Validate"

    ```bash
    mkdocs build --strict
    ```
    
    Validates all links and ensures no warnings

!!! example "Documentation Standards"
    - Add docstrings to all public functions (NumPy style)
    - Update relevant `.md` files for user-facing changes
    - Create ADRs for significant architectural decisions
