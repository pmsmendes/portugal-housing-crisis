"""Dwelling stock: how much of what was completed shows up in the census count, and the stock between censuses (RQ2.4).

The census counts conventional dwellings only in 2011 and 2021 (``ine_census_stock``); completions of new family
dwellings are annual (``ine_construction``). Between the censuses the net change in the count is set against the
dwellings completed in the years in between. The difference is what completions do not explain: demolitions, merged
or split dwellings, conversions to and from other uses, dwellings added by works on existing buildings (not counted as
completions here) and differences in what each census counts. It is an accounting gap, not an estimate of any one of
those. Rolling the stock along the completions then gives a yearly path, valid only as far as the retention held
outside the window it was measured in. Functions take tables; nothing here reads files.
"""

import pandas as pd

from pthousing.config import MUNI_KEY, YEAR_KEY

CENSUS = (2011, 2021)


def reconcile(
    panel: pd.DataFrame, stock: pd.DataFrame, years: tuple[int, int] = CENSUS
) -> pd.DataFrame:
    """One row per municipality: the census count at both ends, the net addition and the completions in between.

    ``panel`` has ``muni_code``, ``year``, ``completed_n``; ``stock`` is ``ine_census_stock`` (``census_year``,
    ``dwellings_n``). Completions are those of the years after the first census year up to and including the second
    (the convention of ``supply.balance``; the censuses are in March, so the window is a quarter off at each end).
    ``gap_n`` is the net addition minus the completions (negative: the count grew less than the completions);
    ``gap_per_1000`` divides it by the dwellings of the first census. ``retention`` is the net addition over the
    completions, NaN without completions, and is only meaningful summed over groups: in a small municipality a few
    dwellings swing it.
    """
    start, end = years
    count = stock.pivot(index=MUNI_KEY, columns="census_year", values="dwellings_n")
    done = panel[(panel[YEAR_KEY] > start) & (panel[YEAR_KEY] <= end)]
    completions = done.groupby(MUNI_KEY)["completed_n"].sum(min_count=1)
    out = pd.DataFrame(index=count.index)
    out["dwellings_start_n"] = count[start]
    out["dwellings_end_n"] = count[end]
    out["added_n"] = out["dwellings_end_n"] - out["dwellings_start_n"]
    out["completions_n"] = completions.reindex(out.index)
    return _rates(out)


def _rates(df: pd.DataFrame) -> pd.DataFrame:
    """Gap, gap per 1,000 dwellings and retention from the count columns (so sums of groups can be recomputed)."""
    out = df.copy()
    out["gap_n"] = out["added_n"] - out["completions_n"]
    out["gap_per_1000"] = 1000 * out["gap_n"] / out["dwellings_start_n"]
    out["completions_per_1000"] = 1000 * out["completions_n"] / out["dwellings_start_n"]
    out["added_per_1000"] = 1000 * out["added_n"] / out["dwellings_start_n"]
    out["retention"] = (out["added_n"] / out["completions_n"]).where(out["completions_n"] > 0)
    return out


def aggregate(rec: pd.DataFrame, by: pd.Series | None = None) -> pd.DataFrame:
    """Sum the counts over a grouping (the country if ``by`` is None) and rebuild the gap and the retention.

    ``by`` is indexed by ``muni_code``; municipalities missing from it are dropped. ``municipalities_n`` counts the
    municipalities of each group and ``losing_n`` those whose count fell between the censuses.
    """
    key = by.reindex(rec.index) if by is not None else pd.Series("Portugal", index=rec.index)
    counts = ["dwellings_start_n", "dwellings_end_n", "added_n", "completions_n"]
    sums = rec[counts].groupby(key).sum(min_count=1)
    sums["municipalities_n"] = rec.groupby(key).size()
    sums["losing_n"] = (rec["added_n"] < 0).groupby(key).sum()
    return _rates(sums)


def roll_stock(
    completions: pd.Series,
    anchor_year: int,
    anchor_stock: float,
    retention: float,
) -> pd.Series:
    """Yearly dwelling stock: the anchor count, moved along the completions at a constant retention.

    ``completions`` is indexed by year. Forward, ``stock[t] = stock[t-1] + retention * completions[t]``; backward,
    ``stock[t-1] = stock[t] - retention * completions[t]``. A retention of 1 means every completion adds one
    dwelling and nothing is lost. The result covers the years of ``completions``; the anchor year holds
    ``anchor_stock`` exactly.
    """
    years = sorted(completions.index)
    flow = completions.astype(float) * retention
    stock = pd.Series(float("nan"), index=years)
    stock.loc[anchor_year] = anchor_stock
    for year in years:
        if year > anchor_year:
            stock.loc[year] = stock.loc[year - 1] + flow.loc[year]
    for year in reversed(years):
        if year < anchor_year:
            stock.loc[year] = stock.loc[year + 1] - flow.loc[year + 1]
    return stock


def stock_path(completions: pd.Series, anchors: dict[int, float], retention: float) -> pd.DataFrame:
    """The rolled stock and its yearly growth (%), with the retention applied and the census years marked.

    ``anchors`` maps a census year to its count; the path is anchored on the later one, and the earlier one is
    returned as ``census_n`` for comparison (it is exactly met only at a retention that closes the gap).
    """
    anchor = max(anchors)
    stock = roll_stock(completions, anchor, anchors[anchor], retention)
    out = pd.DataFrame({"completed_n": completions, "stock_n": stock})
    out["growth_pct"] = 100 * out["stock_n"].pct_change()
    out["census_n"] = pd.Series(anchors)
    return out
