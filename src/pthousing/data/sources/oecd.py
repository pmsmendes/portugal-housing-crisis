"""OECD analytical house price indicators (dataflow DSD_AN_HOUSE_PRICES): Portugal, annual.

Nominal and real house price indices, rent prices, and the price-to-rent and price-to-income ratios (2015 = 100;
income is nominal disposable income per head). The SDMX CSV response is stored untouched in
``data/raw/oecd/<dataset_id>.csv``.
"""

from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import RAW, SOURCES_YAML

SOURCE_ID = "oecd"
HEADERS = {"User-Agent": "pthousing/0.1 (research project)"}


def _entry(dataset_id: str) -> dict:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][dataset_id]


def fetch(dataset_id: str, refresh: bool = False) -> Path:
    """Download one configured OECD dataset into ``data/raw/oecd/``."""
    path = RAW / SOURCE_ID / f"{dataset_id}.csv"
    if path.exists() and not refresh:
        return path
    entry = _entry(dataset_id)
    resp = requests.get(
        f"{entry['base_url']}/{entry['dataflow']}/{entry['key']}",
        params={"format": "csvfilewithlabels"},
        headers=HEADERS,
        timeout=180,
    )
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path


def parse_csv(text: str) -> pd.DataFrame:
    """Tidy frame: ``measure`` (HPI, RHP, HPI_RPI, HPI_YDH, RPI and the standardised ``*_AVG`` ratios), ``unit``,
    ``year``, ``value`` and ``base_year`` (the index base, NaN for the standardised ratios)."""
    df = pd.read_csv(StringIO(text), dtype=str)
    out = pd.DataFrame(
        {
            "measure": df["MEASURE"],
            "unit": df["UNIT_MEASURE"],
            "year": df["TIME_PERIOD"].astype(int),
            "value": df["OBS_VALUE"].astype(float),
            "base_year": pd.to_numeric(df["BASE_PER"], errors="coerce"),
        }
    )
    return out.sort_values(["measure", "year"], ignore_index=True)


def read(dataset_id: str) -> pd.DataFrame:
    path = RAW / SOURCE_ID / f"{dataset_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not in data/raw/oecd; run fetch first")
    return parse_csv(path.read_text(encoding="utf-8"))
