import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import causal
from pthousing.analysis import panel as pn

YEARS = range(2012, 2026)


def _rates(n_munis: int = 240, seed: int = 0) -> pd.DataFrame:
    """Rate paths: most municipalities never change; a share cut once (isolated), a share cut twice in a row."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_munis):
        rate = np.full(len(YEARS), 0.40)
        cut_year = None
        if i % 3 == 0:  # isolated single cut, years 2018-2022 so every window is inside the data
            cut_year = int(rng.integers(2018, 2023))
            size = float(rng.choice([0.02, 0.04, 0.06]))
            rate[cut_year - 2012 :] -= size
        elif i % 3 == 1 and i % 7 == 0:  # two cuts one year apart: neither is isolated
            y = int(rng.integers(2018, 2022))
            rate[y - 2012 :] -= 0.02
            rate[y + 1 - 2012 :] -= 0.02
        rows.append((f"{i:04d}", rate, cut_year))
    return rows


def _panel(effect: float = 0.0, pretrend: float = 0.0, noise: float = 0.01, seed: int = 1):
    """Panel in the shape of ``panel_municipality_year``. Real price = muni effect + region-year effect +
    ``effect`` x dose (0.01 pp units) from the event year on + ``pretrend`` x dose x years before the event."""
    rng = np.random.default_rng(seed)
    region_year = {(r, y): rng.normal(0, 0.05) for r in range(6) for y in YEARS}
    rows = []
    for i, (code, rate, cut_year) in enumerate(_rates(seed=seed)):
        muni_fx = rng.normal(0, 0.3)
        size = 0.40 - rate[-1] if cut_year else 0.0
        dose = size / causal.DOSE_UNIT_PP
        for j, y in enumerate(YEARS):
            event_time = y - cut_year if cut_year else -99
            log_price = 7 + muni_fx + region_year[(i % 6, y)] + rng.normal(0, noise)
            if cut_year:
                log_price += effect * dose * (event_time >= 0)
                log_price += pretrend * dose * min(event_time, 0)
            change = np.nan if j == 0 else round(rate[j] - rate[j - 1], 4)
            rows.append(
                {
                    "muni_code": code,
                    "year": y,
                    "nuts3_name_2024": f"R{i % 6}",
                    "district": "D",
                    "territory": "continente",
                    "price_sqm_eur_real": np.exp(log_price),
                    "pti_years": np.exp(log_price) / 10,
                    "rent_sqm_eur_real": np.nan,
                    "imi_urban_pct": rate[j],
                    "imi_change_pp": change,
                    "imi_parish_rates": False,
                    "imi_deduction_link": False,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def frame():
    return causal.build_frame(_panel(effect=0.01))


def test_isolated_events_need_a_quiet_window_and_observed_changes():
    rates = [0.40, 0.40, 0.40, 0.38, 0.38, 0.38, 0.36, 0.35, 0.35, 0.35]
    frame = pd.DataFrame(
        {
            "muni_code": "0101",
            "year": range(2014, 2024),
            "rate_pct": rates,
            "change_pp": [np.nan] + list(np.round(np.diff(rates), 4)),
        }
    )
    events = causal.rate_events(frame).set_index("event_year")
    # 2017 (-0.02): changes 2015-2018 observed and quiet; 2020 (-0.02) and 2021 (-0.01) are two years apart
    assert bool(events.loc[2017, "isolated"]) and events.loc[2017, "change_pp"] == pytest.approx(
        -0.02
    )
    assert not events.loc[2020, "isolated"] and not events.loc[2021, "isolated"]
    assert events.loc[2017, "rate_before_pct"] == pytest.approx(0.40)
    assert not events["observed"].get(2023, False)  # window leaves the data
    assert list(events.index) == [2017, 2020, 2021]


def test_stacks_have_clean_controls_and_the_event_window(frame):
    stacks = causal.build_stacks(frame)
    assert set(stacks["k"]) == {-2, -1, 0, 1, 2}
    treated = stacks[stacks["treated"]]
    assert (treated["dose"] > 0).all() and (stacks.loc[~stacks["treated"], "dose"] == 0).all()
    # a control never changes its rate between event - 2 and the end of the outcome window, event + 2
    change = frame.pivot(index="muni_code", columns="year", values="change_pp")
    for (stack, code), _ in stacks[~stacks["treated"]].groupby(["stack", "muni_code"]):
        assert (change.loc[code, stack - 2 : stack + 2].abs() < 1e-9).all()
    assert stacks.groupby("unit")["year"].nunique().eq(5).all()


def test_stack_filters_on_cut_size_and_event_years(frame):
    all_stacks = causal.build_stacks(frame)
    big = causal.build_stacks(frame, min_cut_pp=0.04)
    assert big.loc[big["treated"], "dose"].min() >= 4 - 1e-9
    assert (
        big.loc[big["treated"], "unit"].nunique()
        < all_stacks.loc[all_stacks["treated"], "unit"].nunique()
    )
    no_2020 = causal.build_stacks(frame, exclude_events={2020})
    assert 2020 not in set(no_2020["stack"])
    late = causal.build_stacks(frame, event_years=(2021, 2022))
    assert set(late["stack"]) <= {2021, 2022}
    floor = causal.build_stacks(frame, control_min_rate_pct=0.45)
    assert floor["treated"].all()  # nobody is above 0.45%, so no control is left


def test_units_without_an_outcome_in_the_window_drop_out(frame):
    holes = frame.copy()
    hit = holes[(holes["muni_code"] == "0000")]  # municipality 0 cuts; blank one year of its window
    holes.loc[hit.index[hit["year"] == 2018], "log_price_real"] = np.nan
    before = causal.build_stacks(frame)
    after = causal.build_stacks(holes)
    assert (after["muni_code"] == "0000").sum() < (before["muni_code"] == "0000").sum()


def test_event_study_recovers_a_known_effect_and_finds_flat_pretrends(frame):
    es = causal.event_study(causal.build_stacks(frame), dose=True)
    table = es.table.set_index("k")
    assert set(table.index) == {-2, 0, 1, 2}  # k = -1 is the reference
    for k in (0, 1, 2):
        assert table.loc[k, "coef"] == pytest.approx(0.01, abs=0.002)
        assert table.loc[k, "ci_low"] < 0.01 < table.loc[k, "ci_high"]
    assert abs(table.loc[-2, "coef"]) < 0.003 and es.pretrend_p > 0.1
    assert es.n_treated > 30 and es.n_controls > es.n_treated


def test_event_study_flags_a_pretrend():
    frame = causal.build_frame(_panel(effect=0.0, pretrend=0.004, seed=3))
    es = causal.event_study(causal.build_stacks(frame, pre=2, post=2))
    # treated prices rose 0.4% per 0.01 pp of cut for every year before the event: k = -2 sits 0.4% below k = -1
    assert es.table.set_index("k").loc[-2, "coef"] == pytest.approx(-0.004, abs=0.002)
    assert es.pretrend_p < 0.01


def test_binary_event_study_scales_with_the_average_dose(frame):
    stacks = causal.build_stacks(frame)
    binary = causal.event_study(stacks, dose=False).table.set_index("k")
    mean_dose = stacks.loc[stacks["treated"], "dose"].mean()
    assert binary.loc[1, "coef"] == pytest.approx(0.01 * mean_dose, rel=0.25)


def test_cumulative_sums_post_coefficients(frame):
    es = causal.event_study(causal.build_stacks(frame))
    total = causal.cumulative(es, [0, 1, 2])
    assert total["coef"] == pytest.approx(es.table.set_index("k").loc[[0, 1, 2], "coef"].sum())
    assert total["ci_low"] < 0.03 < total["ci_high"]


def test_cohort_did_agrees_with_the_pooled_event_study(frame):
    stacks = causal.build_stacks(frame)
    cohort = causal.cohort_did(stacks, dose=True, n_boot=60).set_index("k")
    assert cohort.loc[1, "coef"] == pytest.approx(0.01, abs=0.003)
    assert cohort.loc[1, "ci_low"] < 0.01 < cohort.loc[1, "ci_high"]
    assert abs(cohort.loc[-2, "coef"]) < 0.004


def test_dose_response_recovers_the_first_difference_of_a_level_effect():
    # a one-off jump of 0.01 x dose in the event year: price growth rises 0.01 per 0.01 pp cut in year t
    frame = causal.build_frame(_panel(effect=0.01, seed=5))
    res = causal.dose_response(frame, lags=(0, 1), years=(2013, 2025))
    table = pn.coef_table(res).set_index("term")
    assert table.loc["cut_l0", "coef"] == pytest.approx(0.01, abs=0.003)
    assert abs(table.loc["cut_l1", "coef"]) < 0.004


def test_dose_response_placebo_lead_is_zero_without_a_pretrend(frame):
    res = causal.dose_response(frame, lags=(0,), leads=(2,), years=(2013, 2023))
    table = pn.coef_table(res).set_index("term")
    assert abs(table.loc["cut_f2", "coef"]) < 0.003


def test_full_capitalisation_benchmark():
    # 0.01 pp cut, tax value = 75% of price, 4% discount rate: 0.0001 * 0.75 / 0.04 = 0.1875%
    assert causal.full_capitalisation_pct(0.01, 0.75, 0.04) == pytest.approx(0.1875)
    with pytest.raises(ValueError):
        causal.full_capitalisation_pct(0.01, 0.75, 0.0)
