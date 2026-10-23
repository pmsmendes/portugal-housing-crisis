"""Regional outlook for price-to-income: which municipalities and regions are likely to worsen further (RQ10.2).

Municipal series have nine annual points (2016 to 2024) and a noisy published level (the 12-month median
price rests on few sales: year-on-year growth has a lag-1 autocorrelation of -0.3 to -0.6), so ETS or ARIMA per
municipality cannot be validated. The methods here forecast the log of price-to-income from straight-line
trends of growing complexity, from no change to a municipal trend shrunk toward its region's:

* ``naive``: the last published value stays;
* ``national_drift``: the last value plus the median national trend;
* ``national_trend``: the municipality's own average level on the national trend (a smoothed level);
* ``own_trend``: the municipality's own straight line;
* ``region_trend`` / ``segment_trend``: own average level on the median trend of its NUTS 3 region / of its
  coast x density class (``segment``);
* ``shrunk_trend``: own line shrunk toward the region trend by empirical Bayes (weight on the own slope =
  between-municipality variance of slopes over that plus the sampling variance of the own slope).

Validation is rolling-origin: every method sees only years up to the origin and forecasts one and two years
ahead; all methods are scored on the same municipalities. Intervals are empirical quantiles of the errors
from the other origins. Everything is on mainland municipalities (the typology and the p2 results are).
"""

import numpy as np
import pandas as pd
from scipy import stats

from pthousing.config import MUNI_KEY, YEAR_KEY

REGION = "nuts3_name_2024"
MIN_OBS = 3  # years of history a municipality needs to be forecast
MIN_REGION = (
    3  # municipalities a region needs for its own trend; otherwise the national trend is used
)
ORIGINS = (2019, 2020, 2021, 2022, 2023)
HORIZONS = (1, 2)
TOP_SHARE = 0.2  # "worsening most" = top fifth of the predicted change


def history(
    panel: pd.DataFrame, start: int = 2016, end: int = 2024
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Log price-to-income (municipality x year, mainland) and the groups of each municipality.

    The groups frame has ``region`` (NUTS 3, 2024 vintage), ``segment`` (coast or inland x urban,
    intermediate or rural; estuary counts as coast) and the name and district for display.
    """
    d = panel[panel["territory"] == "continente"]
    wide = d.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="pti_years")
    y = np.log(wide.loc[:, start:end])
    one = d.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY).reindex(y.index)
    coast = one["coast_class"].replace({"estuary": "coast"})
    groups = pd.DataFrame(
        {
            "region": one[REGION],
            "segment": coast + " / " + one["density_class"],
            "muni_name": one["muni_name"],
            "district": one["district"],
        }
    )
    return y, groups


def last_valid(y: pd.DataFrame) -> pd.Series:
    """Most recent non-missing value of each row."""
    return y.ffill(axis=1).iloc[:, -1]


def line_fit(y: pd.DataFrame) -> pd.DataFrame:
    """Straight line through each row's observed years: ``n``, ``tbar``, ``ybar``, ``slope``, ``sxx`` (sum of
    squared deviations of the years) and ``resid_var``. Rows with fewer than ``MIN_OBS`` points are NaN."""
    t = y.columns.to_numpy(float)
    ok = y.notna().to_numpy()
    n = ok.sum(axis=1)
    keep = n >= MIN_OBS
    values = np.where(ok, y.to_numpy(), 0.0)
    tt = np.where(ok, t, 0.0)
    safe_n = np.maximum(n, 1)
    tbar = tt.sum(axis=1) / safe_n
    ybar = values.sum(axis=1) / safe_n
    dt = np.where(ok, t - tbar[:, None], 0.0)
    dy = np.where(ok, values - ybar[:, None], 0.0)
    sxx = (dt**2).sum(axis=1)
    slope = np.divide((dt * dy).sum(axis=1), sxx, out=np.full(len(y), np.nan), where=sxx > 0)
    rss = ((dy - slope[:, None] * dt) ** 2).sum(axis=1)
    resid_var = np.divide(rss, np.maximum(n - 2, 1), out=np.full(len(y), np.nan), where=n > 2)
    out = pd.DataFrame(
        {"n": n, "tbar": tbar, "ybar": ybar, "slope": slope, "sxx": sxx, "resid_var": resid_var},
        index=y.index,
    )
    return out.where(pd.Series(keep, index=y.index), axis=0)


def _group_slope(fit: pd.DataFrame, labels: pd.Series) -> pd.Series:
    """Median municipal slope of each municipality's group (the national median where the group is small)."""
    national = fit["slope"].median()
    med = fit["slope"].groupby(labels).transform("median")
    size = fit["slope"].groupby(labels).transform("count")
    return med.where(size >= MIN_REGION, national)


