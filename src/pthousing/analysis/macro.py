"""Mortgage rates and the house-price cycle: episodes and a timing test (RQ1.7, RQ9.2, RQ9.5).

National quarterly series only (2003 to 2026): the BIS real and nominal house price index (INE's from 2009),
the agreed rate on new housing loans (Banco de Portugal) and the payment it implies on a 100,000 euro loan.
Real prices are deflated with the consumer price index, so a burst of inflation lowers them mechanically;
``rate_timing`` therefore also runs on nominal prices.

Everything here is association in time. The rate is set by the ECB in response to euro-area conditions and is
persistent, there are two or three regimes in 23 years and the overlapping four-quarter changes leave about 23
independent observations per decade, so the functions report intervals and a placebo, not a causal effect.
Functions take interim tables or the frame from ``quarterly_frame``; nothing here reads files.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from pthousing.features.affordability import mortgage_payment_monthly

#: The rate whose payment the rest of the project uses (``mortgage_payment_100k_eur``).
RATE_COLUMN = "mortgage_rate_new_lt1y_pct"
#: Quarters over which changes are taken: a year, which removes seasonality in the monthly rate average.
CHANGE_QUARTERS = 4
#: Newey-West lags: four-quarter changes overlap for three quarters and the rate is persistent.
HAC_LAGS = 6


def quarterly_frame(bis: pd.DataFrame, mortgage: pd.DataFrame) -> pd.DataFrame:
    """Quarterly real and nominal price index, mortgage rates and the payment on a 100,000 euro loan.

    ``bis`` is the ``bis_spp`` interim table (2010 = 100), ``mortgage`` the monthly ``bp_mortgage`` table; rates are
    averaged over the three months of each quarter. Only quarters with both a price and a rate are kept.
    """
    prices = bis.set_index("period_start")[["hpi_real_b2010", "hpi_nominal_b2010"]]
    quarter = mortgage["period_start"].dt.to_period("Q").dt.to_timestamp()
    rates = mortgage.groupby(quarter)[[RATE_COLUMN, "mortgage_aprc_new_pct"]].mean()
    rates.index.name = "period_start"
    frame = prices.join(rates, how="inner").dropna()
    frame["payment_100k_eur"] = mortgage_payment_monthly(100_000, frame[RATE_COLUMN])
    return frame


def add_changes(frame: pd.DataFrame, n: int = CHANGE_QUARTERS) -> pd.DataFrame:
    """Add n-quarter changes: price growth (log points, real and nominal), rate change (pp), payment growth."""
    out = frame.copy()
    out["growth_real_pct"] = 100 * np.log(out["hpi_real_b2010"]).diff(n)
    out["growth_nominal_pct"] = 100 * np.log(out["hpi_nominal_b2010"]).diff(n)
    out["rate_change_pp"] = out[RATE_COLUMN].diff(n)
    out["aprc_change_pp"] = out["mortgage_aprc_new_pct"].diff(n)
    out["payment_growth_pct"] = 100 * np.log(out["payment_100k_eur"]).diff(n)
    return out


def episodes(
    frame: pd.DataFrame,
    windows: dict[str, tuple[str, str]],
    completions: pd.Series | None = None,
) -> pd.DataFrame:
    """Price, rate and payment between the first and last quarter of each window (labels like ``"2008Q3"``).

    Changes are last quarter over first quarter; ``completions`` (annual, indexed by year) adds the average
    completions per year over the calendar years the window touches.
    """
    rows = {}
    for label, (start, end) in windows.items():
        a, b = pd.Period(start, "Q").to_timestamp(), pd.Period(end, "Q").to_timestamp()
        first, last = frame.loc[a], frame.loc[b]
        row = {
            "start": start,
            "end": end,
            "real_price_change_pct": 100 * (last["hpi_real_b2010"] / first["hpi_real_b2010"] - 1),
            "nominal_price_change_pct": 100
            * (last["hpi_nominal_b2010"] / first["hpi_nominal_b2010"] - 1),
            "rate_start_pct": first[RATE_COLUMN],
            "rate_end_pct": last[RATE_COLUMN],
            "rate_change_pp": last[RATE_COLUMN] - first[RATE_COLUMN],
            "payment_change_pct": 100 * (last["payment_100k_eur"] / first["payment_100k_eur"] - 1),
        }
        if completions is not None:
            years = range(a.year, b.year + 1)
            row["completions_per_year_n"] = completions.reindex(years).mean()
        rows[label] = row
    return pd.DataFrame.from_dict(rows, orient="index")


def lag_profile(changes: pd.DataFrame, y: str, x: str, lags: range) -> pd.DataFrame:
    """Correlation of ``y`` with ``x`` shifted by each lag (positive lag: the x change came earlier).

    The band is the 95% limit for no correlation with independent draws, ``1.96 / sqrt(n / h)``: the overlapping
    changes carry about one independent observation per ``h = 4`` quarters. It is a guide, not a test.
    """
    d = changes[[y, x]].dropna()
    band = 1.96 / np.sqrt(len(d) / CHANGE_QUARTERS)
    corr = [d[y].corr(changes[x].shift(k).reindex(d.index)) for k in lags]
    out = pd.DataFrame({"lag_quarters": list(lags), "corr": corr})
    out["band"] = band
    return out


def rate_timing(
    changes: pd.DataFrame,
    y: str = "growth_real_pct",
    rate_lag: int = CHANGE_QUARTERS,
    own_lag: bool = False,
    lead: bool = False,
    sample: tuple[str, str] | None = None,
) -> dict:
    """Price growth over a year on the rate change over the year ``rate_lag`` quarters before.

    With ``rate_lag`` equal to the change window (4) the two windows do not overlap: this year's price growth
    on last year's rate change. ``own_lag`` adds the previous year's price growth (momentum); ``lead`` adds the
    rate change of the year after as a placebo (a future rate change cannot move today's price, but with a
    persistent rate it picks up the same co-movement). Newey-West standard errors. Returns the coefficient on the
    lagged rate change (log points of price per pp), its 95% interval, p-value, the placebo coefficient and n.
    """
    d = changes.copy()
    d["x"] = d["rate_change_pp"].shift(rate_lag)
    xs = ["x"]
    if own_lag:
        d["y_lag"] = d[y].shift(CHANGE_QUARTERS)
        xs.append("y_lag")
    if lead:
        d["x_lead"] = d["rate_change_pp"].shift(-CHANGE_QUARTERS)
        xs.append("x_lead")
    d = d[[y, *xs]].dropna()
    if sample is not None:
        d = d.loc[sample[0] : sample[1]]
    res = sm.OLS(d[y], sm.add_constant(d[xs])).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    lo, hi = res.conf_int().loc["x"]
    out = {
        "coef_pct_per_pp": res.params["x"],
        "ci_low": lo,
        "ci_high": hi,
        "p_value": res.pvalues["x"],
        "r2": res.rsquared,
        "n": int(res.nobs),
    }
    if own_lag:
        out["own_lag_coef"] = res.params["y_lag"]
    if lead:
        out["lead_coef_pct_per_pp"] = res.params["x_lead"]
        out["lead_p_value"] = res.pvalues["x_lead"]
    return out
