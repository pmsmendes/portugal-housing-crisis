import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import construction


def _inputs():
    months = pd.date_range("2013-01-01", "2026-05-01", freq="MS")  # 2026 incomplete
    n = len(months)
    rows = []
    for factor, growth in (("total", 1.03), ("materials", 1.02), ("labour", 1.04)):
        rows.append(
            pd.DataFrame(
                {
                    "period_start": months,
                    "year": months.year,
                    "factor": factor,
                    "construction_cost_b2021": 100 * growth ** (np.arange(n) / 12 - 8),
                }
            )
        )
    costs = pd.concat(rows, ignore_index=True)
    years = np.arange(2013, 2026)
    cpi = pd.DataFrame(
        {"year": np.arange(2010, 2026), "cpi_index_b2025": 80 + 1.25 * np.arange(16)}
    )
    long = pd.DataFrame(
        {
            "year": years,
            "hpi_nominal_b2015": 100 * 1.08 ** (years - 2015),
            "hpi_real_b2015": 100 * 1.06 ** (years - 2015),
        }
    )
    flows = pd.DataFrame(
        {"licensed_n": 10_000.0 * 1.05 ** np.arange(13), "completed_n": 8_000.0}, index=years
    ).rename_axis("year")
    macro = pd.DataFrame(
        {"year": years, "compensation_per_employee_eur": 20_000.0 * 1.03 ** np.arange(13)}
    )
    return costs, cpi, long, flows, macro


def test_annual_costs_keeps_only_complete_years():
    costs, *_ = _inputs()
    out = construction.annual_costs(costs)
    assert out.index.max() == 2025 and out.index.min() == 2013
    assert list(out.columns) == ["total", "materials", "labour"]


def test_annual_frame_rebases_to_2015_and_splits_the_price_into_cost_and_ratio():
    f = construction.annual_frame(*_inputs())
    for col in ("cost_total_b2015", "cost_labour_b2015", "price_to_cost_b2015", "wage_b2015"):
        assert f.loc[2015, col] == pytest.approx(100)
    assert f.loc[2015, "cost_real_b2015"] == pytest.approx(100)
    ratio = f["hpi_nominal_b2015"] / f["cost_total_b2015"]
    rebased = f["price_to_cost_b2015"] / ratio
    assert np.allclose(rebased, rebased.iloc[0])  # the same ratio, rebased
    assert f.loc[2025, "cost_real_b2015"] < f.loc[2025, "cost_total_b2015"]  # CPI rose


def test_cost_shares_add_up_to_the_price_change():
    f = construction.annual_frame(*_inputs())
    s = construction.cost_shares(f, {"w": (2013, 2025)}).loc["w"]
    assert s["cost_log_pts"] + s["ratio_log_pts"] == pytest.approx(s["price_log_pts"])
    assert 0 < s["cost_part_pct"] < 100


def test_cost_shares_has_no_share_when_the_price_fell():
    f = construction.annual_frame(*_inputs())
    f.loc[2025, "hpi_nominal_b2015"] = 50.0
    assert np.isnan(construction.cost_shares(f, {"w": (2013, 2025)}).loc["w", "cost_part_pct"])


def test_changes_and_mean_flows_by_window():
    f = construction.annual_frame(*_inputs())
    ch = construction.changes(f, {"w": (2015, 2025)}, ["hpi_nominal_b2015"])
    assert ch.loc["w", "hpi_nominal_b2015"] == pytest.approx(100 * (1.08**10 - 1))
    mf = construction.mean_flows(f, {"w": (2013, 2014)})
    assert mf.loc["w", "completed_n"] == 8_000


def test_supply_response_finds_price_and_not_cost():
    rng = np.random.default_rng(1)
    years = np.arange(1999, 2026)
    price = np.cumprod(1 + rng.normal(0.02, 0.06, len(years)))
    cost = np.cumprod(1 + rng.normal(0.01, 0.03, len(years)))
    dprice = np.diff(np.log(price), prepend=np.nan)
    licensed = 10_000 * np.exp(
        np.nancumsum(3 * np.roll(dprice, 1) + rng.normal(0, 0.02, len(years)))
    )
    frame = pd.DataFrame(
        {"hpi_real_b2015": price, "cost_real_b2015": cost, "licensed_n": licensed}, index=years
    )
    out = construction.supply_response(frame, "licensed_n", lag=1)
    assert out.loc["dlog_price", "coef"] == pytest.approx(3, abs=0.8)
    assert abs(out.loc["dlog_cost", "coef"]) < 2
    assert out["n"].iloc[0] >= 20
    dropped = construction.supply_response(frame, "licensed_n", lag=1, drop_years=(2008, 2009))
    assert dropped["n"].iloc[0] == out["n"].iloc[0] - 2


def test_ratio_and_licensing_reports_both_correlations():
    f = construction.annual_frame(*_inputs())
    out = construction.ratio_and_licensing(f)
    assert out["n_levels"] == 12 and out["n_changes"] == 11
