import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import housing_mix as hm


def _households():
    rows = []
    for code, sizes in (
        ("0101", {2011: [10, 20, 30, 40], 2021: [20, 30, 20, 30]}),
        ("0102", {2011: [5, 5, 5, 5], 2021: [8, 6, 4, 2]}),
    ):
        for year, counts in sizes.items():
            for size, n in zip(["1", "2", "3", "4plus"], counts, strict=True):
                rows.append(
                    {"muni_code": code, "census_year": year, "size": size, "households_n": float(n)}
                )
    return pd.DataFrame(rows)


def _construction():
    rows = []
    for code, counts in (("0101", [10, 10, 60, 20]), ("0102", [1, 1, 1, 1])):
        for year in (2011, 2015, 2022):  # 2022 is outside the window
            for size, n in zip(["br_0_1", "br_2", "br_3", "br_4plus"], counts, strict=True):
                rows.append(
                    {"muni_code": code, "year": year, "size": size, "completed_n": float(n)}
                )
    return pd.DataFrame(rows)


def test_household_sizes_gives_both_censuses_and_the_change():
    out = hm.household_sizes(_households()).set_index(["muni_code", "size"])
    assert out.loc[("0101", "1"), "households_change_n"] == 10
    assert out.loc[("0102", "4plus"), "households_2011_n"] == 5


def test_completions_by_size_sums_the_window_and_relabels_bedrooms_as_persons():
    out = hm.completions_by_size(_construction(), 2011, 2021).set_index(["muni_code", "size"])
    assert out.loc[("0101", "3"), "completed_n"] == 120  # 2011 and 2015, not 2022
    assert set(out.index.get_level_values("size")) == {"1", "2", "3", "4plus"}


def test_national_comparison_shares_use_the_column_totals():
    out = hm.national_comparison(_households(), _construction())
    assert out["completed_n"].sum() == 2 * (100 + 4)
    assert out["completed_share_pct"].sum() == pytest.approx(100)
    assert out.loc["1", "households_change_n"] == 13
    assert list(out.index) == ["1", "2", "3", "4plus"]


def test_small_share_by_year_counts_t0_to_t2():
    out = hm.small_share_by_year(_construction())
    assert out.loc[2011] == pytest.approx(100 * 22 / 104)


def test_small_dwelling_gap_is_the_household_mix_minus_the_completion_mix():
    out = hm.small_dwelling_gap(_households(), _construction(), min_completions=50).set_index(
        "muni_code"
    )
    assert out.loc["0101", "small_households_pct"] == pytest.approx(50.0)  # (20 + 30) / 100
    assert out.loc["0101", "small_households_change_pp"] == pytest.approx(50 - 30)
    assert out.loc["0101", "small_completions_pct"] == pytest.approx(20.0)  # 2 x 20 of 2 x 100
    assert out.loc["0101", "small_gap_pp"] == pytest.approx(30.0)
    assert np.isnan(out.loc["0102", "small_completions_pct"])  # 8 completions: below the floor
