"""Households against population: household size, one-person households, and what drove the count of households (RQ3.4, RQ3.5).

Two censuses carry households by number of persons (2011 and 2021, ``ine_households_size``), and the resident
population of the same years comes from ``ine_population`` (``age_structure.band_counts``). Between them the number
of households is split exactly into a part that population growth would give at the old household size and a part
that is due to the change of household size. Only the two census years exist, so nothing is said of the years in
between, and a one-person household is a household, not a person living alone in a free-standing home. Functions take
tables; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import MUNI_KEY

YEARS = (2011, 2021)
SIZE_PERSONS = {
    "1": 1,
    "2": 2,
    "3": 3,
}  # "4plus" is open-ended, so the mean size is not computed from sizes


def profile(
    households: pd.DataFrame, counts: pd.DataFrame, years: tuple[int, int] = YEARS
) -> pd.DataFrame:
    """One row per municipality: households, residents, persons per household and the one-person share, both years.

    ``households`` is ``ine_households_size``; ``counts`` is ``age_structure.band_counts`` (its ``population_n`` is
    residents). Columns are suffixed with the year (``households_2011_n``, ``persons_per_household_2021``,
    ``one_person_2011_pct``, ``two_person_2011_pct``) and the changes are ``size_change`` (persons per household,
    later minus earlier) and ``one_person_change_pp``. Persons per household is residents over households, so it
    includes people living in collective homes (a few per cent of residents).
    """
    start, end = years
    hh = households.pivot_table(
        index=MUNI_KEY, columns=["census_year", "size"], values="households_n", aggfunc="sum"
    )
    pop = counts[counts["year"].isin(years)].pivot(
        index=MUNI_KEY, columns="year", values="population_n"
    )
    out = pd.DataFrame(index=hh.index)
    for year in years:
        total = hh[year].sum(axis=1)
        out[f"households_{year}_n"] = total
        out[f"population_{year}_n"] = pop[year]
        out[f"persons_per_household_{year}"] = pop[year] / total
        out[f"one_person_{year}_pct"] = 100 * hh[(year, "1")] / total
        out[f"two_person_{year}_pct"] = 100 * hh[(year, "2")] / total
    out["size_change"] = out[f"persons_per_household_{end}"] - out[f"persons_per_household_{start}"]
    out["one_person_change_pp"] = out[f"one_person_{end}_pct"] - out[f"one_person_{start}_pct"]
    return out.reset_index()


def decompose(prof: pd.DataFrame, years: tuple[int, int] = YEARS) -> pd.DataFrame:
    """Split the change in households into a population part and a household-size part.

    ``from_population_n`` is the households the population change would add at the earlier persons per household
    (``population_end / size_start - households_start``); ``from_size_n`` is the rest, negative when households got
    larger. They add to ``households_change_n`` exactly. The log versions (``dlog_households``, ``dlog_population``,
    ``dlog_size``) satisfy ``dlog_households = dlog_population - dlog_size``.
    """
    start, end = years
    out = prof[[MUNI_KEY]].copy()
    h0, h1 = prof[f"households_{start}_n"], prof[f"households_{end}_n"]
    p0, p1 = prof[f"population_{start}_n"], prof[f"population_{end}_n"]
    out["households_change_n"] = h1 - h0
    out["from_population_n"] = p1 / (p0 / h0) - h0
    out["from_size_n"] = out["households_change_n"] - out["from_population_n"]
    out["dlog_households"] = np.log(h1 / h0)
    out["dlog_population"] = np.log(p1 / p0)
    out["dlog_size"] = np.log((p1 / h1) / (p0 / h0))
    return out


def aggregate(prof: pd.DataFrame, by: pd.Series | None = None) -> pd.DataFrame:
    """Sum households and residents over a grouping (or the country if ``by`` is None) and rebuild the ratios.

    ``by`` is indexed by ``muni_code``. The one-person share is recomputed from the summed one-person households, so
    large municipalities weigh by their size; it needs ``one_person_<year>_pct`` and the household totals, from which
    the one-person count is recovered.
    """
    start, end = YEARS
    df = prof.set_index(MUNI_KEY)
    key = by.reindex(df.index) if by is not None else pd.Series("Portugal", index=df.index)
    sums = {}
    for year in (start, end):
        sums[f"households_{year}_n"] = df[f"households_{year}_n"]
        sums[f"population_{year}_n"] = df[f"population_{year}_n"]
        sums[f"one_person_{year}_n"] = (
            df[f"households_{year}_n"] * df[f"one_person_{year}_pct"] / 100
        )
    grouped = pd.DataFrame(sums).groupby(key).sum(min_count=1)
    for year in (start, end):
        grouped[f"persons_per_household_{year}"] = (
            grouped[f"population_{year}_n"] / grouped[f"households_{year}_n"]
        )
        grouped[f"one_person_{year}_pct"] = (
            100 * grouped[f"one_person_{year}_n"] / grouped[f"households_{year}_n"]
        )
    grouped["one_person_change_pp"] = (
        grouped[f"one_person_{end}_pct"] - grouped[f"one_person_{start}_pct"]
    )
    return grouped.drop(columns=[f"one_person_{y}_n" for y in (start, end)])
