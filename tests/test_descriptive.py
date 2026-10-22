import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import descriptive as d
from pthousing.features import affordability as aff


def _df():
    return pd.DataFrame(
        {
            "muni_code": ["a", "b", "c", "a", "b", "c"],
            "year": [2020, 2020, 2020, 2021, 2021, 2021],
            "x": [1.0, 2.0, 3.0, 2.0, np.nan, 6.0],
        }
    )


def test_yearly_quantiles_ignore_missing_and_count_municipalities():
    q = d.yearly_quantiles(_df(), "x")
    assert q.loc[2020, ["q10", "q50", "q90", "n"]].tolist() == pytest.approx([1.2, 2.0, 2.8, 3])
    assert q.loc[2021, "n"] == 2 and q.loc[2021, "q50"] == pytest.approx(4.0)


def test_share_above_uses_only_municipalities_with_a_value():
    s = d.share_above(_df(), "x", 2.5)
    assert s.loc[2020, "share"] == pytest.approx(1 / 3) and s.loc[2021, "share"] == pytest.approx(
        0.5
    )
    assert s.loc[2021, "n"] == 2


def test_balanced_sample_keeps_only_municipalities_complete_in_every_year():
    out = d.balanced_sample(_df(), ["x"], [2020, 2021])
    assert sorted(out["muni_code"].unique()) == ["a", "c"] and len(out) == 4


def test_rebase_gives_100_in_the_base_year():
    t = pd.DataFrame({"p": [50.0, 100.0, 150.0]}, index=[2019, 2020, 2021])
    assert d.rebase(t, 2020)["p"].tolist() == [50.0, 100.0, 150.0]
    assert d.rebase(t, 2019)["p"].tolist() == [100.0, 200.0, 300.0]


def test_change_diff_and_pct_with_missing_year():
    diff = d.change(_df(), "x", 2020, 2021)
    assert diff["a"] == 1.0 and diff["c"] == 3.0 and np.isnan(diff["b"])
    pct = d.change(_df(), "x", 2020, 2021, kind="pct")
    assert pct["a"] == pytest.approx(100.0)
    with pytest.raises(ValueError):
        d.change(_df(), "x", 2020, 2021, kind="log")


def test_burden_at_fixed_rate_uses_the_rate_of_the_chosen_year():
    panel = pd.DataFrame(
        {
            "year": [2016, 2024],
            "price_sqm_eur": [1000.0, 2000.0],
            "dwelling_area_sqm": [100.0, 100.0],
            "income_median_eur": [10_000.0, 10_000.0],
            "mortgage_rate_new_lt1y_pct": [2.0, 5.0],
        }
    )
    fixed = d.burden_at_fixed_rate(panel, 2016)
    actual = aff.mortgage_burden_pct(
        panel["price_sqm_eur"],
        100.0,
        panel["income_median_eur"],
        panel["mortgage_rate_new_lt1y_pct"],
    )
    assert fixed.iloc[0] == pytest.approx(actual.iloc[0])  # same rate in the chosen year
    assert fixed.iloc[1] < actual.iloc[1]  # a lower rate lowers the later burden


def test_ranking_and_group_median():
    df = pd.DataFrame(
        {
            "muni_code": ["a", "b", "c"], "year": 2024, "muni_name": list("ABC"), "district": "d",
            "pti_years": [5.0, 20.0, np.nan], "g": ["x", "x", "y"],
        }
    )  # fmt: skip
    top = d.ranking(df, 2024, ["pti_years"], by="pti_years", n=2)
    assert top["muni_name"].tolist() == ["B", "A"]
    assert d.group_median(df, "pti_years", "g").loc[2024, "x"] == pytest.approx(12.5)


def test_median_index_indexes_each_municipality_before_taking_the_median():
    df = pd.DataFrame(
        {
            "muni_code": ["a", "a", "b", "b", "c", "c"],
            "year": [2020, 2021] * 3,
            "x": [100.0, 110.0, 10.0, 12.0, 1000.0, 1100.0],  # +10%, +20%, +10%
        }
    )
    idx = d.median_index(df, ["x"], 2020)
    assert idx["x"].tolist() == pytest.approx([100.0, 110.0])  # median of 110, 120, 110


