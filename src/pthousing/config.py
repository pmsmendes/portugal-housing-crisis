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
# Rent-vs-buy assumptions (features/rent_vs_buy.py; assumptions, not estimates, shown with sensitivity).
OPPORTUNITY_RATE_PCT = 3.0  # yearly return forgone on the deposit
MAINTENANCE_PCT = 1.0  # yearly upkeep as a share of the price
BUYING_COSTS_PCT = 6.0  # IMT, stamp duty, notary and registry, share of the price
HOLDING_YEARS = 10  # years over which the buying costs are spread
IMI_TAXABLE_SHARE = 0.6  # taxable value (VPT) as a share of the market price
EXPECTED_APPRECIATION_PCT = 2.0  # yearly nominal price growth with flat real prices (ECB target)
IMI_URBAN_MIN_PCT = (
    0.30  # legal floor of the municipal urban IMI rate (CIMI); no rate in 2012-2025 is lower
)
# Rent update (analysis/rent_update.py): floor area of a let dwelling, an assumption (the census mean area of all dwellings is
# larger because let homes are smaller); shown with sensitivity at 50 and 90.
RENTED_DWELLING_AREA_SQM = 70
# Vacancy (analysis/vacancy.py): the share of dwellings that are vacant at any time because homes are being sold, let,
# inherited or repaired; vacancy above it is "excess". An assumption, shown with sensitivity (3 and 8).
FRICTIONAL_VACANCY_PCT = 5.0
# Surcharge on vacant dwellings (analysis/revenue.py): CIMI art. 112(3) lets a council raise the urban IMI rate on
# buildings vacant for over a year; the multiple applied in practice is three (the "IMI a triplicar" of 54 councils in 2017).
VACANT_IMI_MULTIPLE = 3.0
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
