"""Model validation module — spatial block cross-validation.

Users wanting spatial autocorrelation diagnostics (e.g. Moran's I) should
call ``esda.Moran`` directly on ``features.parquet``. Users wanting
inter-rater agreement (e.g. Cohen's κ) should call
``sklearn.metrics.cohen_kappa_score`` directly. TerraFlow does not
maintain wrappers around either, since neither earns Methods-section
citations.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupKFold

from .config import build_config, load_config_dict
from .pipeline import resolve_run_dir
from .utils import logger


def _assign_block_ids(
    lats: np.ndarray,
    lons: np.ndarray,
    n_blocks_side: int = 4,
) -> np.ndarray:
    """Assign each cell a spatial block ID based on a regular grid.

    Divides the bounding box of (lats, lons) into an n_blocks_side × n_blocks_side
    grid and returns a 1-D integer array of block IDs.

    Parameters
    ----------
    lats:
        1-D array of latitude values.
    lons:
        1-D array of longitude values.
    n_blocks_side:
        Number of grid cells per side. Total blocks = n_blocks_side².

    Returns
    -------
    np.ndarray:
        Integer array of shape (len(lats),) with block IDs in
        [0, n_blocks_side² - 1].
    """
    lat_edges = np.linspace(lats.min(), lats.max(), n_blocks_side + 1)
    lon_edges = np.linspace(lons.min(), lons.max(), n_blocks_side + 1)
    row_idx = np.digitize(lats, lat_edges[1:-1])
    col_idx = np.digitize(lons, lon_edges[1:-1])
    return row_idx * n_blocks_side + col_idx


def _spatial_block_cv(
    lats: np.ndarray,
    lons: np.ndarray,
    labels: np.ndarray,
    n_blocks_side: int = 4,
    buffer_deg: float = 0.5,
) -> List[float]:
    """Run spatial block cross-validation with buffer-zone exclusion.

    Implements Roberts et al. (2017, Ecography) spatial block CV: cells are
    assigned to a regular spatial grid, one block is held out per fold, and
    training cells within *buffer_deg* degrees of any test cell are excluded
    to prevent spatial autocorrelation leakage.

    Because TerraFlow's suitability model has no free parameters learned from
    data, the fold prediction strategy uses the majority label of the buffered
    training set as a spatial baseline for all test cells. This measures spatial
    label consistency rather than model fit generalisation.

    Parameters
    ----------
    lats, lons:
        1-D arrays of coordinates.
    labels:
        1-D string array of suitability labels.
    n_blocks_side:
        Grid resolution (see _assign_block_ids).
    buffer_deg:
        Exclusion buffer in degrees around test cells.

    Returns
    -------
    list of float:
        Per-fold accuracy values in [0, 1]. Empty list when fewer than 2
        unique blocks exist (degenerate case).
    """
    block_ids = _assign_block_ids(lats, lons, n_blocks_side)
    n_unique_blocks = len(np.unique(block_ids))

    if n_unique_blocks < 2:
        logger.warning(
            "Fewer than 2 unique spatial blocks — spatial block CV skipped. "
            "Increase n_blocks_side or use a larger study area."
        )
        return []

    X = np.column_stack([lats, lons])
    n_splits = min(n_unique_blocks, 5)
    gkf = GroupKFold(n_splits=n_splits)

    fold_accuracies: List[float] = []
    for train_idx, test_idx in gkf.split(X, labels, groups=block_ids):
        test_coords = X[test_idx]
        train_coords = X[train_idx]

        # Exclude training cells within buffer_deg of any test cell
        dists = cdist(train_coords, test_coords).min(axis=1)
        buffered_train_idx = train_idx[dists > buffer_deg]

        if len(buffered_train_idx) == 0 or len(test_idx) == 0:
            continue

        # Spatial baseline prediction: majority label in buffered training set
        train_labels = labels[buffered_train_idx]
        unique, counts = np.unique(train_labels, return_counts=True)
        majority_label = unique[np.argmax(counts)]
        fold_pred = np.full(len(test_idx), majority_label)

        fold_acc = float(accuracy_score(labels[test_idx], fold_pred))
        fold_accuracies.append(fold_acc)

    return fold_accuracies


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


def run_validation(config_path: Path) -> Path:
    """Run model validation and append a validation block to report.json.

    Loads the TerraFlow config, locates the most recent pipeline run directory
    (the one with the latest ``features.parquet``), and computes spatial block
    CV. Results are written atomically to the existing ``report.json`` under
    the ``"validation"`` key.

    Parameters
    ----------
    config_path:
        Path to a TerraFlow YAML config file that includes a ``validation:``
        section.

    Returns
    -------
    Path:
        Absolute path to the updated ``report.json``.

    Raises
    ------
    ValueError:
        If the config has no ``validation:`` section.
    FileNotFoundError:
        If no pipeline run directory containing ``features.parquet`` is found.
    """
    data = load_config_dict(config_path)
    cfg = build_config(data)

    if cfg.validation is None:
        raise ValueError(
            "Config file has no 'validation:' section. "
            "Add a validation: block with optional n_blocks_side and buffer_deg "
            "fields. See TerraFlow documentation for details."
        )

    val_cfg = cfg.validation

    run_dir = resolve_run_dir(config_path)
    features_path = run_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(
            f"No pipeline run found at {run_dir}. "
            "Run `terraflow run -c config.yml` before running validation."
        )

    logger.info(f"Running validation on {run_dir}")

    # Load features
    df = pd.read_parquet(features_path)
    lats = df["lat"].values
    lons = df["lon"].values
    labels = df["label"].values

    # Spatial block CV
    fold_accs = _spatial_block_cv(
        lats,
        lons,
        labels,
        n_blocks_side=val_cfg.n_blocks_side,
        buffer_deg=val_cfg.buffer_deg,
    )
    mean_fold_accuracy: Optional[float] = (
        float(np.mean(fold_accs)) if fold_accs else None
    )

    # Read existing report.json and append validation block
    report_path = run_dir / "report.json"
    if report_path.exists():
        with report_path.open("r", encoding="utf-8") as fh:
            report: Dict[str, Any] = json.load(fh)
    else:
        report = {}

    report["validation"] = {
        "method": "spatial_block_cv",
        "citation": "Roberts et al. 2017, Ecography",
        "n_blocks_side": val_cfg.n_blocks_side,
        "buffer_deg": val_cfg.buffer_deg,
        "n_folds": len(fold_accs),
        "mean_fold_accuracy": mean_fold_accuracy,
        "kriging_loocv_rmse": report.get("kriging_loocv"),
        "note": (
            "model has no free parameters; fold accuracy reflects spatial "
            "label consistency, not fit generalization"
        ),
    }

    _atomic_write_json(report_path, report)
    logger.info(f"Validation block written to {report_path}")

    return report_path
