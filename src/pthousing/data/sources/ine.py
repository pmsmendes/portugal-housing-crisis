"""INE (Statistics Portugal): house prices, rents, income, population, households, construction, Census.

Client for the INE JSON API. Raw responses are stored untouched in ``data/raw/ine/<indicator>/<period>.json``;
``read_indicator`` parses them into one tidy frame. Indicator ids live in ``config/sources.yaml``.

Geography codes (``geocod``): 7 chars = NUTS III prefix + 4-digit municipality code, 4 chars = plain
municipality code (Census), 6 / 9 chars = parish, 1-3 chars = region. A 7-char code can also be a city or
other unit, so ``muni_code`` is only a candidate until it is checked against the CAOP municipality list.
"""

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import MUNI_KEY, RAW, SOURCES_YAML

API = "https://www.ine.pt/ine/json_indicador"
SOURCE_ID = "ine"
ALL_PERIODS = "T"

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], start=1)}  # fmt: skip


def primary_indicator(dataset_id: str) -> str:
    """Primary INE indicator id of a dataset, as set in ``config/sources.yaml``."""
    entry = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][dataset_id]
    if "indicator_id" not in entry:
        raise KeyError(
            f"{dataset_id} has no single indicator_id in sources.yaml; pass a code explicitly"
        )
    return str(entry["indicator_id"])


def _get(endpoint: str, params: dict, retries: int = 4, timeout: int = 240) -> bytes:
    """GET with backoff; INE answers 503 / times out on large requests."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(f"{API}/{endpoint}", params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last = exc
            time.sleep(2**attempt)
    raise RuntimeError(
        f"INE request failed after {retries} attempts: {endpoint} {params}"
    ) from last


def _decode(content: bytes) -> list[dict]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    payload = json.loads(text)
    failure = payload[0].get("Sucesso", {}).get("Falso")
    if failure:
        raise ValueError(failure[0].get("Msg", "INE API error"))
    return payload


def period_codes(code: str) -> list[str]:
    """Period category ids of an indicator (e.g. ``S6A20242``) from its metadata."""
    meta = _decode(_get("pindicaMeta.jsp", {"varcd": code, "lang": "EN"}))[0]
    cats = meta["Dimensoes"]["Categoria_Dim"][0]
    return [v[0]["cat_id"] for k, v in cats.items() if k.startswith("Dim_Num1_")]


def fetch_indicator(
    code: str, periods: list[str] | None = None, refresh: bool = False
) -> list[Path]:
    """Download an indicator into ``data/raw/ine/<code>/`` and return the files written or reused.

    Without ``periods`` it asks for all periods at once and, if INE rejects that (large series), falls
    back to one request per period.
    """
    folder = RAW / SOURCE_ID / code
    folder.mkdir(parents=True, exist_ok=True)

    def one(period: str) -> Path:
        path = folder / f"{period}.json"
        if refresh or not path.exists():
            params = {"op": 2, "varcd": code, "Dim1": period, "lang": "EN"}
            _decode(content := _get("pindica.jsp", params))  # validates before it is stored
            path.write_bytes(content)
        return path

    if periods:
        return [one(p) for p in periods]
    try:
        return [one(ALL_PERIODS)]
    except RuntimeError, ValueError:
        return [one(p) for p in period_codes(code)]


def parse_period(label: str) -> tuple[pd.Timestamp, int]:
    """Start date and year of an INE English period label (annual, semester, quarter or month)."""
    if m := re.fullmatch(r"(\d{4})", label):
        return pd.Timestamp(int(m[1]), 1, 1), int(m[1])
    if m := re.fullmatch(r"(\d)(?:st|nd|rd|th) Semi-annual (\d{4})", label):
        return pd.Timestamp(int(m[2]), 1 if m[1] == "1" else 7, 1), int(m[2])
    if m := re.fullmatch(r"(\d)(?:st|nd|rd|th) Quarter (\d{4})", label):
        return pd.Timestamp(int(m[2]), 3 * int(m[1]) - 2, 1), int(m[2])
    if (m := re.fullmatch(r"([A-Za-z]+) (\d{4})", label)) and m[1] in _MONTHS:
        return pd.Timestamp(int(m[2]), _MONTHS[m[1]], 1), int(m[2])
    raise ValueError(f"Unrecognised INE period label: {label!r}")


def _geo_level(geocod: str) -> str:
    return {
        1: "region",
        2: "region",
        3: "region",
        4: "municipality",
        6: "parish",
        7: "municipality",
        9: "parish",
    }.get(len(geocod), "other")


def parse_payload(payload: list[dict]) -> pd.DataFrame:
    """Tidy frame from one API response: one row per period x geography x extra dimension."""
    record = payload[0]
    rows = []
    for label, items in record["Dados"].items():
        start, year = parse_period(label)
        for item in items:
            rows.append({"period_label": label, "period_start": start, "year": year, **item})
    df = pd.DataFrame(rows)
    df = df.rename(columns={"geodsg": "geo_name"})
    df["indicator_id"] = record["IndicadorCod"]
    df["value"] = pd.to_numeric(df.get("valor"), errors="coerce")  # '-' / missing = suppressed
    df["geo_level"] = df["geocod"].astype(str).map(_geo_level)
    geocod = df["geocod"].astype(str)
    df[MUNI_KEY] = geocod.where(geocod.str.len() == 4, geocod.str[3:]).where(
        geocod.str.len().isin([4, 7])
    )
    dims = [c for c in df.columns if c.startswith("dim_")]
    keep = [
        "indicator_id",
        "period_label",
        "period_start",
        "year",
        "geocod",
        "geo_name",
        "geo_level",
        MUNI_KEY,
    ]
    return df[keep + dims + ["value"]]


def read_indicator(code: str) -> pd.DataFrame:
    """Parse every raw file stored for an indicator (all-periods and per-period files alike)."""
    files = sorted((RAW / SOURCE_ID / code).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No raw files for INE indicator {code}; run fetch_indicator first")
    frames = [parse_payload(_decode(f.read_bytes())) for f in files]
    return pd.concat(frames, ignore_index=True).drop_duplicates()
