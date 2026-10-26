import pandas as pd
import pytest

from pthousing.analysis import lending


def test_lookup_is_readable_and_unique_by_indicator_and_period():
    t = lending.read()
    assert not t.duplicated(["indicator", "period"]).any()
    assert lending.value(t, "ltv_weighted_mean_new", "2024") == 69
    assert pd.isna(lending.value(t, "ltv_share_above_90", "2024"))
    with pytest.raises(KeyError):
        lending.value(t, "ltv_weighted_mean_new", "1999")


def test_capacity_gain_is_zero_for_the_same_term_and_grows_with_the_term():
    assert lending.capacity_gain_pct(4.0, 30, 30) == pytest.approx(0.0)
    assert 0 < lending.capacity_gain_pct(4.0, 30, 35) < lending.capacity_gain_pct(4.0, 30, 40)
    # at a zero rate the loan is proportional to the term
    assert lending.capacity_gain_pct(0.0, 30, 40) == pytest.approx(100 * (40 / 30 - 1))


def test_maturity_table_has_a_row_per_year_and_term():
    out = lending.maturity_table(pd.Series({2013: 4.0, 2024: 3.5}), {"30": 30, "40": 40}, base="30")
    assert len(out) == 4
    assert out.loc[(out["year"] == 2013) & (out["term"] == "30"), "capacity_gain_pct"].iloc[
        0
    ] == pytest.approx(0)
    assert out["payment_per_100k_eur"].min() > 0


def test_deposit_years_falls_with_the_loan_to_value():
    out = lending.deposit_years(pd.Series({"a": 10.0}), {"90": 0.9, "100": 1.0}, 6.0)
    assert out.loc["a", "90"] == pytest.approx(10 * (0.1 + 0.06))
    assert out.loc["a", "100"] == pytest.approx(10 * 0.06)


def test_burden_table_rises_with_the_loan_to_value_and_falls_with_the_term():
    panel = pd.DataFrame(
        {
            "price_sqm_eur": [1000.0, 2000.0],
            "dwelling_area_sqm": [100.0, 100.0],
            "income_median_eur": [15_000.0, 15_000.0],
        }
    )
    out = lending.burden_table(
        panel, 4.0, {"80": 0.8, "100": 1.0}, {"30": 30, "40": 40}, limit_pct=50
    )
    get = lambda ltv, term: out[(out["ltv"] == ltv) & (out["term"] == term)].iloc[0]  # noqa: E731
    assert get("100", "30")["median_burden_pct"] > get("80", "30")["median_burden_pct"]
    assert get("80", "40")["median_burden_pct"] < get("80", "30")["median_burden_pct"]
    assert get("100", "30")["share_above_limit_pct"] >= get("80", "30")["share_above_limit_pct"]
