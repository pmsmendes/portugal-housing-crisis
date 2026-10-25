import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import vacancy as vac


def _stock():
    rows = []
    for code, y11, y21 in (
        ("0101", (1000, 100), (1000, 200)),  # 10% -> 20% vacant
        ("0102", (500, 50), (600, 30)),  # 10% -> 5% vacant
    ):
        for year, (dwellings, vacant) in ((2011, y11), (2021, y21)):
            rows.append(
                {
                    "muni_code": code,
                    "census_year": year,
                    "dwellings_n": float(dwellings),
                    "dwellings_vacant_n": float(vacant),
                }
            )
    return pd.DataFrame(rows)


def _balance():
    return pd.DataFrame(
        {
            "implied_new_households_2021_2023_n": [60.0, 40.0],
            "completions_2022_2023_n": [10.0, 55.0],
        },
        index=pd.Index(["0101", "0102"], name="muni_code"),
    )


def test_table_gives_rates_and_the_change_in_points():
    out = vac.table(_stock())
    assert out.loc["0101", "vacancy_2021_pct"] == pytest.approx(20.0)
    assert out.loc["0102", "vacancy_change_pp"] == pytest.approx(-5.0)


def test_excess_is_vacancy_above_the_frictional_level_and_never_negative():
    tab = vac.table(_stock())
    out = vac.excess(tab["vacant_2021_n"], tab["dwellings_2021_n"], 5.0)
    assert out["0101"] == pytest.approx(150.0)  # 200 - 5% of 1,000
    assert out["0102"] == 0.0  # 30 vacant = exactly 5% of 600


def test_shortfall_floors_surplus_municipalities_at_zero():
    out = vac.shortfall(_balance())
    assert out["0101"] == pytest.approx(50.0)
    assert out["0102"] == 0.0


def test_local_coverage_is_the_smaller_of_usable_excess_and_shortfall():
    excess = pd.Series({"a": 150.0, "b": 10.0})
    short = pd.Series({"a": 50.0, "b": 40.0})
    assert vac.local_coverage(excess, short).to_dict() == {"a": 50.0, "b": 10.0}
    assert vac.local_coverage(excess, short, 0.2).to_dict() == {"a": 30.0, "b": 2.0}


def test_by_group_sums_counts_and_recomputes_rates():
    tab = vac.table(_stock())
    out = vac.by_group(tab, vac.shortfall(_balance()), pd.Series("all", index=tab.index), 5.0)
    row = out.loc["all"]
    assert row["vacant_2021_n"] == 230
    assert row["vacancy_2021_pct"] == pytest.approx(100 * 230 / 1600)
    assert row["excess_n"] == pytest.approx(150)
    assert row["coverage_pct"] == pytest.approx(100.0)  # 150 excess covers the 50 short


def test_sensitivity_coverage_falls_with_the_usable_share_and_the_frictional_level():
    tab = vac.table(_stock())
    out = vac.sensitivity(tab, vac.shortfall(_balance()), (5.0, 15.0), (1.0, 0.2)).set_index(
        ["frictional_pct", "usable_share"]
    )
    assert out.loc[(5.0, 1.0), "coverage_pct"] == pytest.approx(100.0)
    assert out.loc[(5.0, 0.2), "coverage_pct"] == pytest.approx(60.0)  # 30 of 50
    assert out.loc[(15.0, 1.0), "coverage_pct"] == pytest.approx(100 * 50 / 50)  # 200-150=50
    assert out.loc[(15.0, 0.2), "coverage_pct"] == pytest.approx(20.0)


def test_usable_share_for_inverts_coverage_and_is_nan_when_unreachable():
    excess = pd.Series({"a": 100.0})
    short = pd.Series({"a": 50.0})
    assert vac.usable_share_for(50.0, excess, short) == pytest.approx(0.25, abs=1e-3)
    assert np.isnan(vac.usable_share_for(50.0, pd.Series({"a": 10.0}), pd.Series({"a": 50.0})))


def test_largest_shortfalls_ranks_and_names_municipalities():
    tab = vac.table(_stock())
    names = pd.Series({"0101": "Alfa", "0102": "Beta"})
    out = vac.largest_shortfalls(tab, vac.shortfall(_balance()), names, n=1)
    assert out["name"].tolist() == ["Alfa"]
    assert out["coverage_pct"].iloc[0] == pytest.approx(100.0)
