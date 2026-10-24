import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import macro
from pthousing.features.affordability import mortgage_payment_monthly


def _inputs(n=40, seed=0):
    quarters = pd.date_range("2003-01-01", periods=n, freq="QS")
    rng = np.random.default_rng(seed)
    real = 100 * np.exp(np.cumsum(rng.normal(0.01, 0.02, n)))
    bis = pd.DataFrame(
        {"period_start": quarters, "hpi_real_b2010": real, "hpi_nominal_b2010": real * 1.02}
    )
    months = pd.date_range("2003-01-01", periods=3 * n, freq="MS")
    rate = 3 + np.sin(np.arange(3 * n) / 10)
    mortgage = pd.DataFrame(
        {
            "period_start": months,
            "mortgage_rate_new_lt1y_pct": rate,
            "mortgage_aprc_new_pct": rate + 1,
        }
    )
    return bis, mortgage


def test_quarterly_frame_averages_rates_and_prices_payment():
    bis, mortgage = _inputs()
    f = macro.quarterly_frame(bis, mortgage)
    assert len(f) == 40
    first = mortgage["mortgage_rate_new_lt1y_pct"].iloc[:3].mean()
    assert f["mortgage_rate_new_lt1y_pct"].iloc[0] == pytest.approx(first)
    expected = mortgage_payment_monthly(100_000, first)
    assert f["payment_100k_eur"].iloc[0] == pytest.approx(expected)


def test_episodes_changes_between_window_quarters():
    bis, mortgage = _inputs()
    f = macro.quarterly_frame(bis, mortgage)
    completions = pd.Series({2003: 10.0, 2004: 20.0, 2005: 30.0})
    e = macro.episodes(f, {"a": ("2003Q1", "2004Q1")}, completions)
    row = e.loc["a"]
    a, b = f.iloc[0], f.iloc[4]
    assert row["real_price_change_pct"] == pytest.approx(
        100 * (b["hpi_real_b2010"] / a["hpi_real_b2010"] - 1)
    )
    assert row["rate_change_pp"] == pytest.approx(
        b["mortgage_rate_new_lt1y_pct"] - a["mortgage_rate_new_lt1y_pct"]
    )
    assert row["completions_per_year_n"] == pytest.approx(15.0)


def test_rate_timing_recovers_a_planted_effect():
    rng = np.random.default_rng(1)
    n = 200
    idx = pd.date_range("1990-01-01", periods=n, freq="QS")
    rate = pd.Series(np.cumsum(rng.normal(0, 0.3, n)), index=idx)
    d = pd.DataFrame({"rate_change_pp": rate.diff(4)})
    d["growth_real_pct"] = -2.0 * d["rate_change_pp"].shift(4) + rng.normal(0, 0.5, n)
    out = macro.rate_timing(d)
    assert out["coef_pct_per_pp"] == pytest.approx(-2.0, abs=0.3)
    assert out["ci_low"] < -2.0 < out["ci_high"]
    assert macro.rate_timing(d, own_lag=True, lead=True)["n"] < out["n"]


def test_lag_profile_peaks_at_the_planted_lag():
    rng = np.random.default_rng(2)
    n = 200
    idx = pd.date_range("1990-01-01", periods=n, freq="QS")
    d = pd.DataFrame({"x": rng.normal(size=n)}, index=idx)
    d["y"] = d["x"].shift(3) + rng.normal(0, 0.1, n)
    p = macro.lag_profile(d, "y", "x", range(0, 6))
    assert p.loc[p["corr"].idxmax(), "lag_quarters"] == 3
    assert p["band"].iloc[0] == pytest.approx(1.96 / np.sqrt(len(d.dropna()) / 4))
