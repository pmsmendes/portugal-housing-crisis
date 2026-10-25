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


def _euro():
    return pd.DataFrame(
        {
            "year": [2019, 2020, 2021, 2022],
            "population_jan_n": [1000.0, 1010.0, 1000.0, 1100.0],
            "natural_change_n": [5.0, -10.0, -10.0, -5.0],
            "net_migration_n": [5.0, 0.0, 10.0, 105.0],
            "revision_n": [0.0, 0.0, 90.0, 0.0],
        }
    ).assign(population_change_n=lambda d: d["natural_change_n"] + d["net_migration_n"])


def test_national_balance_gives_rates_per_1000_and_total_change():
    b = dem.national_balance(_euro())
    assert b.loc[2022, "net_migration_per_1000"] == pytest.approx(105 / 1100 * 1000)
    assert b.loc[2021, "total_change_n"] == 90.0
    assert b.loc[2021, "revision_per_1000"] == pytest.approx(90.0)


def test_period_balance_sums_ranges_and_keeps_the_revision_apart():
    t = dem.period_balance(_euro(), [(2019, 2020), (2021, 2022)])
    assert t.loc["2019-2020", "natural_change_n"] == -5.0
    assert t.loc["2019-2020", "years_with_decline_n"] == 1
    assert t.loc["2021-2022", "revision_n"] == 90.0
    assert t.loc["2021-2022", "total_change_n"] == 190.0
    assert t.loc["2021-2022", "migration_share_of_change_pct"] == pytest.approx(100 * 115 / 190)
    assert np.isnan(
        t.loc["2019-2020", "migration_share_of_change_pct"]
    )  # the total is not positive


def _change():
    rows = []
    for muni, nat, mig in [
        ("0001", 10, 5),
        ("0002", -10, 30),
        ("0003", -10, 5),
        ("0004", 5, -10),
        ("0005", -5, -5),
    ]:
        for year in (2020, 2021):
            rows.append(
                {
                    "muni_code": muni,
                    "year": year,
                    "natural_increase_n": nat,
                    "net_migration_n": mig,
                    "population_change_n": nat + mig,
                }
            )
    rows.append(
        {
            "muni_code": "0001",
            "year": 2022,
            "natural_increase_n": 99,
            "net_migration_n": 99,
            "population_change_n": 198,
        }
    )
    return pd.DataFrame(rows)


def _pop_panel():
    rows = []
    for i, muni in enumerate(("0001", "0002", "0003", "0004", "0005")):
        for year in (2020, 2021):
            rows.append(
                {
                    "muni_code": muni,
                    "year": year,
                    "population_n": 1000,
                    "density_class": "urban" if i < 2 else "rural",
                }
            )
    return pd.DataFrame(rows)


def test_municipal_balance_sums_the_window_and_scales_by_first_year_population():
    b = dem.municipal_balance(_change(), _pop_panel(), 2020, 2021)
    assert len(b) == 5
    assert b.loc["0002", "natural_increase_n"] == -20 and b.loc["0002", "net_migration_n"] == 60
    assert b.loc["0002", "migration_per_1000_year"] == pytest.approx(30.0)  # 60 / 1000 / 2 years
    assert b.loc["0001", "population_change_n"] == 30  # 2022 is outside the window


def test_municipal_balance_by_group_adds_up_the_members():
    b = dem.municipal_balance(_change(), _pop_panel(), 2020, 2021, by="density_class")
    assert b.loc["urban", "net_migration_n"] == 70
    assert b.loc["rural", "population_start_n"] == 3000
    assert b.loc["rural", "natural_per_1000_year"] == pytest.approx(1000 * -20 / 3000 / 2)


def test_growth_regimes_classify_by_the_sign_of_each_component():
    b = dem.municipal_balance(_change(), _pop_panel(), 2020, 2021)
    r = dem.growth_regimes(b)
    assert r["municipalities_n"].to_dict() == {
        "natural_and_migration_gain": 1,  # 0001
        "migration_offsets_decline": 1,  # 0002: -20 + 60 > 0
        "migration_too_small": 1,  # 0003: -20 + 10 < 0
        "migration_loss": 1,  # 0004: births exceed deaths, migrants leave
        "decline_both": 1,  # 0005
    }
    assert r["share_of_municipalities_pct"].sum() == pytest.approx(100.0)


def _aima_two_munis():
    rows = []
    for muni, scale in (("0101", 1), ("0102", 2)):
        for year, mult in ((2014, 1), (2015, 2)):
            for nat, n in (("br", 10), ("cv", 4), ("ao", 6), ("other", 20)):
                rows.append((muni, year, nat, n * mult * scale))
    df = pd.DataFrame(rows, columns=["muni_code", "year", "nationality", "foreign_residents_n"])
    total = df.groupby(["muni_code", "year"], as_index=False)["foreign_residents_n"].sum()
    return pd.concat([df, total.assign(nationality="total")], ignore_index=True)


def test_group_changes_in_percent_of_last_years_population_and_add_to_total():
    aima = _aima_two_munis()
    pop = pd.Series(
        [1000.0, 1000.0, 2000.0, 2000.0],
        index=pd.MultiIndex.from_tuples(
            [("0101", 2014), ("0101", 2015), ("0102", 2014), ("0102", 2015)],
            names=["muni_code", "year"],
        ),
    )
    groups = {"brazil": ["br"], "palop": ["cv", "ao"], "other": ["other"]}
    out = dem.group_changes(aima, pop, groups)
    assert out.loc[("0101", 2015), "fc_brazil_pct"] == pytest.approx(100 * 10 / 1000)
    assert out.loc[("0101", 2015), "fc_palop_pct"] == pytest.approx(100 * 10 / 1000)
    assert out.loc[("0102", 2015), "fc_other_pct"] == pytest.approx(100 * 40 / 2000)
    assert out.loc[("0101", 2014)].isna().all()
    total = aima.query("nationality == 'total'").set_index(["muni_code", "year"])[
        "foreign_residents_n"
    ]
    expected = (
        100 * total.groupby(level="muni_code").diff() / pop.groupby(level="muni_code").shift(1)
    )
    pd.testing.assert_series_equal(
        out.sum(axis=1, min_count=3).dropna(), expected.dropna(), check_names=False
    )
