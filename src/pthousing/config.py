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

# Mortgage-burden assumptions for a typical new home loan (assumptions, not estimates: results are shown
# with sensitivity to both; see docs/methodology.md and docs/decisions.md).
MORTGAGE_LTV = 0.80  # loan as a share of the dwelling price
MORTGAGE_TERM_YEARS = 30
# Benchmark dwelling for the fixed-size variants of PTI / RTI (comparable across municipalities).
BENCHMARK_AREA_SQM = 100

# Municipality typology (data/external/muni_typology.csv): own transparent proxies, not the INE TIPAU.
DENSITY_URBAN_PER_KM2 = 500  # residents per km2 (2021) from which a municipality is urban
DENSITY_RURAL_PER_KM2 = 100  # below this it is rural; in between, intermediate
TOURIST_AL_PER_1000 = (
    25  # registered short-term rentals per 1,000 dwellings (mainland) from which it is tourist
)

# CRS: ETRS89 / Portugal TM06 for metric operations, WGS84 for web maps.
CRS_METRIC = "EPSG:3763"
CRS_WEB = "EPSG:4326"

# Municipality key: INE DICOFRE 4-digit code (DDCC) stored as a zero-padded string.
MUNI_KEY = "muni_code"
YEAR_KEY = "year"
