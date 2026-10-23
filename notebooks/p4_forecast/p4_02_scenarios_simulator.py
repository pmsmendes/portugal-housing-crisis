# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # P4.02 — Scenarios, policy levers and the cost of acting
#
# **Questions:** RQ10.1 (5 to 10 year paths), RQ10.3 (demand scenarios), RQ10.4 (supply levers), RQ10.5 (best mix under a
# budget), RQ10.6 (sensitivity), RQ8.5 (fiscal cost of IMI/IMT changes), M6 (uncertainty carried into projections).
#
# **The model** (`src/pthousing/simulation`, assumptions in `config/scenarios.yaml`, reasons in `docs/decisions.md`): annual,
# national, 2025 to 2035. Population (natural change + net migration) gives households; completions and policy levers add
# dwellings that can house them; the households formed beyond those dwellings are the year's *balance pressure*. Real prices
# respond to the pressure, to income growth and to the mortgage rate, plus a fading *other demand* drift (tourism, foreign
# buyers, credit, expectations). **The drift starts where it must for the baseline to reproduce the ETS forecast of p4_01 in
# 2028** (its 80% interval is the spread of that anchor), so the first three years are the validated forecast and the later
# years are scenarios. Price-to-income and the mortgage burden of the median municipality move with the national price,
# income and rate paths.
#
# **Direct effects and behavioural responses stay apart:** units, households housed and euros are accounting
# (`simulation/supply.py`, `fiscal.py`); every price response is a behavioural parameter with a low, mid and high value and a
# status (literature, project, assumption). Uncertainty runs draw all of them from triangular distributions with common
# random numbers across scenarios and policies, so differences between runs are the policy and nothing else.

# %%
import numpy as np
import pandas as pd

from pthousing.data import build_panel
from pthousing.simulation import engine as E
from pthousing.simulation import scenarios
from pthousing.viz import charts, style

style.apply_style()
A = scenarios.load()
panel = build_panel.read("panel_municipality_year")
nat = build_panel.read("national_quarterly")
forecast = pd.read_csv("../../reports/tables/p4/national_forecast.csv")
anc = E.anchors(panel, nat, forecast, A)
pd.Series(anc.__dict__).to_frame("start").T.round(3).T

# %% [markdown]
# ## Step 1 — Starting point
# Everything above is read from the project's data: households from the 2021 census rolled forward with population
# (the p2_05 convention), price-to-income and mortgage burden of the 2024 median municipality scaled to 2025 by the real
# price index, an assumed 2.3% income growth and the 2025 mortgage rate. The anchors for the forecast pin are the ETS
# mean and 80% interval for 2028Q2.

# %%
parameters = pd.DataFrame(
    [
        {
            "parameter": name,
            "low": r.low,
            "mid": r.mid,
            "high": r.high,
            "status": A.notes[name.split(".")[0]]["status"],
        }
        for name, r in A.ranges.items()
    ]
)
style.save_table(parameters, "p4", "simulator_parameters")
scenario_inputs = pd.DataFrame(A.scenarios).T
style.save_table(scenario_inputs.reset_index(names="scenario"), "p4", "simulator_scenarios")
scenario_inputs

# %% [markdown]
# ## Step 2 — Three scenarios with parameter uncertainty
# 1,000 joint draws of every behavioural parameter and of the position inside the forecast's 80% interval. The band is
# parameter uncertainty only: scenario inputs are fixed within a scenario, so the three scenarios are conditional paths,
# not a probability distribution over the future.

# %%
N, SEED = 1000, 2026
p = E.draw(A, N, SEED)
drift = E.calibrate(A, anc, p)
runs = {s: E.run(A, anc, s, None, p, drift) for s in A.scenarios}
bands = {
    m: {s: r.summary(m) for s, r in runs.items()}
    for m in ("price_index", "pti_years", "burden_pct")
}
long = pd.concat(
    [b.assign(scenario=s, metric=m) for m, d in bands.items() for s, b in d.items()],
    ignore_index=True,
)
style.save_table(long.round(3), "p4", "scenario_paths")

