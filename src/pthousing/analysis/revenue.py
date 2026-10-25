"""IMI and IMT revenue against house prices and the IMI rate (RQ7.1).

National annual series only, 1995 to 2025: general-government revenue from taxes on land and buildings (IMI) and
from taxes on capital transactions (IMT with stamp duty), both from the national accounts, so on an accrual basis.
No municipal revenue series exists in machine-readable form (docs/data_quality.md).

IMI revenue is the product of a rate chosen by each council and an assessed base that follows the tax value of
homes, not their market price; IMT revenue is a rate schedule applied to the value of homes sold, so it moves with
prices and with the number of sales. Neither is split here into its parts beyond what the data allow: the rate is
observed (2012 onward, weighted by the stock of dwellings), the base is what is left, and the number of sales is not
observed in the national series. Functions take interim tables or the frame from ``annual_frame``; nothing here
reads files.
"""

import numpy as np
import pandas as pd

from pthousing.data.harmonize import annual_deflator

BASE = 2015  # index base of the annual frame, as in ``macro.annual_frame``


def weighted_imi_rate(panel: pd.DataFrame, weight: str = "dwellings_2021_n") -> pd.Series:
    """Average municipal urban IMI rate by year, weighted by a fixed stock of dwellings.

    Municipalities without a single rate in a year (parish-specific rates, or no value) are left out of that
    year and the weights renormalised; a fixed weight keeps the change in the average to the change in rates.
    """
    d = panel.dropna(subset=["imi_urban_pct", weight])
    return (
        d.groupby("year")
        .apply(lambda g: np.average(g["imi_urban_pct"], weights=g[weight]), include_groups=False)
        .rename("imi_rate_pct")
    )


def annual_frame(
    tax: pd.DataFrame,
    cpi: pd.DataFrame,
    long: pd.DataFrame,
    rate: pd.Series | None = None,
) -> pd.DataFrame:
    """Revenue in current and constant euros, as a share of GDP, and against the price level.

    ``tax`` is the ``eurostat_property_tax`` interim table, ``cpi`` the ``ine_cpi`` table (constant ``BASE_YEAR``
    euros), ``long`` the ``national_annual_long`` panel (house price indices, 2015 = 100) and ``rate`` the yearly
    average IMI rate from ``weighted_imi_rate``. Adds ``imi_real_b2015`` and ``imt_real_b2015`` (real revenue,
    2015 = 100) next to the real price index, and, with a rate, ``imi_base_b2015``: revenue over the rate, an index
    of the tax base the rate is applied to.
    """
    d = tax.set_index("year").rename(
        columns={"imi_revenue_eur_m": "imi_eur_m", "imt_revenue_eur_m": "imt_eur_m"}
    )
    deflator = annual_deflator(cpi)
    for name in ("imi", "imt"):
        d[f"{name}_real_eur_m"] = d[f"{name}_eur_m"] * deflator.reindex(d.index)
        d[f"{name}_gdp_pct"] = 100 * d[f"{name}_eur_m"] / d["gdp_eur_m"]
        real = d[f"{name}_real_eur_m"]
        d[f"{name}_real_b2015"] = 100 * real / real.loc[BASE]
    d = d.join(long.set_index("year")[["hpi_nominal_b2015", "hpi_real_b2015"]])
    if rate is not None:
        d["imi_rate_pct"] = rate
        base = d["imi_eur_m"] / d["imi_rate_pct"]
        d["imi_base_b2015"] = 100 * base / base.loc[BASE]
    return d


def changes(
    frame: pd.DataFrame, windows: dict[str, tuple[int, int]], columns: list[str]
) -> pd.DataFrame:
    """Percentage change of each column between the first and last year of each window; one row per window."""
    rows = {
        label: {c: 100 * (frame.loc[end, c] / frame.loc[start, c] - 1) for c in columns}
        for label, (start, end) in windows.items()
    }
    return pd.DataFrame(rows).T.rename_axis("window")


def decompose_imi(frame: pd.DataFrame, start: int, end: int) -> pd.Series:
    """Log-point change of IMI revenue between two years, split into the rate and the base (revenue over rate).

    ``frame`` needs the rate (``annual_frame`` with ``rate``). Also reports the nominal house price and the
    ``gap``: how far the tax base lags the price (base minus price; negative when prices rose faster).
    """
    d = frame.loc[[start, end]]
    log = np.log(d)
    change = log.loc[end] - log.loc[start]
    base = change["imi_eur_m"] - change["imi_rate_pct"]
    return 100 * pd.Series(
        {
            "revenue": change["imi_eur_m"],
            "rate": change["imi_rate_pct"],
            "base": base,
            "price": change["hpi_nominal_b2015"],
            "gap": base - change["hpi_nominal_b2015"],
        }
    )
