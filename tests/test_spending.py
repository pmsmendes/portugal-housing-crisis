import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import spending


def _spending():
    rows = []
    for geo, gdp in (("PT", 200_000.0), ("ES", 1_000_000.0)):
        for year in (2022, 2023):
            rows.append(
                {
                    "geo": geo,
                    "year": year,
                    "housing_development_eur_m": 400.0 if geo == "PT" else np.nan,
                    "housing_benefits_eur_m": 600.0 if geo == "PT" else 3_000.0,
                    "housing_amenities_eur_m": 2_000.0,
                    "gdp_eur_m": gdp,
                }
            )
    return pd.DataFrame(rows)


def test_support_shares_adds_the_two_parts_and_needs_both():
    out = spending.support_shares(_spending())
    assert out.loc[2022, "PT"] == pytest.approx(100 * 1_000 / 200_000)
    assert np.isnan(out.loc[2022, "ES"])  # development is missing


def test_portugal_frame_deflates_and_compares_with_property_tax():
    years = [2022, 2023, 2024, 2025]
    cpi = pd.DataFrame({"year": years, "cpi_index_b2025": [90.0, 95.0, 97.5, 100.0]})
    tax = pd.DataFrame(
        {
            "year": [2022, 2023],
            "imi_revenue_eur_m": [1_500.0, 1_500.0],
            "imt_revenue_eur_m": [500.0, 500.0],
            "gdp_eur_m": 200_000.0,
        }
    )
    out = spending.portugal_frame(_spending(), cpi, tax)
    assert list(out.index) == [2022, 2023]
    assert out.loc[2022, "support_eur_m"] == 1_000.0
    assert out.loc[2022, "support_gdp_pct"] == pytest.approx(0.5)
    assert out.loc[2022, "spending_per_tax_pct"] == pytest.approx(50.0)
    assert (
        out.loc[2022, "support_real_eur_m"] > out.loc[2022, "support_eur_m"]
    )  # past euros, deflated up