def _panel():
    rows = []
    for code, name, district, v16, v24 in (
        ("a", "A", "d1", 5.0, 9.0), ("b", "B", "d1", 7.0, 8.0), ("c", "C", "d2", 6.0, 20.0), ("d", "D", "d2", np.nan, 30.0),
    ):  # fmt: skip
        for year, v in ((2016, v16), (2024, v24)):
            rows.append(
                {"muni_code": code, "year": year, "muni_name": name, "district": district, "x": v}
            )
    return pd.DataFrame(rows)


def test_top_with_baseline_needs_both_years_and_sorts_by_the_end_value():
    top = d.top_with_baseline(_panel(), "x", 2016, 2024, n=2)
    assert top["muni_name"].tolist() == ["C", "A"]  # D has no 2016 value and is left out
    assert top.loc[0, ["start", "end"]].tolist() == [6.0, 20.0]


def test_district_summary_compares_the_same_municipalities_in_both_years():
    out = d.district_summary(_panel(), "x", 2016, 2024).set_index("district")
    assert out.loc["d1", ["median_2016", "median_2024", "municipalities_n"]].tolist() == [
        6.0,
        8.5,
        2,
    ]
    assert (
        out.loc["d2", "median_2024"] == 20.0 and out.loc["d2", "municipalities_n"] == 1
    )  # D dropped
    assert out.loc["d1", "change"] == pytest.approx(2.5)
    assert out.index.tolist() == ["d2", "d1"]  # sorted by the latest median


def _segment_panel():
    rows = []
    for code, pti0, pti1, price0, price1, inc0, inc1 in (
        ("0101", 10.0, 20.0, 1000.0, 2000.0, 10_000.0, 10_000.0),
        ("0102", 10.0, 15.0, 1000.0, 1500.0, 10_000.0, 10_000.0),
        ("0103", 8.0, 8.0, 1000.0, 1000.0, 10_000.0, 10_000.0),
        ("0104", 8.0, 9.6, 1000.0, 1200.0, 10_000.0, 10_000.0),
    ):
        for year, pti, price, income in ((2016, pti0, price0, inc0), (2024, pti1, price1, inc1)):
            rows.append({"muni_code": code, "year": year, "pti_years": pti,
                         "price_sqm_eur_real": price, "income_median_eur_real": income})  # fmt: skip
    return pd.DataFrame(rows)


def _segment_typology():
    return pd.DataFrame({"muni_code": ["0101", "0102", "0103", "0104"],
                         "coast_class": ["coast", "coast", "inland", "inland"]})  # fmt: skip


def test_segment_summary_reports_group_medians_and_changes():
    out = d.segment_summary(
        _segment_panel(), _segment_typology(), {"coast_class": ["coast", "inland"]}, 2016, 2024
    ).set_index("group")
    assert out.loc["coast", "municipalities_n"] == 2
    assert out.loc["coast", "pti_2016"] == 10.0 and out.loc["coast", "pti_2024"] == pytest.approx(
        17.5
    )
    assert out.loc["coast", "pti_change_pct"] == pytest.approx(75.0)  # median of +100% and +50%
    assert out.loc["inland", "pti_change_pct"] == pytest.approx(10.0)  # median of 0% and +20%
    assert out.loc["coast", "income_real_change_pct"] == pytest.approx(0.0)


def test_segment_summary_drops_municipalities_missing_either_year():
    panel = _segment_panel()
    panel.loc[(panel.muni_code == "0102") & (panel.year == 2024), "pti_years"] = float("nan")
    out = d.segment_summary(panel, _segment_typology(), {"coast_class": ["coast"]}, 2016, 2024)
    assert out["municipalities_n"].iloc[0] == 1 and out["pti_change_pct"].iloc[0] == pytest.approx(
        100.0
    )


def test_group_regression_recovers_group_differences_and_labels_terms():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"group": rng.choice(["a", "b", "c"], 300), "x": rng.normal(size=300)})
    df["y"] = (
        df["group"].map({"a": 0.0, "b": 1.0, "c": -2.0}) + 0.5 * df["x"] + rng.normal(0, 0.1, 300)
    )
    df["region"] = rng.choice(["r1", "r2"], 300)
    out = d.group_regression(
        df, "y", {"group": "a"}, controls=["x"], fixed_effects="region"
    ).set_index("term")
    assert out.loc["group: b (vs a)", "coef"] == pytest.approx(1.0, abs=0.05)
    assert out.loc["group: c (vs a)", "coef"] == pytest.approx(-2.0, abs=0.05)
    assert out.loc["x", "coef"] == pytest.approx(0.5, abs=0.05)
    assert not any("region" in term for term in out.index)
    assert out["n_obs"].iloc[0] == 300
