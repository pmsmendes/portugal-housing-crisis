import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import forecasting as fc


def _series(values, start="2010Q1"):
    return pd.Series(
        np.asarray(values, dtype=float), index=pd.period_range(start, periods=len(values), freq="Q")
    )


def _walk(n=60, drift=0.01, sd=0.01, seed=0):
    rng = np.random.default_rng(seed)
    return _series(np.cumsum(rng.normal(drift, sd, n)))


def test_naive_repeats_the_last_value_and_widens_with_the_horizon():
    y = _walk()
    out = fc.naive(y, 6)
    assert (out["mean"] == y.iloc[-1]).all()
    assert out.index[0] == y.index[-1] + 1
    width = out["hi95"] - out["lo95"]
    assert width.is_monotonic_increasing and (out["lo80"] > out["lo95"]).all()
    assert width.iloc[3] == pytest.approx(width.iloc[0] * 2)  # random-walk sd grows with sqrt(h)


def test_seasonal_naive_repeats_the_last_year_exactly():
    pattern = np.array([1.0, 3.0, 2.0, 5.0])
    y = _series(np.tile(pattern, 10))
    out = fc.seasonal_naive(y, 8)
    assert out["mean"].to_numpy() == pytest.approx(np.tile(pattern, 2))


def test_drift_extrapolates_the_average_change():
    y = _series(0.5 + 0.02 * np.arange(40))
    out = fc.drift(y, 4)
    assert out["mean"].to_numpy() == pytest.approx(y.iloc[-1] + 0.02 * np.arange(1, 5))


def test_ets_and_arima_follow_a_trend_and_have_ordered_intervals():
    y = _walk(60, drift=0.02, sd=0.005, seed=1)
    for fn in (fc.ets, fc.arima):
        out = fn(y, 8)
        assert out["mean"].iloc[-1] > y.iloc[-1] + 0.05  # the drift of 0.02 a quarter is picked up
        assert (out["lo95"] < out["lo80"]).all() and (out["lo80"] < out["mean"]).all()
        assert (out["mean"] < out["hi80"]).all() and (out["hi80"] < out["hi95"]).all()
        assert out.index[0] == y.index[-1] + 1


def test_ets_picks_a_seasonal_form_for_a_clear_seasonal_series():
    rng = np.random.default_rng(2)
    y = _series(np.tile([0.0, 0.3, -0.2, 0.1], 15) + np.cumsum(rng.normal(0, 0.01, 60)))
    _, spec = fc.ets(y, 4, return_spec=True)
    assert spec["seasonal"] == "add"


def test_rolling_origin_never_uses_the_target_or_later_data():
    y = _walk(50, seed=3)
    methods = {"naive": fc.naive, "drift": fc.drift}
    base = fc.rolling_origin(y, methods, initial=30, horizon=4)
    changed = y.copy()
    changed.iloc[40:] += 5.0  # a break from the 41st quarter on
    shifted = fc.rolling_origin(changed, methods, initial=30, horizon=4)
    early = (
        base["origin"] < y.index[39]
    ).to_numpy()  # origins whose training data end before the break
    cols = ["method", "origin", "h", "mean", "lo95"]
    pd.testing.assert_frame_equal(
        base.loc[early, cols].reset_index(drop=True),
        shifted.loc[early, cols].reset_index(drop=True),
    )


def test_rolling_origin_keeps_only_observed_targets_and_counts_origins():
    y = _walk(40, seed=4)
    res = fc.rolling_origin(y, {"naive": fc.naive}, initial=30, horizon=4)
    assert res["actual"].notna().all()
    assert (res["target"] == res["origin"] + res["h"]).all()
    # origins after 30..39 observations: h=1 has 10 origins, h=4 has 7
    counts = res.groupby("h").size()
    assert counts[1] == 10 and counts[4] == 7


def test_accuracy_metrics_on_a_hand_computed_case():
    res = pd.DataFrame(
        {
            "method": "m", "h": 1, "actual": [1.0, 2.0, 3.0, 4.0],
            "mean": [1.5, 2.0, 2.0, 4.0], "lo80": [1.0, 1.5, 2.5, 3.0], "hi80": [2.0, 2.5, 3.5, 5.0],
            "lo95": [0.5, 1.0, 2.0, 2.5], "hi95": [2.5, 3.0, 4.0, 5.5],
        }
    )  # fmt: skip
    out = fc.accuracy(res, scale=0.5).iloc[0]
    assert out["rmse"] == pytest.approx(np.sqrt((0.25 + 0 + 1 + 0) / 4))
    assert out["mae"] == pytest.approx(0.375) and out["mase"] == pytest.approx(0.75)
    assert out["bias"] == pytest.approx((-0.5 + 0 + 1 + 0) / 4)
    # inside the 80% interval: 1.0 (on the edge), 2.0, 3.0, 4.0 -> all four; check the narrower miss below
    assert out["coverage80"] == pytest.approx(1.0)
    assert out["coverage95"] == pytest.approx(1.0)


