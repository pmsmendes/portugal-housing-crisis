import pandas as pd
import pytest

from pthousing.analysis import municipal_revenue as mr


def _rev():
    return pd.DataFrame(
        {
            "muni_code": ["0101", "0102", "0101", "0102"],
            "year": [2021, 2021, 2022, 2022],
            "imi_eur": [100.0, 50.0, 110.0, 50.0],
            "imt_eur": [20.0, 0.0, 40.0, 10.0],
            "current_receipts_eur": [1000.0, 500.0, 1000.0, 500.0],
        }
    )


def _panel(rates):
    return pd.DataFrame({"muni_code": ["0101", "0102"], "year": 2021, "imi_urban_pct": rates})


def test_shares_are_percent_of_current_receipts():
    s = mr.shares(_rev())
    assert s.loc[0, "imi_share_pct"] == pytest.approx(10.0)
    assert s.loc[0, "imi_imt_share_pct"] == pytest.approx(12.0)


def test_floor_room_takes_the_share_of_the_bill_above_the_floor_and_uses_the_year_before():
    out = mr.floor_room(_rev(), _panel([0.45, 0.30]), 2022)
    assert out.loc["0101", "room_eur"] == pytest.approx(110.0 * (0.45 - 0.30) / 0.45)
    assert out.loc["0101", "room_share_of_current_pct"] == pytest.approx(100 * 110 / 3 / 1000)
    assert out.loc["0102", "room_eur"] == 0.0  # at the floor


def test_floor_room_leaves_out_councils_without_a_rate():
    out = mr.floor_room(_rev(), _panel([0.45, float("nan")]), 2022)
    assert list(out.index) == ["0101"]


def test_imt_windfall_uses_start_year_receipts_and_flags_a_zero_start():
    w = mr.imt_windfall(_rev(), 2021, 2022)
    assert w.loc["0101", "imt_change_eur"] == 20.0
    assert w.loc["0101", "imt_change_pct"] == pytest.approx(100.0)
    assert pd.isna(w.loc["0102", "imt_change_pct"])
    assert w.loc["0102", "imt_change_share_of_current_pct"] == pytest.approx(2.0)


def test_actual_imi_per_dwelling_and_bottom_up_check_on_a_proportional_model():
    dwellings = pd.Series({"0101": 10.0, "0102": 5.0})
    actual = mr.actual_imi_per_dwelling(_rev(), dwellings, 2021)
    assert actual.to_dict() == {"0101": 10.0, "0102": 10.0}
    codes = [f"{i:04d}" for i in range(1, 21)]
    a = pd.Series(range(10, 30), index=codes, dtype=float)
    check = mr.bottom_up_check(a, 2 * a)  # the model is the actual at twice the level
    assert check["rank_correlation"] == pytest.approx(1.0)
    assert check["ratio_median"] == pytest.approx(0.5)
    assert check["municipalities_n"] == 20
