"""Vacant dwellings against housing pressure: could they realistically ease the shortage? (RQ2.5)

The census counts vacant conventional dwellings per municipality (2011, 2021) but not their condition, ownership,
price or whether they are for sale or rent, so "realistically" is bounded by two things the data do show:

* only vacancy above a frictional level counts (``config.FRICTIONAL_VACANCY_PCT``: homes between tenants, being sold,
  inherited or repaired are vacant in any market), called *excess* vacancy;
* a vacant home cannot be moved: it helps only where households are short. The 2021-2023 shortfall of a municipality is
  its implied new households minus its completions (``supply.balance``; a proxy, see there), floored at zero, and the
  part of it that excess vacancy there could cover is the smaller of the two, summed over municipalities
  (``local_coverage``).

Results are accounting ratios on census years; nothing here says that a vacant home is habitable or for sale.
Functions take tables; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import FRICTIONAL_VACANCY_PCT, MUNI_KEY

CENSUS = (2011, 2021)


def table(stock: pd.DataFrame) -> pd.DataFrame:
    """Dwellings and vacant dwellings per municipality in both census years, with the vacancy rate (%) and its change (pp)."""
    wide = stock.pivot(index=MUNI_KEY, columns="census_year")
    out = pd.DataFrame(index=wide.index)
    for year in CENSUS:
        out[f"dwellings_{year}_n"] = wide[("dwellings_n", year)]
        out[f"vacant_{year}_n"] = wide[("dwellings_vacant_n", year)]
        out[f"vacancy_{year}_pct"] = 100 * out[f"vacant_{year}_n"] / out[f"dwellings_{year}_n"]
    out["vacancy_change_pp"] = out["vacancy_2021_pct"] - out["vacancy_2011_pct"]
    return out


def excess(
    vacant: pd.Series, dwellings: pd.Series, frictional_pct: float = FRICTIONAL_VACANCY_PCT
) -> pd.Series:
    """Vacant dwellings above ``frictional_pct`` of the stock (never negative)."""
    return (vacant - dwellings * frictional_pct / 100).clip(lower=0)


def shortfall(balance: pd.DataFrame) -> pd.Series:
    """Implied new households of 2021-2023 not matched by completions, per municipality, floored at zero.

    Municipalities where completions exceed the implied households have no shortfall: their surplus cannot be
    moved to another municipality.
    """
    gap = balance["implied_new_households_2021_2023_n"] - balance["completions_2022_2023_n"]
    return gap.clip(lower=0).rename("shortfall_2021_2023_n")


def local_coverage(
    excess_n: pd.Series, shortfall_n: pd.Series, usable_share: float = 1.0
) -> pd.Series:
    """Per municipality, the part of the shortfall that its own excess vacancy could house.

    ``usable_share`` scales the excess to the part that is habitable, for sale or let and worth repairing;
    no estimate of it exists in the data, so it is varied, not assumed.
    """
    return np.minimum(excess_n * usable_share, shortfall_n).rename("covered_n")


def by_group(
    tab: pd.DataFrame,
    shortfall_n: pd.Series,
    by: pd.Series,
    frictional_pct: float = FRICTIONAL_VACANCY_PCT,
) -> pd.DataFrame:
    """Vacancy, excess vacancy, shortfall and local coverage per group of municipalities.

    Counts are summed, then rates recomputed from the sums. ``coverage_pct`` is the covered part of the shortfall;
    ``excess_to_shortfall`` the unmatched ratio (excess where it is not needed is counted in it).
    """
    data = tab.assign(
        excess_n=excess(tab["vacant_2021_n"], tab["dwellings_2021_n"], frictional_pct),
        shortfall_n=shortfall_n,
    )
    data["covered_n"] = local_coverage(data["excess_n"], data["shortfall_n"])
    cols = [
        "dwellings_2011_n",
        "dwellings_2021_n",
        "vacant_2011_n",
        "vacant_2021_n",
        "excess_n",
        "shortfall_n",
        "covered_n",
    ]
    out = data[cols].groupby(by).sum()
    out["municipalities_n"] = data.groupby(by).size()
    out["vacancy_2011_pct"] = 100 * out["vacant_2011_n"] / out["dwellings_2011_n"]
    out["vacancy_2021_pct"] = 100 * out["vacant_2021_n"] / out["dwellings_2021_n"]
    out["coverage_pct"] = 100 * out["covered_n"] / out["shortfall_n"]
    out["excess_to_shortfall"] = out["excess_n"] / out["shortfall_n"]
    return out


def sensitivity(
    tab: pd.DataFrame,
    shortfall_n: pd.Series,
    frictional_pcts: tuple[float, ...] = (3.0, 5.0, 8.0),
    usable_shares: tuple[float, ...] = (1.0, 0.5, 0.25),
) -> pd.DataFrame:
    """National excess vacancy and the share of the shortfall covered locally, by frictional level and usable share."""
    rows = []
    for pct in frictional_pcts:
        exc = excess(tab["vacant_2021_n"], tab["dwellings_2021_n"], pct)
        for share in usable_shares:
            covered = local_coverage(exc, shortfall_n, share).sum()
            rows.append(
                {
                    "frictional_pct": pct,
                    "usable_share": share,
                    "excess_n": exc.sum(),
                    "usable_excess_n": exc.sum() * share,
                    "shortfall_n": shortfall_n.sum(),
                    "covered_n": covered,
                    "coverage_pct": 100 * covered / shortfall_n.sum(),
                }
            )
    return pd.DataFrame(rows)


def usable_share_for(
    target_pct: float,
    excess_n: pd.Series,
    shortfall_n: pd.Series,
    tol: float = 1e-4,
) -> float:
    """The usable share of excess vacancy at which local coverage of the shortfall reaches ``target_pct``.

    Coverage rises with the usable share, so it is found by bisection; NaN if even a share of 1 falls short.
    """
    total = shortfall_n.sum()
    if 100 * local_coverage(excess_n, shortfall_n, 1.0).sum() / total < target_pct:
        return float("nan")
    low, high = 0.0, 1.0
    while high - low > tol:
        mid = (low + high) / 2
        if 100 * local_coverage(excess_n, shortfall_n, mid).sum() / total < target_pct:
            low = mid
        else:
            high = mid
    return high


def largest_shortfalls(
    tab: pd.DataFrame, shortfall_n: pd.Series, names: pd.Series, n: int = 10
) -> pd.DataFrame:
    """The ``n`` municipalities with the largest shortfall, with their excess vacancy and what it covers."""
    data = tab.assign(
        excess_n=excess(tab["vacant_2021_n"], tab["dwellings_2021_n"]), shortfall_n=shortfall_n
    )
    data["covered_n"] = local_coverage(data["excess_n"], data["shortfall_n"])
    data["coverage_pct"] = 100 * data["covered_n"] / data["shortfall_n"]
    data["name"] = names.reindex(data.index)
    cols = ["name", "vacancy_2021_pct", "vacant_2021_n", "excess_n", "shortfall_n", "coverage_pct"]
    return data.nlargest(n, "shortfall_n")[cols]
