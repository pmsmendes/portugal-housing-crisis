"""Banco de Portugal BPstat: mortgage rates, new lending, household debt.

Series ids are listed in ``config/sources.yaml``. Each series is stored as one raw file
``data/raw/bportugal/<series_id>.json`` holding the series metadata and the dataset response filtered to it.
"""

import json
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import RAW, SOURCES_YAML
from pthousing.data.sources.jsonstat import parse_jsonstat

SOURCE_ID = "bportugal"
DATASET_ID = "bp_mortgage"
HEADERS = {"User-Agent": "pthousing/0.1 (research project)"}  # the default python UA gets a 403
TIME_DIM = "reference_date"


def series_ids() -> dict[str, int]:
    """Series key -> BPstat series id, from ``config/sources.yaml``."""
    entry = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID]
    return {key: int(value) for key, value in entry["series"].items()}


def _get_json(url: str, params: dict) -> dict | list:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _base_url() -> str:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID][
        "base_url"
    ]


def fetch_series(series_id: int, refresh: bool = False) -> Path:
    """Download one series (metadata + observations) into ``data/raw/bportugal/``."""
    path = RAW / SOURCE_ID / f"{series_id}.json"
    if path.exists() and not refresh:
        return path
    base = _base_url()
    meta = _get_json(f"{base}/series/", {"series_ids": series_id, "lang": "EN"})[0]
    domain, dataset = meta["domain_ids"][0], meta["dataset_id"]
    data = _get_json(
        f"{base}/domains/{domain}/datasets/{dataset}", {"lang": "EN", "series_ids": series_id}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"series": meta, "dataset": data}, ensure_ascii=False), encoding="utf-8"
    )
    return path


def fetch_all(refresh: bool = False) -> list[Path]:
    return [fetch_series(sid, refresh) for sid in series_ids().values()]


def parse_series(raw: dict) -> pd.DataFrame:
    """Tidy monthly frame from one stored series: date, year, month, value, status."""
    df = parse_jsonstat(raw["dataset"])
    if len(df.drop_duplicates(subset=[TIME_DIM])) != len(df):
        raise ValueError(
            f"Series {raw['series']['id']} is not unique per date; filter was not applied"
        )
    date = pd.to_datetime(df[TIME_DIM])
    return pd.DataFrame(
        {
            "series_id": raw["series"]["id"],
            "series_label": raw["series"]["label"],
            "date": date,
            "year": date.dt.year,
            "month": date.dt.month,
            "value": df["value"],
            "status": df["status"],
        }
    )


def read_series(series_id: int) -> pd.DataFrame:
    path = RAW / SOURCE_ID / f"{series_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not in data/raw/bportugal; run fetch_series first")
    return parse_series(json.loads(path.read_text(encoding="utf-8")))


def read_all() -> pd.DataFrame:
    """All configured series stacked, with the yaml key in ``series_key``."""
    frames = [read_series(sid).assign(series_key=key) for key, sid in series_ids().items()]
    return pd.concat(frames, ignore_index=True)
