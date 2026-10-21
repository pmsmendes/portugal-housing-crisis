import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from pthousing.viz import charts  # noqa: E402


def _title(fig):
    return fig.texts[0].get_text()


def _nat():
    q = pd.date_range("2005-01-01", "2026-04-01", freq="QS")
    n = len(q)
    base = pd.DataFrame({"period_start": q})
    base["hpi_total_b2025"] = np.where(q.year >= 2009, np.linspace(40, 114, n), np.nan)
    base["hpi_total_real_b2025"] = base["hpi_total_b2025"] * np.linspace(1.3, 0.95, n)
    base["hpi_pt_b2015"] = np.where(q.year >= 2008, np.linspace(105, 300, n), np.nan)
    base["hpi_eu27_b2015"] = np.linspace(85, 170, n)
    for col in charts.PEER_COLUMNS:
        base[col] = np.linspace(80, 150, n)
    base["mortgage_rate_new_lt1y_pct"] = np.r_[
        np.linspace(3.5, 0.6, n // 2), np.linspace(0.6, 4.8, n - n // 2)
    ]
    base["mortgage_aprc_new_pct"] = base["mortgage_rate_new_lt1y_pct"] + 1.5
    base["mortgage_rate_stock_gt5y_pct"] = base["mortgage_rate_new_lt1y_pct"] * 0.8
    base["mortgage_payment_100k_eur"] = 300 + 40 * base["mortgage_rate_new_lt1y_pct"]
    return base


def test_real_vs_nominal_title_names_the_real_low_and_the_rise_since():
    nat = _nat()
    real = nat.set_index("period_start")["hpi_total_real_b2025"].dropna()
    ratio = real.iloc[-1] / real.min()
    title = _title(charts.hpi_real_vs_nominal(nat))
    assert f"until {real.idxmin().year}" in title and f"{ratio:.1f}x" in title


def test_peers_title_uses_the_latest_index_levels():
    title = _title(charts.hpi_peers(_nat()))
    assert "3.0x" in title and "1.7x" in title  # 300 and 170 on a 2015 = 100 base


def test_mortgage_rates_title_reports_trough_peak_and_payment_rise():
    nat = _nat()
    title = _title(charts.mortgage_rates(nat))
    assert "0.6%" in title and "4.8%" in title and "more a month" in title


def _index(price, rent):
    return pd.DataFrame({"price": price, "rent": rent}, index=[2020, 2021, 2022, 2023, 2024])


def test_growth_index_title_merges_equal_totals_and_names_the_faster_recent_series():
    equal = _index([100, 106, 111, 116, 124], [100, 103, 105, 114, 124])
    title = _title(charts.real_growth_index(equal, 187, 2020))
    assert "both rose about 24% since 2020" in title and "rents rose faster (18% vs 12%)" in title
    different = _index([100, 105, 110, 118, 130], [100, 101, 102, 104, 110])
    title = _title(charts.real_growth_index(different, 50, 2020))
    assert "rents rose 10% and real prices 30%" in title and "prices rose faster" in title


def test_price_fan_and_trend_panels_return_figures_with_computed_titles():
    years = pd.Index(range(2016, 2026))
    fan = pd.DataFrame(
        {"q10": 300.0, "q50": np.linspace(600, 1000, 10), "q90": 1500.0, "n": 300}, index=years
    )
    lisboa = pd.Series(np.linspace(2500, 4500, 10), index=years)
    fig = charts.price_fan(fan, lisboa, "Lisboa", (280, 306))
    assert "rose 67%" in _title(fig) and "Lisboa costs 4.5x the median" in _title(fig)
    panels = [
        {
            "title": "PTI",
            "fan": pd.DataFrame(
                {"q10": 4, "q50": np.linspace(8, 9.5, 9), "q90": np.linspace(12, 18, 9), "n": 299},
                index=range(2016, 2025),
            ),
            "unit_fmt": "{:.1f}",
        },
        {
            "title": "RTI",
            "fan": pd.DataFrame(
                {"q10": 40, "q50": 60.0, "q90": 90, "n": 200}, index=range(2020, 2025)
            ),
            "unit_fmt": "{:.0f}%",
            "step": 1,
        },
    ]
    title = _title(charts.indicator_trends(panels))
    assert (
        "9.5 years of income" in title and "8.0 in 2016" in title and "90th percentile, 18" in title
    )


def test_rate_effect_and_dumbbell_titles():
    years = pd.Index(range(2016, 2025))
    actual = pd.Series(np.linspace(28, 45, 9), index=years)
    fixed = pd.Series(np.linspace(28, 33, 9), index=years)
    rates = pd.Series(2.0, index=years)
    title = _title(charts.burden_rate_effect(actual, fixed, 2016, rates))
    assert "12 of the 17-point rise" in title
    rank = pd.DataFrame(
        {"muni_name": ["Lagos", "Aljezur"], "start": [19.0, 18.0], "end": [31.6, 30.9]}
    )
    assert "In Lagos a typical home now costs 32 years of income" == _title(
        charts.pti_dumbbell(rank, 2016, 2024)
    )
