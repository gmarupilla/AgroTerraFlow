"""Synthetic data builders for drought-benchmark tests (no network, tiny, deterministic)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from terraflow.drought.predictors import ANOM_FEATURES

# 30-field Cause of Loss record order (see terraflow.drought.rma.COL_COLUMNS).
_COL_TEMPLATE = (
    "{year}|{state}|{abbr}|{county}|{cname}|0041|{commodity}|02|RP   |A|H |{cl_code}|{cause}|"
    "07|JUL|{year}|1|1|100.00|.00|{liability}.00|500.00|250.00|250.00|.00|.00|.00|"
    "50.00|{indemnity}.00|{ratio}"
)


def write_synthetic_col(path: Path, rows: list[dict]) -> Path:
    """Write a pipe-delimited COL ``.txt`` (or ``.zip`` if path ends in .zip) from row dicts."""
    lines = []
    for r in rows:
        liability = float(r.get("liability", 1000.0))
        indemnity = float(r.get("indemnity", 0.0))
        lines.append(
            _COL_TEMPLATE.format(
                year=r["year"],
                state=str(r["state"]).zfill(2),
                abbr=r.get("abbr", "IL"),
                county=str(r["county"]).zfill(3),
                cname=r.get("cname", "Test County").ljust(30),
                commodity=r.get("commodity", "CORN").ljust(30),
                cl_code=r.get("cl_code", "31"),
                cause=r.get("cause", "Drought").ljust(35),
                liability=int(liability),
                indemnity=int(indemnity),
                ratio=f"{(indemnity / max(liability, 1)):.2f}",
            )
        )
    text = "\n".join(lines) + "\n"
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("colsom_synthetic.txt", text)
    else:
        path.write_text(text, encoding="latin-1")
    return path


def make_feature_table(
    geoids: list[str],
    years: list[int],
    doys: tuple[int, ...] = (130, 160, 190, 220),
    seed: int = 0,
) -> pd.DataFrame:
    """Minimal feature table with the columns predictors need, filled deterministically."""
    rng = np.random.default_rng(seed)
    recs = []
    for g in geoids:
        for y in years:
            # Give each county-year a latent "stress" that drives both anomalies and severity.
            stress = rng.normal(0, 1)
            for d in doys:
                rec: dict[str, object] = {
                    "GEOID": g,
                    "STATEFP": g[:2],
                    "NAME": "Test",
                    "year": y,
                    "doy": d,
                    "NDVI_anom_z": -stress + rng.normal(0, 0.2),
                    "dm_gte_d2": bool(stress > 0.5),
                    "dm_class": int(np.clip(round(stress + 2), 0, 4)),
                }
                for f in ANOM_FEATURES:
                    rec[f] = stress + rng.normal(0, 0.3)
                recs.append(rec)
    return pd.DataFrame(recs)


def make_benchmark(
    geoids: list[str],
    years: list[int],
    seed: int = 0,
) -> pd.DataFrame:
    """A tiny assembled-style benchmark table (predictor columns + labels) for evaluate tests."""
    from terraflow.drought.baselines import feature_columns

    rng = np.random.default_rng(seed)
    cols = feature_columns("all")
    recs = []
    for g in geoids:
        for y in years:
            stress = rng.normal(0, 1)
            ratio = max(0.0, 0.15 * stress + rng.normal(0, 0.02))
            rec: dict[str, object] = {"GEOID": g, "year": y}
            for c in cols:
                rec[c] = stress + rng.normal(0, 0.3)
            rec["n_obs"] = 4
            rec["n_stress_weeks"] = int(stress > 0.5)
            rec["drought_indemnity"] = max(0.0, stress) * 1000
            rec["total_indemnity"] = abs(stress) * 1000 + 1
            rec["liability"] = 10000.0
            rec["drought_share"] = 0.5
            rec["drought_loss_ratio"] = ratio
            rec["significant_drought_loss"] = ratio >= 0.10
            recs.append(rec)
    return pd.DataFrame(recs)
