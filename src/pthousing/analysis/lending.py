"""Lending conditions: what a longer maturity or a higher loan-to-value buys, and the figures of the macroprudential reports (RQ9.3).

The Banco de Portugal publishes the loan-to-value (LTV), debt-service-to-income (DSTI) and maturity of new housing loans only in
yearly monitoring reports (PDF), transcribed in ``data/external/lending_standards.csv``. Two accounting exercises, no behaviour:

* **Maturity.** At a fixed payment, the loan a household can carry is proportional to the annuity factor, so stretching the term
  raises it by the ratio of the factors at the rate of the day.
* **Deposit.** The cash needed on the day of purchase (the part of the price not lent plus buying costs) in years of income, by
  loan-to-value.

Functions take tables; ``read`` is the only reader.
"""

import pandas as pd

from pthousing.config import EXTERNAL
from pthousing.features.affordability import mortgage_burden_pct, mortgage_payment_monthly
from pthousing.features.rent_vs_buy import upfront_cash_years

PATH = EXTERNAL / "lending_standards.csv"


def read() -> pd.DataFrame:
    """Transcribed figures of the Banco de Portugal reports: ``indicator``, ``period`` (text), ``value``, ``unit``, ``source``, ``note``."""
    return pd.read_csv(PATH, dtype={"period": str})


def value(table: pd.DataFrame, indicator: str, period: str) -> float:
    """One figure of ``read()`` by indicator and period (NaN if the report gives none)."""
    row = table[(table["indicator"] == indicator) & (table["period"] == period)]
    if row.empty:
        raise KeyError(f"{indicator} {period} is not in the table")
    return float(row["value"].iloc[0])


def capacity_gain_pct(rate_pct: float, from_years: float, to_years: float) -> float:
    """Rise (%) of the loan a fixed monthly payment carries when the term goes from ``from_years`` to ``to_years`` at ``rate_pct``."""
    shorter = float(mortgage_payment_monthly(100_000, rate_pct, from_years))
    longer = float(mortgage_payment_monthly(100_000, rate_pct, to_years))
    return 100 * (shorter / longer - 1)


def rate_effect_pct(rate_from_pct: float, rate_to_pct: float, term_years: float) -> float:
    """Cut (%) of the loan a fixed monthly payment carries when the rate goes from ``rate_from_pct`` to ``rate_to_pct``."""
    before = float(mortgage_payment_monthly(100_000, rate_from_pct, term_years))
    after = float(mortgage_payment_monthly(100_000, rate_to_pct, term_years))
    return 100 * (1 - before / after)


def maturity_table(rates: pd.Series, terms: dict[str, float], base: str) -> pd.DataFrame:
    """Payment per 100,000 EUR and the capacity gain over the ``base`` term, for each year of ``rates`` and each term.

    ``rates`` is a mortgage rate (%) indexed by year; ``terms`` maps a label to a term in years. The gain of the base term is zero.
    """
    rows = []
    for year, rate in rates.items():
        for label, years in terms.items():
            rows.append(
                {
                    "year": year,
                    "rate_pct": rate,
                    "term": label,
                    "term_years": years,
                    "payment_per_100k_eur": float(mortgage_payment_monthly(100_000, rate, years)),
                    "capacity_gain_pct": capacity_gain_pct(rate, terms[base], years),
                }
            )
    return pd.DataFrame(rows)


def deposit_years(
    pti_years: pd.Series, ltvs: dict[str, float], buying_costs_pct: float
) -> pd.DataFrame:
    """Cash needed on the day of purchase in years of income, by municipality (rows) and loan-to-value (columns)."""
    return pd.DataFrame(
        {label: upfront_cash_years(pti_years, ltv, buying_costs_pct) for label, ltv in ltvs.items()}
    )


def burden_table(
    year_panel: pd.DataFrame,
    rate_pct: float,
    ltvs: dict[str, float],
    terms: dict[str, float],
    limit_pct: float = 50.0,
) -> pd.DataFrame:
    """Median payment burden (% of median gross income) and the share of municipalities above ``limit_pct``, by loan-to-value and term.

    ``year_panel`` has ``price_sqm_eur``, ``dwelling_area_sqm`` and ``income_median_eur`` by municipality for one year (the panel's
    own affordability indicators).
    The limit is the DSTI cap of the Recommendation, which is measured on net income and with a rate shock, so this is a rough
    proxy, not the test banks apply.
    """
    rows = []
    for ltv_label, ltv in ltvs.items():
        for term_label, years in terms.items():
            burden = mortgage_burden_pct(
                year_panel["price_sqm_eur"],
                year_panel["dwelling_area_sqm"],
                year_panel["income_median_eur"],
                rate_pct,
                ltv,
                years,
            ).dropna()
            rows.append(
                {
                    "ltv": ltv_label,
                    "term": term_label,
                    "median_burden_pct": float(burden.median()),
                    "share_above_limit_pct": 100 * float((burden > limit_pct).mean()),
                    "municipalities_n": len(burden),
                }
            )
    return pd.DataFrame(rows)


def cash_summary(deposit: pd.DataFrame) -> pd.DataFrame:
    """Median cash needed (years of income) and the share of municipalities needing more than a year, by loan-to-value (rows)."""
    return pd.DataFrame(
        {
            "median_years": deposit.median(),
            "share_above_one_pct": 100 * (deposit > 1).mean(),
            "municipalities_n": deposit.notna().sum(),
        }
    )
