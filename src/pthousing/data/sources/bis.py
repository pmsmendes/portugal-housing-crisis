"""BIS residential property prices (selected series, dataflow WS_SPP): Portugal back to 1988.

The BIS Data Portal SDMX API returns the series as CSV; the response is stored untouched in
``data/raw/bis/<dataset_id>.csv``. Series are keyed by ``VALUE`` (N nominal, R real, deflated by the CPI) and
``UNIT_MEASURE`` (628 index 2010 = 100, 771 year-on-year change in %).
"""

import re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import RAW, SOURCES_YAML

SOURCE_ID = "bis"
HEADERS = {"User-Agent": "pthousing/0.1 (research project)"}


def _entry(dataset_id: str) -> dict:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][dataset_id]


def fetch(dataset_id: str, refresh: bool = False) -> Path:
    """Download one configured BIS dataset into ``data/raw/bis/``."""
    path = RAW / SOURCE_ID / f"{dataset_id}.csv"
    if path.exists() and not refresh:
        return path
    entry = _entry(dataset_id)
    resp = requests.get(
        f"{entry['base_url']}/{entry['dataflow']}/{entry['key']}",
        params={"format": "csv"},
        headers=HEADERS,
        timeout=120,
    )
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path


def parse_period(code: str) -> pd.Timestamp:
    """Start date of a BIS quarterly period code such as ``1988-Q1``."""
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", code):
        return pd.Timestamp(int(m[1]), 3 * int(m[2]) - 2, 1)
    raise ValueError(f"Unrecognised BIS period code: {code!r}")


def parse_csv(text: str) -> pd.DataFrame:
    """Tidy frame: ``basis`` (N / R), ``unit`` (628 / 771), ``period_start``, ``year``, ``quarter``, ``value``."""
    df = pd.read_csv(StringIO(text), dtype={"VALUE": str, "UNIT_MEASURE": str})
    out = pd.DataFrame(
        {
            "basis": df["VALUE"],
            "unit": df["UNIT_MEASURE"],
            "period_start": df["TIME_PERIOD"].map(parse_period),
            "value": df["OBS_VALUE"].astype(float),
        }
    )
    out["year"] = out["period_start"].dt.year
    out["quarter"] = out["period_start"].dt.quarter
    return out.sort_values(["basis", "unit", "period_start"], ignore_index=True)


def read(dataset_id: str) -> pd.DataFrame:
    path = RAW / SOURCE_ID / f"{dataset_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not in data/raw/bis; run fetch first")
    return parse_csv(path.read_text(encoding="utf-8"))
