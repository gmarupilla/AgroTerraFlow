# Phase 02: Sensitivity Analysis - Research

**Researched:** 2026-03-27
**Domain:** SALib (Sobol'/Morris), Typer CLI, Pydantic v2 config extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Migrate `terraflow/cli.py` from flat argparse to **Typer** — `terraflow` becomes the top-level app with subcommands as the expansion surface for future phases.
- **D-02:** The existing `terraflow -c config.yml` command is **renamed** to `terraflow run -c config.yml`. This is a one-time breaking change acceptable at the pre-JOSS stage.
- **D-03:** `terraflow sensitivity -c config.yml` is the new Phase 2 subcommand. Future subcommands (`validate`, `export`, `inspect`) follow the same pattern.
- **D-04:** Add a `sensitivity:` section to the existing `config.yml`. The section specifies per-weight bounds (`w_v`, `w_t`, `w_r` each with `low` and `high`), `n_samples` (int, must be power-of-2 for Sobol'), and optionally `method: sobol | morris | both` (default: both).
- **D-05:** Only the three model weights (`w_v`, `w_t`, `w_r`) are sweepable.
- **D-06:** `n_samples` must be a power-of-2 for Sobol' sampling. Non-power-of-2 produces a clear CLI validation error before any computation.
- **D-07:** SALib is a **core dependency** — added to `[project.dependencies]` in `pyproject.toml`.
- **D-08:** `terraflow sensitivity` writes `sensitivity_report.json` to the `output_dir` specified in config.
- **D-09:** Print a ranked parameter table to stdout showing S1/ST (Sobol') or mu* (Morris) per weight parameter.
- **D-10:** `sensitivity_report.json` content constitutes the `sensitivity` block referenced in SENS-03.

### Claude's Discretion

- Internal structure of `sensitivity_report.json` (exact field names, nesting) — follow SALib output conventions.
- Whether `sensitivity` runs Sobol', Morris, or both when `method: both` is set — run sequentially, Sobol' first.
- Typer version pinning strategy — use latest stable compatible with Python 3.10+.

### Deferred Ideas (OUT OF SCOPE)

- `terraflow validate` subcommand — Phase 3 scope
- `terraflow export` subcommand — Phase 4 scope
- `terraflow inspect` — future, not yet in roadmap
- Sweeping normalization bounds (v_min/max, t_min/max, r_min/max) — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SENS-01 | User can run Sobol' S1 and ST indices over all ModelParams bounds using SALib | SALib 1.5.2 `SALib.sample.sobol.sample()` + `SALib.analyze.sobol.analyze()` — verified API below |
| SENS-02 | User can run Morris elementary effects screening over ModelParams bounds | SALib 1.5.2 `SALib.sample.morris.sample()` + `SALib.analyze.morris.analyze()` — verified API below |
| SENS-03 | `report.json` includes a `sensitivity` block with Sobol' indices, CI, and rankings | `sensitivity_report.json` serves as the sensitivity block; content structure documented below |
| SENS-04 | `terraflow sensitivity -c config.yml` CLI subcommand with power-of-2 validation | Typer 0.12+ subcommand pattern + `math.log2` + bitwise check before computation |
</phase_requirements>

---

## Summary

Phase 2 has two distinct technical sub-problems: (1) migrating the CLI from argparse to Typer with a subcommand architecture, and (2) implementing the sensitivity analysis module using SALib. Both are well-understood problems with stable libraries.

The critical API fact for planning: SALib 1.5 replaced `SALib.sample.saltelli` with `SALib.sample.sobol` (saltelli is deprecated, scheduled for removal in 1.5.1). All new code must use `from SALib.sample.sobol import sample` not `from SALib.sample.saltelli import sample`. The Typer migration involves the existing `main()` entry point staying in `cli.py` but its internals being rewritten — the `pyproject.toml` entry point `terraflow = "terraflow.cli:main"` does not change.

The suitability model is a pure function `score = w_v * norm(v) + w_t * norm(t) + w_r * norm(r)`. For sensitivity analysis, the model evaluator is a simple wrapper that accepts a 2D SALib sample matrix, reconstructs weights, calls `suitability_score_array()` with representative fixed inputs (midpoint of normalization bounds), and returns a 1D output vector. Existing `model.py:suitability_score_array()` can be reused directly.

**Primary recommendation:** Implement `terraflow/sensitivity.py` as a standalone module with a `run_sensitivity(config_path)` function, add `SensitivityConfig` to `config.py`, migrate `cli.py` to Typer with `app.add_typer()` pattern, update `pyproject.toml` with SALib and Typer dependencies.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SALib | 1.5.2 (latest) | Sobol' and Morris sensitivity analysis | The citable library for GSA in Python; cited by Herman & Usher 2017 JOSS paper |
| typer | 0.12.5+ (latest: 0.24.1) | CLI subcommand framework | Pydantic-author's CLI library; type-hint-native; standard for Python CLIs |
| numpy | already in deps | SALib sample/evaluate arrays | Required internally by SALib |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | bundled with typer>=0.12 | Table formatting for stdout output | Included automatically via `typer[standard]`; use `rich.table.Table` for ranked output |
| math (stdlib) | stdlib | Power-of-2 validation | `math.log2(n)` + `n & (n-1) == 0` check; no extra dependency |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SALib | chaospy, openturns | SALib is the JOSS-citable standard; chaospy/openturns are heavier and less commonly cited in applied ecology literature |
| typer | click directly | Typer wraps Click; user locked decision |
| rich.Table | tabulate | rich is bundled with typer>=0.12; avoids extra dep |

**Installation:**
```bash
pip install "SALib>=1.5" "typer>=0.12.5"
```

**Version verification (confirmed 2026-03-27):**
- `SALib`: latest 1.5.2 (PyPI verified via `pip index versions SALib`)
- `typer`: latest 0.24.1, currently installed 0.9.0 (PyPI verified). Must upgrade to >=0.12 for `typer-slim[standard]` bundling and `Annotated` patterns.

---

## Architecture Patterns

### Recommended Project Structure

```
terraflow/
├── cli.py           # Typer app (replaces argparse); add_typer for 'run' and 'sensitivity'
├── config.py        # Add SensitivityConfig, WeightBounds Pydantic models
├── sensitivity.py   # New module: run_sensitivity(), _evaluate_model(), _build_problem()
└── model.py         # Unchanged — suitability_score_array() reused by sensitivity module
```

### Pattern 1: Typer Subcommand App

**What:** Replace argparse `main()` with a `typer.Typer()` app that uses `add_typer()` to add subcommands.

**When to use:** Single entry point (`terraflow`) with multiple subcommands (`run`, `sensitivity`).

```python
# terraflow/cli.py
import typer
from pathlib import Path
from typing import Annotated
from .pipeline import run_pipeline
from .sensitivity import run_sensitivity
from .utils import logger

app = typer.Typer(help="TerraFlow: reproducible geospatial agricultural modeling.")

@app.command("run")
def run_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run the geospatial modeling pipeline."""
    logger.info("TerraFlow run starting with config: %s", config)
    run_pipeline(config)
    logger.info("TerraFlow run completed successfully")

@app.command("sensitivity")
def sensitivity_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", exists=True, file_okay=True,
                     dir_okay=False, readable=True, help="Path to YAML config file"),
    ],
) -> None:
    """Run Sobol' and/or Morris sensitivity analysis."""
    run_sensitivity(config)

def main() -> None:
    app()  # entry point stays as terraflow.cli:main

if __name__ == "__main__":
    main()
```

**Key Typer facts:**
- `typer.Option("--config", "-c", ...)` — pass long and short names as positional args to `typer.Option()`.
- `exists=True` on a `Path` option validates file existence before the function body runs.
- `Annotated[Path, typer.Option(...)]` is the recommended pattern in Typer 0.9+ (and continues in 0.12+).
- The `pyproject.toml` entry point `terraflow = "terraflow.cli:main"` requires **no change** — `main()` now calls `app()` instead of `parser.parse_args()`.
- Typer 0.14.0 changed subcommand name inference: always pass `name=` explicitly (or use `@app.command("run")` decorator argument) to be safe across versions.

### Pattern 2: SALib Sobol' Analysis (SALib 1.5 API)

**What:** Define a 3-parameter problem, generate Saltelli-scheme samples via `SALib.sample.sobol`, evaluate the suitability model, and analyze with `SALib.analyze.sobol`.

**Critical API note:** `SALib.sample.saltelli` is deprecated in 1.5 and removed in 1.5.1. Use `SALib.sample.sobol` exclusively.

```python
# Source: github.com/SALib/SALib, main branch, verified 2026-03-27
from SALib.sample.sobol import sample as sobol_sample
from SALib.analyze.sobol import analyze as sobol_analyze
import numpy as np

# Problem definition — 3 parameters, bounds from SensitivityConfig
problem = {
    "num_vars": 3,
    "names": ["w_v", "w_t", "w_r"],
    "bounds": [
        [cfg.sensitivity.w_v.low, cfg.sensitivity.w_v.high],
        [cfg.sensitivity.w_t.low, cfg.sensitivity.w_t.high],
        [cfg.sensitivity.w_r.low, cfg.sensitivity.w_r.high],
    ],
}

N = cfg.sensitivity.n_samples  # must be power-of-2; validated before this point

# SALib 1.5: sobol.sample generates N*(2D+2) = N*8 rows for 3 params, calc_second_order=True
param_values = sobol_sample(problem, N, calc_second_order=True, seed=42)
# param_values.shape == (N*8, 3)

# Evaluate model: wrap suitability_score_array with representative fixed inputs
Y = _evaluate_model(param_values, cfg)  # shape (N*8,)

# Analyze — returns ResultDict with S1, S1_conf, ST, ST_conf, S2, S2_conf
Si = sobol_analyze(problem, Y, calc_second_order=True, seed=42)

# ResultDict access
s1 = Si["S1"]        # shape (3,) — first-order indices for w_v, w_t, w_r
st = Si["ST"]        # shape (3,)
s1_conf = Si["S1_conf"]
st_conf = Si["ST_conf"]

# Convert to DataFrame
total_Si, first_Si, second_Si = Si.to_df()
```

**Sample size relationship:**
- `calc_second_order=True`: produces `N * (2D + 2)` = `N * 8` rows (D=3 parameters)
- `calc_second_order=False`: produces `N * (D + 2)` = `N * 5` rows

### Pattern 3: SALib Morris Analysis

```python
# Source: github.com/SALib/SALib, main branch, verified 2026-03-27
from SALib.sample.morris import sample as morris_sample
from SALib.analyze.morris import analyze as morris_analyze

# Same problem dict as Sobol'
# N here = number of trajectories (not Sobol' base samples)
# Total evaluations = (num_vars + 1) * N = 4 * N for 3 parameters
X = morris_sample(problem, N=10, num_levels=4, seed=42)
# X.shape == (40, 3) for N=10, D=3

Y_morris = _evaluate_model(X, cfg)  # shape (40,)

# analyze requires X (inputs) AND Y (outputs), unlike Sobol'
Si_m = morris_analyze(problem, X, Y_morris, num_levels=4, seed=42)

# ResultDict keys for Morris
mu_star = Si_m["mu_star"]      # shape (3,) — primary ranking metric
mu = Si_m["mu"]                # shape (3,)
sigma = Si_m["sigma"]          # shape (3,)
mu_star_conf = Si_m["mu_star_conf"]  # shape (3,)
```

**Key difference from Sobol':** Morris `analyze()` requires **both** X (sample matrix) and Y (outputs). Sobol' `analyze()` requires only Y (X is not passed).

### Pattern 4: Model Evaluator Function

The sensitivity evaluator needs to convert SALib sample rows (each row = [w_v, w_t, w_r]) to suitability scores. Because only weights are swept (not normalization bounds or input data), use midpoint values of the normalization bounds as representative fixed inputs.

```python
from .model import suitability_score_array
from .config import ModelParams
import numpy as np

def _evaluate_model(param_values: np.ndarray, cfg: "SensitivityRunConfig") -> np.ndarray:
    """Evaluate suitability score for each SALib sample row.

    Each row in param_values is [w_v, w_t, w_r]. Fixed inputs are midpoints
    of the normalization bounds from the base model_params config.
    """
    mp = cfg.model_params
    n = param_values.shape[0]

    # Representative fixed inputs — midpoints of normalization bounds
    v_mid = (mp.v_min + mp.v_max) / 2.0
    t_mid = (mp.t_min + mp.t_max) / 2.0
    r_mid = (mp.r_min + mp.r_max) / 2.0

    v_arr = np.full(n, v_mid)
    t_arr = np.full(n, t_mid)
    r_arr = np.full(n, r_mid)

    # Build per-sample params — vectorized: reconstruct ModelParams for each row
    # IMPORTANT: weights from param_values may not sum to 1.0, so
    # ModelParams.validate_ranges() must NOT be called during sensitivity sweeps.
    # Use suitability_score_array with per-row params — see pitfall below.
    results = np.zeros(n)
    for i in range(n):
        w_v, w_t, w_r = float(param_values[i, 0]), float(param_values[i, 1]), float(param_values[i, 2])
        # Inline weight application without ModelParams construction (avoids weight-sum validator)
        v_n = np.clip((v_mid - mp.v_min) / (mp.v_max - mp.v_min), 0, 1)
        t_n = np.clip((t_mid - mp.t_min) / (mp.t_max - mp.t_min), 0, 1)
        r_n = np.clip((r_mid - mp.r_min) / (mp.r_max - mp.r_min), 0, 1)
        score = w_v * v_n + w_t * t_n + w_r * r_n
        results[i] = np.clip(score, 0.0, 1.0)
    return results
```

**Alternative (vectorized):** Pre-compute normalized fixed inputs once, then dot-product with weight columns:

```python
def _evaluate_model_vectorized(param_values: np.ndarray, cfg) -> np.ndarray:
    mp = cfg.model_params
    v_n = np.clip((mp.v_min + mp.v_max) / 2 - mp.v_min) / (mp.v_max - mp.v_min), 0, 1)
    t_n = np.clip(((mp.t_min + mp.t_max) / 2 - mp.t_min) / (mp.t_max - mp.t_min), 0, 1)
    r_n = np.clip(((mp.r_min + mp.r_max) / 2 - mp.r_min) / (mp.r_max - mp.r_min), 0, 1)
    fixed = np.array([v_n, t_n, r_n])  # shape (3,)
    # param_values: (N, 3), fixed: (3,) — dot gives (N,)
    return np.clip(param_values @ fixed, 0.0, 1.0)
```

The vectorized version is preferred for performance — use it.

### Pattern 5: Pydantic Config Extension

```python
# terraflow/config.py — additions
from pydantic import BaseModel, ConfigDict, field_validator

class WeightBounds(BaseModel):
    """Bounds for a single weight parameter in sensitivity analysis."""
    low: float
    high: float

    model_config = ConfigDict(extra="forbid")

    @field_validator("high")
    @classmethod
    def high_gt_low(cls, v: float, info) -> float:
        low = info.data.get("low")
        if low is not None and v <= low:
            raise ValueError(f"high ({v}) must be greater than low ({low})")
        return v

class SensitivityConfig(BaseModel):
    """Configuration for sensitivity analysis."""
    w_v: WeightBounds
    w_t: WeightBounds
    w_r: WeightBounds
    n_samples: int = 1024
    method: Literal["sobol", "morris", "both"] = "both"

    model_config = ConfigDict(extra="forbid")

    @field_validator("n_samples")
    @classmethod
    def validate_power_of_two(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"n_samples must be positive, got {v}")
        if (v & (v - 1)) != 0:
            raise ValueError(
                f"n_samples must be a power of 2 for Sobol' sampling, got {v}. "
                f"Nearest power of 2: {2 ** round(math.log2(v))}"
            )
        return v
```

**Placement:** `SensitivityConfig` is an optional field in `PipelineConfig` (or loaded separately in the sensitivity subcommand). Because `sensitivity:` is not required for `terraflow run`, add it as `Optional[SensitivityConfig] = None` to `PipelineConfig`. The `sensitivity` subcommand raises a clear error if the `sensitivity:` section is absent from the config.

### Pattern 6: Power-of-2 Validation (SENS-04)

```python
import math

def _validate_power_of_two(n: int) -> None:
    """Raise ValueError with guidance if n is not a power of 2."""
    if n <= 0 or (n & (n - 1)) != 0:
        nearest = 2 ** round(math.log2(max(n, 1)))
        raise typer.BadParameter(
            f"n_samples={n} is not a power of 2. "
            f"Try n_samples={nearest} or {nearest * 2}.",
        )
```

Use `typer.BadParameter` when inside a Typer command so Typer formats the error message correctly (exit code 2, prefixed with "Error: Invalid value for ...").

### Pattern 7: sensitivity_report.json Structure

Follow SALib output conventions. The file is written atomically to `output_dir/sensitivity_report.json`:

```json
{
  "schema_version": "1",
  "method": "both",
  "n_samples": 1024,
  "parameters": ["w_v", "w_t", "w_r"],
  "bounds": {
    "w_v": {"low": 0.2, "high": 0.5},
    "w_t": {"low": 0.2, "high": 0.5},
    "w_r": {"low": 0.1, "high": 0.4}
  },
  "sobol": {
    "S1": {"w_v": 0.35, "w_t": 0.40, "w_r": 0.25},
    "S1_conf": {"w_v": 0.03, "w_t": 0.04, "w_r": 0.02},
    "ST": {"w_v": 0.38, "w_t": 0.43, "w_r": 0.28},
    "ST_conf": {"w_v": 0.04, "w_t": 0.05, "w_r": 0.03},
    "ranking": ["w_t", "w_v", "w_r"]
  },
  "morris": {
    "mu_star": {"w_v": 0.12, "w_t": 0.15, "w_r": 0.09},
    "mu_star_conf": {"w_v": 0.01, "w_t": 0.01, "w_r": 0.01},
    "mu": {"w_v": 0.10, "w_t": 0.13, "w_r": 0.08},
    "sigma": {"w_v": 0.05, "w_t": 0.06, "w_r": 0.04},
    "ranking": ["w_t", "w_v", "w_r"]
  }
}
```

### Anti-Patterns to Avoid

- **Using `SALib.sample.saltelli`:** Deprecated in SALib 1.4.6+, removed in 1.5.1. Always use `SALib.sample.sobol`.
- **Passing X to `sobol.analyze()`:** Sobol' analysis takes only Y and problem. Morris requires both X and Y.
- **Using non-power-of-2 N with Sobol':** SALib will compute incorrect indices silently. Must validate before calling `sobol_sample()`.
- **Constructing `ModelParams` for each sample row:** The weight-sum validator (`abs(sum - 1.0) > 0.01`) will reject swept weight combinations. Use inline weight arithmetic instead.
- **Inferring Typer subcommand names from callback:** Typer 0.14.0 removed automatic name inference. Always use `@app.command("name")` explicitly.
- **Writing to `output_dir` directly without `ensure_dir`:** Use existing `terraflow.utils.ensure_dir()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sobol' variance decomposition | Custom Saltelli sampling + Jansen estimator | `SALib.sample.sobol` + `SALib.analyze.sobol` | Correct bootstrapped CI calculation is non-trivial; SALib is peer-reviewed and citable |
| Morris elementary effects | Custom trajectory generation | `SALib.sample.morris` + `SALib.analyze.morris` | Optimal trajectory selection uses combinatorial optimization; hand-rolling gets it wrong |
| CLI subcommands | Custom dispatcher in argparse | Typer's `add_typer()` / `@app.command()` | Locked decision; Typer handles help text, type coercion, error formatting |
| Terminal table formatting | f-string formatting | `rich.table.Table` (bundled with typer>=0.12) | Column alignment, header formatting, color — free with existing dependency |
| Atomic file writes | `open(..., "w")` directly | `_atomic_write_text()` from `pipeline.py` | Pattern established in Phase 1; prevents partial-write corruption |

**Key insight:** The sensitivity analysis problem is entirely solved by SALib. The implementation work is wiring: config parsing, model evaluation wrapper, result formatting, and CLI plumbing.

---

## Common Pitfalls

### Pitfall 1: ModelParams Weight-Sum Validator Blocks Sensitivity Sweeps
**What goes wrong:** Sensitivity samples include weight combinations like [0.6, 0.3, 0.1] that happen to sum correctly, but also combinations like [0.5, 0.5, 0.1] that do not. Constructing `ModelParams` for each sample row will trigger `validate_ranges()` which checks `abs(sum - 1.0) > 0.01` and raises `ValueError` for most sensitivity samples.
**Why it happens:** The `ModelParams` validator enforces the weight-sum constraint for pipeline runs, but sensitivity analysis intentionally explores all combinations within bounds.
**How to avoid:** Do NOT construct `ModelParams` objects during sensitivity evaluation. Compute `score = w_v * v_n + w_t * t_n + w_r * r_n` directly using inline arithmetic.
**Warning signs:** `ValueError: Weights must sum to approximately 1.0` during sensitivity runs.

### Pitfall 2: SALib 1.5 Sampler Module Change
**What goes wrong:** Code importing `from SALib.sample.saltelli import sample` receives a deprecation warning in 1.4.x and an `ImportError` in 1.5.1+.
**Why it happens:** SALib reorganized samplers. The Sobol' sampler is now at `SALib.sample.sobol`.
**How to avoid:** Use `from SALib.sample.sobol import sample as sobol_sample` exclusively. Confirmed current API in SALib 1.5.2.
**Warning signs:** `DeprecationWarning: salib.sample.saltelli will be removed` or `ImportError`.

### Pitfall 3: Non-Power-of-2 N Produces Silently Wrong Sobol' Indices
**What goes wrong:** Passing `N=100` (not a power of 2) to `sobol_sample()` does not raise an error, but the resulting Sobol' indices are incorrect because the Saltelli scheme requires power-of-2 samples for the quasi-random sequence properties to hold.
**Why it happens:** SALib 1.5 does not enforce this constraint internally; it's documented as a requirement.
**How to avoid:** Validate `n_samples` in `SensitivityConfig.validate_power_of_two()` field validator before any SALib calls. Per SENS-04, this must produce a CLI validation error.
**Warning signs:** Sobol' indices that don't sum correctly or are outside [0, 1].

### Pitfall 4: Typer Version Mismatch with Installed 0.9.0
**What goes wrong:** The project currently has typer 0.9.0 installed. The `Annotated` + `typer.Option(exists=True)` pattern for Path parameters changed slightly between 0.9 and 0.12+. More significantly, 0.12.0 restructured packaging (`typer` depends on `typer-slim[standard]`) and 0.14.0 changed subcommand name inference.
**Why it happens:** Typer is not yet in `pyproject.toml` dependencies; it's only present as a dev install.
**How to avoid:** Pin `typer>=0.12.5` in `pyproject.toml [project.dependencies]`. Test with the upgraded version. The `Annotated` pattern works in both 0.9 and 0.12+ so transition is clean.
**Warning signs:** Subcommand names not resolving, or missing `rich` for table output.

### Pitfall 5: Existing test_cli.py Patches Wrong Import Path
**What goes wrong:** Current `test_cli.py` patches `"terraflow.cli.run_pipeline"`. After the Typer migration, the import path of `run_pipeline` in `cli.py` stays the same, so existing patches remain valid. However, tests that invoke `main()` by patching `sys.argv` with `["terraflow", "-c", ...]` will break — they must become `["terraflow", "run", "-c", ...]`.
**Why it happens:** The `run` subcommand is a new positional argument before `-c`.
**How to avoid:** Update all existing `test_cli.py` tests to use `["terraflow", "run", "-c", ...]`. Also update the three integration test configs that currently use the flat `terraflow -c` interface.
**Warning signs:** `Error: No such option: -c` when running tests post-migration.

### Pitfall 6: Morris Analyze Requires X (Not Just Y)
**What goes wrong:** Following the Sobol' pattern and calling `morris_analyze(problem, Y)` raises a `TypeError` because Morris requires the input matrix X as the second positional argument.
**Why it happens:** The Morris and Sobol' API signatures differ — Morris needs X to compute elementary effects.
**How to avoid:** Store `X = morris_sample(...)` and pass it to `morris_analyze(problem, X, Y, ...)`.
**Warning signs:** `TypeError: analyze() missing 1 required positional argument`.

---

## Code Examples

### Complete Sensitivity Module Skeleton

```python
# terraflow/sensitivity.py
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np

from .config import SensitivityConfig, load_config_dict
from .utils import ensure_dir, logger


def _validate_n_samples(n: int) -> None:
    """Raise ValueError if n is not a positive power of 2."""
    if n <= 0 or (n & (n - 1)) != 0:
        nearest = 2 ** round(math.log2(max(n, 1)))
        raise ValueError(
            f"n_samples={n} must be a power of 2 for Sobol' sampling. "
            f"Try {nearest} or {nearest * 2}."
        )


def _build_problem(sens_cfg: SensitivityConfig) -> Dict[str, Any]:
    return {
        "num_vars": 3,
        "names": ["w_v", "w_t", "w_r"],
        "bounds": [
            [sens_cfg.w_v.low, sens_cfg.w_v.high],
            [sens_cfg.w_t.low, sens_cfg.w_t.high],
            [sens_cfg.w_r.low, sens_cfg.w_r.high],
        ],
    }


def _evaluate_model_vectorized(param_values: np.ndarray, mp) -> np.ndarray:
    """Compute suitability scores for SALib sample matrix without ModelParams construction."""
    v_n = np.clip(((mp.v_min + mp.v_max) / 2 - mp.v_min) / (mp.v_max - mp.v_min), 0.0, 1.0)
    t_n = np.clip(((mp.t_min + mp.t_max) / 2 - mp.t_min) / (mp.t_max - mp.t_min), 0.0, 1.0)
    r_n = np.clip(((mp.r_min + mp.r_max) / 2 - mp.r_min) / (mp.r_max - mp.r_min), 0.0, 1.0)
    fixed = np.array([v_n, t_n, r_n])
    return np.clip(param_values @ fixed, 0.0, 1.0)


def run_sensitivity(config_path: Path) -> Path:
    """Run sensitivity analysis and write sensitivity_report.json.

    Returns path to the written report file.
    """
    # Source: SALib 1.5.2 API
    from SALib.sample.sobol import sample as sobol_sample
    from SALib.analyze.sobol import analyze as sobol_analyze
    from SALib.sample.morris import sample as morris_sample
    from SALib.analyze.morris import analyze as morris_analyze
    ...
```

### Config YAML Extension

```yaml
# config.yml — existing pipeline section unchanged
raster_path: data/raster.tif
climate_csv: data/climate.csv
output_dir: outputs
roi:
  type: bbox
  xmin: -100.0
  ymin: 39.9
  xmax: -99.9
  ymax: 40.1
model_params:
  v_min: 0.0
  v_max: 25.0
  t_min: 0.0
  t_max: 40.0
  r_min: 0.0
  r_max: 300.0
  w_v: 0.4
  w_t: 0.3
  w_r: 0.3

# New section — consumed by 'terraflow sensitivity' only
sensitivity:
  w_v:
    low: 0.2
    high: 0.5
  w_t:
    low: 0.2
    high: 0.5
  w_r:
    low: 0.1
    high: 0.4
  n_samples: 1024
  method: both  # sobol | morris | both
```

### Stdout Ranked Table Pattern

```python
# Use rich.table.Table (bundled with typer>=0.12)
import rich
from rich.table import Table
from rich.console import Console

def _print_sobol_table(names, S1, ST, S1_conf, ST_conf) -> None:
    console = Console()
    table = Table(title="Sobol' Sensitivity Indices", show_header=True)
    table.add_column("Parameter", style="bold")
    table.add_column("S1 (first-order)")
    table.add_column("S1 95% CI")
    table.add_column("ST (total-order)")
    table.add_column("ST 95% CI")
    # Sort by ST descending
    order = np.argsort(ST)[::-1]
    for i in order:
        table.add_row(
            names[i],
            f"{S1[i]:.4f}",
            f"±{S1_conf[i]:.4f}",
            f"{ST[i]:.4f}",
            f"±{ST_conf[i]:.4f}",
        )
    console.print(table)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `SALib.sample.saltelli` | `SALib.sample.sobol` | SALib 1.4.6 (deprecated) / 1.5.1 (removed) | All new code must use `sobol`, not `saltelli` |
| Argparse flat CLI | Typer subcommand app | This phase (D-01/D-02) | Breaking: `terraflow -c` becomes `terraflow run -c` |
| Typer 0.9.0 (installed) | Typer 0.12.5+ | 0.12.0 restructured packaging; 0.14.0 changed name inference | Upgrade required; `Annotated` pattern compatible across both |

**Deprecated/outdated:**
- `SALib.sample.saltelli`: deprecated in 1.4.6, removed in 1.5.1 — do not reference in any code or docs
- `terraflow -c config.yml` (flat command): replaced by `terraflow run -c config.yml` in this phase

---

## Open Questions

1. **SensitivityConfig as optional field in PipelineConfig or loaded separately**
   - What we know: `PipelineConfig` uses `ConfigDict(extra="forbid")`, so any field present in the YAML must be declared in the model. If `sensitivity:` is in the YAML, `PipelineConfig` will reject it unless declared.
   - What's unclear: Should `PipelineConfig` gain `sensitivity: Optional[SensitivityConfig] = None`, or should the sensitivity subcommand load config independently using a separate Pydantic model that extends `PipelineConfig`?
   - Recommendation: Add `sensitivity: Optional[SensitivityConfig] = None` to `PipelineConfig`. This allows the same config.yml to be used for both `terraflow run` and `terraflow sensitivity` without duplication. The sensitivity subcommand reads the full config and raises a user-friendly error if `sensitivity:` is absent.

2. **Morris N meaning vs Sobol' N meaning in config**
   - What we know: For Sobol', `N` is the base count (generates `N * 8` rows). For Morris, `N` is the number of trajectories (generates `(D+1) * N = 4 * N` rows). A single `n_samples: 1024` means very different computational costs for each method.
   - What's unclear: Is the user aware that `method: both` with `n_samples: 1024` runs Sobol' with `8192` model evaluations AND Morris with `4096` evaluations? Should the config expose Morris trajectory count separately?
   - Recommendation: Use `n_samples` for Sobol' (power-of-2 constraint enforced) and a fixed `morris_trajectories: 10` default in `SensitivityConfig` (or derive it as `min(n_samples // 10, 50)`). Document the evaluation counts in CLI output. Flag for planner to decide config shape.

3. **Output location: flat `output_dir/sensitivity_report.json` vs run-dir**
   - What we know: D-08 specifies flat `output_dir` (not a runs/ subdirectory), and the report is standalone.
   - What's unclear: There is no run fingerprint for sensitivity analysis runs, which means re-running overwrites the previous report.
   - Recommendation: Consistent with D-08 — write to `output_dir/sensitivity_report.json` directly. Add a `timestamp` field to the JSON so successive runs are distinguishable in the file's content even if the file is overwritten.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SALib | SENS-01, SENS-02 | Not installed | — (latest: 1.5.2) | None — must install |
| typer | D-01, D-02, D-03 | Installed (dev) | 0.9.0 (latest: 0.24.1) | None — must upgrade to >=0.12.5 |
| numpy | SALib internal | Installed | (existing dep) | — |
| rich | stdout table | Bundled with typer>=0.12 | — (comes with upgrade) | tabulate (extra dep), but unnecessary if typer upgraded |
| Python | all | 3.x | Darwin, zsh shell | — |

**Missing dependencies with no fallback:**
- SALib 1.5.x — must be added to `[project.dependencies]` and installed

**Missing dependencies with fallback:**
- typer 0.12+ — currently 0.9.0 is installed; upgrade required; 0.9.0 could work for basic Typer patterns but lacks bundled `rich` and has the naming behavior that changed in 0.14.0

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_sensitivity.py tests/test_cli.py -x` |
| Full suite command | `pytest --cov=terraflow --cov-report=term-missing --cov-fail-under=85` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SENS-01 | `run_sensitivity()` returns Sobol' S1/ST for w_v, w_t, w_r with CIs | unit | `pytest tests/test_sensitivity.py::test_sobol_produces_s1_st -x` | Wave 0 |
| SENS-01 | S1 and ST values are in [0, 1], CIs are positive | unit | `pytest tests/test_sensitivity.py::test_sobol_index_bounds -x` | Wave 0 |
| SENS-02 | `run_sensitivity()` returns Morris mu_star, mu, sigma | unit | `pytest tests/test_sensitivity.py::test_morris_produces_mu_star -x` | Wave 0 |
| SENS-03 | `sensitivity_report.json` contains `sobol` and `morris` blocks with expected keys | unit | `pytest tests/test_sensitivity.py::test_report_json_schema -x` | Wave 0 |
| SENS-03 | File is written atomically to `output_dir/sensitivity_report.json` | unit | `pytest tests/test_sensitivity.py::test_report_written_to_output_dir -x` | Wave 0 |
| SENS-04 | `terraflow sensitivity -c config.yml` exits with error code 2 when n_samples is not power-of-2 | integration | `pytest tests/test_cli.py::test_sensitivity_nonpower_of_two -x` | Wave 0 |
| SENS-04 | `terraflow sensitivity -c config.yml` runs successfully with valid power-of-2 n_samples | integration | `pytest tests/test_cli.py::test_sensitivity_cmd_success -x` | Wave 0 |
| D-02 | Existing `terraflow run -c config.yml` works (renamed from flat `terraflow -c`) | integration | `pytest tests/test_cli.py::test_cli_run_subcommand -x` | Wave 0 (update existing) |
| D-02 | Old `terraflow -c config.yml` invocation no longer works | integration | `pytest tests/test_cli.py::test_old_flat_command_fails -x` | Wave 0 (update existing) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_sensitivity.py tests/test_cli.py -x`
- **Per wave merge:** `pytest --cov=terraflow --cov-report=term-missing --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_sensitivity.py` — new file covering SENS-01 through SENS-03
- [ ] `tests/test_cli.py` — update existing tests for `run` subcommand, add `sensitivity` subcommand tests
- [ ] `pip install "SALib>=1.5" "typer>=0.12.5"` — required before any test can pass

---

## Sources

### Primary (HIGH confidence)

- [github.com/SALib/SALib — sobol.py main branch](https://github.com/SALib/SALib/blob/main/src/SALib/analyze/sobol.py) — `analyze()` signature and ResultDict keys verified
- [github.com/SALib/SALib — morris.py main branch](https://github.com/SALib/SALib/blob/main/src/SALib/analyze/morris.py) — `analyze()` signature and return keys verified
- [github.com/SALib/SALib — sobol sampler main branch](https://github.com/SALib/SALib/blob/main/src/SALib/sample/sobol.py) — `sample()` signature verified; saltelli deprecation confirmed
- [github.com/SALib/SALib — morris sampler main branch](https://github.com/SALib/SALib/blob/main/src/SALib/sample/morris/morris.py) — `sample()` signature, N=trajectories, total evals formula
- [typer.tiangolo.com — Parameter Types: Path](https://typer.tiangolo.com/tutorial/parameter-types/path/) — `Annotated[Path, typer.Option(exists=True)]` syntax verified
- [typer.tiangolo.com — Release Notes](https://typer.tiangolo.com/release-notes/) — 0.12.0 packaging change, 0.14.0 name inference breaking change
- `pip index versions SALib` — latest 1.5.2 verified 2026-03-27
- `pip index versions typer` — latest 0.24.1, installed 0.9.0 verified 2026-03-27

### Secondary (MEDIUM confidence)

- [quaquel/EMAworkbench PR #211](https://github.com/quaquel/EMAworkbench/pull/211) — cross-referenced saltelli deprecation, confirms switch to `salib.sample.sobol` started in 1.4.6
- [SALib PyPI page](https://pypi.org/project/SALib/) — version history and deprecation notice

### Tertiary (LOW confidence)

- None — all critical claims verified against primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — SALib 1.5.2 and Typer versions verified from PyPI and GitHub main branch
- Architecture: HIGH — SALib API verified from source; Typer patterns verified from official docs
- Pitfalls: HIGH — saltelli deprecation confirmed by multiple sources; ModelParams validator issue identified from reading source code directly
- Open questions: MEDIUM — Q1/Q3 are architectural choices without wrong answers; Q2 requires planner judgment on config UX

**Research date:** 2026-03-27
**Valid until:** 2026-05-27 (SALib stable; Typer fast-moving but pinned version mitigates risk)
