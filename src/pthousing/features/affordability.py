"""Affordability indicators: price-to-income, rent-to-income, mortgage burden, housing vs household growth.

Definitions are in docs/methodology.md. All functions are vectorised (scalars, Series or arrays) and take
nominal euros of the same year: ratios need no deflation. INE reports prices and rents per m2, so a dwelling
price or rent is the per-m2 value times a dwelling area (the municipality's census mean useful area, or a
fixed benchmark area for comparability).
"""

import numpy as np
import pandas as pd

from pthousing.config import MORTGAGE_LTV, MORTGAGE_TERM_YEARS


def dwelling_value(sqm_eur, area_sqm):
    """Euro value of a dwelling of ``area_sqm`` at a per-m2 price or rent."""
    return sqm_eur * area_sqm


def price_to_income(price_sqm_eur, area_sqm, income_eur):
    """PTI: years of annual household income needed to buy the dwelling (price / income)."""
    return dwelling_value(price_sqm_eur, area_sqm) / income_eur


def rent_to_income_pct(rent_sqm_eur, area_sqm, income_eur):
    """RTI: annual rent (12 months of the monthly per-m2 rent) as a percentage of annual income."""
    return 100 * dwelling_value(rent_sqm_eur, area_sqm) * 12 / income_eur


def mortgage_payment_monthly(loan_eur, annual_rate_pct, term_years=MORTGAGE_TERM_YEARS):
    """Monthly payment of a fixed-payment (annuity) loan; a zero rate gives loan / months."""
    n = term_years * 12
    r = np.asarray(annual_rate_pct, dtype=float) / 100 / 12
    loan = np.asarray(loan_eur, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        annuity = np.where(r == 0, loan / n, loan * r / (1 - (1 + r) ** -n))
    result = np.where(np.isnan(r) | np.isnan(loan), np.nan, annuity)
    return _like(result, loan_eur, annual_rate_pct)


def mortgage_burden_pct(
    price_sqm_eur,
    area_sqm,
    income_eur,
    annual_rate_pct,
    ltv=MORTGAGE_LTV,
    term_years=MORTGAGE_TERM_YEARS,
):
    """Mortgage burden: yearly payments on a loan of ``ltv`` x dwelling price, as a % of annual income."""
    loan = ltv * dwelling_value(price_sqm_eur, area_sqm)
    return 100 * 12 * mortgage_payment_monthly(loan, annual_rate_pct, term_years) / income_eur


def supply_gap_per_1000(dwellings_start, dwellings_end, households_start, households_end):
    """Housing vs household growth: (change in dwellings - change in households) per 1,000 households at start.

    Positive: the dwelling stock grew faster than the number of households.
    """
    return (
        1000
        * ((dwellings_end - dwellings_start) - (households_end - households_start))
        / households_start
    )


def _like(result, *templates):
    """Return a Series (with the index of the first Series template) when one was given, else the array."""
    for template in templates:
        if isinstance(template, pd.Series):
            return pd.Series(result, index=template.index)
    return result if np.ndim(result) else float(result)
