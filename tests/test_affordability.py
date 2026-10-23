import numpy as np
import pandas as pd
import pytest

from pthousing.features import affordability as aff


def test_price_to_income_is_years_of_income():
    assert aff.price_to_income(2000, 100, 20_000) == pytest.approx(10.0)


def test_rent_to_income_uses_twelve_monthly_rents():
    # 10 EUR/m2/month x 100 m2 x 12 = 12,000 a year on 30,000 income
    assert aff.rent_to_income_pct(10, 100, 30_000) == pytest.approx(40.0)


def test_annuity_payment_matches_textbook_value():
    # 100,000 at 3% over 30 years: 421.60 a month
    assert aff.mortgage_payment_monthly(100_000, 3.0, 30) == pytest.approx(421.60, abs=0.01)


def test_zero_rate_is_loan_over_months_and_missing_rate_stays_missing():
    assert aff.mortgage_payment_monthly(120_000, 0.0, 10) == pytest.approx(1000.0)
    assert np.isnan(aff.mortgage_payment_monthly(120_000, np.nan, 10))


def test_mortgage_burden_combines_ltv_rate_term_and_income():
    loan = 0.8 * 2000 * 100  # 160,000
    expected = 100 * 12 * aff.mortgage_payment_monthly(loan, 4.0, 30) / 25_000
    assert aff.mortgage_burden_pct(2000, 100, 25_000, 4.0, ltv=0.8, term_years=30) == pytest.approx(
        expected
    )
    # a higher rate or a longer purchase means a higher burden
    assert aff.mortgage_burden_pct(2000, 100, 25_000, 6.0) > aff.mortgage_burden_pct(
        2000, 100, 25_000, 3.0
    )
    assert aff.mortgage_burden_pct(2000, 100, 25_000, 4.0, ltv=0.9) > aff.mortgage_burden_pct(
        2000, 100, 25_000, 4.0, ltv=0.7
    )


def test_series_in_series_out_with_aligned_index():
    price = pd.Series([1000.0, 2000.0], index=["a", "b"])
    rate = pd.Series([3.0, np.nan], index=["a", "b"])
    out = aff.mortgage_burden_pct(
        price, 100, pd.Series([20_000.0, 20_000.0], index=["a", "b"]), rate
    )
    assert list(out.index) == ["a", "b"] and out["a"] > 0 and np.isnan(out["b"])
    assert isinstance(aff.price_to_income(price, 100, 20_000.0), pd.Series)


def test_supply_gap_sign_and_scale():
    # +60k dwellings vs +40k households on a base of 1M households: +20 per 1,000
    assert aff.supply_gap_per_1000(2_000_000, 2_060_000, 1_000_000, 1_040_000) == pytest.approx(
        20.0
    )
    assert aff.supply_gap_per_1000(2_000_000, 2_020_000, 1_000_000, 1_040_000) == pytest.approx(
        -20.0
    )


def test_ownership_cost_index_is_the_payment_rebased_to_the_base_period():
    price = pd.Series([100.0, 110.0, 120.0], index=[2022, 2023, 2024])
    payment = pd.Series([400.0, 400.0, 500.0], index=[2022, 2023, 2024])
    idx = aff.ownership_cost_index(price, payment, price.index == 2022)
    assert idx[2022] == pytest.approx(100.0)
    assert idx[2023] == pytest.approx(110.0)  # price up 10%, payment factor unchanged
    assert idx[2024] == pytest.approx(150.0)  # price up 20% and payment factor up 25%
