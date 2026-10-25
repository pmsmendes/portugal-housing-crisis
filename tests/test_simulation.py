import numpy as np
import pandas as pd
import pytest
import yaml

from pthousing.features import affordability as aff
from pthousing.simulation import engine as E
from pthousing.simulation import fiscal, funding, scenarios, supply

A = scenarios.load()


# ---- scenarios -----------------------------------------------------------------------------------


def test_range_checks_order_and_draws_stay_inside():
    with pytest.raises(ValueError):
        scenarios.Range(2, 1, 3)
    r = scenarios.Range(1.0, 1.5, 2.0)
    d = r.draw(np.random.default_rng(0), 1000)
    assert d.min() >= 1.0 and d.max() <= 2.0 and abs(d.mean() - 1.5) < 0.05
    assert (scenarios.Range(3, 3, 3).draw(np.random.default_rng(0), 4) == 3).all()


def test_shipped_assumptions_are_complete_and_ordered():
    assert set(A.scenarios) == {"optimistic", "baseline", "pessimistic"}
    for key in scenarios.SCENARIO_KEYS:
        assert A.scenarios["optimistic"][key] != A.scenarios["pessimistic"][key] or key == "x"
    assert A.end_year == A.start_year + A.horizon_years
    assert all(set(v) <= set(scenarios.LEVER_KEYS) for v in A.packages.values())
    # the ranges that carry a source note have a status
    assert all(n["status"] in {"literature", "project", "assumption"} for n in A.notes.values())


def test_empty_value_is_rejected(tmp_path):
    raw = yaml.safe_load(open(scenarios.SCENARIOS_YAML, encoding="utf-8"))
    raw["scenarios"]["baseline"]["mortgage_rate_pct"] = None
    bad = tmp_path / "s.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="mortgage_rate_pct"):
        scenarios.load(bad)


# ---- supply and fiscal accounting ----------------------------------------------------------------


def test_ramp_reaches_the_target_and_stays():
    out = supply.ramp(10.0, 40.0, 3, 5)
    assert out.tolist() == pytest.approx([20, 30, 40, 40, 40])


def test_usable_additions_counts_each_channel():
    kw = dict(net_ratio=0.9, usable_share=0.8, additionality=0.5, reoccupation=0.5, crowd_out=0.2)
    base = supply.usable_additions(1000, 0, 0, 0, **kw)
    assert base == pytest.approx(0.8 * 0.9 * 1000)
    assert supply.usable_additions(1000, 200, 0, 0, **kw) - base == pytest.approx(0.8 * 0.5 * 200)
    assert supply.usable_additions(1000, 0, 100, 0, **kw) - base == pytest.approx(50)
    assert supply.usable_additions(1000, 0, 0, 100, **kw) - base == pytest.approx(80)


def test_balance_pressure_is_positive_when_households_outrun_dwellings():
    assert supply.balance_pressure(1000.0, 1020.0, 5.0) == pytest.approx(0.015)
    assert supply.balance_pressure(1000.0, 1020.0, 30.0) < 0


def test_household_size_follows_trend_with_a_floor():
    out = supply.household_size_path(2.5, -0.1, 3)
    assert out.tolist() == pytest.approx([2.4, 2.3, 2.2])
    assert supply.household_size_path(1.6, -0.5, 2).min() == 1.5


def test_imi_benchmark_matches_the_p3_full_capitalisation_figure():
    # a permanent 0.01 pp cut, assessed value 75% of price, 4% discount rate: 0.19% of the price
    assert fiscal.imi_capitalisation(-0.01, 1.0, 0.75, 0.04) == pytest.approx(0.001875)
    assert fiscal.imi_capitalisation(-0.01, 0.0, 0.75, 0.04) == 0
    assert fiscal.imi_capitalisation(0.01, 1.0, 0.75, 0.04) < 0  # an increase lowers prices


def test_revenue_loss_signs_and_scale():
    # halving the average rate halves the revenue
    assert fiscal.imi_revenue_loss(-0.16, 0.32, 1000.0) == pytest.approx(500.0)
    assert fiscal.imi_revenue_loss(0.16, 0.32, 1000.0) == pytest.approx(-500.0)
    assert fiscal.imt_revenue_loss(-1.0, 30e9) == pytest.approx(300e6)
    assert fiscal.imt_capitalisation(-1.0, 1.0) == pytest.approx(0.01)


# ---- anchors and engine on a small synthetic country ---------------------------------------------


