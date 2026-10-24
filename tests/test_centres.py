import numpy as np
import pandas as pd
import pytest
from libpysal import weights

from pthousing.analysis import centres


def _line_weights(n):
    """A chain 0-1-2-...-(n-1) as weights (codes '00', '01', ...)."""
    ids = [f"{i:02d}" for i in range(n)]
    neighbours = {ids[i]: [ids[j] for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)}
    return weights.W(neighbours, silence_warnings=True)


def test_find_centres_orders_by_population_and_uses_the_threshold():
    pop = pd.Series({"a": 150_000, "b": 99_999, "c": 100_000, "d": 500_000})
    assert centres.find_centres(pop) == ["d", "a", "c"]
    assert centres.find_centres(pop, minimum=200_000) == ["d"]


def test_steps_from_centre_counts_borders_to_the_nearest_centre():
    w = _line_weights(7)
    steps = centres.steps_from_centre(w, ["01", "05"])
    assert steps.to_dict() == {"00": 1, "01": 0, "02": 1, "03": 2, "04": 1, "05": 0, "06": 1}


def test_steps_are_nan_for_components_without_a_centre():
    w = weights.W({"a": ["b"], "b": ["a"], "x": ["y"], "y": ["x"]}, silence_warnings=True)
    steps = centres.steps_from_centre(w, ["a"])
    assert steps["b"] == 1
    assert steps[["x", "y"]].isna().all()


def test_gradient_pools_the_far_distances_and_counts():
    steps = pd.Series({"a": 0, "b": 1, "c": 1, "d": 4, "e": 6, "f": np.nan}, dtype=float)
    values = pd.Series({"a": 100.0, "b": 60.0, "c": 40.0, "d": 20.0, "e": 30.0, "f": 5.0})
    out = centres.gradient({"price": values}, steps, cap=4)
    assert out.loc[("price", 0.0), "median"] == 100
    assert out.loc[("price", 1.0), "median"] == 50
    assert out.loc[("price", 4.0), "municipalities_n"] == 2  # distances 4 and 6 pooled
    assert out.loc[("price", 4.0), "median"] == 25
    assert out["municipalities_n"].sum() == 5  # the municipality without a distance is left out


def test_gradient_within_regions_recovers_a_planted_gap_with_region_effects():
    rng = np.random.default_rng(0)
    rows = []
    for r in range(6):
        base = rng.normal(0, 30)  # region effect in log points
        for steps in (0, 1, 1, 2, 2, 3, 3, 3):
            log_change = base + 80 - 15 * min(steps, 3) + rng.normal(0, 2)
            rows.append(
                {"steps": float(steps), "region": f"r{r}", "y": 100 * np.expm1(log_change / 100)}
            )
    d = pd.DataFrame(rows)
    d.index = [f"{i:03d}" for i in range(len(d))]
    out = centres.gradient_within_regions(d["y"], d["steps"], d["region"], cap=3)
    assert out.loc[1, "diff_log_points"] == pytest.approx(-15, abs=3)
    assert out.loc[3, "diff_log_points"] == pytest.approx(-45, abs=3)
    assert out["regions_with_centre_n"].iloc[0] == 6
    assert out.loc[3, "ci_low"] < out.loc[3, "diff_log_points"] < out.loc[3, "ci_high"]


def test_core_vs_rest_compares_each_core_with_the_rest_of_its_area():
    outcome = pd.Series(
        {"L": 70.0, "a": 100.0, "b": 120.0, "P": 120.0, "c": 80.0, "d": 60.0, "z": 500.0}
    )
    area = pd.Series(
        {"L": "lis", "a": "lis", "b": "lis", "P": "por", "c": "por", "d": "por", "z": np.nan}
    )
    out = centres.core_vs_rest(outcome, ["L", "P"], area)
    assert out.loc["L", "rest_median"] == 110
    assert out.loc["L", "share_of_rest_above_core_pct"] == 100
    assert out.loc["P", "rest_median"] == 70
    assert out.loc["P", "share_of_rest_above_core_pct"] == 0
    assert out.loc["P", "rest_n"] == 2
