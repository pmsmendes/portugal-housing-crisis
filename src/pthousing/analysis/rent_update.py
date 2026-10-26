"""Rents of sitting tenants against rents of new leases: the legal update coefficient and the gap it leaves (RQ6.1, RQ6.3).

An existing lease can be raised each year only by the coefficient INE publishes under the NRAU (CPI without housing, 12 months to
August), and in 2023 only by the extraordinary ceiling of 2%. A new lease is set at the market. Starting from the median rent of
the new leases of a base year, the highest rent a sitting tenant could pay later is that rent times the product of the coefficients;
the gap to the median of new leases is what a newcomer pays above a tenant who signed at the median. Accounting from legal rules and
observed rents, no behaviour. Functions take tables; nothing here reads files.
"""

import pandas as pd

from pthousing.config import EXTERNAL, MUNI_KEY

PATH = EXTERNAL / "rent_update_coefficients.csv"


def read() -> pd.DataFrame:
    """Legal and formula coefficients by year (``legal_coefficient``, ``formula_coefficient``)."""
    return pd.read_csv(PATH).set_index("year")


def cumulative(coefficients: pd.Series, first_year: int, last_year: int) -> float:
    """Product of the yearly coefficients from ``first_year`` to ``last_year`` inclusive (1 if the range is empty).

    A coefficient below 1 (2021: 0.9997) is taken as 1: the update is optional and a rent cannot fall by it.
    """
    return float(coefficients.loc[first_year:last_year].clip(lower=1.0).prod())


def allowed_rise_pct(table: pd.DataFrame, base_year: int, year: int, column: str) -> float:
    """Rise (%) a lease signed in ``base_year`` can have taken by ``year``: updates from the year after the base to ``year``."""
    return 100 * (cumulative(table[column], base_year + 1, year) - 1)


def national_path(
    table: pd.DataFrame, base_year: int, years: range, new_lease_rent: pd.Series, cpi: pd.Series
) -> pd.DataFrame:
    """Yearly index (``base_year`` = 100) of the legal rent, the rent without the 2023 ceiling, new leases and prices.

    ``new_lease_rent`` is the national median rent of new leases by year (any unit); ``cpi`` a price index by year.
    """
    rows = {}
    for y in years:
        rows[y] = {
            "legal_rent_index": 100 * cumulative(table["legal_coefficient"], base_year + 1, y),
            "formula_rent_index": 100 * cumulative(table["formula_coefficient"], base_year + 1, y),
            "new_lease_rent_index": 100 * new_lease_rent[y] / new_lease_rent[base_year],
            "cpi_index": 100 * cpi[y] / cpi[base_year],
        }
    out = pd.DataFrame.from_dict(rows, orient="index").rename_axis("year")
    out["new_over_legal_pct"] = 100 * (out["new_lease_rent_index"] / out["legal_rent_index"] - 1)
    return out


def balanced_median(rent_sqm: pd.DataFrame, first_year: int, last_year: int) -> pd.Series:
    """Median rent per m2 of new leases by year, over the municipalities with a rent in both ``first_year`` and ``last_year``.

    A fixed set of places, so a year's median does not move because more or fewer municipalities publish a rent.
    """
    have = rent_sqm.dropna(subset=["rent_sqm_eur"])
    both = set(have.loc[have["year"] == first_year, MUNI_KEY]) & set(
        have.loc[have["year"] == last_year, MUNI_KEY]
    )
    kept = have[have[MUNI_KEY].isin(both) & have["year"].between(first_year, last_year)]
    return kept.groupby("year")["rent_sqm_eur"].median()


