"""Autoridade Tributaria (Portal das Financas): municipal IMI rates, one page per tax year and district.

The portal's "Consultar Taxas do Municipio" lists, for each municipality, the urban rate (prédios urbanos
avaliados nos termos do CIMI), the rustic rate, whether a "Taxas por freguesia" link is shown and whether the
household deduction page is linked. ``ano`` is the tax year: the municipal assembly fixes the rate in the last months of
the year and it applies to that year's assessment (inferred from press counts of municipalities at the 0.3%
floor, see ``docs/data_quality.md``).

The portal shows the rates as stored today, so every download is kept as a dated snapshot,
``data/raw/at/imi_rates_<YYYY-MM-DD>/<year>_<district>.html`` (pages exactly as received), and parsing reads a
snapshot, never the network. A snapshot is reused unless ``refresh`` is set: 300 requests to somebody else's
server are not repeated daily. Requests are sequential with a pause and a research User-Agent. An interrupted
download is resumed by the next call.
"""

import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import MUNI_KEY, RAW, SOURCES_YAML

SOURCE_ID = "at"
DATASET_ID = "at_imi_rates"
FIRST_YEAR = (
    2012  # the portal offers 1989 to 2026; the project needs the years before and after 2016 prices
)
LAST_YEAR = 2025  # the last complete tax year (2026 is still being communicated)
PAUSE_SECONDS = 0.8
USER_AGENT = "pthousing-research/0.1 (open portfolio project; contact via the GitHub repository)"
ENCODING = "iso-8859-1"
TITLE = re.compile(r"Lista das taxas IMI por Munic.pio do Distrito (.+?) para o ano (\d{4})")

# The portal numbers island municipalities by district list (19xx Angra do Heroismo, 20xx Horta, 21xx Ponta
# Delgada, 22xx Funchal); mainland codes are the INE codes. Portal code -> INE ``muni_code``.
ISLAND_CODES = {
    "1901": "4301",  # Angra do Heroismo
    "1902": "4501",  # Calheta (Acores) = Calheta de Sao Jorge
    "1903": "4401",  # Santa Cruz da Graciosa
    "1904": "4502",  # Velas
    "1905": "4302",  # Vila Praia da Vitoria
    "2001": "4901",  # Corvo
    "2002": "4701",  # Horta
    "2003": "4801",  # Lajes das Flores
    "2004": "4601",  # Lajes do Pico
    "2005": "4602",  # Madalena
    "2006": "4802",  # Santa Cruz das Flores
    "2007": "4603",  # S. Roque do Pico
    "2101": "4201",  # Lagoa (Acores)
    "2102": "4202",  # Nordeste
    "2103": "4203",  # Ponta Delgada
    "2104": "4204",  # Povoacao
    "2105": "4205",  # Ribeira Grande
    "2106": "4206",  # Vila Franca do Campo
    "2107": "4101",  # Vila do Porto
    "2201": "3101",  # Calheta (Madeira)
    "2202": "3102",  # Camara de Lobos
    "2203": "3103",  # Funchal
    "2204": "3104",  # Machico
    "2205": "3105",  # Ponta do Sol
    "2206": "3106",  # Porto Moniz
    "2207": "3201",  # Porto Santo
    "2208": "3107",  # Ribeira Brava
    "2209": "3108",  # Santa Cruz
    "2210": "3109",  # Santana
    "2211": "3110",  # S. Vicente
}


def _config() -> dict:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID]


def _page_url(year: int, district: str) -> tuple[str, dict]:
    return _config()["url"], {
        "body": "/imi/consultarTaxasIMI.jsp",
        "ano": year,
        "distrito": district,
    }


def page_name(year: int, district: str) -> str:
    """File name of one page inside a snapshot: ``<year>_<district number>.html``."""
    return f"{year}_{district[:2]}.html"


def _get(year: int, district: str, retries: int = 3) -> bytes:
    url, params = _page_url(year, district)
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def check_page(html: str, year: int) -> None:
    """Raise if a page is not the rate list of ``year`` (the portal answers 200 even for error pages)."""
    found = TITLE.search(html)
    if not found:
        raise ValueError("page is not an IMI rate list")
    if int(found.group(2)) != year:
        raise ValueError(f"page is for {found.group(2)}, asked for {year}")


