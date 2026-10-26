import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import household_size as hs


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


def _counts():
    return pd.DataFrame(
        {
            "muni_code": ["0101", "0101", "0102", "0102"],
            "year": [2011, 2021, 2011, 2021],
            "population_n": [250.0, 250.0, 50.0, 40.0],
        }
    )


def test_profile_gives_size_and_one_person_share_for_both_censuses():
    out = hs.profile(_households(), _counts()).set_index("muni_code")
    assert out.loc["0101", "persons_per_household_2011"] == pytest.approx(2.5)
    assert out.loc["0101", "persons_per_household_2021"] == pytest.approx(2.5)
    assert out.loc["0101", "one_person_2011_pct"] == pytest.approx(10.0)
    assert out.loc["0101", "one_person_change_pp"] == pytest.approx(10.0)
    assert out.loc["0102", "size_change"] == pytest.approx(2.0 - 2.5)


def test_decompose_parts_add_to_the_change_in_households():
    prof = hs.profile(_households(), _counts())
    out = hs.decompose(prof).set_index("muni_code")
    assert out.loc["0101", "households_change_n"] == 0
    assert out.loc["0102", "households_change_n"] == 0
    assert out["from_population_n"].add(out["from_size_n"]).tolist() == pytest.approx(
        out["households_change_n"].tolist()
    )
    # 0102: population 50 -> 40 at 2.5 persons per household would lose 4 households; the other 4 come from size
    assert out.loc["0102", "from_population_n"] == pytest.approx(-4.0)
    assert out.loc["0102", "from_size_n"] == pytest.approx(4.0)


def test_decompose_log_identity():
    out = hs.decompose(hs.profile(_households(), _counts()))
    assert np.allclose(out["dlog_households"], out["dlog_population"] - out["dlog_size"])


def test_aggregate_weights_by_households_and_rebuilds_ratios():
    prof = hs.profile(_households(), _counts())
    country = hs.aggregate(prof).loc["Portugal"]
    assert country["households_2011_n"] == 120
    assert country["persons_per_household_2011"] == pytest.approx(300 / 120)
    assert country["one_person_2011_pct"] == pytest.approx(100 * 15 / 120)
    by = pd.Series({"0101": "a", "0102": "b"})
    groups = hs.aggregate(prof, by)
    assert groups.loc["b", "one_person_2021_pct"] == pytest.approx(100 * 8 / 20)
