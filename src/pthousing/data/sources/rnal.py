"""RNAL (Turismo de Portugal): short-term rental (Alojamento Local) registrations.

The registry is a snapshot of units that are registered *today*: cancelled registrations are gone, so
counting units by registration date understates past stock. Every download is therefore kept as a dated
snapshot, ``data/raw/rnal/rnal_<YYYY-MM-DD>.json``, so a true history can be assembled from now on.

Only the fields needed for the analysis are requested; names and street addresses are not stored.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import CRS_WEB, MUNI_KEY, RAW, SOURCES_YAML

SOURCE_ID = "rnal"
DATASET_ID = "rnal_al"
PAGE_SIZE = 20_000
# Registrations jump from 73 (2007) to 550 (2008); earlier dates look like legacy or placeholder entries.
FIRST_PLAUSIBLE_REGISTRATION_YEAR = 2008
RELIABILITY = {
    "Fiavel": "reliable",
    "Fiável": "reliable",
    "PoucoFiavel": "low",
    "NaoFiavel": "unreliable",
}
FIELDS = [
    "NrRNAL",
    "DataRegisto",
    "DataAberturaPublico",
    "Modalidade",
    "NrUtentes",
    "DTMNFR",
    "Freguesia",
    "Concelho",
    "NUTSIII",
    "FiabilidadeGeo",
]


def _layer_url() -> str:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID]["url"]


def _query(url: str, **params) -> dict:
    resp = requests.get(f"{url}/query", params={"f": "json", **params}, timeout=300)
    resp.raise_for_status()
    payload = json.loads(resp.content.decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"RNAL service error: {payload['error']}")
    return payload


def fetch(refresh: bool = False, today: date | None = None) -> Path:
    """Download the full registry as today's snapshot (reused if already downloaded today)."""
    day = (today or date.today()).isoformat()
    path = RAW / SOURCE_ID / f"rnal_{day}.json"
    if path.exists() and not refresh:
        return path
    url = _layer_url()
    expected = _query(url, where="1=1", returnCountOnly="true")["count"]
    features: list[dict] = []
    while len(features) < expected:
        page = _query(
            url,
            where="1=1",
            outFields=",".join(FIELDS),
            returnGeometry="true",
            outSR=CRS_WEB.split(":")[1],
            orderByFields="OBJECTID",
            resultOffset=len(features),
            resultRecordCount=PAGE_SIZE,
        )["features"]
        if not page:
            break
        features.extend(page)
    if len(features) != expected:
        raise RuntimeError(f"RNAL download incomplete: {len(features)} of {expected} records")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"snapshot_date": day, "count": expected, "features": features}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    return path


def latest_snapshot() -> Path:
    snapshots = sorted((RAW / SOURCE_ID).glob("rnal_*.json"))
    if not snapshots:
        raise FileNotFoundError("No RNAL snapshot in data/raw/rnal; run fetch() first")
    return snapshots[-1]


def parse_snapshot(raw: dict) -> pd.DataFrame:
    """One row per registered unit with registration dates, modality, capacity, municipality and location."""
    rows = []
    for feature in raw["features"]:
        geometry = feature.get("geometry") or {}
        rows.append({**feature["attributes"], "lon": geometry.get("x"), "lat": geometry.get("y")})
    df = pd.DataFrame(rows).rename(
        columns={
            "NrRNAL": "rnal_n",
            "Modalidade": "modality",
            "NrUtentes": "guests_n",
            "DTMNFR": "parish_code",
            "Freguesia": "parish_name",
            "NUTSIII": "nuts3_name",
            "FiabilidadeGeo": "geo_reliability",
        }
    )
    for src, dst in (("DataRegisto", "registered"), ("DataAberturaPublico", "opened")):
        df[dst] = pd.to_datetime(df[src], unit="ms", errors="coerce").dt.normalize()
    # Municipality names are not kept: they differ from CAOP only in capitalisation, the code is what matters.
    df[MUNI_KEY] = df["parish_code"].str[:4]
    df["geo_reliability"] = df["geo_reliability"].map(RELIABILITY)
    df["registered_before_2008"] = df["registered"].dt.year < FIRST_PLAUSIBLE_REGISTRATION_YEAR
    df["snapshot_date"] = pd.Timestamp(raw["snapshot_date"])
    keep = [
        "rnal_n", "registered", "registered_before_2008", "opened", "modality", "guests_n", MUNI_KEY,
        "parish_code", "parish_name", "nuts3_name", "geo_reliability", "lon", "lat", "snapshot_date",
    ]  # fmt: skip
    return df[keep]


def read(path: Path | None = None) -> pd.DataFrame:
    """Parse a snapshot (default: the most recent one)."""
    path = path or latest_snapshot()
    return parse_snapshot(json.loads(path.read_text(encoding="utf-8")))
