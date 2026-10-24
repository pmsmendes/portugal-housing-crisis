import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import age_structure as ag


def _pop(rows):
    """rows: {(muni, year): {age_group: n}} -> tidy population frame."""
    return pd.DataFrame(
        [
            {"muni_code": m, "year": y, "age_group": g, "population_n": n}
            for (m, y), groups in rows.items()
            for g, n in groups.items()
        ]
    )


def _flat(n=10):
    return {g: n for g in ag.AGE_ORDER}


def test_bands_partition_the_population_and_80plus_is_a_subset():
    row = ag.band_counts(_pop({("0101", 2011): _flat(10)})).iloc[0]
    assert row["age_0_14"] == 30 and row["age_25_44"] == 40 and row["age_65plus"] == 50
    assert row["population_n"] == 180 == sum(row[b] for b in ag.PARTITION)
    assert row["age_80plus"] == 20


def test_missing_group_makes_the_band_nan_rather_than_a_short_count():
    groups = _flat()
    del groups["30-34"]
    counts = ag.band_counts(_pop({("0101", 2011): groups}))
    assert np.isnan(counts.loc[0, "age_25_44"]) and np.isnan(counts.loc[0, "population_n"])


def test_shares_and_ageing_index():
    old = _flat(10)
    old.update({g: 30 for g in ag.BANDS["age_65plus"]})
    counts = ag.band_counts(_pop({("0101", 2011): _flat(10), ("0101", 2023): old}))
    shares = ag.band_shares(counts).set_index("year")
    assert shares.loc[2011, "age_65plus_pct"] == pytest.approx(100 * 50 / 180)
    assert shares.loc[2011, "ageing_index"] == pytest.approx(100 * 50 / 30)
    assert shares.loc[2023, "age_65plus_pct"] > shares.loc[2011, "age_65plus_pct"]
    assert sum(shares.loc[2023, f"{b}_pct"] for b in ag.PARTITION) == pytest.approx(100)


def test_national_bands_sum_municipalities_and_change_is_in_points():
    rows = {
        ("0101", 2011): _flat(10),
        ("0102", 2011): _flat(20),
        ("0101", 2023): _flat(10),
        ("0102", 2023): _flat(10),
    }
    counts = ag.band_counts(_pop(rows))
    assert ag.national_bands(counts).loc[2011, "population_n"] == 180 + 360
    ch = ag.change_between(ag.band_shares(counts), 2011, 2023, ["age_65plus_pct"])
    assert ch["age_65plus_pct_change_pp"].abs().max() == pytest.approx(0)  # flat profiles
    assert set(ch.columns) == {
        "age_65plus_pct_2011",
        "age_65plus_pct_2023",
        "age_65plus_pct_change_pp",
    }


def test_national_profile_is_in_age_order():
    prof = ag.national_profile(_pop({("0101", 2011): _flat(1), ("0102", 2011): _flat(2)}), [2011])
    assert list(prof.index) == ag.AGE_ORDER and (prof[2011] == 3).all()
