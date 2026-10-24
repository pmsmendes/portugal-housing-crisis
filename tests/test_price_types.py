import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import price_types as pt


def _row(muni, year, kind, new, old, price, valuation):
    return {
        "muni_code": muni,
        "year": year,
        "kind": kind,
        "price_new_sqm_eur": new,
        "price_existing_sqm_eur": old,
        "price_new_sqm_eur_real": new,
        "price_existing_sqm_eur_real": old,
        "price_sqm_eur": price,
        "valuation_sqm_eur": valuation,
    }


def _panel():
    rows = []
    for muni, new0, old0, kind in [
        ("0001", 130, 100, "a"),
        ("0002", 110, 100, "a"),
        ("0003", 90, 100, "b"),
    ]:
        for i, year in enumerate((2020, 2021)):
            rows.append(
                _row(
                    muni,
                    year,
                    kind,
                    new0 * (1 + 0.1 * i),
                    old0 * (1 + 0.2 * i),
                    100 * (1 + 0.2 * i),
                    110 * (1 + 0.1 * i),
                )
            )
    rows.append(_row("0004", 2020, "b", np.nan, 100.0, 100.0, 150.0))  # no new-build price
    return pd.DataFrame(rows)


def test_new_vs_existing_premium_and_indexes_use_balanced_municipalities():
    out = pt.new_vs_existing(_panel(), 2020, 2021)
    assert out["municipalities_n"].tolist() == [3, 3]  # 0004 lacks a new-build price
    assert out.loc[2020, "median_premium_pct"] == pytest.approx(10.0)
    assert out.loc[2020, "share_new_dearer_pct"] == pytest.approx(200 / 3)
    assert out.loc[2020, "new_real_index"] == 100
    assert out.loc[2021, "new_real_index"] == pytest.approx(110)
    assert out.loc[2021, "existing_real_index"] == pytest.approx(120)
    assert out.loc[2021, "median_premium_pct"] == pytest.approx(100 * (110 * 1.1 / 120 - 1))


def test_premium_by_class_counts_municipalities_with_both_prices():
    out = pt.premium_by_class(_panel(), 2020, "kind")
    assert out.loc["a", "municipalities_n"] == 2
    assert out.loc["a", "median_premium_pct"] == pytest.approx(20.0)
    assert out.loc["b", "municipalities_n"] == 1  # 0004 has no new price
    assert out.loc["b", "median_premium_pct"] == pytest.approx(-10.0)


def _valuation():
    rows = []
    for muni, flats, villas in [("0001", 200, 100), ("0002", 150, 100)]:
        for year, k in ((2011, 1.0), (2025, 2.0)):
            rows.append(
                {"muni_code": muni, "year": year, "type": "flats", "valuation_sqm_eur": flats * k}
            )
            rows.append(
                {
                    "muni_code": muni,
                    "year": year,
                    "type": "villas",
                    "valuation_sqm_eur": villas * 1.0,
                }
            )
    rows.append({"muni_code": "0003", "year": 2025, "type": "flats", "valuation_sqm_eur": 90.0})
    return pd.DataFrame(rows)


def test_flats_vs_villas_ratio_and_real_change():
    deflator = pd.Series({2011: 1.2, 2025: 1.0})
    out = pt.flats_vs_villas(_valuation(), deflator)
    assert out.loc[2011, "flats_to_villas"] == pytest.approx(1.75)  # median of 2.0 and 1.5
    assert out.loc[2025, "flats_to_villas"] == pytest.approx(3.5)
    assert out.loc[2025, "municipalities_n"] == 2  # 0003 has no villa value
    change = pt.valuation_change(_valuation(), deflator, 2011, 2025)
    assert change.loc["villas", "median_real_change_pct"] == pytest.approx(100 * (1 / 1.2 - 1))
    assert change.loc["flats", "median_real_change_pct"] == pytest.approx(100 * (2 / 1.2 - 1))


def test_appraisal_ratio_balanced_against_all():
    out = pt.appraisal_vs_transaction(_panel(), 2020, 2021)
    assert out["balanced_n"].tolist() == [3, 3]
    assert out.loc[2020, "balanced_median"] == pytest.approx(1.1)
    assert out.loc[2021, "balanced_median"] == pytest.approx(121 / 120)
    assert out.loc[2020, "all_n"] == 4
    assert out.loc[2021, "all_n"] == 3
    assert out.loc[2020, "all_median"] == pytest.approx(1.1)  # 1.1, 1.1, 1.1, 1.5


def test_growth_leadlag_finds_the_planted_lead():
    rng = np.random.default_rng(0)
    n, years = 80, list(range(2016, 2026))
    appraisal_growth = rng.normal(0.05, 0.03, (n, len(years)))
    price_growth = np.roll(appraisal_growth, 1, axis=1) + rng.normal(0, 0.003, (n, len(years)))
    rows = []
    for i in range(n):
        val, price = 100.0, 100.0
        for j, year in enumerate(years):
            val *= np.exp(appraisal_growth[i, j])
            price *= np.exp(price_growth[i, j])
            rows.append(
                {
                    "muni_code": f"{i:04d}",
                    "year": year,
                    "valuation_sqm_eur": val,
                    "price_sqm_eur": price,
                }
            )
    out = pt.growth_leadlag(pd.DataFrame(rows), 2016, 2025, range(-1, 3)).set_index("lag_years")[
        "corr"
    ]
    assert out.idxmax() == 1
    assert out.loc[1] > 0.9
