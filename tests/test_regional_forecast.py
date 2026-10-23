import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import regional_forecast as R


def _synthetic(n_per_region=8, years=range(2016, 2025), seed=0):
    """Two regions growing at 5% and 1% a year with noise; log price-to-income by municipality."""
    rng = np.random.default_rng(seed)
    rows, region = {}, {}
    for r, slope in (("A", 0.05), ("B", 0.01)):
        for i in range(n_per_region):
            code = f"{r}{i:02d}"
            level = 2.0 + 0.1 * i
            rows[code] = [level + slope * (y - 2016) + rng.normal(0, 0.03) for y in years]
            region[code] = r
    y = pd.DataFrame.from_dict(rows, orient="index", columns=list(years))
    groups = pd.DataFrame(
        {
            "region": pd.Series(region),
            "segment": pd.Series(region),
            "muni_name": y.index,
            "district": "d",
        }
    )
    return y, groups


def test_line_fit_recovers_slope_and_needs_min_obs():
    y = pd.DataFrame(
        [[1.0, 1.5, 2.0, 2.5], [np.nan, np.nan, 1.0, 2.0]], columns=[2020, 2021, 2022, 2023]
    )
    fit = R.line_fit(y)
    assert fit["slope"].iloc[0] == pytest.approx(0.5)
    assert fit["slope"].iloc[0] > 0 and np.isnan(fit["slope"].iloc[1])  # two points: too few


def test_last_valid_skips_missing_final_year():
    y = pd.DataFrame([[1.0, 2.0, np.nan]], columns=[2020, 2021, 2022])
    assert R.last_valid(y).iloc[0] == 2.0


def test_forecasts_use_only_years_up_to_the_origin():
    y, groups = _synthetic()
    changed = y.copy()
    changed.loc[:, 2022:] = 99.0  # the future must not matter
    a = R.forecast_all(y, groups, 2021, 1)
    b = R.forecast_all(changed, groups, 2021, 1)
    pd.testing.assert_frame_equal(a, b)


def test_region_trend_separates_fast_and_slow_regions():
    y, groups = _synthetic()
    fc = R.forecast_all(y, groups, 2022, 2)
    gain = (fc["region_trend"] - fc["last"]).groupby(groups["region"]).median()
    assert gain["A"] > gain["B"]


def test_backtest_scores_every_method_on_the_same_municipalities():
    y, groups = _synthetic()
    bt = R.backtest(y, groups)
    counts = bt.groupby(["origin", "h", "method"])["muni_code"].nunique().unstack()
    assert (counts.nunique(axis=1) == 1).all()
    assert set(bt["method"]) == set(R.METHODS)
    assert bt["origin"].max() + bt["h"].max() <= 2025  # no target beyond the data
    assert (bt[bt["origin"] == 2023]["h"] == 1).all()


def test_trend_beats_naive_when_regions_trend_differently():
    y, groups = _synthetic()
    acc = R.accuracy(R.backtest(y, groups)).set_index(["method", "h"])
    assert acc.loc[("region_trend", 2), "rmse"] < acc.loc[("naive", 2), "rmse"]
    assert acc.loc[("region_trend", 2), "spearman"] > 0.5
    assert np.isnan(acc.loc[("naive", 2), "spearman"])  # no ranking: it predicts no change


def test_select_method_prefers_the_simpler_one_within_one_percent():
    rows = [{"method": m, "h": 1, "rmse": 0.10} for m in R.METHODS]
    rows[-1]["rmse"] = 0.0995  # the most complex is 0.5% better: not enough
    assert R.select_method(pd.DataFrame(rows)) == R.METHODS[0]
    rows[-1]["rmse"] = 0.08
    assert R.select_method(pd.DataFrame(rows)) == R.METHODS[-1]


def test_group_backtest_drops_small_groups_and_aggregates_by_median():
    y, groups = _synthetic(n_per_region=2)  # two municipalities per region: below MIN_REGION
    assert R.group_backtest(R.backtest(y, groups), groups).empty
    y, groups = _synthetic()
    gb = R.group_backtest(R.backtest(y, groups), groups)
    assert set(gb["group"]) == {"A", "B"}


def test_intervals_and_coverage_on_symmetric_errors():
    rng = np.random.default_rng(1)
    errors = pd.DataFrame(
        {
            "h": 1,
            "origin": np.repeat([2019, 2020, 2021, 2022], 500),
            "error": rng.normal(0, 0.1, 2000),
        }
    )
    q = R.error_quantiles(errors)
    assert q.loc[1, 0.1] == pytest.approx(-0.128, abs=0.02)
    cover = R.interval_coverage(errors)["coverage"].mean()
    assert cover == pytest.approx(0.8, abs=0.04)


def test_outlook_summary_is_relative_to_the_median_municipality():
    y, groups = _synthetic()
    bt = R.backtest(y, groups)
    out = R.outlook(y, groups, "region_trend")
    assert out["year"].max() == 2026 and set(out["h"]) == {1, 2}
    rel = R.relative_errors(bt, "region_trend", groups, "region")
    table = R.outlook_summary(out, "region", 2, rel)
    top = table.iloc[0]
    assert top["region"] == "A" and top["relative"] > 0 > table.iloc[-1]["relative"]
    assert (table["relative_lo80"] <= table["relative"]).all()
    assert (table["relative"] <= table["relative_hi80"]).all()
