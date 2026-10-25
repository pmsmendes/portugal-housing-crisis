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


def _annual(n=30, seed=3):
    rng = np.random.default_rng(seed)
    years = np.arange(1995, 1995 + n)
    cpi = 100 * np.cumprod(1 + rng.normal(0.02, 0.005, n))
    wage_nominal = 10_000 * np.cumprod(1 + rng.normal(0.03, 0.01, n))
    long = pd.DataFrame(
        {
            "year": years,
            "hpi_nominal_b2015": 100 * np.cumprod(1 + rng.normal(0.04, 0.03, n)),
            "hpi_real_b2015": 100 * np.cumprod(1 + rng.normal(0.02, 0.03, n)),
            "cpi_index_b2015": cpi,
            "price_to_income_b2015": 100.0,
        }
    )
    macro_tbl = pd.DataFrame(
        {
            "year": years,
            "gdp_growth_pct": rng.normal(2, 2, n),
            "unemployment_pct": 8 + np.cumsum(rng.normal(0, 0.5, n)),
            "compensation_per_employee_eur": wage_nominal,
        }
    )
    return long, macro_tbl


def test_annual_frame_rebases_wages_and_ratio_to_2015():
    long, macro_tbl = _annual()
    d = macro.annual_frame(long, macro_tbl)
    assert d.loc[2015, "wage_real_b2015"] == pytest.approx(100)
    assert d.loc[2015, "price_to_wage_b2015"] == pytest.approx(100)
    expected = 100 * np.log(d["compensation_per_employee_eur"] / d["cpi_index_b2015"]).diff()
    pd.testing.assert_series_equal(d["wage_growth_real_pct"], expected, check_names=False)
    assert d["unemployment_change_pp"].iloc[1] == pytest.approx(
        d["unemployment_pct"].iloc[1] - d["unemployment_pct"].iloc[0]
    )


def test_annual_frame_adds_real_rent_growth_only_when_rents_are_given():
    long, macro_tbl = _annual()
    assert "rent_growth_real_pct" not in macro.annual_frame(long, macro_tbl)
    long["rent_real_b2015"] = 100 * 1.02 ** np.arange(len(long))
    d = macro.annual_frame(long, macro_tbl)
    assert d["rent_growth_real_pct"].iloc[1:].to_numpy() == pytest.approx(100 * np.log(1.02))


def test_fundamentals_recovers_planted_wage_coefficient_and_lag():
    long, macro_tbl = _annual(n=200)
    d = macro.annual_frame(long, macro_tbl)
    rng = np.random.default_rng(4)
    d["price_growth_real_pct"] = 1.5 * d["wage_growth_real_pct"].shift(1) + rng.normal(
        0, 0.3, len(d)
    )
    lead = macro.fundamentals(d, ["wage_growth_real_pct"], lag=1)
    assert lead.loc["wage_growth_real_pct", "coef"] == pytest.approx(1.5, abs=0.1)
    assert lead["n"].iloc[0] == len(d) - 2  # first year has no growth, the lag drops another
    same_year = macro.fundamentals(d, ["wage_growth_real_pct"])
    assert abs(same_year.loc["wage_growth_real_pct", "coef"]) < 0.5


def test_fundamentals_drops_years_and_adds_own_lag():
    long, macro_tbl = _annual()
    d = macro.annual_frame(long, macro_tbl)
    base = macro.fundamentals(d, ["wage_growth_real_pct"])
    fewer = macro.fundamentals(d, ["wage_growth_real_pct"], drop_years=(2000, 2001))
    assert fewer["n"].iloc[0] == base["n"].iloc[0] - 2
    assert "price_growth_lag" in macro.fundamentals(d, ["wage_growth_real_pct"], own_lag=True).index


def _rates(years, value):
    return pd.Series(value, index=pd.Index(years, name="year"), name="mortgage_rate_new_lt1y_pct")


def test_annual_rates_averages_months_by_year():
    m = pd.DataFrame({"year": [2020, 2020, 2021], "mortgage_rate_new_lt1y_pct": [1.0, 3.0, 5.0]})
    assert macro.annual_rates(m).to_dict() == {2020: 2.0, 2021: 5.0}


def test_financeable_price_is_scaled_to_the_price_on_average_and_tracks_wages():
    long, macro_tbl = _annual(n=30)
    d = macro.annual_frame(long, macro_tbl)
    d["hpi_nominal_b2015"] = d["compensation_per_employee_eur"] * 0.01  # price moves with wages
    f = macro.financeable_price(d, _rates(d.index, 3.0), base=(1995, 2024))
    assert f["gap_pct"].abs().max() == pytest.approx(0, abs=1e-9)  # constant rate, price ~ wage
    assert f.loc[2015, "payment_to_wage_b2015"] == pytest.approx(100)


def test_higher_rate_lowers_the_implied_price_and_opens_a_gap():
    long, macro_tbl = _annual(n=30)
    d = macro.annual_frame(long, macro_tbl)
    d["hpi_nominal_b2015"] = d["compensation_per_employee_eur"] * 0.01
    rate = _rates(d.index, 2.0)
    rate.loc[2010:] = 6.0
    f = macro.financeable_price(d, rate)
    assert f.loc[2012, "implied_price_b2015"] < f.loc[2005, "implied_price_b2015"]
    assert f.loc[2012, "gap_pct"] > f.loc[2005, "gap_pct"]


def test_price_change_parts_add_up_to_the_price_change():
    long, macro_tbl = _annual(n=30)
    d = macro.annual_frame(long, macro_tbl)
    rate = _rates(d.index, np.linspace(5, 2, len(d)))
    f = macro.financeable_price(d, rate)
    parts = macro.price_change_parts(f, 2000, 2012)
    assert parts["wages_pct"] + parts["rate_pct"] + parts["gap_pct"] == pytest.approx(
        parts["price_change_pct"]
    )
    assert parts["rate_pct"] > 0  # falling rate raises what can be financed
