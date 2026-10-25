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


def test_moran_trends_title_follows_the_data():
    rows = [
        {"year": y, "series": s, "I": v + 0.05 * i, "p_sim": 0.001}
        for s, v in (("pti", 0.6), ("income", 0.5), ("price", 0.62))
        for i, y in enumerate((2016, 2017, 2018))
    ]
    fig = charts.moran_trends(pd.DataFrame(rows), "Queen contiguity.")
    assert "resemble each other more" in fig.texts[0].get_text()
    assert "0.60 to 0.70" in fig.texts[0].get_text()
    falling = pd.DataFrame(rows).assign(I=lambda d: d["I"].iloc[::-1].to_numpy())
    assert "differ from each other less" in charts.moran_trends(falling, "").texts[0].get_text()


def test_coef_ladder_has_one_panel_per_driver_and_a_computed_title():
    rows = []
    for spec in ("Main", "Region", "Other"):
        for term, coef in (("a", 0.02), ("b", -0.01)):
            rows.append(
                {"spec": spec, "term": term, "coef": coef, "ci_low": coef - 0.01,
                 "ci_high": coef + 0.01, "sd_within": 2.0, "coef_per_sd": coef * 2.0}
            )  # fmt: skip
    fig = charts.coef_ladder(
        pd.DataFrame(rows),
        {"a": "Driver A (unit)", "b": "Driver B"},
        "Main",
        "Region",
        "price-to-income",
    )
    assert len(fig.axes) == 2
    assert "driver a" in fig.texts[0].get_text() and "+4.0%" in fig.texts[0].get_text()


def test_neighbour_placebo_title_compares_lag_and_lead():
    def rows(effects, lag, lead):
        return [
            {"spec": f"{effects}|{key}", "term": "w_log_pti", "coef": c, "ci_low": c - 0.1, "ci_high": c + 0.1}
            for key, c in (("lag", lag), ("lead", lead))
        ]  # fmt: skip

    labels = {"lag": "Last year", "lead": "Next year (placebo)"}
    close = pd.DataFrame(rows("A", 0.3, 0.3) + rows("B", 0.2, 0.15))
    text = charts.neighbour_placebo(close, labels, "A", "B").texts[0].get_text()
    assert "(0.20)" in text and "almost as well (0.15)" in text
    far = pd.DataFrame(rows("A", 0.3, 0.3) + rows("B", 0.2, 0.02))
    assert "much less (0.02)" in charts.neighbour_placebo(far, labels, "A", "B").texts[0].get_text()


def test_segment_trends_draws_one_panel_per_dimension_with_a_computed_title():
    years = list(range(2016, 2025))
    line = lambda start, end: pd.Series(np.linspace(start, end, len(years)), index=years)  # noqa: E731
    panels = [
        {
            "title": "Coast",
            "series": {"coast": line(10, 17), "inland": line(7, 7.4), "estuary": line(8, 13)},
        },
        {"title": "Density", "series": {"urban": line(10, 16), "rural": line(6.5, 6.6)}},
    ]
    changes = {"coast": {"coast": 52.0, "inland": 10.0}, "density": {"urban": 72.0, "rural": 7.0}}
    fig = charts.segment_trends(panels, changes, 2016, 2024)
    assert len(fig.axes) == 2
    title = fig.texts[0].get_text()
    assert "72% in urban and 7% in rural" in title and "52% on the coast and 10% inland" in title


def test_construction_flows_title_names_peak_trough_and_latest():
    years = list(range(1995, 2026))
    done = pd.Series(
        [
            60_000 + 2_000 * min(y - 1995, 10)
            if y <= 2005
            else max(8_000, 80_000 - 7_000 * (y - 2005))
            for y in years
        ],
        index=years,
    )
    done.loc[2020:] = [10_000, 12_000, 18_000, 21_000, 25_000, 27_000]
    flows = pd.DataFrame({"completed_n": done, "licensed_n": done * 1.2})
    fig = charts.construction_flows(flows)
    title = fig.texts[0].get_text()
    assert f"from {done.max() / 1000:.0f}k in 2005" in title and "back to 27k" in title