forecast_real = forecast[forecast["series"] == "Real house price index"].copy()
hpi_start = (
    nat.assign(year=pd.to_datetime(nat["period_start"]).dt.year)
    .groupby("year")["hpi_total_real_b2025"]
    .mean()[A.start_year]
)
ref_years = forecast_real["period"].str[:4].astype(float) + 0.5
reference = {
    "years": ref_years.to_numpy(),
    "mean": (100 * forecast_real["mean"] / hpi_start).to_numpy(),
    "lo80": (100 * forecast_real["lo80"] / hpi_start).to_numpy(),
    "hi80": (100 * forecast_real["hi80"] / hpi_start).to_numpy(),
}
fig = charts.scenario_fans(
    [
        {
            "title": f"Real house price index ({A.start_year} = 100)",
            "unit_fmt": "{:.0f}",
            "bands": bands["price_index"],
        },
        {
            "title": "Price-to-income, median municipality (years of income)",
            "unit_fmt": "{:.1f}",
            "bands": bands["pti_years"],
        },
        {
            "title": "Mortgage burden, median municipality (% of income)",
            "unit_fmt": "{:.0f}%",
            "bands": bands["burden_pct"],
        },
    ],
    reference=reference,
    headline=(
        f"Price-to-income goes from {anc.pti_years:.1f} to {bands['pti_years']['baseline']['p50'].iloc[-1]:.1f} years by {A.end_year} in the baseline "
        f"(optimistic {bands['pti_years']['optimistic']['p50'].iloc[-1]:.1f}, pessimistic {bands['pti_years']['pessimistic']['p50'].iloc[-1]:.1f})"
    ),
)
style.save_fig(fig, "p4", "scenario_fans")
fig

# %% [markdown]
# The black diamonds are the ETS forecast (quarterly, 2026Q3 to 2028Q2, rebased to the 2025 mean). The baseline median goes
# through the last one by construction; the bands narrow there only to the forecast's own width.

# %%
end = pd.DataFrame(
    {
        s: {
            "real price, % vs start": np.median(r.end("price_index")) - 100,
            "PTI (median)": np.median(r.end("pti_years")),
            "PTI 10th pct": np.quantile(r.end("pti_years"), 0.1),
            "PTI 90th pct": np.quantile(r.end("pti_years"), 0.9),
            "burden % (median)": np.median(r.end("burden_pct")),
            "cumulative shortfall, households": np.median(r.end("cumulative_shortfall_n")),
        }
        for s, r in runs.items()
    }
).T.round(2)
style.save_table(end.reset_index(names="scenario"), "p4", "scenario_end_year")
end

# %% [markdown]
# ## Step 3 — What do the policy levers do? (baseline scenario)
# Illustrative sizes from 2027: 10,000 extra completions a year, 10,000 renovated vacant homes, 5,000 public homes, an IMI cut
# of 0.05 pp (about 15% of the average bill), an IMT cut of 1 pp. Gain = fall in price-to-income in 2035 against no policy
# (positive is better), with the cumulative budget cost. Tax cuts are scored on their price effect only, which is the
# behavioural half of their effect; the saving to owners and the revenue they cost are shown separately.

# %%
labels = {
    "construction": "10,000 extra homes a year",
    "renovation": "10,000 vacant homes renovated a year",
    "public": "5,000 public homes a year",
    "supply_mix": "Supply mix (5,000 + 5,000 + 2,500)",
    "imi_cut": "IMI cut of 0.05 pp",
    "imt_cut": "IMT cut of 1 pp",
}
rows = []
for name, label in labels.items():
    c = E.compare(A, anc, "baseline", E.Policy.package(A, name), p)
    s = E.summarise(c)
    rows.append(
        {"package": name, "label": label, **s.to_dict(), "cost_bn": s["cost_eur_p50"] / 1e9}
    )
effects = pd.DataFrame(rows)
style.save_table(effects.round(4), "p4", "policy_effects_baseline")
fig = charts.policy_effects(effects, A.end_year)
style.save_fig(fig, "p4", "policy_effects")
effects[
    [
        "label",
        "pti_gain_p10",
        "pti_gain_p50",
        "pti_gain_p90",
        "price_effect_pct_p50",
        "cost_bn",
        "gain_per_bn_p50",
        "share_improving",
    ]
].round(3)

# %% [markdown]
# ### The IMI lever at both ends
# Phase 3 could not pin down capitalisation (every interval contains zero and full capitalisation), so the lever is run at
# no capitalisation and at full capitalisation instead of with an estimate. At no capitalisation the cut changes nothing in
# prices and only costs revenue (an owner's saving, not in this indicator); at full capitalisation it lifts prices
# by the p3 benchmark.

