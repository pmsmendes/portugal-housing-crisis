"""Naive and seasonal-naive baselines, drift, ETS, ARIMA, rolling-origin validation and prediction intervals.

Every forecaster takes a quarterly series ``y`` (log scale, ``PeriodIndex`` with freq Q) and a horizon ``h`` and
returns a frame indexed by the forecast periods with ``mean`` and the 80% and 95% interval limits
(``lo80``, ``hi80``, ``lo95``, ``hi95``). ``rolling_origin`` refits each method at every origin using data up to
the origin only, so no forecast sees its own target; ``accuracy`` summarises the errors by horizon.

Series are short (70 quarters) and span structural breaks (the 2011-2013 crisis, the 2022 rate shock), so the
intervals are the honest part of the output: ``accuracy`` reports their empirical coverage.
"""

import warnings
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

SEASON = 4  # quarters in a year
LEVELS = {80: 0.20, 95: 0.05}  # interval label -> alpha
INTERVAL_COLUMNS = ["lo80", "hi80", "lo95", "hi95"]


def _frame(index: pd.PeriodIndex, mean: np.ndarray, sigma: np.ndarray) -> pd.DataFrame:
    """Forecast frame from a mean and a standard deviation per horizon (normal intervals)."""
    out = pd.DataFrame({"mean": mean}, index=index)
    for level, alpha in LEVELS.items():
        z = stats.norm.ppf(1 - alpha / 2)
        out[f"lo{level}"] = mean - z * sigma
        out[f"hi{level}"] = mean + z * sigma
    return out


def _future(y: pd.Series, h: int) -> pd.PeriodIndex:
    return pd.period_range(y.index[-1] + 1, periods=h, freq=y.index.freq)


# ---- baselines ------------------------------------------------------------------------------------


def naive(y: pd.Series, h: int) -> pd.DataFrame:
    """Last value; the interval is that of a random walk (residual sd of the one-step changes x sqrt(h))."""
    sigma = y.diff().dropna().std(ddof=1) * np.sqrt(np.arange(1, h + 1))
    return _frame(_future(y, h), np.full(h, y.iloc[-1]), sigma)


def seasonal_naive(y: pd.Series, h: int, season: int = SEASON) -> pd.DataFrame:
    """Value of the same quarter last year; the interval from the sd of the year-on-year changes."""
    last = y.iloc[-season:].to_numpy()
    mean = np.array([last[i % season] for i in range(h)])
    steps = np.ceil(np.arange(1, h + 1) / season)
    sigma = y.diff(season).dropna().std(ddof=1) * np.sqrt(steps)
    return _frame(_future(y, h), mean, sigma)


def drift(y: pd.Series, h: int) -> pd.DataFrame:
    """Last value plus the average change per quarter (a random walk with drift)."""
    n = len(y)
    d = y.diff().dropna()
    steps = np.arange(1, h + 1)
    resid_sd = np.sqrt(((d - d.mean()) ** 2).sum() / (n - 2))
    sigma = resid_sd * np.sqrt(steps * (1 + steps / (n - 1)))
    return _frame(_future(y, h), y.iloc[-1] + d.mean() * steps, sigma)


# ---- ETS and ARIMA --------------------------------------------------------------------------------

ETS_CANDIDATES = [
    {"trend": trend, "damped_trend": damped, "seasonal": seasonal}
    for trend, damped in ((None, False), ("add", False), ("add", True))
    for seasonal in (None, "add")
]
ARIMA_CANDIDATES = [
    {"order": (p, 1, q), "trend": trend} for p in range(3) for q in range(3) for trend in ("n", "t")
]


def _interval_frame(index: pd.PeriodIndex, get) -> pd.DataFrame:
    """Frame from a function ``get(alpha)`` returning (mean, lower, upper) arrays."""
    mean, lo80, hi80 = get(LEVELS[80])
    _, lo95, hi95 = get(LEVELS[95])
    return pd.DataFrame(
        {"mean": mean, "lo80": lo80, "hi80": hi80, "lo95": lo95, "hi95": hi95}, index=index
    )


def _aicc(res, n: int, k: int) -> float:
    aic = float(res.aic)
    return aic + 2 * k * (k + 1) / max(n - k - 1, 1)


def ets(y: pd.Series, h: int, return_spec: bool = False):
    """ETS with additive errors, chosen among six trend/seasonal forms by AICc (on the log series)."""
    best, best_spec = None, None
    for spec in ETS_CANDIDATES:
        if spec["seasonal"] and len(y) < 3 * SEASON:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = ETSModel(
                    y,
                    error="add",
                    seasonal_periods=SEASON if spec["seasonal"] else None,
                    **spec,
                ).fit(disp=False, maxiter=200)
        except Exception:  # a form that does not converge is not a candidate
            continue
        score = _aicc(res, len(y), len(res.params))
        if np.isfinite(score) and (best is None or score < best[0]):
            best, best_spec = (score, res), spec
    if best is None:
        raise RuntimeError("no ETS specification could be fitted")
    res = best[1]

    def get(alpha):
        frame = res.get_prediction(start=len(y), end=len(y) + h - 1).summary_frame(alpha=alpha)
        return frame["mean"].to_numpy(), frame["pi_lower"].to_numpy(), frame["pi_upper"].to_numpy()

    out = _interval_frame(_future(y, h), get)
    return (out, best_spec) if return_spec else out


