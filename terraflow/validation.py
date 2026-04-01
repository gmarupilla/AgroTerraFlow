"""Model validation module — spatial block CV, Cohen's kappa, Moran's I."""
from __future__ import annotations

import json
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from scipy.spatial.distance import cdist
from sklearn.metrics import accuracy_score, cohen_kappa_score
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


def _compute_kappa(
    cells_df: pd.DataFrame,
    reference_df: pd.DataFrame,
) -> float:
    """Compute Cohen's kappa comparing reference labels to nearest TerraFlow cells.

    Each row in *reference_df* is matched to the nearest cell in *cells_df*
    via a KDTree on (lat, lon) coordinates (WGS84 degrees). If any reference
    point is more than 1.0 degree from its nearest cell, a warning is emitted
    indicating a possible geographic extent mismatch.

    Parameters
    ----------
    cells_df:
        DataFrame with columns ``lat``, ``lon``, ``label`` from features.parquet.
    reference_df:
        Reference CSV as a DataFrame with columns ``lat``, ``lon``, ``label``.

    Returns
    -------
    float:
        Cohen's kappa in [-1, 1].
    """
    cell_coords = np.column_stack(
        [cells_df["lat"].values, cells_df["lon"].values]
    )
    ref_coords = np.column_stack(
        [reference_df["lat"].values, reference_df["lon"].values]
    )

    tree = KDTree(cell_coords)
    dists, cell_idxs = tree.query(ref_coords)

    max_dist = float(dists.max())
    if max_dist > 1.0:
        warnings.warn(
            f"Reference points are up to {max_dist:.1f} degrees distance from nearest cell "
            "— possible extent mismatch. Ensure reference CSV uses WGS84 degrees "
            "and covers the same region as the pipeline output.",
            stacklevel=2,
        )

    matched_labels = cells_df["label"].values[cell_idxs]
    return float(
        cohen_kappa_score(
            reference_df["label"].values,
            matched_labels,
            labels=["low", "medium", "high"],
        )
    )


def _morans_i(
    lats: np.ndarray,
    lons: np.ndarray,
    residuals: np.ndarray,
) -> Optional[float]:
    """Compute global Moran's I on residuals using row-standardized inverse-distance weights.

    Formula: I = (n / S0) * (z^T W z) / (z^T z)
    where z = residuals − mean(residuals), W = row-standardized weight matrix.

    Reference: Cliff & Ord (1981). *Spatial Processes: Models and Applications*.

    Parameters
    ----------
    lats, lons:
        1-D coordinate arrays.
    residuals:
        1-D array of residual values (e.g. score − mean_score).

    Returns
    -------
    float or None:
        Global Moran's I. Returns None when all residuals are identical
        (z^T z = 0) or when the weight matrix sums to zero.
    """
    coords = np.column_stack([lats, lons])
    D = cdist(coords, coords)
    W = np.exp(-D)
    np.fill_diagonal(W, 0.0)

    row_sums = W.sum(axis=1, keepdims=True)
    W_row = np.where(row_sums > 0, W / row_sums, 0.0)

    z = residuals - residuals.mean()
    n = len(z)
    S0 = float(W_row.sum())

    if S0 == 0 or float(z @ z) == 0:
        return None

    return float((n / S0) * (z @ W_row @ z) / (z @ z))


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
    (the one with the latest ``features.parquet``), computes spatial block CV,
    Moran's I on score residuals, and optionally Cohen's kappa against a
    reference CSV. Results are written atomically to the existing ``report.json``
    under the ``"validation"`` key.

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
            "Add a validation: block with optional n_blocks_side, buffer_deg, "
            "and reference_csv fields. See TerraFlow documentation for details."
        )

    val_cfg = cfg.validation
    config_dir = Path(config_path).resolve().parent

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
    scores = df["score"].values

    # Spatial block CV
    fold_accs = _spatial_block_cv(
        lats, lons, labels,
        n_blocks_side=val_cfg.n_blocks_side,
        buffer_deg=val_cfg.buffer_deg,
    )
    mean_fold_accuracy: Optional[float] = float(np.mean(fold_accs)) if fold_accs else None

    # Moran's I on score residuals
    morans_i_val = _morans_i(lats, lons, scores - float(scores.mean()))

    # Cohen's kappa (optional)
    kappa: Optional[float] = None
    n_ref: Optional[int] = None
    if val_cfg.reference_csv is not None:
        ref_path = (config_dir / val_cfg.reference_csv).resolve()
        reference_df = pd.read_csv(ref_path)
        n_ref = len(reference_df)
        kappa = _compute_kappa(df, reference_df)
        logger.info(f"Cohen's kappa computed from {n_ref} reference points: {kappa:.4f}")

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
        "cohen_kappa": kappa,
        "morans_i_residuals": morans_i_val,
        "kriging_loocv_rmse": report.get("kriging_loocv"),
        "reference_dataset": str(val_cfg.reference_csv) if val_cfg.reference_csv else None,
        "n_reference_points": n_ref if kappa is not None else None,
        "note": (
            "model has no free parameters; fold accuracy reflects spatial "
            "label consistency, not fit generalization"
        ),
    }

    _atomic_write_json(report_path, report)
    logger.info(f"Validation block written to {report_path}")

    return report_path
