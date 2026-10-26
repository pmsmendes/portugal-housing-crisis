import pandas as pd
import pytest

from pthousing.analysis import incidence as inc


def _stock():
    return pd.DataFrame(
        {
            "muni_code": ["0101", "0102", "0101"],
            "census_year": [2021, 2021, 2011],
            "dwellings_n": [100, 50, 90],
            "dwellings_usual_n": [60, 30, 50],
            "dwellings_secondary_n": [25, 10, 20],
            "dwellings_vacant_n": [15, 10, 20],
        }
    )


def _census():
    return pd.DataFrame(
        {
            "muni_code": ["0101", "0102"],
            "census_year": [2021, 2021],
            "owner_occupied_n": [30, 20],
            "rented_n": [20, 5],
            "other_tenure_n": [10, 5],
        }
    )


def test_dwellings_by_use_splits_usual_by_tenure_and_adds_to_the_stock():
    out = inc.dwellings_by_use(_stock(), _census())
    assert out.loc["0101", "owner_occupied"] == pytest.approx(30.0)  # 60 x 30/60
    assert out.loc["0102", "rented"] == pytest.approx(5.0)  # 30 x 5/30
    assert out.sum(axis=1).tolist() == pytest.approx([100, 50])
    assert list(out.columns) == list(inc.USES)


def test_capped_cut_stops_at_the_legal_floor():
    rate = pd.Series({"a": 0.45, "b": 0.32, "c": 0.30})
    out = inc.capped(rate, 0.05, floor=0.30)
    assert out.tolist() == pytest.approx([0.05, 0.02, 0.0])


def test_imi_cut_by_use_scales_with_the_cut_over_the_rate():
    uses = inc.dwellings_by_use(_stock(), _census())
    unit = pd.Series({"0101": 400.0, "0102": 200.0})
    rate = pd.Series({"0101": 0.40, "0102": 0.30})
    cut = pd.Series({"0101": 0.10, "0102": 0.0})
    out = inc.imi_cut_by_use(uses, unit, rate, cut)
    assert out.loc["0101", "owner_occupied"] == pytest.approx(30 * 400 * 0.10 / 0.40)
    assert out.loc["0102"].sum() == 0.0
    assert inc.shares(out).sum() == pytest.approx(100)


def test_by_group_adds_shares_of_each_total():
    frame = pd.DataFrame({"x": [1.0, 3.0, 4.0], "y": [2.0, 2.0, 4.0]})
    group = pd.Series(["lo", "lo", "hi"])
    out = inc.by_group(frame, group, {"x": "x", "y": "y"})
    assert out.loc["lo", "x"] == 4.0
    assert out.loc["lo", "x_share_pct"] == pytest.approx(50.0)
    assert out["y_share_pct"].sum() == pytest.approx(100)


def test_terciles_and_sales_value():
    values = pd.Series(range(9), name="v", dtype=float)
    out = inc.terciles(values, ("a", "b", "c"))
    assert out.value_counts().to_dict() == {"a": 3, "b": 3, "c": 3}
    panel = pd.DataFrame(
        {
            "muni_code": ["0101", "0101"],
            "year": [2023, 2024],
            "sales_12m_n": [10.0, 20.0],
            "price_sqm_eur_real": [1000.0, 2000.0],
        }
    )
    assert inc.sales_value(panel, 2024)["0101"] == pytest.approx(20 * 2000 * 100)
