"""Prices by kind of home and by kind of measure (RQ1.2, RQ1.8).

Two splits the data allow: new against existing homes (transaction prices per m2, 2019 onward) and flats against
villas (bank appraisals per m2, 2011 onward); and appraisal against transaction prices for the same municipality
(2016 onward), the only gap between two price measures that we hold (advertised prices are not available).
Property types by number of rooms (T0 to T4+) are not published for prices.

Appraisals are annual and sparse (small municipalities are suppressed), so every trend uses municipalities observed
in every year it compares ("balanced"); the unbalanced medians are shown where the composition matters for the
reading. Functions take the municipality-year panel (see ``viz.dashboard.load_panel``) or the interim annual
appraisal table; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import MUNI_KEY, YEAR_KEY


def _balanced(panel: pd.DataFrame, columns: list[str], years: list[int]) -> pd.DataFrame:
    """Municipality x (column, year) values for municipalities with every column in every year."""
    d = panel[panel[YEAR_KEY].isin(years)]
    return d.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=columns).dropna()


def new_vs_existing(panel: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Premium of new over existing homes and real price indexes, by year (balanced municipalities).

    Premium is new over existing price per m2, minus one, in %. The indexes are the median over municipalities of
    each municipality's real price relative to ``start`` (start = 100).
    """
    years = list(range(start, end + 1))
    new_col, old_col = "price_new_sqm_eur_real", "price_existing_sqm_eur_real"
    w = _balanced(panel, [new_col, old_col], years)
    premium = w[new_col] / w[old_col] - 1
    out = pd.DataFrame(
        {
            "municipalities_n": len(w),
            "median_premium_pct": 100 * premium.median(),
            "share_new_dearer_pct": 100 * (premium > 0).mean(),
            "new_real_index": 100 * (w[new_col].div(w[new_col][start], axis=0)).median(),
            "existing_real_index": 100 * (w[old_col].div(w[old_col][start], axis=0)).median(),
        }
    )
    out.index.name = YEAR_KEY
    return out


def premium_by_class(panel: pd.DataFrame, year: int, by: str) -> pd.DataFrame:
    """Median new-build premium (%) in ``year`` by a typology column, municipalities with both prices."""
    d = panel[panel[YEAR_KEY] == year].dropna(
        subset=["price_new_sqm_eur", "price_existing_sqm_eur", by]
    )
    prem = 100 * (d["price_new_sqm_eur"] / d["price_existing_sqm_eur"] - 1)
    out = prem.groupby(d[by]).agg(["count", "median"])
    out.columns = ["municipalities_n", "median_premium_pct"]
    return out


def flats_vs_villas(annual: pd.DataFrame, deflator: pd.Series) -> pd.DataFrame:
    """Appraised value of flats against villas per m2, by year.

    ``annual`` is ``ine_bank_valuation_annual``, ``deflator`` ``harmonize.annual_deflator``. Per year, over the
    municipalities that have both: the median flats-to-villas ratio and the number of municipalities. Real
    medians of the two types are over the same municipalities (the composition changes by year).
    """
    wide = annual.pivot_table(
        index=[MUNI_KEY, YEAR_KEY], columns="type", values="valuation_sqm_eur"
    )
    wide = wide[["flats", "villas"]].dropna()
    real = wide.mul(wide.index.get_level_values(YEAR_KEY).map(deflator), axis=0)
    g = real.groupby(level=YEAR_KEY)
    return pd.DataFrame(
        {
            "municipalities_n": g.size(),
            "flats_real_sqm_eur": g["flats"].median(),
            "villas_real_sqm_eur": g["villas"].median(),
            "flats_to_villas": (wide["flats"] / wide["villas"]).groupby(level=YEAR_KEY).median(),
        }
    )


def valuation_change(
    annual: pd.DataFrame, deflator: pd.Series, start: int, end: int
) -> pd.DataFrame:
    """Median real change (%) of appraised flats and villas between two years, over municipalities with both types in both."""
    wide = annual.pivot_table(
        index=MUNI_KEY, columns=["type", YEAR_KEY], values="valuation_sqm_eur"
    )
    w = wide[[(t, y) for t in ("flats", "villas") for y in (start, end)]].dropna()
    rows = {}
    for t in ("flats", "villas"):
        change = (w[(t, end)] * deflator[end]) / (w[(t, start)] * deflator[start]) - 1
        rows[t] = {"municipalities_n": len(w), "median_real_change_pct": 100 * change.median()}
    return pd.DataFrame(rows).T


def appraisal_vs_transaction(panel: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Appraised over transaction price per m2 by year: balanced municipalities, with the unbalanced median beside it.

    The appraisal is the year's value, the transaction price the median of the last twelve months to the fourth
    quarter, so the ratio carries a timing difference as well as a difference of measure. ``balanced_*`` columns use
    municipalities with both prices in every year from ``start`` to ``end``.
    """
    years = list(range(start, end + 1))
    cols = ["valuation_sqm_eur", "price_sqm_eur"]
    w = _balanced(panel, cols, years)
    ratio = w["valuation_sqm_eur"] / w["price_sqm_eur"]
    every = panel[panel[YEAR_KEY].isin(years)].dropna(subset=cols)
    every = (every["valuation_sqm_eur"] / every["price_sqm_eur"]).groupby(every[YEAR_KEY])
    out = pd.DataFrame(
        {
            "balanced_n": len(w),
            "balanced_median": ratio.median(),
            "balanced_q25": ratio.quantile(0.25),
            "balanced_q75": ratio.quantile(0.75),
            "all_n": every.size(),
            "all_median": every.median(),
        }
    )
    out.index.name = YEAR_KEY
    return out


def growth_leadlag(panel: pd.DataFrame, start: int, end: int, lags: range) -> pd.DataFrame:
    """Correlation of a year's appraisal growth with transaction-price growth ``lag`` years later (pooled municipalities).

    Growth is the log change of the balanced municipalities; a lag of 1 asks whether appraisals lead transaction
    prices by a year, a lag of -1 whether they follow them.
    """
    years = list(range(start, end + 1))
    w = _balanced(panel, ["valuation_sqm_eur", "price_sqm_eur"], years)
    appraisal = np.log(w["valuation_sqm_eur"]).diff(axis=1).iloc[:, 1:]
    price = np.log(w["price_sqm_eur"]).diff(axis=1).iloc[:, 1:]
    rows = []
    for lag in lags:
        a, b = [], []
        for year in appraisal.columns:
            if year + lag in price.columns:
                a.append(appraisal[year].to_numpy())
                b.append(price[year + lag].to_numpy())
        corr = np.corrcoef(np.concatenate(a), np.concatenate(b))[0, 1]
        rows.append({"lag_years": lag, "corr": corr})
    return pd.DataFrame(rows)