def test_housing_balance_by_area_counts_areas_with_a_shortfall():
    census = pd.Series({"A": -30.0, "B": 10.0, "C": 50.0})
    after = pd.Series({"A": -70.0, "B": -20.0, "C": 3.0})
    fig = charts.housing_balance_by_area(census, after, {"census": 1.5, "after": -45.0})
    assert len(fig.axes) == 2
    assert "2 of 3 areas since 2021, against 1 of 3 between" in fig.texts[0].get_text()


def test_r2_ladder_title_names_first_block_and_the_rest():
    table = pd.DataFrame(
        {
            "block": ["Geography", "Demand", "Supply"],
            "r2": [0.55, 0.60, 0.61],
            "r2_adj": [0.50, 0.55, 0.55],
            "r2_added": [0.55, 0.05, 0.01],
            "n_obs": [270, 270, 270],
        }
    )
    fig = charts.r2_ladder(table, "price-to-income")
    title = fig.texts[0].get_text()
    assert "Geography explains 55%" in title and "add 6 points" in title


def test_imi_rate_changes_title_counts_cuts_increases_and_floor_share():
    years = pd.Series(range(2013, 2026))
    table = pd.DataFrame(
        {
            "year": years,
            "cuts": [50] * 12 + [90],
            "increases": [5] * 13,
            "at_floor_pct": np.linspace(40, 60, 13),
        }
    )
    title = _title(charts.imi_rate_changes(table))
    assert "690 rate cuts and 65 increases" in title and "60% of municipalities" in title


def _es_table(coefs):
    ks = [-2, 0, 1, 2]
    return pd.DataFrame(
        {
            "k": ks,
            "coef": coefs,
            "ci_low": [c - 0.02 for c in coefs],
            "ci_high": [c + 0.02 for c in coefs],
        }
    )


def test_event_study_plot_shows_the_pretrend_p_and_both_estimators():
    table = _es_table([-0.01, 0.0, 0.01, 0.02])
    fig = charts.event_study_plot(
        [
            {
                "title": "Per 0.01 pp",
                "table": table,
                "compare": table,
                "pretrend_p": 0.024,
                "benchmark": 0.19,
            }
        ]
    )
    assert "p = 0.02" in fig.axes[0].get_title(loc="left")
    assert fig.axes[0].get_legend() is not None


def test_robustness_ladder_title_counts_rejected_pretrends_and_ambiguous_intervals():
    rows = []
    for spec, p, lo, hi in (("Main", 0.02, -1.0, 1.0), ("Other", 0.5, -2.0, 0.1)):
        for k in (1, 2):
            rows.append(
                {"spec": spec, "k": k, "coef": 0.0, "ci_low": lo, "ci_high": hi, "pretrend_p": p}
            )
    title = _title(charts.robustness_ladder(pd.DataFrame(rows), "Main", (0.1, 0.19, 0.33)))
    assert title.startswith("1 of 2 specifications") and "1 fail the pre-trend test" in title


def _bands(end):
    years = np.arange(2025, 2036)
    return pd.DataFrame(
        {"year": years, "p10": end * 0.8, "p50": np.linspace(10, end, len(years)), "p90": end * 1.2}
    )


def test_scenario_fans_title_lists_the_end_value_of_each_scenario():
    bands = {"optimistic": _bands(12), "baseline": _bands(15), "pessimistic": _bands(20)}
    ref = {
        "years": np.array([2027.5]),
        "mean": np.array([12.0]),
        "lo80": np.array([11.0]),
        "hi80": np.array([13.0]),
    }
    fig = charts.scenario_fans(
        [{"title": "PTI", "unit_fmt": "{:.1f}", "bands": bands}], reference=ref
    )
    assert (
        _title(fig)
        == "Scenarios, median in the last year: optimistic 12.0, baseline 15.0, pessimistic 20.0"
    )


def test_policy_effects_title_names_the_best_package_and_counts_the_harmful():
    table = pd.DataFrame(
        {
            "label": ["Build", "Tax cut", "Free"],
            "pti_gain_p10": [0.1, -0.2, -0.1],
            "pti_gain_p50": [0.3, -0.1, 0.0],
            "pti_gain_p90": [0.5, -0.05, 0.1],
            "cost_bn": [3.0, 2.0, 0.0],
        }
    )
    title = _title(charts.policy_effects(table, 2035))
    assert title == "Build helps most (+0.30 years of income); 1 of 3 packages raise the ratio"


