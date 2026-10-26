"""Construction costs against house prices and new building (RQ2.7).

INE's cost index of new housing (monthly, 2000 to 2026, materials and labour) is the one national series of what building
costs. It measures input costs, not what builders charge, the price of land or licensing time, so the question it answers
is narrow: did building get dearer in step with house prices, and did licensing and completions follow costs or prices?
The price-to-cost ratio is an index (2015 = 100) of everything in the price that is not the cost index: land, margin,
design, financing and the premium for location. It is not a margin in euros, because the level of the cost per m2 is not
in the data.

Everything is national and annual, about 25 years, so the regressions on yearly changes are a guide to size and sign, not
a test; the two big movements (the 2008 crisis and the recovery) dominate them. Functions take interim tables or the frame
from ``annual_frame``; nothing here reads files.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from pthousing.data.harmonize import annual_deflator

BASE = 2015  # index base of the annual frame, as in ``macro.annual_frame``
FACTORS = ("total", "materials", "labour")


def annual_costs(costs: pd.DataFrame) -> pd.DataFrame:
    """Yearly average of the monthly cost index (2021 = 100) by factor, complete years only.

    ``costs`` is the ``ine_construction_costs`` interim table. A year with fewer than 12 months (the current one) is left
    out, so a year is never compared on a different part of the seasonal pattern or of a rising trend.
    """
    wide = costs.pivot_table(index="year", columns="factor", values="construction_cost_b2021")
    months = costs[costs["factor"] == "total"].groupby("year").size()
    return wide.loc[months[months == 12].index, list(FACTORS)]


def annual_frame(
    costs: pd.DataFrame,
    cpi: pd.DataFrame,
    long: pd.DataFrame,
    flows: pd.DataFrame,
    macro: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Costs, prices, wages and new building by year, indices 2015 = 100.

    ``cpi`` is the ``ine_cpi`` table, ``long`` the ``national_annual_long`` panel (house price indices), ``flows``
    ``supply.national_flows`` (licensed and completed dwellings) and ``macro`` the ``eurostat_macro`` table. Columns:
    nominal cost indices (``cost_<factor>_b2015``), the real total (``cost_real_b2015``, deflated with the CPI like the
    real price index), ``price_to_cost_b2015`` (nominal price index over the total cost index), the price indices,
    compensation per employee (``wage_b2015``) and, with it, ``labour_cost_vs_wage_b2015`` (labour cost index over wages).
    """
    a = annual_costs(costs)
    d = pd.DataFrame(index=a.index)
    for f in FACTORS:
        d[f"cost_{f}_b2015"] = 100 * a[f] / a.loc[BASE, f]
    cpi_index = 1 / annual_deflator(cpi, BASE)  # CPI relative to its base-year value
    d["cost_real_b2015"] = d["cost_total_b2015"] / cpi_index.reindex(d.index)
    d = d.join(long.set_index("year")[["hpi_nominal_b2015", "hpi_real_b2015"]])
    ratio = d["hpi_nominal_b2015"] / d["cost_total_b2015"]
    d["price_to_cost_b2015"] = 100 * ratio / ratio.loc[BASE]
    if macro is not None:
        wage = macro.set_index("year")["compensation_per_employee_eur"].reindex(d.index)
        d["wage_b2015"] = 100 * wage / wage.loc[BASE]
        d["labour_cost_vs_wage_b2015"] = 100 * d["cost_labour_b2015"] / d["wage_b2015"]
    return d.join(flows[["licensed_n", "completed_n"]])


def changes(
    frame: pd.DataFrame, windows: dict[str, tuple[int, int]], columns: list[str]
) -> pd.DataFrame:
    """Percentage change of each column between the first and last year of each window; one row per window."""
    rows = {
        label: {c: 100 * (frame.loc[end, c] / frame.loc[start, c] - 1) for c in columns}
        for label, (start, end) in windows.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def mean_flows(frame: pd.DataFrame, windows: dict[str, tuple[int, int]]) -> pd.DataFrame:
    """Average licensed and completed dwellings per year over the years of each window (both ends included)."""
    rows = {
        label: frame.loc[start:end, ["licensed_n", "completed_n"]].mean()
        for label, (start, end) in windows.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def cost_shares(frame: pd.DataFrame, windows: dict[str, tuple[int, int]]) -> pd.DataFrame:
    """How much of the nominal price change the cost index accounts for, in log points, by window.

    The price index change splits exactly into the cost index change and the change in the price-to-cost ratio
    (log of price = log of cost + log of ratio). ``cost_part_pct`` is the cost index's share of the price change; it is
    only meaningful when the price rose.
    """
    rows = {}
    for label, (start, end) in windows.items():
        price = 100 * np.log(
            frame.loc[end, "hpi_nominal_b2015"] / frame.loc[start, "hpi_nominal_b2015"]
        )
        cost = 100 * np.log(
            frame.loc[end, "cost_total_b2015"] / frame.loc[start, "cost_total_b2015"]
        )
        rows[label] = {
            "price_log_pts": price,
            "cost_log_pts": cost,
            "ratio_log_pts": price - cost,
            "cost_part_pct": 100 * cost / price if price > 0 else np.nan,
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def supply_response(
    frame: pd.DataFrame,
    y: str = "licensed_n",
    lag: int = 1,
    drop_years: tuple[int, ...] = (),
) -> pd.DataFrame:
    """Yearly change in licensed (or completed) dwellings on last year's change in the real price and the real cost.

    All in log points; the two regressors are entered together so that each coefficient is the response to one holding
    the other fixed (they are correlated, so read the intervals as wide). Newey-West standard errors with two lags.
    Returns one row per term with the coefficient, 95% interval, p-value, R2 and n on every row. An association between
    years, in a sample of two cycles: not a supply elasticity.
    """
    d = pd.DataFrame(
        {
            "dlog_y": 100 * np.log(frame[y]).diff(),
            "dlog_price": 100 * np.log(frame["hpi_real_b2015"]).diff().shift(lag),
            "dlog_cost": 100 * np.log(frame["cost_real_b2015"]).diff().shift(lag),
        }
    )
    d = d.drop(index=[t for t in drop_years if t in d.index]).dropna()
    res = sm.OLS(d["dlog_y"], sm.add_constant(d[["dlog_price", "dlog_cost"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": 2}
    )
    ci = res.conf_int()
    out = pd.DataFrame(
        {
            "coef": res.params,
            "ci_low": ci[0],
            "ci_high": ci[1],
            "p_value": res.pvalues,
            "r2": res.rsquared,
            "n": int(res.nobs),
        }
    )
    return out.drop(index="const").rename_axis("term")


def ratio_and_licensing(frame: pd.DataFrame, lag: int = 1) -> dict:
    """Correlation of licensed dwellings (log) with last year's price-to-cost ratio (log), in levels and in changes.

    Levels share the 2008 collapse and the recovery, so the level correlation is high by construction; the change
    correlation is the stricter check. Returns both and the number of years.
    """
    d = pd.DataFrame(
        {
            "log_licensed": np.log(frame["licensed_n"]),
            "log_ratio": np.log(frame["price_to_cost_b2015"]).shift(lag),
        }
    ).dropna()
    dd = d.diff().dropna()
    return {
        "corr_levels": d["log_licensed"].corr(d["log_ratio"]),
        "corr_changes": dd["log_licensed"].corr(dd["log_ratio"]),
        "n_levels": len(d),
        "n_changes": len(dd),
    }
