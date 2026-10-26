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


def test_observed_retention_closes_the_census_gap():
    rec = sr.reconcile(_panel(), _stock())
    nat = sr.aggregate(rec).loc["Portugal"]
    done = _panel().groupby("year")["completed_n"].sum()
    path = sr.stock_path(
        done, {2011: nat["dwellings_start_n"], 2021: nat["dwellings_end_n"]}, nat["retention"]
    )
    assert path.loc[2021, "stock_n"] == nat["dwellings_end_n"]
    assert path.loc[2011, "stock_n"] == pytest.approx(nat["dwellings_start_n"])
    assert path.loc[2011, "census_n"] == nat["dwellings_start_n"]
    assert path["growth_pct"].dropna().shape[0] == len(done) - 1
