"""Sensitivity analysis module -- Sobol' and Morris methods via SALib."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
from SALib.analyze.morris import analyze as morris_analyze
from SALib.analyze.sobol import analyze as sobol_analyze
from SALib.sample.morris import sample as morris_sample
from SALib.sample.sobol import sample as sobol_sample

from .config import PipelineConfig, SensitivityConfig, load_config_dict, build_config
from .utils import ensure_dir, logger


def _build_problem(sens_cfg: SensitivityConfig) -> Dict[str, Any]:
    """Build SALib problem definition from SensitivityConfig."""
    return {
        "num_vars": 3,
        "names": ["w_v", "w_t", "w_r"],
        "bounds": [
            [sens_cfg.w_v.low, sens_cfg.w_v.high],
            [sens_cfg.w_t.low, sens_cfg.w_t.high],
            [sens_cfg.w_r.low, sens_cfg.w_r.high],
        ],
    }


def _evaluate_model(param_values: np.ndarray, cfg: PipelineConfig) -> np.ndarray:
    """Evaluate suitability score for each SALib sample row.

    Uses inline weight arithmetic -- does NOT construct ModelParams objects
    because the weight-sum validator would reject most sensitivity samples
    (weights intentionally do not sum to 1.0 during sweeps).

    Parameters
    ----------
    param_values:
        Array of shape (N, 3) where columns are [w_v, w_t, w_r].
    cfg:
        Pipeline configuration (used for model_params normalization bounds).

    Returns
    -------
    np.ndarray:
        Array of shape (N,) suitability scores in [0, 1].
    """
    mp = cfg.model_params
    # Pre-compute normalized fixed inputs (midpoints of normalization bounds).
    # These represent a "typical" cell used to measure weight sensitivity.
    v_n = np.clip(
        ((mp.v_min + mp.v_max) / 2 - mp.v_min) / (mp.v_max - mp.v_min), 0.0, 1.0
    )
    t_n = np.clip(
        ((mp.t_min + mp.t_max) / 2 - mp.t_min) / (mp.t_max - mp.t_min), 0.0, 1.0
    )
    r_n = np.clip(
        ((mp.r_min + mp.r_max) / 2 - mp.r_min) / (mp.r_max - mp.r_min), 0.0, 1.0
    )
    fixed = np.array([v_n, t_n, r_n])  # shape (3,)
    # Vectorized dot product: (N, 3) @ (3,) -> (N,)
    return np.clip(param_values @ fixed, 0.0, 1.0)


def _run_sobol(
    problem: Dict[str, Any], cfg: PipelineConfig, n_samples: int
) -> Dict[str, Any]:
    """Run Sobol' sensitivity analysis.

    Parameters
    ----------
    problem:
        SALib problem definition dict.
    cfg:
        Pipeline config (passed to _evaluate_model).
    n_samples:
        Base sample count N. Total evaluations = N * 8 (Saltelli estimator).

    Returns
    -------
    dict:
        Sobol' result dict with S1, S1_conf, ST, ST_conf, ranking keys.
    """
    logger.info(f"Running Sobol' analysis with N={n_samples} (total evaluations: {n_samples * 8})")
    param_values = sobol_sample(problem, n_samples, calc_second_order=True, seed=42)
    Y = _evaluate_model(param_values, cfg)
    Si = sobol_analyze(problem, Y, calc_second_order=True, seed=42)

    names = problem["names"]
    return {
        "S1": {name: float(Si["S1"][i]) for i, name in enumerate(names)},
        "S1_conf": {name: float(Si["S1_conf"][i]) for i, name in enumerate(names)},
        "ST": {name: float(Si["ST"][i]) for i, name in enumerate(names)},
        "ST_conf": {name: float(Si["ST_conf"][i]) for i, name in enumerate(names)},
        "ranking": [names[i] for i in np.argsort(Si["ST"])[::-1]],
    }


def _run_morris(
    problem: Dict[str, Any], cfg: PipelineConfig, n_samples: int
) -> Dict[str, Any]:
    """Run Morris elementary effects analysis.

    Parameters
    ----------
    problem:
        SALib problem definition dict.
    cfg:
        Pipeline config (passed to _evaluate_model).
    n_samples:
        Base sample count N. Number of Morris trajectories = max(4, min(N//10, 50)).

    Returns
    -------
    dict:
        Morris result dict with mu_star, mu_star_conf, mu, sigma, ranking keys.
    """
    # Morris N = number of trajectories; derive from n_samples capped at 50
    n_trajectories = max(4, min(n_samples // 10, 50))
    total_evals = (problem["num_vars"] + 1) * n_trajectories
    logger.info(f"Running Morris analysis with {n_trajectories} trajectories (total evaluations: {total_evals})")

    X = morris_sample(problem, N=n_trajectories, num_levels=4, seed=42)
    Y = _evaluate_model(X, cfg)
    # CRITICAL: Morris analyze() requires X as 2nd arg (unlike Sobol which only takes Y)
    Si = morris_analyze(problem, X, Y, num_levels=4, seed=42)

    names = problem["names"]
    return {
        "mu_star": {name: float(Si["mu_star"][i]) for i, name in enumerate(names)},
        "mu_star_conf": {
            name: float(Si["mu_star_conf"][i]) for i, name in enumerate(names)
        },
        "mu": {name: float(Si["mu"][i]) for i, name in enumerate(names)},
        "sigma": {name: float(Si["sigma"][i]) for i, name in enumerate(names)},
        "ranking": [names[i] for i in np.argsort(Si["mu_star"])[::-1]],
    }


def _print_sobol_table(result: Dict[str, Any]) -> None:
    """Print ranked Sobol' indices table to stdout via rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Sobol' Sensitivity Indices", show_header=True)
    table.add_column("Rank", style="bold")
    table.add_column("Parameter", style="bold")
    table.add_column("S1 (first-order)")
    table.add_column("S1 95% CI")
    table.add_column("ST (total-order)")
    table.add_column("ST 95% CI")

    for rank, name in enumerate(result["ranking"], 1):
        table.add_row(
            str(rank),
            name,
            f"{result['S1'][name]:.4f}",
            f"\u00b1{result['S1_conf'][name]:.4f}",
            f"{result['ST'][name]:.4f}",
            f"\u00b1{result['ST_conf'][name]:.4f}",
        )
    console.print(table)


def _print_morris_table(result: Dict[str, Any]) -> None:
    """Print ranked Morris elementary effects table to stdout via rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Morris Elementary Effects", show_header=True)
    table.add_column("Rank", style="bold")
    table.add_column("Parameter", style="bold")
    table.add_column("mu* (mean abs effect)")
    table.add_column("mu* 95% CI")
    table.add_column("mu (mean effect)")
    table.add_column("sigma (std dev)")

    for rank, name in enumerate(result["ranking"], 1):
        table.add_row(
            str(rank),
            name,
            f"{result['mu_star'][name]:.4f}",
            f"\u00b1{result['mu_star_conf'][name]:.4f}",
            f"{result['mu'][name]:.4f}",
            f"{result['sigma'][name]:.4f}",
        )
    console.print(table)


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON data to path atomically (write-to-tmp, rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd = tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    )
    try:
        json.dump(data, tmp_fd, indent=2)
        tmp_fd.close()
        Path(tmp_fd.name).replace(path)
    except Exception:
        Path(tmp_fd.name).unlink(missing_ok=True)
        raise


def run_sensitivity(config_path: Path) -> Path:
    """Run sensitivity analysis and write sensitivity_report.json.

    Loads config from *config_path*, validates the ``sensitivity:`` section
    exists, runs Sobol' and/or Morris analysis per the ``method`` setting,
    writes ``sensitivity_report.json`` atomically to ``output_dir``, and
    prints ranked parameter tables to stdout.

    Parameters
    ----------
    config_path:
        Path to a TerraFlow YAML config file that includes a ``sensitivity:``
        section with weight bounds and ``n_samples``.

    Returns
    -------
    Path:
        Absolute path to the written ``sensitivity_report.json``.

    Raises
    ------
    ValueError:
        If the config has no ``sensitivity:`` section.
    FileNotFoundError:
        If *config_path* does not exist.
    """
    data = load_config_dict(config_path)
    cfg = build_config(data)

    if cfg.sensitivity is None:
        raise ValueError(
            "Config file has no 'sensitivity:' section. "
            "Add a sensitivity: block with w_v, w_t, w_r bounds and n_samples. "
            "See terraflow documentation for config format."
        )

    sens_cfg = cfg.sensitivity
    problem = _build_problem(sens_cfg)
    method = sens_cfg.method
    n_samples = sens_cfg.n_samples

    report: Dict[str, Any] = {
        "schema_version": "1",
        "method": method,
        "n_samples": n_samples,
        "parameters": problem["names"],
        "bounds": {
            "w_v": {"low": sens_cfg.w_v.low, "high": sens_cfg.w_v.high},
            "w_t": {"low": sens_cfg.w_t.low, "high": sens_cfg.w_t.high},
            "w_r": {"low": sens_cfg.w_r.low, "high": sens_cfg.w_r.high},
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if method in ("sobol", "both"):
        sobol_result = _run_sobol(problem, cfg, n_samples)
        report["sobol"] = sobol_result
        _print_sobol_table(sobol_result)

    if method in ("morris", "both"):
        morris_result = _run_morris(problem, cfg, n_samples)
        report["morris"] = morris_result
        _print_morris_table(morris_result)

    # Write report atomically to output_dir
    output_dir = ensure_dir(cfg.output_dir)
    report_path = output_dir / "sensitivity_report.json"
    _atomic_write_json(report_path, report)
    logger.info(f"Sensitivity report written to {report_path}")

    return report_path
