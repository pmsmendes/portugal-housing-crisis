"""Eurostat: HPI, HICP deflator, EU comparison series.

Datasets and query parameters come from ``config/sources.yaml``; each response is stored untouched in
``data/raw/eurostat/<dataset_id>.json`` and parsed with the shared JSON-stat parser.
"""

import json
import re
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import RAW, SOURCES_YAML
from pthousing.data.sources.jsonstat import parse_jsonstat

SOURCE_ID = "eurostat"
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def _entry(dataset_id: str) -> dict:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][dataset_id]


def fetch(dataset_id: str, refresh: bool = False) -> Path:
    """Download one configured Eurostat dataset into ``data/raw/eurostat/``."""
    path = RAW / SOURCE_ID / f"{dataset_id}.json"
    if path.exists() and not refresh:
        return path
    entry = _entry(dataset_id)
    params = {**entry["params"], "geo": entry["geo"], "format": "JSON", "lang": "EN"}
    resp = requests.get(f"{API}/{entry['dataset']}", params=params, timeout=120)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path


def parse_time(code: str) -> pd.Timestamp:
    """Start date of a Eurostat period code: annual ``1996``, quarterly ``2005-Q1`` or monthly ``2005-03``."""
    if m := re.fullmatch(r"(\d{4})", code):
        return pd.Timestamp(int(m[1]), 1, 1)
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", code):
        return pd.Timestamp(int(m[1]), 3 * int(m[2]) - 2, 1)
    if m := re.fullmatch(r"(\d{4})-(\d{2})", code):
        return pd.Timestamp(int(m[1]), int(m[2]), 1)
    raise ValueError(f"Unrecognised Eurostat period code: {code!r}")


def parse_dataset(payload: dict) -> pd.DataFrame:
    """Tidy frame: geo, period code, start date, year, value, status (+ other dimension codes)."""
    df = parse_jsonstat(payload).rename(columns={"time": "period"})
    df["period_start"] = df["period"].map(parse_time)
    df["year"] = df["period_start"].dt.year
    return df.sort_values(["geo", "period_start"], ignore_index=True)


def read(dataset_id: str) -> pd.DataFrame:
    path = RAW / SOURCE_ID / f"{dataset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not in data/raw/eurostat; run fetch first")
    return parse_dataset(json.loads(path.read_text(encoding="utf-8")))
