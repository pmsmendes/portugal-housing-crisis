import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import rents


def _panel():
    rows = []
    spec = {
        # code: (rent 2020, rent 2024, price 2020, price 2024, foreign 2020, foreign 2023)
        "0101": (10.0, 12.0, 1000.0, 1500.0, 1.0, 3.0),
        "0102": (8.0, 8.0, 800.0, 1000.0, 2.0, 2.0),
        "0103": (np.nan, np.nan, 500.0, 600.0, 1.0, 1.5),  # no rent published: dropped
    }
    for code, (r0, r1, p0, p1, f0, f1) in spec.items():
        for year in range(2020, 2025):
            frac = (year - 2020) / 4
            rows.append(
                {
                    "muni_code": code,
                    "year": year,
                    "rent_sqm_eur_real": r0 + frac * (r1 - r0) if year in (2020, 2024) else np.nan,
                    "price_sqm_eur_real": p0 + frac * (p1 - p0),
                    "foreign_residents_pct": f0 + (f1 - f0) * min(year - 2020, 3) / 3,
                    "population_n": 1000.0 + 10 * (year - 2020),
                    "completed_n": 5.0,
                    "dwellings_2021_n": 500.0,
                    "al_units_per_1000_dwellings_2021": 20.0,
                }
            )
    return pd.DataFrame(rows)


def test_change_frame_keeps_only_municipalities_with_a_rent_in_both_years():
    out = rents.change_frame(_panel())
    assert list(out.index) == ["0101", "0102"]


def test_logs_changes_and_the_price_to_rent_difference():
    out = rents.change_frame(_panel())
    assert out.loc["0101", "dlog_rent"] == pytest.approx(np.log(1.2))
    assert out.loc["0101", "dlog_price"] == pytest.approx(np.log(1.5))
    assert out.loc["0101", "dlog_price_to_rent"] == pytest.approx(np.log(1.5) - np.log(1.2))
    assert out.loc["0102", "dlog_rent"] == 0.0
    assert out.loc["0101", "rent_start_log"] == pytest.approx(np.log(10.0))
    assert out.loc["0101", "price_start_log"] == pytest.approx(np.log(1000.0))


def test_drivers_use_their_own_windows():
    out = rents.change_frame(_panel())
    assert out.loc["0101", "foreign_change_pp"] == pytest.approx(2.0)  # 2020 to 2023
    assert out.loc["0101", "population_change_pct"] == pytest.approx(3.0)  # 1000 to 1030
    assert out.loc["0101", "completions_per_1000"] == pytest.approx(1000 * 4 * 5 / 500)  # 2021-2024
    assert out.loc["0101", "al_per_1000"] == 20.0


def test_sample_share_is_the_population_share_of_the_frame():
    panel = _panel()
    share = rents.sample_share(panel, rents.change_frame(panel), 2021)
    assert share == pytest.approx(100 * 2 / 3)
