"""Geography crosswalks and boundary changes, CPI deflation to base-year EUR, frequency conversion."""

import pandas as pd

from pthousing.config import BASE_YEAR, EXTERNAL, MUNI_KEY

CROSSWALK_PATH = EXTERNAL / "muni_crosswalk.csv"

# Municipalities created after 1995 (Vizela, Trofa, Odivelas). INE does not back-cast them: its 1995+ series
# hold exact zeros, not missing values, until the first year with data, while the parent municipalities still
# carry the territory. First year with data = first non-zero year of the licensed-dwellings series (0000087).
VALID_FROM_YEAR = {"0314": 1998, "1318": 1998, "1116": 1999}

# One municipality-level indicator per NUTS vintage; INE's 7-char geocod = NUTS III prefix + muni_code.
NUTS_2013_SOURCE = ("0009490", "S5A20213")  # sale prices, methodology 2018, 3Q2021
NUTS_2024_SOURCE = ("0012600", "S7A2024")  # median rent of new leases, 2024


def nuts_prefixes(ine_frame: pd.DataFrame, caop_codes: set[str], column: str) -> pd.Series:
    """NUTS III code per municipality from the 7-char ``geocod`` of a parsed INE frame."""
    rows = ine_frame[(ine_frame["geocod"].str.len() == 7) & ine_frame[MUNI_KEY].isin(caop_codes)]
    pairs = rows.assign(**{column: rows["geocod"].str[:3]})[[MUNI_KEY, column]].drop_duplicates()
    if pairs[MUNI_KEY].duplicated().any():
        raise ValueError(f"{column}: a municipality maps to more than one NUTS III code")
    missing = caop_codes - set(pairs[MUNI_KEY])
    if missing:
        raise ValueError(
            f"{column}: {len(missing)} municipalities not found in INE frame, e.g. {sorted(missing)[:5]}"
        )
    return pairs.set_index(MUNI_KEY)[column]


def build_crosswalk(
    caop: pd.DataFrame, ine_nuts2013: pd.DataFrame, ine_nuts2024: pd.DataFrame
) -> pd.DataFrame:
    """Municipality lookup: CAOP 2024 attributes plus NUTS III / II codes in the 2013 and 2024 vintages."""
    codes = set(caop[MUNI_KEY])
    out = caop[
        [MUNI_KEY, "muni_name", "district", "territory", "nuts3_name_2024", "nuts2_name_2024"]
    ].copy()
    for vintage, frame in (("2013", ine_nuts2013), ("2024", ine_nuts2024)):
        out[f"nuts3_{vintage}"] = out[MUNI_KEY].map(nuts_prefixes(frame, codes, f"nuts3_{vintage}"))
        out[f"nuts2_{vintage}"] = out[f"nuts3_{vintage}"].str[:2]
    out["valid_from_year"] = out[MUNI_KEY].map(VALID_FROM_YEAR).astype("Int64")
    return out.sort_values(MUNI_KEY, ignore_index=True)


def write_crosswalk() -> pd.DataFrame:
    """Build ``data/external/muni_crosswalk.csv`` from the CAOP files and two INE series (downloads if missing)."""
    from pthousing.data.sources import caop, ine

    caop.download()
    frames = []
    for code, period in (NUTS_2013_SOURCE, NUTS_2024_SOURCE):
        ine.fetch_indicator(code, periods=[period])
        frames.append(ine.read_indicator(code))
    crosswalk = build_crosswalk(caop.read_municipalities(geometry=False), *frames)
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(CROSSWALK_PATH, index=False, encoding="utf-8", lineterminator="\n")
    return crosswalk


def read_crosswalk() -> pd.DataFrame:
    return pd.read_csv(CROSSWALK_PATH, dtype=str, encoding="utf-8")


def mask_pre_creation(df: pd.DataFrame, crosswalk: pd.DataFrame | None = None) -> pd.DataFrame:
    """Set ``value`` to NaN for municipality-years before the municipality existed (structural zeros).

    The parent municipalities keep the territory until then, so their series have a boundary break at
    the same date; this only cleans the new municipalities' own history."""
    cw = crosswalk if crosswalk is not None else read_crosswalk()
    start = pd.to_numeric(cw.set_index(MUNI_KEY)["valid_from_year"]).dropna()
    return df.assign(value=df["value"].mask(df["year"] < df[MUNI_KEY].map(start)))


def keep_municipalities(df: pd.DataFrame, crosswalk: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rows of a parsed INE frame that belong to one of the 308 municipalities (parishes, regions and
    cities dropped). Use ``unmatched_codes`` to see what was left out."""
    codes = set((crosswalk if crosswalk is not None else read_crosswalk())[MUNI_KEY])
    return df[df[MUNI_KEY].isin(codes) & df["geo_level"].eq("municipality")]


def unmatched_codes(df: pd.DataFrame, crosswalk: pd.DataFrame | None = None) -> pd.DataFrame:
    """Municipality-level geographies of an INE frame whose ``muni_code`` is not in the crosswalk."""
    codes = set((crosswalk if crosswalk is not None else read_crosswalk())[MUNI_KEY])
    rows = df[df["geo_level"].eq("municipality") & ~df[MUNI_KEY].isin(codes)]
    return rows[["geocod", "geo_name", MUNI_KEY]].drop_duplicates().reset_index(drop=True)


# ---- CPI deflation to constant BASE_YEAR euros ---------------------------------------------------


def annual_deflator(cpi_annual: pd.DataFrame, base_year: int = BASE_YEAR) -> pd.Series:
    """Factor by year that turns nominal euros into constant ``base_year`` euros: CPI(base) / CPI(year).

    ``cpi_annual`` has columns ``year`` and ``cpi_index_b2025`` (the interim ``ine_cpi`` table).
    """
    cpi = cpi_annual.set_index("year")["cpi_index_b2025"]
    if base_year not in cpi.index:
        raise ValueError(f"Base year {base_year} is not in the CPI series")
    return (cpi[base_year] / cpi).rename("deflator")


def quarterly_deflator(cpi_monthly: pd.DataFrame, base_year: int = BASE_YEAR) -> pd.Series:
    """Factor by quarter start: average CPI of ``base_year`` / average CPI of the quarter.

    A quarter is only used when all three months are present. ``cpi_monthly`` is the interim
    ``ine_cpi_monthly`` table.
    """
    cpi = cpi_monthly.set_index("period_start")["cpi_index_b2025"]
    months = cpi[cpi.index.year == base_year]
    if len(months) != 12:
        raise ValueError(f"Base year {base_year} does not have 12 monthly CPI values")
    quarter = cpi.index.to_period("Q").to_timestamp()
    grouped = cpi.groupby(quarter)
    mean = grouped.mean()[grouped.count() == 3]
    return (months.mean() / mean).rename("deflator")


def to_real(nominal: pd.Series, deflator: pd.Series, period: pd.Series) -> pd.Series:
    """Nominal values times the deflator of their period (year or quarter start); NaN if no deflator."""
    return nominal * period.map(deflator)
