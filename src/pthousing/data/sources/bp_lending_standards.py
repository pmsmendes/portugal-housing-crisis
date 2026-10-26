"""Banco de Portugal macroprudential progress report: the data behind its charts on new housing loans.

The March 2026 edition (covering 2025) ships the chart data as a workbook, one sheet per chart: loan-to-value,
debt-service-to-income (DSTI), risk profile, maturity and the State guarantee, yearly from 2018 Q3. ``build``
reads the workbook with the standard library (no spreadsheet dependency) into a tidy table written to
``data/external/lending_series.csv``; the figures transcribed from the March 2025 report stay in
``lending_standards.csv`` (``analysis/lending.py``).

Files are kept as downloaded in ``data/raw/bp_lending_standards/``; ``fetch`` downloads them from ``config/sources.yaml``.
"""

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yaml

from pthousing.config import EXTERNAL, RAW, SOURCES_YAML

SOURCE_ID = "bportugal"
DATASET_ID = "bp_lending_standards"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (research project)"
}  # the bank's site refuses the default python UA
WORKBOOK = "chart_data_march_2026.xlsx"
OUT = EXTERNAL / "lending_series.csv"

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
_ROW = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_PERIOD = re.compile(r"^(?:Average )?(\d{4})(?: Q([1-4]))?$")
_MONTH = re.compile(r"^([A-Z][a-z]{2})\. (\d{2})$")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# sheet -> {column number: (indicator, unit)}; labels are in column 3 (English), values from column 4
SPECS: dict[str, dict[int, tuple[str, str]]] = {
    "G3.1": {
        4: ("ltv_share_at_most_80", "pct"),
        5: ("ltv_share_80_to_90", "pct"),
        6: ("ltv_share_90_to_100", "pct"),
        7: ("ltv_share_above_100", "pct"),
    },
    "G3.3": {
        4: ("ltv_weighted_mean", "pct"),
        5: ("ltv_weighted_mean_guarantee", "pct"),
    },
    "G3.6": {
        4: ("dsti_actual_mean", "pct"),
        5: ("dsti_actual_mean_guarantee", "pct"),
    },
    "G3.9": {
        4: ("risk_share_low", "pct"),
        5: ("risk_share_intermediate", "pct"),
        6: ("risk_share_high", "pct"),
    },
    "G3.10": {
        4: ("maturity_share_at_most_10", "pct"),
        5: ("maturity_share_10_to_20", "pct"),
        6: ("maturity_share_20_to_30", "pct"),
        7: ("maturity_share_30_to_40", "pct"),
    },
    "G3.11": {
        4: ("maturity_weighted_mean", "years"),
        6: ("maturity_weighted_mean_guarantee", "years"),
    },
    "G C2.2": {
        4: ("guarantee_share_contracts", "pct"),
        5: ("guarantee_share_amount", "pct"),
    },
    "G C2.3": {4: ("share_borrowers_up_to_35", "pct")},
}


def fetch(refresh: bool = False) -> list[Path]:
    """Download the report and its chart data into ``data/raw/bp_lending_standards/`` (cached unless ``refresh``)."""
    entry = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID]
    paths = []
    for name, url in entry["files"].items():
        path = RAW / DATASET_ID / name
        if refresh or not path.exists():
            resp = requests.get(url, headers=HEADERS, timeout=300)
            resp.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(resp.content)
        paths.append(path)
    return paths


def _column(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n


def read_sheet(path: Path, sheet: str) -> dict[int, dict[int, str]]:
    """Cell texts of one sheet as ``{row: {column: text}}`` (empty cells left out)."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(_T)) for si in root]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {
            r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        }
        target = next(rels[s.get(_REL)] for s in wb.find("m:sheets", _NS) if s.get("name") == sheet)
        target = target.lstrip("/")
        root = ET.fromstring(z.read(target if target.startswith("xl/") else f"xl/{target}"))
    rows: dict[int, dict[int, str]] = {}
    for row in root.iter(_ROW):
        cells = {}
        for c in row.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if v is None or v.text in (None, ""):
                continue
            cells[_column(c.get("r"))] = strings[int(v.text)] if c.get("t") == "s" else v.text
        if cells:
            rows[int(row.get("r"))] = cells
    return rows


def parse_period(label: str) -> str | None:
    """``'2019'`` -> ``'2019'``, ``'Average 2025'`` -> ``'2025'``, ``'2019 Q3'`` -> ``'2019-Q3'``, ``'Jan. 25'`` -> ``'2025-01'``; None for other text."""
    label = label.strip()
    if m := _PERIOD.match(label):
        return m.group(1) if m.group(2) is None else f"{m.group(1)}-Q{m.group(2)}"
    if (m := _MONTH.match(label)) and m.group(1) in _MONTHS:
        return f"20{m.group(2)}-{_MONTHS.index(m.group(1)) + 1:02d}"
    return None


def tidy(
    rows: dict[int, dict[int, str]], spec: dict[int, tuple[str, str]], sheet: str
) -> pd.DataFrame:
    """Rows of one sheet (label in column 3, or 2) as ``indicator, period, value, unit, sheet``; blank cells are dropped."""
    out = []
    for _, cells in sorted(rows.items()):
        period = parse_period(cells.get(3, "")) or parse_period(
            cells.get(2, "")
        )  # an average row has its labels swapped
        if period is None:
            continue
        for col, (indicator, unit) in spec.items():
            if col in cells:
                out.append((indicator, period, float(cells[col]), unit, sheet))
    return pd.DataFrame(out, columns=["indicator", "period", "value", "unit", "sheet"])


def build(path: Path | None = None) -> pd.DataFrame:
    """All series of the workbook, long, with the guarantee-free risk profile of 2025 added (sheet G3.9, columns 9 to 11)."""
    path = path or RAW / DATASET_ID / WORKBOOK
    parts = [tidy(read_sheet(path, sheet), spec, sheet) for sheet, spec in SPECS.items()]
    risk = read_sheet(path, "G3.9")
    ex = {9: "risk_share_low", 10: "risk_share_intermediate", 11: "risk_share_high"}
    for cells in risk.values():
        if cells.get(8) == "2025":
            parts.append(
                pd.DataFrame(
                    [
                        (f"{name}_no_guarantee", "2025", float(cells[c]), "pct", "G3.9")
                        for c, name in ex.items()
                    ],
                    columns=["indicator", "period", "value", "unit", "sheet"],
                )
            )
    return pd.concat(parts, ignore_index=True)


def write(path: Path | None = None) -> pd.DataFrame:
    """Build the table and write ``data/external/lending_series.csv``."""
    table = build(path)
    table.round(4).to_csv(OUT, index=False)
    return table
