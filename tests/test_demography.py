import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import demography as dem


def _panel():
    rows = []
    for muni, density, district, pop, f in [
        ("0001", "urban", "A", 1000, (50, 150)),
        ("0002", "urban", "B", 500, (10, 60)),
        ("0003", "rural", "B", 500, (5, 15)),
    ]:
        for year, count in zip((2020, 2021), f, strict=True):
            rows.append(
                {
                    "muni_code": muni,
                    "year": year,
                    "density_class": density,
                    "district": district,
                    "population_n": pop + (100 if year == 2021 else 0),
                    "foreign_residents_n": count,
                }
            )
    rows.append(
        {"muni_code": "0001", "year": 2022, "density_class": "urban", "district": "A",
         "population_n": 1200, "foreign_residents_n": np.nan}
    )  # fmt: skip
    return pd.DataFrame(rows)


def _aima():
    rows = []
    for muni, br, gb in [("0001", 100, 0), ("0002", 40, 20), ("0003", 10, 5)]:
        for nat, n in (("br", br), ("gb", gb)):
            rows.append(
                {"muni_code": muni, "year": 2021, "nationality": nat, "foreign_residents_n": n}
            )
        rows.append(
            {
                "muni_code": muni,
                "year": 2021,
                "nationality": "total",
                "foreign_residents_n": br + gb,
            }
        )
    return pd.DataFrame(rows)


def test_national_totals_ignore_years_without_a_count():
    t = dem.national_totals(_panel())
    assert list(t.index) == [2020, 2021]
    assert t.loc[2021, "foreign_residents_n"] == 225
    assert t.loc[2021, "foreign_share_pct"] == pytest.approx(100 * 225 / 2300)


def test_nationality_totals_put_the_total_last():
    t = dem.nationality_totals(_aima())
    assert list(t.columns) == ["br", "gb", "total"]
    assert t.loc[2021, "total"] == t.loc[2021, ["br", "gb"]].sum()


def test_group_distribution_shares_add_to_100_and_compare_with_population():
    g = dem.group_distribution(_panel(), 2021, "density_class")
    assert g["foreign_share_of_total_pct"].sum() == pytest.approx(100)
    assert g["population_share_of_total_pct"].sum() == pytest.approx(100)
    assert list(g.index) == ["urban", "rural"]  # sorted by foreign residents
    assert (
        g.loc["urban", "foreign_share_of_total_pct"]
        > g.loc["urban", "population_share_of_total_pct"]
    )
    assert g.loc["rural", "foreign_share_pct"] == pytest.approx(100 * 15 / 600)


def test_concentration_cumulates_the_municipalities_with_most_foreign_residents():
    c = dem.concentration(_panel(), 2021, ns=(1, 3))
    assert c["foreign_share_of_total_pct"].tolist() == pytest.approx([100 * 150 / 225, 100.0])
    assert c["population_share_of_total_pct"].iloc[1] == pytest.approx(100.0)


def test_nationality_location_rows_add_to_100_and_the_rest_is_other():
    loc = dem.nationality_location(_aima(), _panel(), 2021, "district", ["A"])
    assert list(loc.columns) == ["A", "other"]
    assert loc.sum(axis=1).tolist() == pytest.approx([100.0] * 3)
    assert loc.loc["br", "A"] == pytest.approx(100 * 100 / 150)
    assert loc.loc["gb", "A"] == pytest.approx(0.0)


def test_growth_contribution_splits_the_population_change():
    s = dem.growth_contribution(_panel(), 2020, 2021)
    assert s["population_change_n"] == 300
    assert s["foreign_change_n"] == 160
    assert s["other_change_n"] == 140
    assert s["foreign_share_of_change_pct"] == pytest.approx(100 * 160 / 300)


def test_growth_contribution_share_is_missing_when_the_population_fell():
    panel = _panel()
    panel.loc[(panel["year"] == 2021), "population_n"] = 100
    assert np.isnan(dem.growth_contribution(panel, 2020, 2021)["foreign_share_of_change_pct"])
