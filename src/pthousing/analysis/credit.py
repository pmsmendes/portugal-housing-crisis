"""Mortgage credit, household debt and the house-price cycle (RQ9.2, RQ9.3).

National quarterly series, 2007 Q4 to 2026 Q2: the housing-loan stock and household debt (Banco de Portugal,
domain 18) against the BIS real and nominal house price index. Real stocks are deflated with the price index's
own deflator (nominal over real), so prices and loans share one deflator. "Loans per unit of price" is the
housing-loan stock over the nominal price index: the credit tied to the same average house, if the housing stock
and the share bought with a loan were fixed (they are not; it is a gauge of how much of the price rise credit
financed, not a leverage ratio).

Association in time, as in ``macro``: two credit regimes in 18 years and overlapping four-quarter changes. Timing
tests reuse ``macro.rate_timing`` with the credit growth as the regressor. Nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.analysis import macro

#: Quarters over which changes are taken (a year, as in ``macro``).
CHANGE_QUARTERS = macro.CHANGE_QUARTERS
#: The year whose average of loans per unit of price is 100 (the BIS index base).
BASE_YEAR = 2010
#: Growth rate of the housing-loan flow (transactions-based, excludes write-offs and sales of loans).
GROWTH_COLUMN = "housing_loans_growth_pct"


def quarterly_frame(bis: pd.DataFrame, debt: pd.DataFrame) -> pd.DataFrame:
    """Quarterly prices (BIS, 2010 = 100), debt stocks and ratios, real housing-loan stock, loans per unit of price (2010 = 100).

    ``bis`` is the ``bis_spp`` interim table, ``debt`` the ``bp_household_debt`` table. Only quarters with both
    are kept. ``deflator_b2010`` is the nominal over the real price index (CPI, 2010 = 1).
    """
    prices = bis.set_index("period_start")[["hpi_real_b2010", "hpi_nominal_b2010"]]
    debt = debt.drop(columns=["date", "year", "quarter"]).set_index("period_start")
    frame = prices.join(debt, how="inner")
    frame["deflator_b2010"] = frame["hpi_nominal_b2010"] / frame["hpi_real_b2010"]
    frame["housing_loans_real_eur_m"] = frame["housing_loans_stock_eur_m"] / frame["deflator_b2010"]
    base = frame.index.year == BASE_YEAR
    real = frame["housing_loans_real_eur_m"]
    frame["housing_loans_real_b2010"] = 100 * real / real[base].mean()
    ratio = frame["housing_loans_stock_eur_m"] / frame["hpi_nominal_b2010"]
    frame["loans_per_price_b2010"] = 100 * ratio / ratio[base].mean()
    return frame


def add_changes(frame: pd.DataFrame, n: int = CHANGE_QUARTERS) -> pd.DataFrame:
    """Add n-quarter changes in log points: real price, real and nominal loan stock; and the debt ratios in pp."""
    out = frame.copy()
    out["growth_real_pct"] = 100 * np.log(out["hpi_real_b2010"]).diff(n)
    out["loans_real_growth_pct"] = 100 * np.log(out["housing_loans_real_eur_m"]).diff(n)
    out["loans_nominal_growth_pct"] = 100 * np.log(out["housing_loans_stock_eur_m"]).diff(n)
    out["debt_income_change_pp"] = out["household_debt_income_pct"].diff(n)
    return out


def _pct(first: pd.Series, last: pd.Series, col: str) -> float:
    return 100 * (last[col] / first[col] - 1)


def episodes(frame: pd.DataFrame, windows: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Prices, credit and debt ratios between the first and last quarter of each window (labels like ``"2013Q4"``).

    Changes are last over first quarter in per cent for prices and stocks, in percentage points for the ratios.
    """
    rows = {}
    for label, (start, end) in windows.items():
        first = frame.loc[pd.Period(start, "Q").to_timestamp()]
        last = frame.loc[pd.Period(end, "Q").to_timestamp()]

        rows[label] = {
            "start": start,
            "end": end,
            "real_price_change_pct": _pct(first, last, "hpi_real_b2010"),
            "nominal_price_change_pct": _pct(first, last, "hpi_nominal_b2010"),
            "loans_real_change_pct": _pct(first, last, "housing_loans_real_eur_m"),
            "loans_nominal_change_pct": _pct(first, last, "housing_loans_stock_eur_m"),
            "loans_per_price_change_pct": _pct(first, last, "loans_per_price_b2010"),
            "loans_gdp_change_pp": last["housing_loans_gdp_pct"] - first["housing_loans_gdp_pct"],
            "debt_income_start_pct": first["household_debt_income_pct"],
            "debt_income_end_pct": last["household_debt_income_pct"],
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def credit_timing(
    changes: pd.DataFrame,
    x_col: str = GROWTH_COLUMN,
    lag: int = CHANGE_QUARTERS,
    own_lag: bool = False,
    lead: bool = False,
    sample: tuple[str, str] | None = None,
) -> dict:
    """A year's real price growth on credit growth ``lag`` quarters earlier (``lag`` 0: the same year).

    Wraps ``macro.rate_timing`` with the credit growth as the regressor: with ``lag`` 4 the two years do not
    overlap. ``lead`` adds next year's credit growth as a placebo, ``own_lag`` last year's price growth. The
    coefficient is log points of price per percentage point of credit growth.
    """
    return macro.rate_timing(
        changes,
        y="growth_real_pct",
        rate_lag=lag,
        own_lag=own_lag,
        lead=lead,
        sample=sample,
        x_col=x_col,
    )
