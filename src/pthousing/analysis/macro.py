"""Mortgage rates, wages, unemployment and the house-price cycle (RQ1.7, RQ1.4, RQ9.1, RQ9.2, RQ9.4, RQ9.5).

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

from pthousing.config import MORTGAGE_TERM_YEARS
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
    x_col: str = "rate_change_pp",
) -> dict:
    """Price growth over a year on the rate change over the year ``rate_lag`` quarters before.

    ``x_col`` names another four-quarter change to use in place of the rate change (``credit.py`` passes
    housing-loan growth); the output keys keep their "per pp" names.

    With ``rate_lag`` equal to the change window (4) the two windows do not overlap: this year's price growth
    on last year's rate change. ``own_lag`` adds the previous year's price growth (momentum); ``lead`` adds the
    rate change of the year after as a placebo (a future rate change cannot move today's price, but with a
    persistent rate it picks up the same co-movement). Newey-West standard errors. Returns the coefficient on the
    lagged rate change (log points of price per pp), its 95% interval, p-value, the placebo coefficient and n.
    """
    d = changes.copy()
    d["x"] = d[x_col].shift(rate_lag)
    xs = ["x"]
    if own_lag:
        d["y_lag"] = d[y].shift(CHANGE_QUARTERS)
        xs.append("y_lag")
    if lead:
        d["x_lead"] = d[x_col].shift(-CHANGE_QUARTERS)
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


# ---- wages, unemployment and GDP (annual) ---------------------------------------------------------

BASE = 2015  # index base of the annual long series (``build_panel.national_annual_long``)


def annual_frame(long: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    """Annual national prices, wages, unemployment and GDP growth, 1995 to the last year.

    ``long`` is ``national_annual_long`` (nominal and real price index, CPI, OECD price-to-income; 2015 = 100) and
    ``macro`` the ``eurostat_macro`` interim table. Adds real compensation per employee (deflated with the same
    CPI as the real price index), the price-to-wage index (nominal price over nominal compensation per employee,
    2015 = 100) and yearly changes: log points for prices and wages, percentage points for unemployment. When
    ``long`` holds the OECD real rent index (``rent_real_b2015``, all leases) its yearly change is added as
    ``rent_growth_real_pct``.
    """
    d = long.set_index("year")[
        ["hpi_nominal_b2015", "hpi_real_b2015", "cpi_index_b2015", "price_to_income_b2015"]
    ].join(macro.set_index("year"))
    wage_real = d["compensation_per_employee_eur"] / d["cpi_index_b2015"]
    d["wage_real_b2015"] = 100 * wage_real / wage_real.loc[BASE]
    ratio = d["hpi_nominal_b2015"] / d["compensation_per_employee_eur"]
    d["price_to_wage_b2015"] = 100 * ratio / ratio.loc[BASE]
    d["price_growth_real_pct"] = 100 * np.log(d["hpi_real_b2015"]).diff()
    d["price_growth_nominal_pct"] = 100 * np.log(d["hpi_nominal_b2015"]).diff()
    d["wage_growth_real_pct"] = 100 * np.log(wage_real).diff()
    d["wage_growth_nominal_pct"] = 100 * np.log(d["compensation_per_employee_eur"]).diff()
    d["inflation_pct"] = 100 * np.log(d["cpi_index_b2015"]).diff()
    d["unemployment_change_pp"] = d["unemployment_pct"].diff()
    if "rent_real_b2015" in long.columns:
        d["rent_real_b2015"] = long.set_index("year")["rent_real_b2015"]
        d["rent_growth_real_pct"] = 100 * np.log(d["rent_real_b2015"]).diff()
    return d


def fundamentals(
    annual: pd.DataFrame,
    xs: list[str],
    y: str = "price_growth_real_pct",
    lag: int = 0,
    own_lag: bool = False,
    drop_years: tuple[int, ...] = (),
) -> pd.DataFrame:
    """Yearly price growth on wage growth, unemployment change and GDP growth (``xs``), lagged ``lag`` years.

    ``own_lag`` adds last year's price growth (momentum). Newey-West standard errors with two lags; ``drop_years``
    removes years from the sample (the pandemic, when wages and the CPI jumped). Returns one row per term with the
    coefficient, 95% interval and p-value, and the R2 and number of years on every row. With lag 0 these are
    co-movements within the year, with lag 1 the variables lead.
    """
    d = annual[[y]].copy()
    for x in xs:
        d[x] = annual[x].shift(lag)
    if own_lag:
        d["price_growth_lag"] = annual[y].shift(1)
    d = d.drop(index=list(drop_years)).dropna()
    cols = [c for c in d.columns if c != y]
    res = sm.OLS(d[y], sm.add_constant(d[cols])).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
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


# ---- what wages and rates could finance (annual) --------------------------------------------------


def annual_rates(mortgage: pd.DataFrame, column: str = RATE_COLUMN) -> pd.Series:
    """Calendar-year mean of a monthly ``bp_mortgage`` rate column, indexed by year."""
    return mortgage.groupby("year")[column].mean().rename(column)


def financeable_price(
    annual: pd.DataFrame,
    rates: pd.Series,
    base: tuple[int, int] = (2003, 2025),
    term_years: int = MORTGAGE_TERM_YEARS,
    terms: pd.Series | None = None,
) -> pd.DataFrame:
    """The nominal price a constant payment-to-wage burden could finance, against the actual price.

    A buyer who spends a fixed share of the average wage on a loan of a fixed share of the price can pay
    ``wage / payment_per_euro_borrowed``: the implied price rises with wages and falls with the rate. Both are
    nominal. ``annual`` is ``annual_frame`` (nominal price index, compensation per employee), ``rates`` yearly
    rates in per cent. The level of the burden is not observed, so the implied price is scaled to equal the actual
    price on average over ``base`` (years, inclusive): the gap (log points) is relative to that average, and its
    changes, not its level, carry the information. Returns the actual and implied price (2015 = 100 scale), the
    gap, the payment per 100,000 euros and the payment-to-wage ratio of buying at the index price (2015 = 100).

    ``terms`` (year -> mean term of new loans, years) replaces the fixed ``term_years`` by the observed term: the first
    observed value is held back to the earlier years and the last forward, so only the changes within the observed
    years move the benchmark (a longer term raises what the same payment carries).
    """
    d = (
        annual[["hpi_nominal_b2015", "compensation_per_employee_eur"]]
        .join(rates, how="inner")
        .dropna()
    )
    term = term_years
    if terms is not None:
        term = (
            terms.reindex(d.index.union(terms.index))
            .sort_index()
            .bfill()
            .ffill()
            .loc[d.index]
            .to_numpy()
        )
    payment = pd.Series(
        mortgage_payment_monthly(100_000, d[rates.name], term), index=d.index, name="payment"
    )
    log_implied = np.log(d["compensation_per_employee_eur"]) - np.log(payment)
    window = (d.index >= base[0]) & (d.index <= base[1])
    shift = (np.log(d["hpi_nominal_b2015"]) - log_implied)[window].mean()
    out = pd.DataFrame(
        {
            "price_b2015": d["hpi_nominal_b2015"],
            "implied_price_b2015": np.exp(log_implied + shift),
            "rate_pct": d[rates.name],
            "payment_100k_eur": payment,
            "wage_eur": d["compensation_per_employee_eur"],
        }
    )
    out["gap_pct"] = 100 * (np.log(out["price_b2015"]) - np.log(out["implied_price_b2015"]))
    burden = out["price_b2015"] * out["payment_100k_eur"] / out["wage_eur"]
    out["payment_to_wage_b2015"] = 100 * burden / burden.loc[BASE]
    return out


def price_change_parts(frame: pd.DataFrame, start: int, end: int) -> dict[str, float]:
    """Log-point change of the nominal price from ``start`` to ``end``, split into wages, the rate and the gap.

    ``price = wage / payment x exp(gap)``, so the change is wage growth, minus the change in the payment per
    euro borrowed (the rate; positive when it falls) and the change in the gap (what the two do not account for).
    """
    a, b = frame.loc[start], frame.loc[end]
    wages = 100 * np.log(b["wage_eur"] / a["wage_eur"])
    rate = -100 * np.log(b["payment_100k_eur"] / a["payment_100k_eur"])
    gap = b["gap_pct"] - a["gap_pct"]
    return {
        "price_change_pct": 100 * np.log(b["price_b2015"] / a["price_b2015"]),
        "wages_pct": wages,
        "rate_pct": rate,
        "gap_pct": gap,
    }
