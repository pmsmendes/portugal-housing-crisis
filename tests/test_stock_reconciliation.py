import pandas as pd
import pytest

from pthousing.analysis import stock_reconciliation as sr


def _stock():
    rows = []
    for code, (a, b) in (("0101", (1000, 1090)), ("0102", (500, 480)), ("0103", (200, 200))):
        rows.append({"muni_code": code, "census_year": 2011, "dwellings_n": float(a)})
        rows.append({"muni_code": code, "census_year": 2021, "dwellings_n": float(b)})
    return pd.DataFrame(rows)


def _panel():
    rows = []
    for code, per_year in (("0101", 10.0), ("0102", 5.0), ("0103", 0.0)):
        for year in range(2011, 2022):
            rows.append({"muni_code": code, "year": year, "completed_n": per_year})
    return pd.DataFrame(rows)


def test_reconcile_counts_completions_after_the_first_census_year_only():
    out = sr.reconcile(_panel(), _stock())
    assert out.loc["0101", "completions_n"] == 100  # 2012-2021, not 2011
    assert out.loc["0101", "added_n"] == 90
    assert out.loc["0101", "gap_n"] == -10
    assert out.loc["0101", "gap_per_1000"] == pytest.approx(-10.0)
    assert out.loc["0101", "retention"] == pytest.approx(0.9)


def test_reconcile_handles_losing_municipalities_and_no_completions():
    out = sr.reconcile(_panel(), _stock())
    assert out.loc["0102", "added_n"] == -20
    assert out.loc["0102", "retention"] == pytest.approx(-0.4)
    assert pd.isna(out.loc["0103", "retention"])  # no completions: no ratio
    assert out.loc["0103", "gap_n"] == 0


def test_aggregate_sums_counts_and_rebuilds_ratios():
    rec = sr.reconcile(_panel(), _stock())
    nat = sr.aggregate(rec).loc["Portugal"]
    assert nat["added_n"] == 70
    assert nat["completions_n"] == 150
    assert nat["retention"] == pytest.approx(70 / 150)
    assert nat["gap_per_1000"] == pytest.approx(1000 * (70 - 150) / 1700)
    assert nat["losing_n"] == 1
    assert nat["municipalities_n"] == 3


def test_aggregate_by_group_does_not_average_ratios():
    rec = sr.reconcile(_panel(), _stock())
    by = pd.Series({"0101": "a", "0102": "a", "0103": "b"})
    out = sr.aggregate(rec, by)
    assert out.loc["a", "retention"] == pytest.approx(70 / 150)
    assert pd.isna(out.loc["b", "retention"])


def test_roll_stock_forward_and_backward_from_the_anchor():
    done = pd.Series({2010: 4.0, 2011: 6.0, 2012: 10.0, 2013: 20.0})
    out = sr.roll_stock(done, 2012, 100.0, 1.0)
    assert out.loc[2012] == 100
    assert out.loc[2013] == 120
    assert out.loc[2011] == 90
    assert out.loc[2010] == 84


def test_roll_stock_scales_the_flow_by_the_retention():
    done = pd.Series({2011: 10.0, 2012: 10.0, 2013: 10.0})
    out = sr.roll_stock(done, 2013, 100.0, 0.5)
    assert out.loc[2011] == pytest.approx(90.0)


def test_roll_stock_accepts_a_retention_by_year():
    done = pd.Series({2011: 10.0, 2012: 10.0, 2013: 10.0})
    out = sr.roll_stock(done, 2013, 100.0, pd.Series({2011: 1.0, 2012: 0.5, 2013: 0.0}))
    assert out.loc[2012] == 100  # 2013 adds nothing
    assert out.loc[2011] == pytest.approx(95.0)  # 2012 added 5


def _done_and_anchors():
    done = pd.Series({year: 10.0 for year in range(2000, 2026)})
    # 2001-2011: 100 completions, count +125; 2011-2021: 100 completions, count +80
    return done, {2001: 1000.0, 2011: 1125.0, 2021: 1205.0}


def test_interval_retentions_are_net_addition_over_completions():
    done, anchors = _done_and_anchors()
    out = sr.interval_retentions(done, anchors)
    assert out.loc[2011] == pytest.approx(1.25)
    assert out.loc[2021] == pytest.approx(0.8)


def test_stock_path_meets_every_census_and_uses_each_decades_retention():
    done, anchors = _done_and_anchors()
    path = sr.stock_path(done, anchors)
    for year, count in anchors.items():
        assert path.loc[year, "stock_n"] == pytest.approx(count)
        assert path.loc[year, "census_n"] == count
    assert path.loc[2005, "retention"] == pytest.approx(1.25)
    assert path.loc[2015, "retention"] == pytest.approx(0.8)
    # outside the censuses the nearest decade's retention applies by default
    assert path.loc[2000, "retention"] == pytest.approx(1.25)
    assert path.loc[2024, "retention"] == pytest.approx(0.8)
    assert path.loc[2025, "stock_n"] == pytest.approx(1205.0 + 4 * 10.0 * 0.8)
    assert path["growth_pct"].dropna().shape[0] == len(done) - 1


def test_stock_path_outside_retentions_set_the_band():
    done, anchors = _done_and_anchors()
    low = sr.stock_path(done, anchors, outside=(0.8, 0.8))
    high = sr.stock_path(done, anchors, outside=(1.25, 1.25))
    assert low.loc[2025, "stock_n"] < high.loc[2025, "stock_n"]
    assert (
        low.loc[2000, "stock_n"] > high.loc[2000, "stock_n"]
    )  # a smaller retention takes off less
    assert low.loc[2011, "stock_n"] == pytest.approx(high.loc[2011, "stock_n"])
