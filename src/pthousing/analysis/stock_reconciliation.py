"""Dwelling stock: how much of what was completed shows up in the census count, and the stock between censuses (RQ2.4).

The census counts conventional dwellings only in 2001, 2011 and 2021 (``ine_census_stock``); completions of new family
dwellings are annual. Between two censuses the net change in the count is set against the dwellings completed in the
years in between. The difference is what completions do not explain: demolitions, merged or split dwellings,
conversions to and from other uses, dwellings added by works on existing buildings (not counted as completions here)
and differences in what each census counts. It is an accounting gap, not an estimate of any one of those, and it is not
constant: the count rose by 1.25 dwellings per completion in 2002-2011 and 0.89 in 2012-2021. Rolling the stock along the
completions with each decade's own retention gives a yearly path that meets every census; before the first and after
the last, the retention of the nearest decade is an extrapolation and a band is drawn. Functions take tables; nothing
here reads files.
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
    retention: float | pd.Series,
) -> pd.Series:
    """Yearly dwelling stock: the anchor count, moved along the completions at a retention.

    ``completions`` is indexed by year; ``retention`` is one number or a series by year (the retention that applies to
    the completions of that year). Forward, ``stock[t] = stock[t-1] + retention[t] * completions[t]``; backward,
    ``stock[t-1] = stock[t] - retention[t] * completions[t]``. A retention of 1 means every completion adds one dwelling
    and nothing is lost. The result covers the years of ``completions``; the anchor year holds ``anchor_stock``
    exactly.
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


def interval_retentions(completions: pd.Series, anchors: dict[int, float]) -> pd.Series:
    """Net addition over completions between each pair of consecutive census years, indexed by the later year.

    Completions are those of the years after the earlier census year up to and including the later one.
    """
    years = sorted(anchors)
    out = {}
    for a, b in zip(years[:-1], years[1:], strict=True):
        out[b] = (anchors[b] - anchors[a]) / completions.loc[a + 1 : b].sum()
    return pd.Series(out)


def stock_path(
    completions: pd.Series,
    anchors: dict[int, float],
    outside: tuple[float, float] | None = None,
) -> pd.DataFrame:
    """The stock rolled along completions, meeting every census, with its yearly growth (%).

    ``anchors`` maps a census year to its count. Inside each interval between censuses the retention is the one observed
    there (``interval_retentions``), so the path equals every census count. Before the first census the retention of the
    first interval applies and after the last that of the last interval, unless ``outside`` = (before, after) gives
    other values (an extrapolation, so the caller draws a band). Columns: ``completed_n``, ``retention`` (the one used
    that year), ``stock_n``, ``growth_pct`` and ``census_n``.
    """
    cens = sorted(anchors)
    observed = interval_retentions(completions, anchors)
    before, after = outside or (observed.iloc[0], observed.iloc[-1])
    per_year = {}
    for year in completions.index:
        if year <= cens[0]:
            per_year[year] = before
        elif year > cens[-1]:
            per_year[year] = after
        else:
            per_year[year] = observed[min(c for c in observed.index if c >= year)]
    retention = pd.Series(per_year)
    stock = roll_stock(completions, cens[-1], anchors[cens[-1]], retention)
    out = pd.DataFrame({"completed_n": completions, "retention": retention, "stock_n": stock})
    out["growth_pct"] = 100 * out["stock_n"].pct_change()
    out["census_n"] = pd.Series(anchors)
    return out
