import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import peers


def _hpi():
    rows = []
    for geo, factor in (("PT", 1.5), ("ES", 1.2)):
        for year, level in ((2015, 100.0), (2024, 100.0 * factor)):
            for quarter in range(1, 5):
                rows.append(
                    {"geo": geo, "year": year, "quarter": quarter, "hpi_index_b2015": level}
                )
    return pd.DataFrame(rows)


def _tax():
    return pd.DataFrame(
        {
            "geo": ["PT", "PT", "ES", "ES"],
            "year": [2015, 2016, 2015, 2016],
            "land_buildings_tax_eur_m": [1_000.0, 2_000.0, 500.0, 500.0],
            "transaction_tax_eur_m": 0.0,
            "gdp_eur_m": [100_000.0, 100_000.0, 100_000.0, 100_000.0],
        }
    )


def _housing():
    return pd.DataFrame(
        {
            "geo": ["PT", "PT", "ES", "ES"],
            "year": [2015, 2016, 2015, 2016],
            "housing_development_eur_m": [100.0, 300.0, 50.0, 50.0],
            "housing_benefits_eur_m": [100.0, 100.0, 50.0, 50.0],
            "housing_amenities_eur_m": 1_000.0,
            "gdp_eur_m": [100_000.0] * 4,
        }
    )


def test_price_change_uses_annual_means():
    out = peers.price_change(_hpi(), 2015, 2024)
    assert out["PT"] == pytest.approx(50.0) and out["ES"] == pytest.approx(20.0)


def test_property_tax_share_is_the_mean_over_the_window():
    out = peers.property_tax_share(_tax(), 2015, 2016)
    assert out["PT"] == pytest.approx(1.5) and out["ES"] == pytest.approx(0.5)
    assert peers.property_tax_share(_tax(), 2016, 2016)["PT"] == pytest.approx(2.0)


def test_policy_mix_joins_the_three_indicators_and_can_drop_a_spending_series():
    out = peers.policy_mix(_hpi(), _tax(), _housing(), start=2015, end=2024)
    assert list(out.columns) == [
        "price_change_pct",
        "property_tax_gdp_pct",
        "housing_support_gdp_pct",
    ]
    assert out.loc["PT", "price_change_pct"] == pytest.approx(50.0)
    assert out.loc["PT", "property_tax_gdp_pct"] == pytest.approx(1.5)
    assert out.loc["PT", "housing_support_gdp_pct"] == pytest.approx(
        0.3
    )  # (200 + 400) / 2 over 100,000
    dropped = peers.policy_mix(
        _hpi(), _tax(), _housing(), start=2015, end=2024, exclude_spending=("ES",)
    )
    assert np.isnan(dropped.loc["ES", "housing_support_gdp_pct"])
    assert dropped.loc["ES", "price_change_pct"] == pytest.approx(20.0)