def test_coverage_counts_actuals_outside_the_interval():
    res = pd.DataFrame(
        {
            "method": "m", "h": 1, "actual": [0.0, 1.5, 3.0, 1.5],
            "mean": 1.5, "lo80": 1.0, "hi80": 2.0, "lo95": 0.5, "hi95": 2.5,
        }
    )  # fmt: skip
    out = fc.accuracy(res, scale=1.0).iloc[0]
    assert out["coverage80"] == pytest.approx(0.5) and out["coverage95"] == pytest.approx(0.5)


def test_interval_score_penalises_misses_by_two_over_alpha():
    assert fc.interval_score(1.5, 1.0, 2.0, 0.2) == pytest.approx(1.0)
    assert fc.interval_score(3.0, 1.0, 2.0, 0.2) == pytest.approx(1.0 + 10 * 1.0)


def test_relative_to_divides_by_the_baseline_at_each_horizon():
    table = pd.DataFrame(
        {"method": ["naive", "ets"] * 2, "h": [1, 1, 2, 2], "rmse": [0.1, 0.05, 0.2, 0.1]}
    )
    rel = fc.relative_to(table, "naive")
    assert rel.loc[1, "ets"] == pytest.approx(0.5) and (rel["naive"] == 1).all()


def test_intervals_cover_close_to_nominal_on_a_random_walk():
    methods = {"naive": fc.naive, "drift": fc.drift}
    res = [
        fc.rolling_origin(_walk(70, seed=seed), methods, initial=40, horizon=4)
        for seed in range(15)
    ]
    acc = fc.accuracy(pd.concat(res), scale=0.01, by="h").query("method == 'drift'")
    assert acc["coverage80"].between(0.7, 0.9).all() and acc["coverage95"].between(0.9, 0.99).all()


# ---- validation schemes -----------------------------------------------------------------------------


def test_direct_design_rows_use_only_the_past_and_a_target_h_ahead():
    y = _series(np.arange(30.0) ** 1.5)
    X, target, t = fc.direct_design(y, h=3, lags=4)
    v = y.to_numpy()
    assert t[0] == 4 and t[-1] == len(y) - 1 - 3
    assert target == pytest.approx(v[t + 3] - v[t])
    assert X[:, 1] == pytest.approx(v[t] - v[t - 1])  # first lag is the latest change
    assert (X[:, 0] == 1).all()


def test_rolling_origin_scheme_never_trains_on_a_target_unknown_at_the_origin():
    # a series that breaks upward after quarter 40: a model trained only on the past predicts the old drift
    y = _series(np.r_[np.arange(40) * 0.01, 0.4 + np.arange(30) * 0.05])
    out = fc.validation_schemes(y, h=4, lags=2, initial=30, repeats=2)
    roll = out[out["scheme"] == "rolling origin"]
    assert roll["t"].min() == 29
    just_after = roll[roll["t"].between(40, 41)]
    assert (just_after["pred"] < just_after["actual"]).all()  # the new regime is under-predicted


def test_random_folds_look_better_than_rolling_origin_after_a_regime_change():
    y = _series(np.r_[np.arange(40) * 0.01, 0.4 + np.arange(30) * 0.05])
    scores = fc.scheme_scores(
        fc.validation_schemes(y, h=4, lags=2, initial=30, repeats=5)
    ).set_index("scheme")
    assert scores.loc["random folds", "rmse"] < scores.loc["rolling origin", "rmse"]
    assert (
        scores.loc["random folds", "n"] == scores.loc["rolling origin", "n"]
    )  # scored on the same rows


def test_all_schemes_score_the_same_rows_and_return_finite_values():
    rng = np.random.default_rng(1)
    y = _series(np.cumsum(rng.normal(0.01, 0.02, 80)))
    out = fc.validation_schemes(y, h=4, lags=4, initial=30, repeats=3)
    assert set(out["scheme"]) == set(fc.SCHEMES)
    assert out.groupby("scheme")["t"].apply(lambda s: s.min() >= 29).all()
    assert out.groupby("scheme")["t"].nunique().nunique() == 1
    assert np.isfinite(out[["actual", "pred"]].to_numpy()).all()
