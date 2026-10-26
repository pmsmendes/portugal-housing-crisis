import pandas as pd
import pytest

from pthousing.analysis import rent_update as ru


def _table():
    return pd.DataFrame(
        {
            "legal_coefficient": [1.01, 1.02, 1.05],
            "formula_coefficient": [1.01, 1.06, 1.05],
        },
        index=pd.Index([2021, 2022, 2023], name="year"),
    )


def test_lookup_has_every_year_and_the_2023_ceiling():
    t = ru.read()
    assert t.index.is_unique
    assert t.loc[2023, "legal_coefficient"] == 1.02
    assert t.loc[2023, "formula_coefficient"] > t.loc[2023, "legal_coefficient"]
    assert (t["legal_coefficient"] <= t["formula_coefficient"]).all()


def test_cumulative_and_allowed_rise_start_the_year_after_the_base():
    t = _table()
    assert ru.cumulative(t["legal_coefficient"], 2022, 2023) == pytest.approx(1.02 * 1.05)
    assert ru.allowed_rise_pct(t, 2021, 2023, "legal_coefficient") == pytest.approx(
        100 * (1.02 * 1.05 - 1)
    )
    assert ru.cumulative(t["legal_coefficient"], 2024, 2023) == 1.0


def test_national_path_indexes_to_the_base_year():
    t = _table()
    rent = pd.Series({2021: 4.0, 2022: 4.4, 2023: 5.0})
    cpi = pd.Series({2021: 100.0, 2022: 105.0, 2023: 110.0})
    out = ru.national_path(t, 2021, range(2021, 2024), rent, cpi)
    assert out.loc[2021, "legal_rent_index"] == 100
    assert out.loc[2023, "legal_rent_index"] == pytest.approx(100 * 1.02 * 1.05)
    assert out.loc[2023, "formula_rent_index"] == pytest.approx(100 * 1.06 * 1.05)
    assert out.loc[2023, "new_lease_rent_index"] == pytest.approx(125.0)
    assert out.loc[2023, "new_over_legal_pct"] == pytest.approx(100 * (125 / 107.1 - 1))


def test_market_gap_compares_new_leases_with_the_updated_base_rent():
    rent = pd.DataFrame(
        {
            "muni_code": ["0101", "0101", "0102", "0103"],
            "year": [2020, 2024, 2020, 2024],
            "rent_sqm_eur": [4.0, 6.0, 5.0, 7.0],
        }
    )
    out = ru.market_gap(rent, 2020, 2024, 1.10)
    assert list(out.index) == ["0101"]
    assert out.loc["0101", "rent_sitting_eur"] == pytest.approx(4.4)
    assert out.loc["0101", "market_rise_pct"] == pytest.approx(50.0)
    assert out.loc["0101", "gap_pct"] == pytest.approx(100 * (6 / 4.4 - 1))


def test_turnover_is_new_leases_per_100_rented_dwellings():
    out = ru.turnover(pd.Series({"a": 10.0, "b": 5.0}), pd.Series({"a": 100.0, "c": 50.0}))
    assert out.to_dict() == {"a": 10.0}


def test_ceiling_saving_is_the_difference_of_the_two_updates():
    out = ru.ceiling_saving(pd.Series({"a": 5.0}), pd.Series({"a": 80.0}), 1.02, 1.0543)
    assert out.loc["a", "rent_before_eur"] == pytest.approx(400)
    assert out.loc["a", "saving_eur_month"] == pytest.approx(400 * (1.0543 - 1.02))


def test_cumulative_ignores_a_coefficient_below_one():
    c = pd.Series({2021: 0.9997, 2022: 1.01})
    assert ru.cumulative(c, 2021, 2022) == pytest.approx(1.01)


def test_balanced_median_keeps_only_municipalities_with_both_end_years():
    rent = pd.DataFrame(
        {
            "muni_code": ["a", "a", "a", "b", "b", "c"],
            "year": [2020, 2021, 2022, 2020, 2022, 2022],
            "rent_sqm_eur": [4.0, 4.5, 5.0, 6.0, 8.0, 100.0],
        }
    )
    out = ru.balanced_median(rent, 2020, 2022)
    assert out.to_dict() == {2020: 5.0, 2021: 4.5, 2022: 6.5}


def test_gap_by_group_medians_and_pooled_share_let():
    gap = pd.DataFrame(
        {
            "market_rise_pct": [10.0, 30.0, 50.0],
            "gap_pct": [5.0, 25.0, 45.0],
            "rented_n": [10.0, 30.0, 20.0],
            "dwellings_n": [100.0, 100.0, 100.0],
            "turnover": [10.0, 20.0, 30.0],
        },
        index=["a", "b", "c"],
    )
    group = pd.Series({"a": "lo", "b": "lo", "c": None, "d": "hi"}, name="g")
    out = ru.gap_by_group(gap, group)
    assert list(out.index) == ["lo"]
    assert out.loc["lo", "median_gap_pct"] == pytest.approx(15.0)
    assert out.loc["lo", "rented_share_pct"] == pytest.approx(20.0)
    assert out.loc["lo", "municipalities_n"] == 2


def test_rank_correlations_and_saving_summary():
    frame = pd.DataFrame({"y": [1, 2, 3, 4], "x": [4, 3, 2, 1], "z": [1, 2, 3, 4]})
    out = ru.rank_correlations(frame, "y", ["x", "z"])
    assert out["x"] == pytest.approx(-1.0) and out["z"] == pytest.approx(1.0)
    saving = ru.ceiling_saving(pd.Series({"a": 5.0, "b": 5.0}), 80.0, 1.02, 1.0543)
    s = ru.saving_summary(saving, 1_000_000)
    assert s.loc[0, "saving_eur_month"] == pytest.approx(400 * 0.0343)
    assert s.loc[0, "saving_pct_of_rent"] == pytest.approx(3.43)
    assert s.loc[0, "upper_bound_eur_m_year"] == pytest.approx(12 * 400 * 0.0343)