def _on_slope(fit: pd.DataFrame, slope: pd.Series, year: int) -> pd.Series:
    """Forecast of log price-to-income in ``year`` from the own average level on a given slope."""
    return fit["ybar"] + slope * (year - fit["tbar"])


def shrunk_slope(fit: pd.DataFrame, region: pd.Series) -> pd.Series:
    """Own slope shrunk toward the region's median slope (empirical Bayes, one variance for the noise).

    The sampling variance of a municipality's slope is ``sigma2 / sxx``, with ``sigma2`` the average residual
    variance of all municipalities; the between-municipality variance of true slopes is, within each region,
    the variance of the slopes minus the average sampling variance (floored at 0).
    """
    sigma2 = fit["resid_var"].mean()
    v = sigma2 / fit["sxx"]
    center = _group_slope(fit, region)
    spread = (fit["slope"] - center).pow(2).groupby(region).transform("mean")
    tau2 = (spread - v.groupby(region).transform("mean")).clip(lower=0)
    weight = (tau2 / (tau2 + v)).fillna(0.0)
    return weight * fit["slope"] + (1 - weight) * center


def forecast_all(y: pd.DataFrame, groups: pd.DataFrame, origin: int, h: int) -> pd.DataFrame:
    """Forecasts of log price-to-income in ``origin + h`` from the data up to ``origin``, one column per
    method. Municipalities with fewer than ``MIN_OBS`` observations are dropped."""
    hist = y.loc[:, :origin]
    fit = line_fit(hist).dropna(subset=["slope"])
    region = groups["region"].reindex(fit.index)
    segment = groups["segment"].reindex(fit.index)
    last = last_valid(hist).reindex(fit.index)
    year = origin + h
    national = fit["slope"].median()
    out = pd.DataFrame(index=fit.index)
    out["naive"] = last
    out["national_drift"] = last + h * national
    out["national_trend"] = _on_slope(fit, pd.Series(national, index=fit.index), year)
    out["own_trend"] = _on_slope(fit, fit["slope"], year)
    out["region_trend"] = _on_slope(fit, _group_slope(fit, region), year)
    out["segment_trend"] = _on_slope(fit, _group_slope(fit, segment), year)
    out["shrunk_trend"] = _on_slope(fit, shrunk_slope(fit, region), year)
    out["last"] = last
    return out


METHODS = [
    "naive", "national_drift", "national_trend", "own_trend", "region_trend", "segment_trend",
    "shrunk_trend",
]  # fmt: skip


