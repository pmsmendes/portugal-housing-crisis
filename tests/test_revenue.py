import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import revenue
from pthousing.config import BASE_YEAR


def _inputs():
    years = np.arange(2010, 2026)
    cpi = pd.DataFrame({"year": years, "cpi_index_b2025": 80 + 1.25 * (years - 2010)})
    n = len(years)
    tax = pd.DataFrame(
        {
            "year": years,
            "imi_revenue_eur_m": 1_000.0 * 1.03 ** np.arange(n),
            "imt_revenue_eur_m": 500.0 * 1.08 ** np.arange(n),
            "gdp_eur_m": 200_000.0,
        }
    )
    long = pd.DataFrame(
        {
            "year": years,
            "hpi_nominal_b2015": 100 * 1.06 ** (years - 2015),
            "hpi_real_b2015": 100 * 1.04 ** (years - 2015),
        }
    )
    return tax, cpi, long


def test_weighted_imi_rate_uses_fixed_weights_and_skips_municipalities_without_a_rate():
    panel = pd.DataFrame(
        {
            "year": [2020, 2020, 2020, 2021, 2021, 2021],
            "imi_urban_pct": [0.4, 0.3, np.nan, 0.4, 0.3, 0.5],
            "dwellings_2021_n": [100.0, 300.0, 600.0, 100.0, 300.0, 600.0],
        }
    )
    out = revenue.weighted_imi_rate(panel)
    assert out.loc[2020] == pytest.approx((0.4 * 100 + 0.3 * 300) / 400)  # the NaN rate is left out
    assert out.loc[2021] == pytest.approx((0.4 * 100 + 0.3 * 300 + 0.5 * 600) / 1000)


def test_annual_frame_deflates_to_the_base_year_and_computes_shares_and_indices():
    tax, cpi, long = _inputs()
    d = revenue.annual_frame(tax, cpi, long)
    assert d.loc[BASE_YEAR, "imi_real_eur_m"] == pytest.approx(d.loc[BASE_YEAR, "imi_eur_m"])
    assert (
        d.loc[2010, "imi_real_eur_m"] < d.loc[2010, "imi_eur_m"] * 1.5
    )  # deflated upward from the past
    assert d.loc[2015, "imt_real_b2015"] == pytest.approx(100)
    assert d.loc[2020, "imi_gdp_pct"] == pytest.approx(100 * d.loc[2020, "imi_eur_m"] / 200_000)
    assert "imi_base_b2015" not in d


def test_annual_frame_with_a_rate_adds_the_tax_base_index():
    tax, cpi, long = _inputs()
    rate = pd.Series(0.4 - 0.01 * np.arange(16), index=pd.Index(range(2010, 2026), name="year"))
    d = revenue.annual_frame(tax, cpi, long, rate=rate)
    assert d.loc[2015, "imi_base_b2015"] == pytest.approx(100)
    expected = (d["imi_eur_m"] / rate) / (d.loc[2015, "imi_eur_m"] / rate.loc[2015]) * 100
    pd.testing.assert_series_equal(d["imi_base_b2015"], expected, check_names=False)


def test_decompose_imi_splits_revenue_change_into_rate_and_base():
    tax, cpi, long = _inputs()
    rate = pd.Series(0.4 * 0.98 ** np.arange(16), index=pd.Index(range(2010, 2026), name="year"))
    d = revenue.annual_frame(tax, cpi, long, rate=rate)
    parts = revenue.decompose_imi(d, 2015, 2025)
    assert parts["rate"] == pytest.approx(100 * 10 * np.log(0.98))
    assert parts["revenue"] == pytest.approx(parts["rate"] + parts["base"])
    assert parts["price"] == pytest.approx(100 * 10 * np.log(1.06))
    assert parts["gap"] == pytest.approx(parts["base"] - parts["price"])


def test_changes_reports_percentage_change_per_window():
    tax, cpi, long = _inputs()
    d = revenue.annual_frame(tax, cpi, long)
    out = revenue.changes(d, {"a": (2012, 2014)}, ["imt_eur_m"])
    assert out.loc["a", "imt_eur_m"] == pytest.approx(100 * (1.08**2 - 1))


def _panel():
    return pd.DataFrame(
        {
            "year": 2025,
            "imi_urban_pct": [0.30, 0.30, 0.40, np.nan],
            "dwellings_2021_n": [100.0, 100.0, 200.0, 500.0],
            "sales_12m_n": [10.0, 20.0, 30.0, 40.0],
            "price_sqm_eur_real": [1_000.0, 2_000.0, 3_000.0, 4_000.0],
        }
    )


def test_imi_headroom_counts_the_floor_and_weights_the_gap_to_it():
    out = revenue.imi_headroom(_panel(), 2025)
    assert out["municipalities_n"] == 3 and out["at_floor_n"] == 2  # the NaN rate is left out
    assert out["average_rate_pct"] == pytest.approx((0.3 * 100 + 0.3 * 100 + 0.4 * 200) / 400)
    assert out["headroom_pp"] == pytest.approx(0.1 * 200 / 400)
    assert out["headroom_share"] == pytest.approx(out["headroom_pp"] / out["average_rate_pct"])


def test_dwelling_sales_value_uses_the_benchmark_dwelling():
    # (10*1000 + 20*2000 + 30*3000 + 40*4000) * 100 m2
    assert revenue.dwelling_sales_value(_panel(), 2025) == pytest.approx(300_000 * 100)


def test_offset_growth_restores_the_revenue_after_the_cut():
    for share in (0.05, 0.2, 0.5):
        assert (1 - share) * (1 + revenue.offset_growth(share)) == pytest.approx(1)


def test_capped_cut_never_goes_below_the_floor():
    out = revenue.capped_cut(_panel(), 2025, 0.05)
    assert out["full_cut_n"] == 1  # only the 0.40 council can cut 0.05 and stay above 0.30
    assert out["average_cut_pp"] == pytest.approx(0.05 * 200 / 400)
    assert revenue.capped_cut(_panel(), 2025, 0.5)["average_cut_pp"] == pytest.approx(
        revenue.imi_headroom(_panel(), 2025)["headroom_pp"]
    )


def test_dwelling_sales_value_is_nan_without_sales():
    assert np.isnan(revenue.dwelling_sales_value(_panel().assign(sales_12m_n=np.nan), 2025))
