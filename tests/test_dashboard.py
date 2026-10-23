import numpy as np
import pandas as pd
import pytest

from pthousing.viz import dashboard as D


@pytest.fixture(scope="module")
def panel():
    return D.load_panel()


def test_every_indicator_column_is_in_the_panel(panel):
    assert set(D.INDICATORS) <= set(panel.columns)


def test_years_with_data_requires_enough_municipalities(panel):
    years = D.years_with_data(panel, "pti_years")
    assert years == sorted(years)
    assert (
        panel[panel["year"].isin(years)].groupby("year")["pti_years"].count() >= D.MIN_MUNIS
    ).all()
    assert 2008 not in years


def test_geometry_covers_every_municipality(panel):
    codes = {f["properties"]["muni_code"] for f in D.load_geometry()["features"]}
    assert codes == set(panel["muni_code"])


def test_map_frame_level_and_change(panel):
    level = D.map_frame(panel, "pti_years", 2024)
    assert len(level) == panel["muni_code"].nunique()
    change = D.map_frame(panel, "pti_years", 2024, since=2016)
    both = panel.pivot(index="muni_code", columns="year", values="pti_years")
    expected = (both[2024] - both[2016]).reindex(change["muni_code"]).to_numpy()
    np.testing.assert_allclose(change["value"].to_numpy(), expected)
    pct = D.map_frame(panel, "pti_years", 2024, since=2016, relative=True)
    assert pct["value"].median() > 0  # affordability worsened in the median municipality


def test_colour_scale_puts_red_on_the_bad_direction():
    up, mid = D.colour_scale("worse_high", change=True)
    down, _ = D.colour_scale("better_high", change=True)
    assert mid == 0.0 and down == up[::-1]
    levels, mid_level = D.colour_scale("worse_high", change=False)
    assert mid_level is None and len(levels) == 6


def test_group_trend_uses_a_fixed_sample(panel):
    trend = D.group_trend(panel, "pti_years", "coast_class")
    assert not trend.isna().any().any()
    assert "unknown" not in trend.columns


def test_driver_frame_is_mainland_only(panel):
    d = D.driver_frame(panel)
    assert set(d["muni_code"]) <= set(panel[panel["territory"] == "continente"]["muni_code"])
    assert d["pti_change_pct"].notna().all()
    assert set(D.DRIVERS) <= set(d.columns)


def test_fit_line_recovers_a_slope():
    x = pd.Series(np.arange(1, 51, dtype=float))
    fit = D.fit_line(x, 3 * x + 2)
    assert fit["r"] == pytest.approx(1.0)
    assert fit["y"][0] == pytest.approx(3 * fit["x"][0] + 2)
    assert D.fit_line(x, np.log10(x), log_x=True)["r"] == pytest.approx(1.0)