def backtest(
    y: pd.DataFrame,
    groups: pd.DataFrame,
    origins: tuple[int, ...] = ORIGINS,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """Rolling-origin forecasts in long form: ``origin``, ``h``, ``muni_code``, ``method``, ``forecast``,
    ``actual`` (both log price-to-income) and ``last`` (the last published value at the origin).

    Only municipalities with an observed value at ``origin + h`` and a forecast from every method are kept,
    so all methods are scored on the same set.
    """
    rows = []
    for origin in origins:
        for h in horizons:
            if origin + h > y.columns.max():
                continue
            fc = forecast_all(y, groups, origin, h)
            fc["actual"] = y[origin + h].reindex(fc.index)
            fc = fc.dropna()
            long = fc.melt(
                id_vars=["actual", "last"],
                value_vars=METHODS,
                var_name="method",
                value_name="forecast",
                ignore_index=False,
            )
            rows.append(long.assign(origin=origin, h=h).rename_axis(MUNI_KEY).reset_index())
    return pd.concat(rows, ignore_index=True)


def _top_precision(pred: pd.Series, actual: pd.Series) -> float:
    k = max(int(round(TOP_SHARE * len(pred))), 1)
    hit = set(pred.nlargest(k).index) & set(actual.nlargest(k).index)
    return len(hit) / k


def _scores(g: pd.DataFrame) -> pd.Series:
    """Skill of one set of forecasts (one origin, one horizon, one method): errors in log points, and how
    well the predicted change from the last published value ranks the actual change."""
    err = g["actual"] - g["forecast"]
    pred = g["forecast"] - g["last"]
    actual = g["actual"] - g["last"]
    rho = stats.spearmanr(pred, actual).statistic if pred.nunique() > 1 else np.nan
    p = pred.set_axis(g[MUNI_KEY].to_numpy())
    a = actual.set_axis(g[MUNI_KEY].to_numpy())
    return pd.Series(
        {
            "n": len(g),
            "rmse": float(np.sqrt((err**2).mean())),
            "mae": float(err.abs().mean()),
            "bias": float(-err.mean()),  # forecast minus actual
            "spearman": float(rho),
            "top_precision": _top_precision(p, a),
        }
    )


def accuracy(bt: pd.DataFrame) -> pd.DataFrame:
    """Mean over origins of the scores, by method and horizon (``n`` is the mean sample size)."""
    per_origin = bt.groupby(["method", "h", "origin"]).apply(_scores, include_groups=False)
    return per_origin.groupby(["method", "h"]).mean().reset_index()


def group_backtest(bt: pd.DataFrame, groups: pd.DataFrame, by: str = "region") -> pd.DataFrame:
    """The same forecasts aggregated to the groups of ``by`` (``region`` or ``segment``): median predicted and
    actual log change from the last published value of the group's municipalities, in long form (``origin``,
    ``h``, ``method``, ``group``). Groups with fewer than ``MIN_REGION`` municipalities in a sample are dropped."""
    d = bt.assign(
        group=bt[MUNI_KEY].map(groups[by]),
        pred=bt["forecast"] - bt["last"],
        real=bt["actual"] - bt["last"],
    )
    agg = d.groupby(["origin", "h", "method", "group"]).agg(
        pred=("pred", "median"), real=("real", "median"), n=("pred", "size")
    )
    return agg[agg["n"] >= MIN_REGION].reset_index()


def group_accuracy(gb: pd.DataFrame) -> pd.DataFrame:
    """Group-level RMSE of the median change, RMSE of the change relative to the cross-group mean (which
    groups move more than the others, not the common swing) and rank skill across groups, mean over origins."""

    def one(g: pd.DataFrame) -> pd.Series:
        err = g["real"] - g["pred"]
        rel = (g["real"] - g["real"].mean()) - (g["pred"] - g["pred"].mean())
        rho = stats.spearmanr(g["pred"], g["real"]).statistic if g["pred"].nunique() > 1 else np.nan
        k = max(int(round(TOP_SHARE * len(g))), 1)
        hit = set(g.nlargest(k, "pred")["group"]) & set(g.nlargest(k, "real")["group"])
        return pd.Series(
            {"groups": len(g), "rmse": float(np.sqrt((err**2).mean())),
             "rmse_relative": float(np.sqrt((rel**2).mean())), "spearman": float(rho),
             "top_precision": len(hit) / k}
        )  # fmt: skip

    per = gb.groupby(["method", "h", "origin"]).apply(one, include_groups=False)
    return per.groupby(["method", "h"]).mean().reset_index()


def select_method(acc: pd.DataFrame) -> str:
    """Lowest RMSE averaged over horizons; a tie within 1% goes to the simpler method (order of ``METHODS``)."""
    mean = acc.groupby("method")["rmse"].mean().reindex(METHODS)
    best = mean.min()
    return str(next(m for m in METHODS if mean[m] <= best * 1.01))


def error_quantiles(
    errors: pd.DataFrame, by: str = "h", levels: tuple[float, ...] = (0.1, 0.9)
) -> pd.DataFrame:
    """Empirical quantiles of ``error`` (actual minus forecast) for each ``by`` value, pooled over origins."""
    return errors.groupby(by)["error"].quantile(list(levels)).unstack()


def interval_coverage(errors: pd.DataFrame, level: float = 0.8) -> pd.DataFrame:
    """Share of errors inside the interval built from the *other* origins' errors (leave-one-origin-out)."""
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    rows = []
    for (h, origin), g in errors.groupby(["h", "origin"]):
        rest = errors[(errors["h"] == h) & (errors["origin"] != origin)]["error"]
        lo, hi = rest.quantile(lo_q), rest.quantile(hi_q)
        rows.append(
            {"h": h, "origin": origin, "coverage": float(g["error"].between(lo, hi).mean())}
        )
    return pd.DataFrame(rows)


def outlook(
    y: pd.DataFrame,
    groups: pd.DataFrame,
    method: str,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """Municipal forecasts beyond the last year: ``muni_code``, ``h``, ``year``, ``last``, ``forecast`` (log
    price-to-income) with the municipality's group labels. ``last`` is the last published value."""
    origin = int(y.columns.max())
    parts = []
    for h in horizons:
        fc = forecast_all(y, groups, origin, h)
        parts.append(
            pd.DataFrame(
                {"h": h, "year": origin + h, "last": fc["last"], "forecast": fc[method]}
            ).rename_axis(MUNI_KEY)
        )
    out = pd.concat(parts).reset_index()
    return out.join(groups, on=MUNI_KEY)


def relative_errors(
    bt: pd.DataFrame, method: str, groups: pd.DataFrame | None = None, by: str | None = None
) -> pd.DataFrame:
    """Errors of the change relative to the cross-section, for the intervals of a relative outlook.

    With ``by`` the forecasts are first aggregated to the groups of that column (``group_backtest``); otherwise
    the unit is the municipality. For every origin and horizon the cross-unit median of the predicted and of the
    actual change (from the last published value) is removed, and ``error`` = actual minus predicted.
    """
    d = bt[bt["method"] == method]
    if by is not None:
        gb = group_backtest(d, groups, by)
        d = gb.rename(columns={"group": "unit"})
    else:
        d = d.assign(unit=d[MUNI_KEY], pred=d["forecast"] - d["last"], real=d["actual"] - d["last"])
    key = ["origin", "h"]
    rel_pred = d["pred"] - d.groupby(key)["pred"].transform("median")
    rel_real = d["real"] - d.groupby(key)["real"].transform("median")
    return d.assign(error=rel_real - rel_pred)[[*key, "unit", "error"]]


def outlook_summary(out: pd.DataFrame, by: str, h: int, rel_err: pd.DataFrame) -> pd.DataFrame:
    """Outlook of the groups of ``by`` ``h`` years ahead, relative to the median municipality.

    ``change`` is the median forecast change in log price-to-income from the last published value (``change_pct``
    in %); ``relative`` is that minus the median municipality's (log points, about %) with the 80% interval
    built from ``rel_err`` (``relative_errors``) for the same horizon; ``share_rising`` is the share of the group's
    municipalities forecast to rise.
    """
    d = out[out["h"] == h].assign(change=lambda x: x["forecast"] - x["last"])
    national = d["change"].median()
    g = d.groupby(by).agg(
        municipalities_n=("change", "size"),
        change=("change", "median"),
        share_rising=("change", lambda s: float((s > 0).mean())),
    )
    q = rel_err[rel_err["h"] == h]["error"].quantile([0.1, 0.9])
    g["change_pct"] = 100 * np.expm1(g["change"])
    g["relative"] = 100 * (g["change"] - national)
    g["relative_lo80"] = g["relative"] + 100 * q[0.1]
    g["relative_hi80"] = g["relative"] + 100 * q[0.9]
    return g.sort_values("relative", ascending=False).reset_index()
