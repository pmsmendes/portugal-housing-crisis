import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import supply
from pthousing.features import affordability as aff


def _stock():
    rows = [
        # muni, year, dwellings, usual, secondary, vacant, households
        ("a", 2011, 1000, 600, 250, 150, 620),
        ("a", 2021, 1100, 700, 250, 150, 700),
        ("b", 2011, 500, 300, 100, 100, 320),
        ("b", 2021, 480, 290, 100, 90, 300),
    ]
    return pd.DataFrame(
        rows,
        columns=["muni_code", "census_year", "dwellings_n", "dwellings_usual_n",
                 "dwellings_secondary_n", "dwellings_vacant_n", "households_n"],
    )  # fmt: skip


def _panel():
    rows = []
    for muni, pops, done in (("a", {2011: 2000, 2021: 2100, 2023: 2200}, 10),
                             ("b", {2011: 900, 2021: 800, 2023: 790}, 1)):  # fmt: skip
        for year in range(2011, 2025):
            rows.append(
                {"muni_code": muni, "year": year, "population_n": pops.get(year, np.nan),
                 "completed_n": done, "pti_years": 10.0 + (year - 2016) * (1 if muni == "a" else 0)}
            )  # fmt: skip
    return pd.DataFrame(rows)


def test_implied_gap_is_completions_minus_new_households_per_1000():
    assert aff.implied_gap_per_1000(20, 50, 1000) == pytest.approx(-30.0)


def test_balance_computes_observed_and_implied_gaps():
    b = supply.balance(_panel(), _stock())
    a = b.loc["a"]
    # (+100 dwellings - 80 households) / 620 households
    assert a["supply_gap_2011_2021_per_1000"] == pytest.approx(1000 * 20 / 620)
    assert a["completions_2012_2021_n"] == 100  # ten years of 10
    pph = 2100 / 700
    assert a["persons_per_household_2021"] == pytest.approx(pph)
    assert a["implied_new_households_2021_2023_n"] == pytest.approx(100 / pph)
    assert a["completions_2022_2023_n"] == 20
    assert a["implied_gap_2021_2023_per_1000"] == pytest.approx(1000 * (20 - 100 / pph) / 700)
    assert b.loc["b", "households_change_pct"] == pytest.approx(100 * (300 / 320 - 1))


def test_aggregate_recomputes_ratios_from_summed_counts():
    b = supply.balance(_panel(), _stock())
    g = supply.aggregate(b, pd.Series("all", index=b.index)).loc["all"]
    assert g["municipalities_n"] == 2
    assert g["dwellings_2021_n"] == 1580 and g["households_2011_n"] == 940
    # not the mean of the two municipalities' gaps
    assert g["supply_gap_2011_2021_per_1000"] == pytest.approx(
        1000 * ((1580 - 1500) - (1000 - 940)) / 940
    )
    assert g["implied_new_households_2021_2023_n"] == pytest.approx(
        b["implied_new_households_2021_2023_n"].sum()
    )


def test_composition_shares_sum_to_100_and_follow_groups():
    comp = supply.composition(_stock())
    row = comp[comp["census_year"] == 2011].iloc[0]
    assert row["dwellings_n"] == 1500
    assert row["usual_pct"] + row["secondary_pct"] + row["vacant_pct"] == pytest.approx(100)
    by = supply.composition(_stock(), pd.Series({"a": "x", "b": "y"}))
    assert by[(by["group"] == "y") & (by["census_year"] == 2021)]["vacant_pct"].iloc[
        0
    ] == pytest.approx(100 * 90 / 480)


def test_associations_recover_a_known_slope_with_group_intercepts():
    rng = np.random.default_rng(1)
    n = 120
    df = pd.DataFrame({"x": rng.normal(size=n), "g": np.repeat(["u", "v", "w"], n // 3)})
    df["y"] = 0.5 * df["x"] + df["g"].map({"u": 0, "v": 2, "w": -1}) + rng.normal(scale=0.1, size=n)
    out = supply.associations(df, "y", ["x"], fixed_effects="g")
    assert out["coef"].iloc[0] == pytest.approx(0.5, abs=0.05)
    assert out["coef_per_sd"].iloc[0] == pytest.approx(0.5 * df["x"].std(), abs=0.05)
    assert out["n_obs"].iloc[0] == n and list(out["term"]) == ["x"]


def test_pti_change_is_log_ratio_and_nan_when_a_year_is_missing():
    panel = _panel()
    panel.loc[(panel["muni_code"] == "b") & (panel["year"] == 2024), "pti_years"] = np.nan
    out = supply.pti_change(panel, 2016, 2024)
    assert out["a"] == pytest.approx(np.log(18 / 10)) and np.isnan(out["b"])


def test_area_of_uses_district_on_the_mainland_and_territory_for_islands():
    panel = pd.DataFrame(
        {
            "muni_code": ["1", "2"],
            "district": ["Faro", "Ilha Terceira"],
            "territory": ["continente", "azores"],
        }
    )
    assert supply.area_of(panel).to_dict() == {"1": "Faro", "2": "Açores"}


def test_national_flows_sum_over_municipalities():
    panel = pd.DataFrame(
        {
            "muni_code": ["a", "b"],
            "year": [2020, 2020],
            "licensed_n": [5, 7],
            "completed_n": [3, np.nan],
        }
    )
    f = supply.national_flows(panel)
    assert f.loc[2020, "licensed_n"] == 12 and f.loc[2020, "completed_n"] == 3
