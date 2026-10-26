import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import renovation


def _works(n=6):
    """Family-housing and other buildings for n municipalities, 2010-2021; the first municipality renovates more."""
    rows = []
    for i in range(n):
        code = f"{i + 101:04d}"
        for year in range(2010, 2022):
            alt = 10 if i == 0 else 2
            new = 20
            for project, count in (("new", new), ("alteration", alt), ("total", new + alt)):
                for purpose, share in (("family_housing", 1.0), ("other", 0.0), ("total", 1.0)):
                    n_lic = count * share
                    n_comp = np.nan if year < 2011 else count * share / 2
                    rows.append((code, year, project, purpose, n_lic, n_comp))
    return pd.DataFrame(
        rows,
        columns=[
            "muni_code",
            "year",
            "project",
            "purpose",
            "licensed_buildings_n",
            "completed_buildings_n",
        ],
    )


def _stock(n=6):
    return pd.DataFrame(
        {"dwellings_2011_n": 1000.0},
        index=pd.Index([f"{i + 101:04d}" for i in range(n)], name="muni_code"),
    )


def test_national_sums_family_housing_and_leaves_early_completions_missing():
    out = renovation.national(_works())
    assert out.loc[2015, "licensed_new_n"] == 6 * 20
    assert out.loc[2015, "licensed_alteration_n"] == 10 + 5 * 2
    assert np.isnan(out.loc[2010, "completed_new_n"]) and out.loc[2011, "completed_new_n"] == 60
    share = out.loc[2015, "alteration_share_licensed_pct"]
    assert share == pytest.approx(100 * 20 / (120 + 20))


def test_changes_between_two_years():
    out = renovation.changes(renovation.national(_works()), {"w": (2012, 2020)}, ["licensed_new_n"])
    assert out.loc["w", "licensed_new_n"] == pytest.approx(0.0)


def test_intensity_counts_works_per_1000_dwellings_and_their_share():
    out = renovation.intensity(_works(), _stock(), start=2012, end=2021)
    first, other = out.loc["0101"], out.loc["0102"]
    assert first["completed_alteration_n"] == 10 * 5  # ten years, 5 completed a year
    assert first["completed_alteration_per_1000"] == pytest.approx(1000 * 50 / 1000)
    assert other["completed_alteration_per_1000"] == pytest.approx(10.0)
    assert first["alteration_share_completed_pct"] == pytest.approx(100 * 50 / (50 + 100))
    assert first["alteration_share_completed_pct"] > other["alteration_share_completed_pct"]


def test_association_is_spearman_with_n():
    rng = np.random.default_rng(0)
    x = rng.normal(size=60)
    frame = pd.DataFrame({"x": x, "up": 2 * x + rng.normal(0, 0.1, 60), "down": -x})
    out = renovation.association(frame, "x", ["up", "down"])
    assert out.loc["up", "spearman"] > 0.95 and out.loc["down", "spearman"] == pytest.approx(-1.0)
    assert (out["n"] == 60).all()


def test_years_to_clear_scales_with_the_usable_share_and_dwellings_per_building():
    out = renovation.years_to_clear(400_000, 2_000, [1, 4], [0.25, 1.0])
    assert out.loc[1, "25% usable"] == pytest.approx(50.0)
    assert out.loc[1, "100% usable"] == pytest.approx(200.0)
    assert out.loc[4, "100% usable"] == pytest.approx(50.0)


def test_group_summary_gives_medians_and_counts():
    frame = pd.DataFrame({"v": [1.0, 3.0, 10.0, 20.0]}, index=list("abcd"))
    out = renovation.group_summary(frame, pd.Series(["u", "u", "r", "r"], index=frame.index), ["v"])
    assert out.loc["u", "v"] == 2.0 and out.loc["r", "v"] == 15.0
    assert (out["municipalities_n"] == 2).all()
