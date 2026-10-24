"""Age structure of the resident population: shares by age band, national profile, change between two years (RQ3.5).

Population by five-year age group exists for 2011-2023 (``ine_population``). Bands: children (0-14), young adults
(15-24), the household-forming ages (25-44), older adults (45-64), the old (65+) and the oldest (80+). The shares
describe who lives where; they say nothing of who moves, and ageing is not separable from migration here (the
municipal population change of ``demography.municipal_balance`` is the place to look at flows).
"""

import pandas as pd

from pthousing.config import MUNI_KEY, YEAR_KEY
from pthousing.data import interim

BANDS = {
    "age_0_14": ["0-4", "5-9", "10-14"],
    "age_15_24": ["15-19", "20-24"],
    "age_25_44": ["25-29", "30-34", "35-39", "40-44"],
    "age_45_64": ["45-49", "50-54", "55-59", "60-64"],
    "age_65plus": ["65-69", "70-74", "75-79", "80-84", "85+"],
    "age_80plus": ["80-84", "85+"],
}
PARTITION = list(BANDS)[:5]  # the five bands that partition the population; 80+ is a subset of 65+
AGE_ORDER = [g for band in PARTITION for g in BANDS[band]]
BAND_LABELS = {
    "age_0_14": "0-14",
    "age_15_24": "15-24",
    "age_25_44": "25-44",
    "age_45_64": "45-64",
    "age_65plus": "65+",
    "age_80plus": "80+",
}


def read_population() -> pd.DataFrame:
    """Population by municipality, year and five-year group (both sexes, totals excluded)."""
    pop = interim.read("ine_population").query("sex == 'total' and age_group != 'total'")
    return pop[[MUNI_KEY, YEAR_KEY, "age_group", "population_n"]]


def band_counts(pop: pd.DataFrame) -> pd.DataFrame:
    """People in each band per municipality and year, plus the total (``population_n``).

    A band is NaN if any of its groups is missing, so a short count is never read as a small one.
    """
    wide = pop.pivot_table(
        index=[MUNI_KEY, YEAR_KEY],
        columns="age_group",
        values="population_n",
        aggfunc="sum",
        dropna=False,
    ).reindex(columns=AGE_ORDER)
    out = pd.DataFrame(
        {name: wide[groups].sum(axis=1, min_count=len(groups)) for name, groups in BANDS.items()}
    )
    out["population_n"] = out[PARTITION].sum(axis=1, min_count=len(PARTITION))
    return out.reset_index()


def band_shares(counts: pd.DataFrame) -> pd.DataFrame:
    """Share of residents in each band (``<band>_pct``) and the ageing index (people 65+ per 100 aged 0-14)."""
    out = counts[[MUNI_KEY, YEAR_KEY]].copy()
    for name in BANDS:
        out[f"{name}_pct"] = 100 * counts[name] / counts["population_n"]
    out["ageing_index"] = 100 * counts["age_65plus"] / counts["age_0_14"]
    return out


def national_profile(pop: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Residents by five-year group (rows, in age order) for each year in ``years`` (columns), all municipalities."""
    p = pop[pop[YEAR_KEY].isin(years)].pivot_table(
        index="age_group", columns=YEAR_KEY, values="population_n", aggfunc="sum"
    )
    return p.reindex(AGE_ORDER)


def national_bands(counts: pd.DataFrame) -> pd.DataFrame:
    """People in each band and its share of residents (``<band>_pct``), by year, summed over municipalities."""
    n = counts.groupby(YEAR_KEY)[[*BANDS, "population_n"]].sum(min_count=1)
    for name in BANDS:
        n[f"{name}_pct"] = 100 * n[name] / n["population_n"]
    return n


def change_between(shares: pd.DataFrame, start: int, end: int, columns: list[str]) -> pd.DataFrame:
    """Per municipality: each column in ``start`` and ``end`` and its change (``<col>_change_pp``)."""
    wide = shares[shares[YEAR_KEY].isin([start, end])].pivot(
        index=MUNI_KEY, columns=YEAR_KEY, values=columns
    )
    out = pd.DataFrame(index=wide.index)
    for c in columns:
        out[f"{c}_{start}"] = wide[(c, start)]
        out[f"{c}_{end}"] = wide[(c, end)]
        out[f"{c}_change_pp"] = wide[(c, end)] - wide[(c, start)]
    return out
