"""Single source of project constants: paths, CRS, base year and geographic keys."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"
EXTERNAL = DATA / "external"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"

CONFIG = ROOT / "config"
SOURCES_YAML = CONFIG / "sources.yaml"
SCENARIOS_YAML = CONFIG / "scenarios.yaml"

REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"

PHASES = ("p1", "p2", "p3", "p4")

# Real values are expressed in constant euros of this year (HICP/CPI deflator, see harmonize.py).
BASE_YEAR = 2024

# CRS: ETRS89 / Portugal TM06 for metric operations, WGS84 for web maps.
CRS_METRIC = "EPSG:3763"
CRS_WEB = "EPSG:4326"

# Municipality key: INE DICOFRE 4-digit code (DDCC) stored as a zero-padded string.
MUNI_KEY = "muni_code"
YEAR_KEY = "year"
