import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import credit


def _inputs(n=40, seed=0):
    quarters = pd.date_range("2005-01-01", periods=n, freq="QS")
    rng = np.random.default_rng(seed)
    real = 100 * np.exp(np.cumsum(rng.normal(0.01, 0.02, n)))
    bis = pd.DataFrame(
        {"period_start": quarters, "hpi_real_b2010": real, "hpi_nominal_b2010": real * 1.25}
    )
    debt = pd.DataFrame(
        {
            "date": quarters + pd.offsets.QuarterEnd(0),
            "period_start": quarters,
            "year": quarters.year,
            "quarter": quarters.quarter,
            "housing_loans_stock_eur_m": 100_000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
            "housing_loans_gdp_pct": 60.0,
            "housing_loans_growth_pct": rng.normal(0, 2, n),
            "household_debt_stock_eur_m": 150_000.0,
            "household_debt_gdp_pct": 80.0,
            "household_debt_income_pct": np.linspace(110, 70, n),
        }
    )
    return bis, debt


def test_quarterly_frame_deflates_and_rebases_to_2010():
    bis, debt = _inputs()
    f = credit.quarterly_frame(bis, debt)
    assert len(f) == 40
    assert f["deflator_b2010"].iloc[0] == pytest.approx(1.25)
    assert f["housing_loans_real_eur_m"].iloc[0] == pytest.approx(
        debt["housing_loans_stock_eur_m"].iloc[0] / 1.25
    )
    base = f.index.year == credit.BASE_YEAR
    assert f.loc[base, "housing_loans_real_b2010"].mean() == pytest.approx(100)
    assert f.loc[base, "loans_per_price_b2010"].mean() == pytest.approx(100)


def test_quarterly_frame_keeps_only_common_quarters():
    bis, debt = _inputs()
    f = credit.quarterly_frame(bis.iloc[:30], debt.iloc[5:])
    assert len(f) == 25


def test_episodes_changes_between_window_quarters():
    bis, debt = _inputs()
    f = credit.quarterly_frame(bis, debt)
    e = credit.episodes(f, {"a": ("2006Q1", "2008Q1")}).loc["a"]
    a, b = f.loc["2006-01-01"], f.loc["2008-01-01"]
    assert e["real_price_change_pct"] == pytest.approx(
        100 * (b["hpi_real_b2010"] / a["hpi_real_b2010"] - 1)
    )
    assert e["loans_gdp_change_pp"] == pytest.approx(0.0)
    assert e["debt_income_start_pct"] == pytest.approx(a["household_debt_income_pct"])


def test_add_changes_uses_log_points_over_four_quarters():
    f = credit.quarterly_frame(*_inputs())
    c = credit.add_changes(f)
    assert c["growth_real_pct"].iloc[4] == pytest.approx(
        100 * np.log(f["hpi_real_b2010"].iloc[4] / f["hpi_real_b2010"].iloc[0])
    )
    assert c["debt_income_change_pp"].iloc[4] == pytest.approx(
        f["household_debt_income_pct"].iloc[4] - f["household_debt_income_pct"].iloc[0]
    )


def test_credit_timing_recovers_a_planted_effect_and_lead_placebo():
    rng = np.random.default_rng(1)
    n = 200
    idx = pd.date_range("1970-01-01", periods=n, freq="QS")
    d = pd.DataFrame({"housing_loans_growth_pct": rng.normal(0, 3, n)}, index=idx)
    d["growth_real_pct"] = 1.5 * d["housing_loans_growth_pct"].shift(4) + rng.normal(0, 0.5, n)
    out = credit.credit_timing(d)
    assert out["coef_pct_per_pp"] == pytest.approx(1.5, abs=0.2)
    placebo = credit.credit_timing(d, lead=True)
    assert abs(placebo["lead_coef_pct_per_pp"]) < 0.4
    assert abs(credit.credit_timing(d, lag=0)["coef_pct_per_pp"]) < 0.4


def test_rate_timing_default_regressor_unchanged():
    from pthousing.analysis import macro

    rng = np.random.default_rng(2)
    n = 120
    idx = pd.date_range("1990-01-01", periods=n, freq="QS")
    d = pd.DataFrame({"rate_change_pp": rng.normal(size=n)}, index=idx)
    d["growth_real_pct"] = -2 * d["rate_change_pp"].shift(4) + rng.normal(0, 0.3, n)
    assert macro.rate_timing(d)["coef_pct_per_pp"] == pytest.approx(-2, abs=0.2)
    explicit = macro.rate_timing(d, x_col="rate_change_pp")
    assert explicit["coef_pct_per_pp"] == macro.rate_timing(d)["coef_pct_per_pp"]
