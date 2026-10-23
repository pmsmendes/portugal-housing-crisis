import numpy as np
import pandas as pd
import pytest

from pthousing.features import affordability as aff
from pthousing.features import rent_vs_buy as rvb

ASSUMPTIONS = dict(
    ltv=0.8,
    opportunity_rate_pct=3.0,
    maintenance_pct=1.0,
    buying_costs_pct=6.0,
    holding_years=10,
    imi_taxable_share=0.5,
)


def test_gross_yield_is_twelve_monthly_rents_over_price():
    assert rvb.gross_rent_yield_pct(10, 2400) == pytest.approx(5.0)


def test_owner_cost_adds_up_by_hand():
    # 0.8 x 4 interest + 0.2 x 3 deposit + 0.5 x 0.4 tax + 1 upkeep + 6 / 10 buying costs
    assert rvb.owner_cost_rate_pct(4.0, 0.4, **ASSUMPTIONS) == pytest.approx(
        3.2 + 0.6 + 0.2 + 1.0 + 0.6
    )


def test_components_sum_to_the_rate_and_follow_the_inputs():
    rates = pd.Series([1.0, 4.0], index=["a", "b"])
    parts = rvb.owner_cost_components(rates, 0.3, **ASSUMPTIONS)
    assert list(parts.index) == ["a", "b"]
    assert list(parts.columns) == rvb.COMPONENTS
    assert parts.sum(axis=1).tolist() == pytest.approx(
        rvb.owner_cost_rate_pct(rates, 0.3, **ASSUMPTIONS).tolist()
    )
    # only the interest term moves with the mortgage rate
    assert (parts.loc["b"] - parts.loc["a"]).drop("interest").abs().sum() == 0
    assert parts["interest"].tolist() == pytest.approx([0.8, 3.2])


def test_missing_rate_gives_missing_cost():
    cost = rvb.owner_cost_rate_pct(pd.Series([np.nan, 3.0]), 0.3)
    assert np.isnan(cost.iloc[0]) and cost.iloc[1] > 0


def test_breakeven_is_cost_minus_yield():
    assert rvb.breakeven_appreciation_pct(5.9, 5.6) == pytest.approx(0.3)
    assert rvb.breakeven_appreciation_pct(2.9, 6.0) < 0


def test_upfront_cash_is_deposit_plus_buying_costs_in_years_of_income():
    assert rvb.upfront_cash_years(10.0, ltv=0.8, buying_costs_pct=6.0) == pytest.approx(2.6)


def test_cash_cost_includes_principal_so_exceeds_the_economic_cost_at_normal_rates():
    cash = rvb.owner_cash_cost_pct(
        4.0, 0.4, ltv=0.8, term_years=30, maintenance_pct=1.0, imi_taxable_share=0.5
    )
    payment = 12 * 0.8 * aff.mortgage_payment_monthly(1.0, 4.0, 30) * 100
    assert cash == pytest.approx(payment + 0.2 + 1.0)
    assert cash > rvb.owner_cost_rate_pct(4.0, 0.4, **ASSUMPTIONS)


def test_yield_scale_is_the_geometric_mean_of_yield_times_price_to_rent():
    years = pd.Index([2020, 2021], name="year")
    scale = rvb.calibrate_yield_scale(
        pd.Series([5.0, 4.0], index=years), pd.Series([20.0, 25.0], index=years)
    )
    assert scale == pytest.approx(100.0)  # both years give 100


def test_national_breakeven_scales_the_yield_with_price_to_rent():
    years = pd.Index([2020, 2021, 2022], name="year")
    out = rvb.national_breakeven(
        pd.Series([100.0, 125.0, 200.0], index=years),
        pd.Series([1.0, 1.0, 1.0], index=years),
        pd.Series([0.3, 0.3, 0.3], index=years),
        yield_scale=625.0,
        **ASSUMPTIONS,
    )
    assert out["rent_yield_pct"].tolist() == pytest.approx([6.25, 5.0, 3.125])
    assert out["owner_cost_pct"].nunique() == 1
    assert out["breakeven_pct"].iloc[2] > out["breakeven_pct"].iloc[0]
    assert set(rvb.COMPONENTS) <= set(out.columns)


def test_national_breakeven_drops_years_missing_an_input():
    years = pd.Index([2019, 2020, 2021], name="year")
    out = rvb.national_breakeven(
        pd.Series([100.0, 110.0, 120.0], index=years),
        pd.Series([np.nan, 1.0, 1.0], index=years),
        pd.Series([0.3, 0.3, 0.3], index=years),
        yield_scale=550.0,
    )
    assert list(out.index) == [2020, 2021]


def _panel():
    return pd.DataFrame(
        {
            "year": [2024, 2024, 2024, 2023],
            "price_sqm_eur": [2400.0, 1200.0, 1500.0, 1500.0],
            "rent_sqm_eur": [10.0, 5.0, np.nan, 6.0],
            "pti_years": [10.0, 6.0, 7.0, 7.0],
            "imi_urban_pct": [0.4, np.nan, 0.3, 0.3],
            "mortgage_rate_new_lt1y_pct": [4.0, 4.0, 4.0, 4.0],
        }
    )


def test_add_indicators_fills_missing_imi_and_leaves_unpublished_rents_missing():
    d = rvb.add_indicators(_panel())
    assert d["rent_yield_pct"].iloc[0] == pytest.approx(5.0)
    assert d["imi_filled_pct"].iloc[1] == pytest.approx(0.35)  # mean of the 2024 rates (0.4, 0.3)
    assert np.isnan(d["breakeven_pct"].iloc[2])
    assert d["breakeven_pct"].iloc[0] == pytest.approx(d["owner_cost_pct"].iloc[0] - 5.0)
    assert d["upfront_cash_years"].iloc[0] == pytest.approx(rvb.upfront_cash_years(10.0))
    assert (d["cash_cost_vs_rent"].dropna() > 0).all()


def test_assumption_overrides_reach_the_columns():
    base, dear = rvb.add_indicators(_panel()), rvb.add_indicators(_panel(), maintenance_pct=3.0)
    assert dear["owner_cost_pct"].iloc[0] == pytest.approx(base["owner_cost_pct"].iloc[0] + 2.0)
    assert dear["cash_cost_vs_rent"].iloc[0] > base["cash_cost_vs_rent"].iloc[0]


def test_sensitivity_has_a_base_row_and_moves_the_right_way():
    table = rvb.breakeven_sensitivity(
        _panel(), 2024, {"maintenance_pct": [0.5, 2.0], "opportunity_rate_pct": [0.0]}
    )
    assert table["assumption"].tolist() == [
        "base",
        "maintenance_pct",
        "maintenance_pct",
        "opportunity_rate_pct",
    ]
    base, low, high, zero = table["median_breakeven_pct"]
    assert low < base < high and zero < base