# %%
imi = []
for share in (0.0, 1.0):
    pm = E.central(A, **{"imi_reform__capitalisation_share": share})
    c = E.compare(A, anc, "baseline", E.Policy.package(A, "imi_cut"), pm)
    imi.append(
        {
            "capitalisation": share,
            "price_effect_pct": c["price_effect_pct"].iloc[0],
            "pti_gain": c["pti_gain"].iloc[0],
            "budget_cost_bn": c["cost_eur"].iloc[0] / 1e9,
        }
    )
imi = pd.DataFrame(imi)
style.save_table(imi.round(4), "p4", "imi_bounds")
imi

# %% [markdown]
# ## Step 4 — Same package, different futures
# Does the ranking of the levers depend on the scenario? Gain in 2035 for each package under the three scenarios.

# %%
table = E.scenario_table(A, anc, p)
style.save_table(table.round(3), "p4", "scenario_by_package")
gain = []
for s in A.scenarios:
    for name in labels:
        c = E.compare(A, anc, s, E.Policy.package(A, name), p)
        gain.append({"scenario": s, "package": name, "gain_p50": c["pti_gain"].median()})
gain = pd.DataFrame(gain).pivot(index="package", columns="scenario", values="gain_p50")[
    list(A.scenarios)
]
style.save_table(gain.round(3).reset_index(), "p4", "policy_gain_by_scenario")
gain.round(3)

# %% [markdown]
# ## Step 5 — Sensitivity (RQ10.6)
# Each input moves alone from its low to its high value, with all others at their central value. Behavioural parameters are
# recalibrated to the forecast each time. Scenario inputs span the range between the three scenarios.

# %%
sens = E.sensitivity(A, anc, "baseline", E.Policy.package(A, "supply_mix"))
style.save_table(sens.round(3), "p4", "sensitivity")
base_pti = E.run(A, anc, "baseline").end("pti_years")[0]
fig = charts.sensitivity_tornado(sens, base_pti, A.end_year)
style.save_fig(fig, "p4", "sensitivity_tornado")
sens[["parameter", "kind", "low_pti_end", "high_pti_end", "swing_pti_end", "swing_pti_gain"]].round(
    2
)

# %% [markdown]
# ## Step 6 — Best mix under a budget (RQ10.5)
# Every split of an annual budget over the five levers in steps of 25%, for budgets of 0.5, 1 and 2 billion EUR a year
# from 2027 (units at mid cost; tax cuts sized so that their revenue loss equals their share). Ranked by the median fall in
# price-to-income in 2035.

# %%
mixes = []
for budget in (0.5e9, 1e9, 2e9):
    m = E.mix_search(A, anc, "baseline", budget, p)
    mixes.append(m.assign(budget_bn_a_year=budget / 1e9))
mixes = pd.concat(mixes, ignore_index=True)
style.save_table(mixes.round(4), "p4", "budget_mixes")
top = mixes.groupby("budget_bn_a_year").head(5)
top.round(3)

# %% [markdown]
# ### How much does the ranking depend on the unit costs?
# The mixes put the whole budget into one lever because the model is linear in every lever, so the ranking is the ranking of
# gain per euro, and the unit costs are the weakest numbers (assumptions, not estimates). Gain per billion euros with each
# lever's unit cost at its low, mid and high value (others at mid).

# %%
cost_check = []
for pkg, key in (
    ("construction", "construction_boost.cost_per_unit_eur"),
    ("renovation", "vacant_renovation.cost_per_unit_eur"),
    ("public", "public_housing.cost_per_unit_eur"),
):
    for which in ("low", "mid", "high"):
        pm = E.central(A, **{key: A.ranges[key].at(which)})
        c = E.compare(A, anc, "baseline", E.Policy.package(A, pkg), pm)
        cost_check.append(
            {
                "package": pkg,
                "unit_cost": which,
                "unit_cost_eur": A.ranges[key].at(which),
                "gain_per_bn": c["gain_per_bn"].iloc[0],
            }
        )
cost_check = pd.DataFrame(cost_check)
style.save_table(cost_check.round(4), "p4", "unit_cost_check")
cost_check.pivot(index="package", columns="unit_cost", values="gain_per_bn")[
    ["low", "mid", "high"]
].round(3)

# %% [markdown]
# ## What this says
# See `reports/p4_forecast.md` for the reading, the limits and what to carry into the dashboard page. Parameters, scenario
# paths and every table are in `reports/tables/p4/`.