def market_gap(
    rent_sqm: pd.DataFrame, base_year: int, year: int, legal_cumulative: float
) -> pd.DataFrame:
    """Per municipality, the new-lease rent of ``year`` against the base-year median rent updated by the legal rise.

    ``rent_sqm`` has ``muni_code``, ``year`` and ``rent_sqm_eur``. ``gap_pct`` is what a new tenant pays above a sitting tenant who
    signed at the base-year median and had every update allowed; municipalities without a rent in both years are left out.
    """
    a = rent_sqm[rent_sqm["year"] == base_year].set_index(MUNI_KEY)["rent_sqm_eur"]
    b = rent_sqm[rent_sqm["year"] == year].set_index(MUNI_KEY)["rent_sqm_eur"]
    out = pd.DataFrame({"rent_base_eur": a, "rent_new_eur": b}).dropna()
    out["rent_sitting_eur"] = out["rent_base_eur"] * legal_cumulative
    out["market_rise_pct"] = 100 * (out["rent_new_eur"] / out["rent_base_eur"] - 1)
    out["gap_pct"] = 100 * (out["rent_new_eur"] / out["rent_sitting_eur"] - 1)
    return out


def turnover(new_leases_n: pd.Series, rented_dwellings_n: pd.Series) -> pd.Series:
    """New leases of a year per 100 rented dwellings: a rough upper bound of the share of the let stock repriced in a year.

    Renewals, other regimes and any change of the stock between the years are not told apart; use the census year of the stock.
    """
    both = pd.concat([new_leases_n, rented_dwellings_n], axis=1, keys=["new", "rented"]).dropna()
    return (100 * both["new"] / both["rented"]).rename("new_leases_per_100_rented")


def ceiling_saving(
    rent_sqm_eur: pd.Series, area_sqm: float | pd.Series, legal: float, formula: float
) -> pd.DataFrame:
    """Monthly rent (EUR) a tenant at ``rent_sqm_eur`` saves in the year of a ceiling, municipality by municipality.

    ``legal`` and ``formula`` are the coefficients of that year; the rent before the update is ``rent_sqm_eur * area_sqm``
    (``area_sqm`` a number or a series by municipality).
    """
    before = (rent_sqm_eur * area_sqm).rename("rent_before_eur")
    out = pd.DataFrame({"rent_before_eur": before})
    out["with_ceiling_eur"] = before * legal
    out["without_ceiling_eur"] = before * formula
    out["saving_eur_month"] = out["without_ceiling_eur"] - out["with_ceiling_eur"]
    return out


def gap_by_group(gap: pd.DataFrame, group: pd.Series) -> pd.DataFrame:
    """Medians of the rise and the gap, share of homes let and median turnover by group of municipalities.

    ``gap`` is ``market_gap`` output joined with ``rented_n``, ``dwellings_n`` and ``turnover``; ``group`` labels each
    municipality (NaN is left out).
    """
    sub = gap[group.reindex(gap.index).notna()].groupby(group.dropna(), observed=True)
    return pd.DataFrame(
        {
            "municipalities_n": sub.size(),
            "median_market_rise_pct": sub["market_rise_pct"].median(),
            "median_gap_pct": sub["gap_pct"].median(),
            "rented_share_pct": 100 * sub["rented_n"].sum() / sub["dwellings_n"].sum(),
            "median_new_leases_per_100_rented": sub["turnover"].median(),
        }
    )


def rank_correlations(frame: pd.DataFrame, column: str, others: list[str]) -> pd.Series:
    """Spearman rank correlation of ``column`` with each of ``others`` (pairwise complete)."""
    return frame[[column, *others]].corr(method="spearman")[column].drop(column)


def saving_summary(saving: pd.DataFrame, rented_dwellings_n: float) -> pd.DataFrame:
    """Median lease before the update, its monthly saving and the stock-wide yearly saving if every let home had it (EUR m).

    The stock figure is an upper bound: it assumes each let dwelling was updated at the ceiling.
    """
    med = saving.median()
    return pd.DataFrame(
        {
            "median_rent_before_eur": [med["rent_before_eur"]],
            "saving_eur_month": [med["saving_eur_month"]],
            "saving_pct_of_rent": [100 * med["saving_eur_month"] / med["rent_before_eur"]],
            "rented_dwellings_n": [rented_dwellings_n],
            "upper_bound_eur_m_year": [12 * med["saving_eur_month"] * rented_dwellings_n / 1e6],
        }
    )
