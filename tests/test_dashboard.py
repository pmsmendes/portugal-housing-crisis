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


def test_value_text_carries_the_unit_for_levels_and_changes():
    pti = D.INDICATORS["pti_years"]
    assert D.value_text(pti, 9.46) == "9.5 years of income"
    assert D.value_text(pti, 1.44, "diff") == "+1.4 years of income"
    assert D.value_text(pti, 25.2, "pct") == "+25%"
    burden = D.INDICATORS["mortgage_burden_pct"]
    assert D.value_text(burden, 45.3) == "45% of income"
    assert D.value_text(burden, 17.2, "diff") == "+17 pp"


def test_every_indicator_has_a_short_unit():
    assert set(D.INDICATORS) <= set(D.SHORT_UNITS)


def test_group_guide_names_every_class_in_the_typology(panel):
    for by, guide in D.GROUP_GUIDE.items():
        stored = set(panel[by].dropna()) - {"unknown"}
        assert stored <= set(guide["classes"]), by
        assert guide["title"] and guide["intro"]
        assert D.class_label(by, next(iter(guide["classes"]))) != ""


def test_group_counts_match_the_lines_of_group_trend(panel):
    for by in D.GROUP_GUIDE:
        trend = D.group_trend(panel, "pti_years", by)
        counts = D.group_counts(panel, "pti_years", by)
        assert list(trend.columns) == [
            c for c in D.GROUP_GUIDE[by]["classes"] if c in trend.columns
        ]
        assert set(trend.columns) <= set(counts.index)
        assert (counts[trend.columns] > 0).all()


def test_segment_label_reads_as_words():
    assert D.segment_label("coast / urban") == "Coastal, urban"
    assert D.segment_label("inland / intermediate") == "Inland, intermediate"
    assert D.segment_label("somewhere else") == "somewhere else"