@pytest.fixture(scope="module")
def anc():
    rows = []
    for muni, (pop21, hh11, hh21) in {
        "0101": (6000, 2400, 2500),
        "0102": (4000, 1500, 1500),
    }.items():
        for year in (2011, 2021, 2023, 2024, 2025):
            pop = {2011: 0.97, 2021: 1.0, 2023: 1.05}.get(year, 1.05) * pop21
            rows.append(
                {
                    "muni_code": muni, "year": year, "population_n": pop,
                    "households_2011_n": hh11, "households_2021_n": hh21,
                    "pti_years": 10.0 if muni == "0101" else 8.0,
                    "mortgage_burden_pct": 45.0 if muni == "0101" else 35.0,
                    "completed_n": 200.0, "sales_12m_n": 100.0, "price_sqm_eur_real": 1000.0,
                    "imi_urban_pct": 0.3 if muni == "0101" else 0.4,
                }
            )  # fmt: skip
    panel = pd.DataFrame(rows)
    quarters = pd.date_range("2024-01-01", "2025-10-01", freq="QS")
    nat = pd.DataFrame(
        {
            "period_start": quarters,
            "hpi_total_real_b2025": [80.0] * 4 + [100.0] * 4,
            "mortgage_rate_new_lt1y_pct": [4.0] * 4 + [3.0] * 4,
        }
    )
    forecast = pd.DataFrame(
        {
            "series": ["Real house price index"] * 2,
            "period": ["2027Q2", f"{A.near_term_year}Q2"],
            "mean": [115.0, 130.0], "lo80": [105.0, 110.0], "hi80": [125.0, 150.0],
        }
    )  # fmt: skip
    return E.anchors(panel, nat, forecast, A)


def test_anchors_roll_the_start_year_forward(anc):
    assert anc.population == pytest.approx(10000 * 1.05 + 2 * A.common["population_change_2024"])
    assert anc.households == pytest.approx(anc.population / anc.persons_per_household)
    # persons per household: 9,700 / 3,900 in 2011 and 10,000 / 4,000 in 2021
    assert anc.household_size_trend == pytest.approx((10000 / 4000 - 9700 / 3900) / 10)
    # the median PTI of 9 grows with prices (80 -> 100) and shrinks with the income growth assumed for the start year
    income = 1 + A.common["income_growth_2025_pct"] / 100
    assert anc.pti_years == pytest.approx(9.0 * 1.25 / income)
    assert anc.mortgage_rate_pct == 3.0
    assert anc.near_term_log_growth == pytest.approx(np.log(130 / 100))
    assert anc.near_term_sigma == pytest.approx(np.log(150 / 110) / (2 * E.Z80))
    assert anc.imi_average_rate_pct == pytest.approx(0.35)
    assert anc.transaction_value_eur == pytest.approx(200 * 1000 * 100)


def test_calibration_reproduces_the_forecast_in_the_near_term(anc):
    r = E.run(A, anc, "baseline")
    k = anc.near_term_steps
    assert r.series["price_index"][0, k] == pytest.approx(100 * 1.3)
    shifted = E.run(A, anc, "baseline", p=E.central(A, near_term_z=1.0))
    assert shifted.series["price_index"][0, k] == pytest.approx(
        100 * 1.3 * np.exp(anc.near_term_sigma)
    )


def test_run_without_policy_has_no_cost_and_policy_is_dated(anc):
    assert E.run(A, anc, "baseline").series["cumulative_cost_eur"].max() == 0
    r = E.run(A, anc, "baseline", E.Policy(public_housing_units=1000))
    years = r.years[1:]
    cost = r.series["cost_eur"][0]
    assert (cost[years < A.policy_start_year] == 0).all()
    assert (cost[years >= A.policy_start_year] > 0).all()


def test_empty_policy_changes_nothing(anc):
    out = E.compare(A, anc, "baseline", E.Policy(), E.draw(A, 20))
    assert out["pti_gain"].abs().max() < 1e-12 and out["cost_eur"].max() == 0


def test_supply_levers_lower_price_to_income_and_cost_money(anc):
    p = E.draw(A, 50)
    for lever in ("construction_boost_units", "vacant_renovation_units", "public_housing_units"):
        out = E.compare(A, anc, "baseline", E.Policy(**{lever: 5000}), p)
        assert (out["pti_gain"] > 0).all() and (out["cost_eur"] > 0).all()
        assert (out["price_effect_pct"] < 0).all()
    small = E.compare(A, anc, "baseline", E.Policy(construction_boost_units=2000), p)
    big = E.compare(A, anc, "baseline", E.Policy(construction_boost_units=4000), p)
    assert (big["pti_gain"] > small["pti_gain"]).all()
    assert big["cost_eur"].median() == pytest.approx(2 * small["cost_eur"].median())


