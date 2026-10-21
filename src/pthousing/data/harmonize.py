"""Geography crosswalks and boundary changes, CPI deflation to base-year EUR, frequency conversion."""

import pandas as pd

from pthousing.config import EXTERNAL, MUNI_KEY

CROSSWALK_PATH = EXTERNAL / "muni_crosswalk.csv"

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