def arima(y: pd.Series, h: int, return_spec: bool = False):
    """ARIMA(p, 1, q) with or without drift, p and q up to 2, chosen by AICc (on the log series)."""
    best, best_spec = None, None
    for spec in ARIMA_CANDIDATES:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = ARIMA(y.to_numpy(), **spec).fit()
        except Exception:
            continue
        k = len(res.params)
        score = _aicc(res, len(y) - 1, k)
        if np.isfinite(score) and (best is None or score < best[0]):
            best, best_spec = (score, res), spec
    if best is None:
        raise RuntimeError("no ARIMA specification could be fitted")
    res = best[1]

    def get(alpha):
        frame = res.get_forecast(h).summary_frame(alpha=alpha)
        return (
            frame["mean"].to_numpy(),
            frame["mean_ci_lower"].to_numpy(),
            frame["mean_ci_upper"].to_numpy(),
        )

    out = _interval_frame(_future(y, h), get)
    return (out, best_spec) if return_spec else out


METHODS: dict[str, Callable[[pd.Series, int], pd.DataFrame]] = {
    "naive": naive,
    "seasonal naive": seasonal_naive,
    "drift": drift,
    "ETS": ets,
    "ARIMA": arima,
}


# ---- rolling-origin validation --------------------------------------------------------------------


def rolling_origin(
    y: pd.Series,
    methods: dict[str, Callable[[pd.Series, int], pd.DataFrame]] | None = None,
    initial: int = 36,
    horizon: int = 8,
    step: int = 1,
) -> pd.DataFrame:
    """Forecast every target ``h`` = 1..``horizon`` quarters ahead from each origin, refitting at every origin.

    The first origin has ``initial`` observations; origins move forward by ``step`` quarters. A forecast is kept
    only if its target is observed. Returns tidy rows: ``method``, ``origin`` (last observation used), ``h``,
    ``target``, ``actual``, ``mean`` and the interval limits.
    """
    methods = methods or METHODS
    rows = []
    for end in range(initial, len(y), step):
        train = y.iloc[:end]
        h_max = min(horizon, len(y) - end)
        for name, fn in methods.items():
            fc = fn(train, h_max)
            fc = fc.assign(
                method=name,
                origin=train.index[-1],
                h=np.arange(1, h_max + 1),
                target=fc.index,
                actual=y.reindex(fc.index).to_numpy(),
            )
            rows.append(fc.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True)[
        ["method", "origin", "h", "target", "actual", "mean", *INTERVAL_COLUMNS]
    ]


def mase_scale(y: pd.Series, initial: int = 36) -> float:
    """Mean absolute one-step change over the first training window: the scale for MASE."""
    return float(y.iloc[:initial].diff().abs().mean())


def interval_score(actual, lo, hi, alpha: float) -> np.ndarray:
    """Winkler interval score: width plus a penalty of 2/alpha times how far the actual falls outside."""
    actual, lo, hi = (np.asarray(v, dtype=float) for v in (actual, lo, hi))
    return (
        (hi - lo)
        + (2 / alpha) * np.maximum(lo - actual, 0)
        + (2 / alpha) * np.maximum(actual - hi, 0)
    )


def accuracy(results: pd.DataFrame, scale: float, by: str = "h") -> pd.DataFrame:
    """Errors (in the units of the series, log points) by method and horizon (or other column ``by``).

    ``rmse``, ``mae``, ``mase`` (mae over the scale of the one-step changes), ``bias``, ``coverage80`` and
    ``coverage95`` (share of actuals inside the interval), ``score80`` (mean Winkler score, 80% interval) and the
    number of forecasts ``n``.
    """
    r = results.assign(error=results["actual"] - results["mean"])
    r["in80"] = r["actual"].between(r["lo80"], r["hi80"])
    r["in95"] = r["actual"].between(r["lo95"], r["hi95"])
    r["score80"] = interval_score(r["actual"], r["lo80"], r["hi80"], LEVELS[80])
    grouped = r.groupby(["method", by])
    out = pd.DataFrame(
        {
            "rmse": grouped["error"].apply(lambda e: float(np.sqrt((e**2).mean()))),
            "mae": grouped["error"].apply(lambda e: float(e.abs().mean())),
            "bias": grouped["error"].mean(),
            "coverage80": grouped["in80"].mean(),
            "coverage95": grouped["in95"].mean(),
            "score80": grouped["score80"].mean(),
            "n": grouped["error"].size(),
        }
    )
    out["mase"] = out["mae"] / scale
    return out.reset_index()


def relative_to(table: pd.DataFrame, baseline: str, column: str = "rmse") -> pd.DataFrame:
    """Each method's ``column`` divided by the baseline's at the same ``h`` (below 1 means better)."""
    wide = table.pivot(index="h", columns="method", values=column)
    return wide.div(wide[baseline], axis=0)
