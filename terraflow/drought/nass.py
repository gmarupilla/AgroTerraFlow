"""Fetch county planted acreage from the USDA NASS QuickStats API.

Planted acres provide the denominator for the coverage-bias column (insured acres / planted acres),
documenting that RMA Cause of Loss covers only *insured* acres. An API key is required (free, from
https://quickstats.nass.usda.gov/api); pass it explicitly or set ``NASS_API_KEY``. The key is never
persisted by this module.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

QUICKSTATS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"


def parse_nass_records(records: list[dict]) -> pd.DataFrame:
    """Turn QuickStats ``data`` records into per-(GEOID, year) planted acres.

    Keeps county-level rows with a numeric value; skips withheld values ("(D)", "(Z)") and rows
    without a county ANSI code. ``GEOID`` = state FIPS (2) + county ANSI (3).
    """
    rows = []
    for r in records:
        if r.get("agg_level_desc") != "COUNTY":
            continue
        state_fips = str(r.get("state_fips_code", "")).zfill(2)
        county_ansi = str(r.get("county_ansi", "")).strip()
        if not county_ansi or not county_ansi.isdigit():
            continue
        value = str(r.get("Value", "")).replace(",", "").strip()
        try:
            acres = float(value)
        except ValueError:
            continue  # withheld/non-numeric ("(D)", "(Z)", etc.)
        rows.append(
            {
                "GEOID": state_fips + county_ansi.zfill(3),
                "year": int(r["year"]),
                "planted_acres": acres,
                "is_total": r.get("prodn_practice_desc") == "ALL PRODUCTION PRACTICES",
            }
        )
    if not rows:
        return pd.DataFrame(columns=["GEOID", "year", "planted_acres"])
    df = pd.DataFrame(rows)
    # QuickStats returns an "ALL PRODUCTION PRACTICES" total alongside IRRIGATED/NON-IRRIGATED
    # breakouts that sum to it; summing everything would double-count. Prefer the total, and fall
    # back to summing breakouts only for county-years that have no total row.
    totals = df[df["is_total"]].groupby(["GEOID", "year"], as_index=False)["planted_acres"].max()
    others = df[~df["is_total"]].merge(totals[["GEOID", "year"]], on=["GEOID", "year"], how="left", indicator=True)
    fallback = others[others["_merge"] == "left_only"].groupby(["GEOID", "year"], as_index=False)["planted_acres"].sum()
    return pd.concat([totals, fallback], ignore_index=True).sort_values(["GEOID", "year"]).reset_index(drop=True)


def _query_state(state_alpha: str, commodity: str, api_key: str) -> list[dict]:
    params = {
        "key": api_key,
        "source_desc": "SURVEY",
        "commodity_desc": commodity,
        "statisticcat_desc": "AREA PLANTED",
        "agg_level_desc": "COUNTY",
        "state_alpha": state_alpha,
        "unit_desc": "ACRES",
        "format": "JSON",
    }
    url = QUICKSTATS_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (trusted USDA host)
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("data", [])


def fetch_planted_acres(state_alphas: list[str], commodity: str = "CORN", api_key: str | None = None) -> pd.DataFrame:
    """Fetch county planted acres for the given state postal codes via QuickStats.

    ``api_key`` falls back to the ``NASS_API_KEY`` environment variable.
    """
    key = api_key or os.environ.get("NASS_API_KEY")
    if not key:
        raise ValueError("NASS API key required (pass api_key or set NASS_API_KEY).")
    records: list[dict] = []
    for state in state_alphas:
        records.extend(_query_state(state, commodity, key))
    return parse_nass_records(records)