def test_sensitivity_tornado_title_names_the_widest_input():
    table = pd.DataFrame(
        {
            "parameter": ["mortgage_rate_pct", "other_demand_half_life_years"],
            "kind": ["scenario", "scenario"],
            "low_pti_end": [14.5, 13.0],
            "high_pti_end": [15.7, 19.1],
            "swing_pti_end": [1.2, 6.1],
        }
    )
    title = _title(charts.sensitivity_tornado(table, 15.2, 2035))
    assert (
        title
        == "Fade of the other-demand boom moves price-to-income in 2035 by 6.1 years, the most of any input"
    )


def _skill(offset=0.0):
    rows = [
        {"method": m, "h": h, "spearman": s + offset}
        for m, s in (
            ("naive", np.nan),
            ("national_drift", -0.1),
            ("segment_trend", 0.4),
            ("own_trend", 0.2),
        )
        for h in (1, 2)
    ]
    return pd.DataFrame(rows)


def test_regional_skill_names_the_best_method_and_skips_naive():
    fig = charts.regional_skill({"Municipalities": _skill(), "Regions": _skill(-0.2)})
    assert "segment trend" in _title(fig)
    labels = [t.get_text() for t in fig.axes[0].get_yticklabels()]
    assert "naive" not in labels and len(labels) == 3


def test_outlook_ranking_colours_only_clear_differences():
    table = pd.DataFrame(
        {
            "label": ["A", "B", "C"],
            "relative": [10.0, 0.5, -8.0],
            "relative_lo80": [4.0, -5.0, -12.0],
            "relative_hi80": [16.0, 6.0, -4.0],
            "change_pct": [20.0, 8.0, 0.0],
        }
    )
    fig = charts.outlook_ranking(table, "region", "regions", 2, 2026)
    assert "A is expected to worsen most" in _title(fig)
    assert "2 of 3 regions differ clearly" in _title(fig)


def test_long_run_prices_title_is_computed_from_the_cycle():
    years = np.arange(1988, 2026)
    real = np.interp(years, [1988, 2001, 2013, 2025], [110, 140, 90, 210])
    long = pd.DataFrame(
        {
            "year": years,
            "hpi_real_b2015": real,
            "rent_real_b2015": np.linspace(75, 110, len(years)),
            "price_to_income_b2015": np.where(
                years >= 1995, np.interp(years, [1995, 2013, 2025], [140, 97, 167]), np.nan
            ),
        }
    )
    title = _title(charts.long_run_prices(long))
    assert "peaked in 2001" in title and "fell 36% to 2013" in title
    assert "passed that peak again in 2019" in title or "again in 2020" in title
    assert "1.2x its 1995 level" in title


def test_population_components_title_names_the_final_run_of_natural_decline():
    years = np.arange(1990, 2026)
    natural = np.where(years < 2005, 5000.0, -5000.0)
    natural[
        (years >= 1998) & (years < 2000)
    ] = -100.0  # an earlier dip does not start the final run
    balance = pd.DataFrame(
        {
            "natural_change_n": natural,
            "net_migration_n": np.full(len(years), 20000.0),
            "revision_n": np.where(years == 2021, 90000.0, 0.0),
        },
        index=pd.Index(years, name="year"),
    )
    rates = {
        label: pd.DataFrame(
            {
                "natural_per_1000_year": [0.0, -1.0, -5.0],
                "migration_per_1000_year": [3.0, 1.0, 0.0],
            },
            index=["urban", "intermediate", "rural"],
        )
        for label in ("2012-19", "2022-23")
    }
    fig = charts.population_components(balance, rates, first_year=1990)
    assert "Since 2005 deaths outnumber births" in _title(fig)


def test_property_tax_revenue_title_gives_the_change_since_2015_for_each_series():
    years = np.arange(1995, 2026)
    frame = pd.DataFrame(
        {
            "imi_real_eur_m": 1_000.0,
            "imt_real_eur_m": 500.0 + 10 * (years - 1995),
            "imi_real_b2015": np.where(years >= 2015, 100 - (years - 2015), 100.0),
            "imt_real_b2015": 100 + 5.0 * (years - 2015),
            "hpi_real_b2015": 100 + 4.0 * (years - 2015),
        },
        index=pd.Index(years, name="year"),
    )
    title = _title(charts.property_tax_revenue(frame))
    assert "+40%" in title and "+50%" in title and "-10%" in title