def test_imi_cut_costs_revenue_and_raises_prices_only_through_capitalisation(anc):
    cut = E.Policy(imi_rate_change_pp=-0.05)
    none = E.compare(
        A, anc, "baseline", cut, E.central(A, **{"imi_reform__capitalisation_share": 0})
    )
    full = E.compare(
        A, anc, "baseline", cut, E.central(A, **{"imi_reform__capitalisation_share": 1})
    )
    assert none["price_effect_pct"].iloc[0] == pytest.approx(0, abs=1e-12)
    # 0.05 pp = five 0.01 pp cuts of 0.19% each, at the mid values
    assert full["price_effect_pct"].iloc[0] == pytest.approx(100 * 0.009375, rel=0.01)
    years_active = A.end_year - A.policy_start_year + 1
    expected = 0.05 / anc.imi_average_rate_pct * A.fiscal["imi_revenue_eur"] * years_active
    assert none["cost_eur"].iloc[0] == pytest.approx(expected)
    assert (
        full["pti_gain"].iloc[0] < 0
    )  # the price rise outweighs: no income effect in this indicator


def test_a_dearer_mortgage_raises_the_burden_not_the_ratio(anc):
    calm = {**A.scenarios["baseline"], "mortgage_rate_pct": anc.mortgage_rate_pct}
    dear = {**calm, "mortgage_rate_pct": 6.0}
    p = E.central(A, mortgage_rate_semi_elasticity=0)
    a, b = E.run(A, anc, calm, p=p), E.run(A, anc, dear, p=p)
    # prices do not respond (elasticity 0) but the drift is recalibrated on the baseline, so compare the ratio
    assert (b.series["burden_pct"] > a.series["burden_pct"])[0, 1:].all()
    assert b.end("pti_years")[0] == pytest.approx(a.end("pti_years")[0])
    pay = aff.mortgage_payment_monthly
    assert b.end("burden_pct")[0] / a.end("burden_pct")[0] == pytest.approx(
        pay(1.0, 6.0) / pay(1.0, 3.0)
    )


def test_scenarios_order_affordability_in_the_expected_direction(anc):
    p = E.draw(A, 200)
    drift = E.calibrate(A, anc, p)
    end = {s: np.median(E.run(A, anc, s, None, p, drift).end("pti_years")) for s in A.scenarios}
    assert end["optimistic"] < end["baseline"] < end["pessimistic"]


def test_uncertainty_widens_with_the_horizon_and_is_pinned_near_term(anc):
    p = E.draw(A, 300)
    r = E.run(A, anc, "baseline", None, p)
    s = r.summary("pti_years")
    width = (s["p90"] - s["p10"]).to_numpy()
    assert width[0] == 0 and width[-1] > width[anc.near_term_steps] > width[1]


def test_budget_split_spends_the_budget(anc):
    pol = E.policy_for_budget(
        A, anc, {"construction_boost_units": 0.5, "imi_rate_change_pp": 0.5}, 1e9
    )
    assert pol.construction_boost_units * A.ranges[
        "construction_boost.cost_per_unit_eur"
    ].mid == pytest.approx(5e8)
    assert fiscal.imi_revenue_loss(
        pol.imi_rate_change_pp, anc.imi_average_rate_pct, A.fiscal["imi_revenue_eur"]
    ) == pytest.approx(5e8)
    assert pol.imt_rate_change_pp == 0


def test_mix_search_enumerates_every_split_and_ranks_by_gain(anc):
    out = E.mix_search(A, anc, "baseline", 5e8, E.draw(A, 40), step=0.5)
    assert len(out) == 15  # compositions of 2 halves into 5 levers
    shares = out.filter(like="share_").drop(columns="share_improving")
    assert shares.sum(axis=1).round(9).eq(1).all()
    assert out["pti_gain_p50"].is_monotonic_decreasing


def test_sensitivity_covers_every_parameter_and_scenario_input(anc):
    out = E.sensitivity(A, anc)
    assert set(out["parameter"]) == set(A.ranges) | set(scenarios.SCENARIO_KEYS)
    assert out["swing_pti_end"].is_monotonic_decreasing
    flex = out.set_index("parameter").loc["price_flexibility_balance"]
    assert (
        flex["high_pti_gain"] > flex["low_pti_gain"]
    )  # a stiffer price response magnifies the lever


def test_gain_for_budget_buys_units_at_mid_cost_and_gains_scale_with_the_budget(anc):
    p = E.draw(A, 40)
    small = funding.gain_for_budget(A, anc, "baseline", p, 1e8, {"construction_boost_units": 1.0})
    large = funding.gain_for_budget(A, anc, "baseline", p, 4e8, {"construction_boost_units": 1.0})
    unit = A.ranges["construction_boost.cost_per_unit_eur"].mid
    assert small["construction_boost_units"] == pytest.approx(1e8 / unit)
    assert small["vacant_renovation_units"] == 0
    assert 0 < small["gain_p10"] <= small["gain_p50"] <= small["gain_p90"]
    assert large["gain_p50"] > 2 * small["gain_p50"]  # a larger budget buys more
    assert np.isnan(small["gain_share_of_rise_pct"])  # the synthetic baseline does not rise
