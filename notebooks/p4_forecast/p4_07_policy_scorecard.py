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
# # P4.07 — Policy scorecard: what each option does, costs and rests on
#
# **Questions:** RQ6.6 (which policy combination improves affordability while minimising unintended consequences?), RQ8.3 (which
# expenditure could be reduced or made more efficient?, partly). A synthesis of results already in the project, on one scale; it adds
# one calculation, what it would take to cancel the baseline rise of price-to-income by supply alone.
#
# Every option the project has put a number on is listed with its effect on the 2035 median price-to-income (years of income, 80%
# range, from the simulator `p4_02`), its cost to 2035, who pays and how firm the evidence is. The vacant-home surcharge has no
# simulator effect and is listed with what `p3_08` does know. The scorecard compares options inside one model with assumed parameters;
# it is not a recommendation. The indicator is the ownership ratio of a median municipality, so public housing, for example, is scored
# without credit for housing its tenants directly.

# %%
import pandas as pd

from pthousing.analysis import supply
from pthousing.data import build_panel, interim
from pthousing.simulation import engine as E
from pthousing.simulation import funding, scenarios
from pthousing.viz import charts, style

style.apply_style()
A = scenarios.load()
YEARS = A.end_year - A.policy_start_year + 1
effects = pd.read_csv("../../reports/tables/p4/policy_effects_baseline.csv").set_index("package")
gain_by_scenario = pd.read_csv("../../reports/tables/p4/policy_gain_by_scenario.csv").set_index(
    "package"
)
surcharge = pd.read_csv("../../reports/tables/p3/vacant_surcharge_revenue.csv")
bite = pd.read_csv("../../reports/tables/p3/vacant_surcharge_bite.csv").set_index("statistic")

# the baseline rise of the median price-to-income, as in p4_06 (same draws)
panel = build_panel.read("panel_municipality_year")
nat = build_panel.read("national_quarterly")
forecast = pd.read_csv("../../reports/tables/p4/national_forecast.csv")
anc = E.anchors(panel, nat, forecast, A)
p = E.draw(A, 1000, 2026)
baseline = E.run(A, anc, "baseline", None, p, E.calibrate(A, anc, p))
rise = float(pd.Series(baseline.end("pti_years") - anc.pti_years).median())
print(
    f"price-to-income {anc.pti_years:.1f} years at the start, rise to {A.end_year} {rise:.2f} years, {YEARS} policy years"
)

# %% [markdown]
# ## Step 1 — One table
# Gain is the fall in 2035 price-to-income (positive helps). The tax cuts have a negative gain because prices cannot fall in the
# model, so they can only raise them (at the `p3` capitalisation benchmark; with no capitalisation the effect is zero and the cost is
# the revenue lost). Who pays: IMI and IMT are municipal revenue (`p3_05`); the supply levers are assumed to be funded by the State.

# %%
who_pays = {
    "construction": "State (assumed)",
    "renovation": "State (assumed)",
    "public": "State (assumed)",
    "supply_mix": "State (assumed)",
    "imi_cut": "Councils (lost IMI)",
    "imt_cut": "Councils (lost IMT)",
}
evidence = {
    "construction": "Modelled; unit cost and price response assumed",
    "renovation": "Modelled; unit cost from press cases, reoccupation assumed",
    "public": "Modelled; unit cost assumed, tenants' gain not in the indicator",
    "supply_mix": "Modelled; as its parts",
    "imi_cut": "p3 event study inconclusive (pre-trend rejected); run at no and full capitalisation",
    "imt_cut": "Price response assumed from the IMI benchmark; no estimate",
}
card = effects[
    [
        "label",
        "pti_gain_p10",
        "pti_gain_p50",
        "pti_gain_p90",
        "cost_bn",
        "gain_per_bn_p50",
        "homes_added_n_p50",
    ]
].copy()
card["who_pays"] = pd.Series(who_pays)
card["evidence"] = pd.Series(evidence)
card["gain_optimistic_scenario"] = gain_by_scenario["optimistic"]
card["gain_pessimistic_scenario"] = gain_by_scenario["pessimistic"]
style.save_table(card.round(3).reset_index(), "p4", "policy_scorecard")
card[
    [
        "label",
        "pti_gain_p50",
        "pti_gain_p10",
        "pti_gain_p90",
        "cost_bn",
        "gain_per_bn_p50",
        "who_pays",
    ]
].round(2)

# %% [markdown]
# ## Step 2 — The surcharge, which the simulator does not score
# From `p3_08`: the revenue is municipal and an upper bound (owners are assumed not to respond), and the bite on the owner is small.

# %%
print(surcharge.round(1).to_string())
print(bite.round(1).to_string())

# %% [markdown]
# ## Step 3 — What would it take to cancel the baseline rise?
# Scaling each supply package linearly until its fall equals the baseline rise gives the yearly cost, its share of GDP, its multiple of
# today's housing spending and the extra completions a year it would need, against the highest completions of the last thirty years.
# This is arithmetic on the simulator's linear response, far outside the packages tested (10,000 a year), and ignores the capacity to build.

# %%
completions = supply.national_flows(panel)["completed_n"]
tax = interim.read("eurostat_property_tax").set_index("year")
spend = interim.read("eurostat_housing_spending")
pt = spend[(spend["geo"] == "PT") & (spend["year"] == 2024)].iloc[0]
housing_m = float(pt["housing_development_eur_m"] + pt["housing_benefits_eur_m"])
gdp_m = float(tax.loc[2024, "gdp_eur_m"])
supply_rows = effects.loc[["construction", "renovation", "public", "supply_mix"]]
offset = funding.offset_requirement(supply_rows, rise, YEARS, gdp_m, housing_m)
offset["units_a_year_gross"] = pd.Series(
    {pkg: sum(A.packages[pkg].values()) * offset.loc[pkg, "scale"] for pkg in offset.index}
)
offset["units_vs_peak_completions"] = offset["units_a_year_gross"] / completions.max()
style.save_table(offset.round(2).reset_index(), "p4", "policy_offset_requirement")
labels = {
    "construction": "Extra completions",
    "renovation": "Renovated vacant homes",
    "public": "Public housing",
    "supply_mix": "Mix of the three",
}
fig = charts.offset_cost(offset, labels, housing_m / 1000, rise)
style.save_fig(fig, "p4", "policy_offset_cost")
offset.round(2)

# %% [markdown]
# ## Key numbers

# %%
print(
    f"baseline rise {rise:.2f} years, GDP 2024 {gdp_m:,.0f} EUR m, housing spending 2024 {housing_m:,.0f} EUR m; "
    f"completions peak {completions.max():,.0f} ({completions.idxmax()}), 2025 {completions.loc[2025]:,.0f}"
)
for pkg, r in offset.iterrows():
    print(
        f"  {pkg}: x{r.scale:.1f} the tested package, {r.yearly_cost_bn:.1f} bn a year ({r.yearly_cost_gdp_pct:.1f}% of GDP, "
        f"{r.yearly_cost_vs_housing_spending:.1f}x spending), {r.units_a_year_gross:,.0f} units a year ({r.units_vs_peak_completions:.1f}x the peak of completions)"
    )
for pkg, r in card.iterrows():
    print(
        f"  {pkg}: gain {r.pti_gain_p50:+.2f} ({r.pti_gain_p10:+.2f} to {r.pti_gain_p90:+.2f}) years for {r.cost_bn:.1f} bn, {r.who_pays}"
    )
