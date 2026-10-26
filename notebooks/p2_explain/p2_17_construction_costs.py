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
# # P2.17 — What it costs to build, and what that did to supply
#
# **Question:** RQ2.7 (how have construction costs, land availability, planning rules and licensing times affected supply?).
# Only the first part can be answered with the data held: INE's cost index of new housing (monthly, 2000 to 2026, split into
# materials and labour). Land availability, planning rules and licensing times are not in the project, so they stay open.
#
# The cost index measures input costs. It says nothing about the price of land, margins or financing, so the ratio of the house
# price index to the cost index is an index of "everything in the price except the cost of building", not a margin in euros.
# National and annual: about 25 years and two cycles, so the regressions below are a guide to sign and size, not a test.

# %%
import pandas as pd

from pthousing.analysis import construction, supply
from pthousing.config import PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, dashboard, style

style.apply_style()
long = pd.read_parquet(PROCESSED / "national_annual_long.parquet")
flows = supply.national_flows(dashboard.load_panel())
frame = construction.annual_frame(
    interim.read("ine_construction_costs"),
    interim.read("ine_cpi"),
    long,
    flows,
    interim.read("eurostat_macro"),
)
print(f"{frame.index.min()}-{frame.index.max()}, complete years only")

# %% [markdown]
# ## Step 1 — Costs against prices
# Nominal indices (2015 = 100) and the new family dwellings licensed and completed.

# %%
fig = charts.construction_costs(frame)
style.save_fig(fig, "p2", "construction_costs")
frame.round(1)

# %% [markdown]
# ## Step 2 — Four episodes
# The boundaries are the same as in the rest of the project: the 2007 peak of licensing, the 2013 trough of prices, the 2021 start
# of the cost surge. The price change is split exactly into the cost index's change and the change in the price-to-cost ratio.

# %%
windows = {
    "boom 2000-2007": (2000, 2007),
    "crisis 2007-2013": (2007, 2013),
    "recovery 2013-2021": (2013, 2021),
    "since 2021": (2021, 2025),
    "2013-2025": (2013, 2025),
}
cols = [
    "cost_total_b2015",
    "cost_materials_b2015",
    "cost_labour_b2015",
    "cost_real_b2015",
    "wage_b2015",
    "hpi_nominal_b2015",
    "hpi_real_b2015",
]
changed = construction.changes(frame, windows, cols).round(0)
shares = construction.cost_shares(frame, windows).round(1)
per_year = construction.mean_flows(frame, windows).round(0)
table = changed.join(shares).join(per_year, rsuffix="_per_year")
style.save_table(table.reset_index(names="window"), "p2", "construction_episodes")
table

# %% [markdown]
# ## Step 3 — Does building follow prices or costs?
# Yearly change in licensed (and completed) dwellings on last year's change in the real house price and in the real cost, both in
# log points, together. Then two checks: without the crisis years (2008-2011, when licensing fell 60% in four years) and
# without the cost surge (2021-2023).

# %%
rows = []
variants = {
    "all years": {},
    "without 2008-2011": {"drop_years": (2008, 2009, 2010, 2011)},
    "without 2021-2023": {"drop_years": (2021, 2022, 2023)},
}
for y, lag in (("licensed_n", 1), ("completed_n", 1), ("completed_n", 2)):
    for label, kwargs in variants.items():
        r = construction.supply_response(frame, y, lag, **kwargs).reset_index()
        rows.append(r.assign(outcome=y, lag_years=lag, sample=label))
response = pd.concat(rows, ignore_index=True)
style.save_table(response.round(3), "p2", "construction_supply_response")
response.round(2)

# %%
link = construction.ratio_and_licensing(frame)
print({k: round(float(v), 2) for k, v in link.items()})

# %% [markdown]
# ## Step 4 — Labour against wages
# Labour is the faster-rising part of the cost. Whether that is more than wages in general: the labour cost index over
# compensation per employee.

# %%
wage = frame[["cost_labour_b2015", "wage_b2015", "labour_cost_vs_wage_b2015"]].round(1)
style.save_table(wage.reset_index(), "p2", "construction_labour_vs_wages")
wage.loc[[2000, 2007, 2013, 2021, 2025]]

# %% [markdown]
# ## Key numbers

# %%
f, ch, sh = frame, changed, shares
w = "2013-2025"
print(
    f"since 2013: nominal house prices {ch.loc[w, 'hpi_nominal_b2015']:+.0f}%, building cost {ch.loc[w, 'cost_total_b2015']:+.0f}% "
    f"(materials {ch.loc[w, 'cost_materials_b2015']:+.0f}%, labour {ch.loc[w, 'cost_labour_b2015']:+.0f}%), "
    f"wages {ch.loc[w, 'wage_b2015']:+.0f}%; real cost {ch.loc[w, 'cost_real_b2015']:+.0f}%, real prices {ch.loc[w, 'hpi_real_b2015']:+.0f}%"
)
print(
    f"the cost index accounts for {sh.loc[w, 'cost_part_pct']:.0f}% of the log rise in price since 2013 "
    f"(recovery {sh.loc['recovery 2013-2021', 'cost_part_pct']:.0f}%, since 2021 {sh.loc['since 2021', 'cost_part_pct']:.0f}%); "
    f"price-to-cost ratio {100 * (f.loc[2025, 'price_to_cost_b2015'] / f.loc[2013, 'price_to_cost_b2015'] - 1):+.0f}% since 2013"
)
print(
    f"licensed dwellings per year: boom {per_year.loc['boom 2000-2007', 'licensed_n']:,.0f}, crisis {per_year.loc['crisis 2007-2013', 'licensed_n']:,.0f}, "
    f"recovery {per_year.loc['recovery 2013-2021', 'licensed_n']:,.0f}, since 2021 {per_year.loc['since 2021', 'licensed_n']:,.0f}"
)
for label in variants:
    r = response[(response["outcome"] == "licensed_n") & (response["sample"] == label)].set_index(
        "term"
    )
    print(
        f"licensed, {label}: price {r.loc['dlog_price', 'coef']:.2f} [{r.loc['dlog_price', 'ci_low']:.2f}, {r.loc['dlog_price', 'ci_high']:.2f}], "
        f"cost {r.loc['dlog_cost', 'coef']:.2f} [{r.loc['dlog_cost', 'ci_low']:.2f}, {r.loc['dlog_cost', 'ci_high']:.2f}], n {int(r['n'].iloc[0])}"
    )
print(
    f"labour cost over wages: 2013 {f.loc[2013, 'labour_cost_vs_wage_b2015']:.0f}, 2025 {f.loc[2025, 'labour_cost_vs_wage_b2015']:.0f} (2015 = 100)"
)
