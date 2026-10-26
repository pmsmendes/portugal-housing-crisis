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


def test_rate_effect_is_the_cut_in_the_loan_a_payment_carries():
    assert lending.rate_effect_pct(2.0, 2.0, 30) == pytest.approx(0.0)
    cut = lending.rate_effect_pct(1.0, 4.0, 30)
    assert 0 < cut < 100
    # a loan carried at 1% shrinks by the ratio of the two payments per euro
    low = float(lending.mortgage_payment_monthly(1.0, 1.0, 30))
    high = float(lending.mortgage_payment_monthly(1.0, 4.0, 30))
    assert cut == pytest.approx(100 * (1 - low / high))


def test_cash_summary_gives_median_and_share_above_a_year():
    dep = pd.DataFrame({"80%": [0.5, 1.5, 2.5], "100%": [0.1, 0.2, 1.1]})
    out = lending.cash_summary(dep)
    assert out.loc["80%", "median_years"] == pytest.approx(1.5)
    assert out.loc["80%", "share_above_one_pct"] == pytest.approx(200 / 3)
    assert out.loc["100%", "share_above_one_pct"] == pytest.approx(100 / 3)


def test_lookup_figures_are_plausible_and_each_cites_a_source():
    t = lending.read()
    assert t["source"].str.contains("BdP 2025 report").all()
    pct = t[(t["unit"] == "pct") & t["value"].notna()]
    assert pct["value"].between(0, 100).all()
    assert t.loc[t["unit"] == "years", "value"].between(15, 45).all()
    # the July 2018 mean term is derived from December 2024 (31.0) plus the 2.4 years the report gives
    assert lending.value(t, "maturity_weighted_mean", "2018-07") == pytest.approx(
        lending.value(t, "maturity_weighted_mean", "2024-12") + 2.4
    )


def test_series_table_is_unique_and_yearly_averages_quarters():
    s = lending.read_series()
    assert not s.duplicated(["indicator", "period"]).any()
    ltv = [
        "ltv_share_at_most_80",
        "ltv_share_80_to_90",
        "ltv_share_90_to_100",
        "ltv_share_above_100",
    ]
    shares = lending.yearly(s, ltv)
    assert shares.index.min() == 2018 and shares.index.max() == 2025
    assert (shares.sum(axis=1) - 100).abs().max() < 0.1  # the four bands cover every loan
    term = lending.yearly(s, ["maturity_weighted_mean"])["maturity_weighted_mean"]
    quarters = s[(s["indicator"] == "maturity_weighted_mean") & s["period"].str.startswith("2025")]
    assert term[2025] == pytest.approx(quarters["value"].mean())


def test_standards_by_year_sums_the_bands_above_90_and_covers_2018_to_2025():
    s = lending.read_series()
    t = lending.standards_by_year(s)
    assert list(t.columns) == lending.STANDARDS_COLUMNS
    assert t.index.min() == 2018 and t.index.max() == 2025
    assert t["ltv_above_90_pct"].notna().all()
    assert t.loc[2025, "ltv_above_90_pct"] > 10 > t.loc[2024, "ltv_above_90_pct"]
