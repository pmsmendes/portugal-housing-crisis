"""Renovation of existing buildings against new building and vacant homes (RQ2.8).

INE counts buildings licensed (2002-2025) and completed (2011-2025) by type of project, municipality by municipality:
new constructions, and "enlargements, changes and reconstructions", which is every work on an existing building, extensions
included. The unit is the building, not the dwelling, and works that need no licence are not counted, so the series show the
pace and the place of rehabilitation work, not the number of homes it returned to use. How many dwellings a renovated
building holds, how many of them were empty and whether they were let or sold afterwards is not in the data: ``years_to_clear``
varies the dwellings per building instead of assuming it. Functions take interim tables; nothing here reads files.
"""

import numpy as np
import pandas as pd
from scipy import stats

from pthousing.config import MUNI_KEY

HOUSING = "family_housing"


def national(works: pd.DataFrame) -> pd.DataFrame:
    """Family-housing buildings licensed and completed by year, summed over municipalities, new against alteration.

    ``works`` is the ``ine_building_works`` table. Columns ``licensed_<project>_n`` and ``completed_<project>_n`` for new,
    alteration and total, and ``alteration_share_licensed_pct`` (alteration works over all licensed family-housing
    buildings). Completed counts exist from 2011 only and are NaN before.
    """
    d = works[works["purpose"] == HOUSING]
    out = pd.DataFrame(index=sorted(d["year"].unique()))
    for kind, column in (
        ("licensed", "licensed_buildings_n"),
        ("completed", "completed_buildings_n"),
    ):
        wide = d.groupby(["year", "project"])[column].sum(min_count=1).unstack("project")
        for project in ("new", "alteration", "total"):
            out[f"{kind}_{project}_n"] = wide[project]
    out.index.name = "year"
    out["alteration_share_licensed_pct"] = (
        100 * out["licensed_alteration_n"] / out["licensed_total_n"]
    )
    out["alteration_share_completed_pct"] = (
        100 * out["completed_alteration_n"] / out["completed_total_n"]
    )
    return out


def changes(
    frame: pd.DataFrame, windows: dict[str, tuple[int, int]], columns: list[str]
) -> pd.DataFrame:
    """Percentage change of each column between the first and last year of each window; one row per window."""
    rows = {
        label: {c: 100 * (frame.loc[end, c] / frame.loc[start, c] - 1) for c in columns}
        for label, (start, end) in windows.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def intensity(
    works: pd.DataFrame, stock: pd.DataFrame, start: int = 2012, end: int = 2021
) -> pd.DataFrame:
    """Family-housing buildings completed (and licensed) in works on existing buildings per 1,000 dwellings, by municipality.

    Sums the years ``start`` to ``end`` (the years between the two censuses, 2011 being partial) and divides by the
    2011 stock of dwellings; ``stock`` is ``vacancy.table`` (``dwellings_2011_n``). Also the same for new constructions, so that
    the two kinds of work can be compared, and ``alteration_share_completed_pct`` (works on existing buildings over all
    completed family-housing buildings), which does not depend on how many dwellings a building holds, unlike the rates
    per 1,000 dwellings: a city's blocks hold many dwellings each, so its rates per dwelling look low for either kind of work.
    """
    d = works[(works["purpose"] == HOUSING) & works["year"].between(start, end)]
    out = pd.DataFrame(index=stock.index)
    for project in ("alteration", "new"):
        part = d[d["project"] == project].groupby(MUNI_KEY)
        out[f"completed_{project}_n"] = part["completed_buildings_n"].sum()
        out[f"licensed_{project}_n"] = part["licensed_buildings_n"].sum()
        for kind in ("completed", "licensed"):
            out[f"{kind}_{project}_per_1000"] = (
                1000 * out[f"{kind}_{project}_n"] / stock["dwellings_2011_n"]
            )
    both = out["completed_alteration_n"] + out["completed_new_n"]
    out["alteration_share_completed_pct"] = 100 * out["completed_alteration_n"] / both
    return out


def association(frame: pd.DataFrame, x: str, ys: list[str]) -> pd.DataFrame:
    """Spearman correlation of ``x`` with each of ``ys`` across municipalities, with its p-value and n."""
    rows = {}
    for y in ys:
        d = frame[[x, y]].dropna()
        rho, p = stats.spearmanr(d[x], d[y])
        rows[y] = {"spearman": rho, "p_value": p, "n": len(d)}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("against")


def years_to_clear(
    excess_vacant_n: float,
    pace_buildings_per_year: float,
    dwellings_per_building: list[float],
    usable_shares: list[float],
) -> pd.DataFrame:
    """Years of renovation at today's pace needed to bring back the usable share of excess vacant homes.

    Each renovated building is taken to return ``dwellings_per_building`` homes that were vacant (an upper bound: some were
    occupied, some are not for sale or let afterwards). Rows are dwellings per building, columns the usable share of the
    excess; the number is a comparison of scale against the pace of work observed, not a forecast.
    """
    table = pd.DataFrame(
        {
            f"{share:.0%} usable": [
                excess_vacant_n * share / (pace_buildings_per_year * d)
                for d in dwellings_per_building
            ]
            for share in usable_shares
        },
        index=pd.Index(dwellings_per_building, name="dwellings_per_building"),
    )
    return table


def group_summary(frame: pd.DataFrame, by: pd.Series, columns: list[str]) -> pd.DataFrame:
    """Median of ``columns`` by group, with the number of municipalities."""
    g = frame.groupby(by)
    out = g[columns].median()
    out.insert(0, "municipalities_n", g.size())
    return out.replace([np.inf, -np.inf], np.nan)