def _snapshots() -> list[Path]:
    return sorted((RAW / SOURCE_ID).glob("imi_rates_*"))


def latest_snapshot() -> Path:
    """The most recent complete snapshot (one with a manifest)."""
    done = [p for p in _snapshots() if (p / "manifest.json").exists()]
    if not done:
        raise FileNotFoundError("No IMI rate snapshot in data/raw/at; run fetch() first")
    return done[-1]


def fetch(
    refresh: bool = False,
    today: date | None = None,
    years: range | None = None,
    pause: float = PAUSE_SECONDS,
) -> Path:
    """Download every (year, district) page into a dated snapshot folder and return it.

    A complete snapshot is reused unless ``refresh``; a folder without a manifest (interrupted download) is
    resumed, skipping the pages already saved.
    """
    if not refresh and any((p / "manifest.json").exists() for p in _snapshots()):
        return latest_snapshot()
    years = years or range(FIRST_YEAR, LAST_YEAR + 1)
    districts = _config()["districts"]
    open_folders = [p for p in _snapshots() if not (p / "manifest.json").exists()]
    day = (today or date.today()).isoformat()
    folder = open_folders[-1] if open_folders else RAW / SOURCE_ID / f"imi_rates_{day}"
    folder.mkdir(parents=True, exist_ok=True)
    for year in years:
        for district in districts:
            path = folder / page_name(year, district)
            if path.exists():
                continue
            content = _get(year, district)
            check_page(content.decode(ENCODING), year)
            path.write_bytes(content)
            time.sleep(pause)
    manifest = {
        "snapshot_date": folder.name.removeprefix("imi_rates_"),
        "years": [min(years), max(years)],
        "districts": districts,
        "pages": len(list(folder.glob("*.html"))),
        "url": _config()["url"],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder


# ---- parsing --------------------------------------------------------------------------------------


def _text(cell: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", cell)).strip()


def _rate(cell: str) -> float:
    digits = re.sub(r"[^\d,]", "", cell)
    return float(digits.replace(",", ".")) if digits else float("nan")


def parse_page(html: str, year: int | None = None) -> pd.DataFrame:
    """One row per municipality listed in a district page.

    Columns: ``portal_code`` (4 digits), ``year`` (read from the page title), ``urban_pct`` and ``rustic_pct``
    (NaN when the page shows no single rate: parish-specific rates), ``parish_rates`` (a parish-rate link is
    shown) and ``deduction_link`` (the household-deduction page is linked).
    """
    found = TITLE.search(html)
    if not found:
        raise ValueError("page is not an IMI rate list")
    page_year = int(found.group(2))
    if year is not None and year != page_year:
        raise ValueError(f"page is for {page_year}, asked for {year}")
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        if len(cells) < 6 or not re.fullmatch(r"\d{4}", _text(cells[0])):
            continue
        rows.append(
            {
                "portal_code": _text(cells[0]),
                "year": page_year,
                "urban_pct": _rate(_text(cells[2])),
                "rustic_pct": _rate(_text(cells[3])),
                "parish_rates": bool(_text(cells[4])),
                "deduction_link": "consultaDeducao" in cells[5],
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "portal_code",
            "year",
            "urban_pct",
            "rustic_pct",
            "parish_rates",
            "deduction_link",
        ],
    )


def to_muni_code(portal_code: pd.Series) -> pd.Series:
    """INE ``muni_code`` of portal codes: mainland codes are unchanged, island codes use ``ISLAND_CODES``."""
    mapped = portal_code.map(ISLAND_CODES)
    island = portal_code.str[:2].isin({"19", "20", "21", "22"})
    if (island & mapped.isna()).any():
        unknown = sorted(portal_code[island & mapped.isna()].unique())
        raise ValueError(f"island codes without a mapping: {unknown}")
    return mapped.where(island, portal_code)


def read(folder: Path | None = None) -> pd.DataFrame:
    """Parse every page of a snapshot (default: the latest) into one table keyed by ``muni_code`` and year."""
    folder = folder or latest_snapshot()
    frames = [
        parse_page(path.read_bytes().decode(ENCODING), int(path.name.split("_")[0]))
        for path in sorted(folder.glob("*.html"))
    ]
    out = pd.concat(frames, ignore_index=True)
    out[MUNI_KEY] = to_muni_code(out["portal_code"])
    return out.drop(columns="portal_code")
