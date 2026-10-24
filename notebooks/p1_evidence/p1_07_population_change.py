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
# # P1.07 — Population change: natural change and net migration
#
# **Question:** RQ3.1 (how has the population evolved, split into natural change and net migration?). Context for
# RQ3.3 and RQ3.6 (demand and prices, `p2_02`, `p2_07`).
#
# Two sources. **National, 1960-2025:** Eurostat's demographic balance (`eurostat_demography`; INE data). **Municipal,
# 2011-2023:** INE's annual estimates (`ine_population_change`), the only municipal split that exists. Net migration is a
# residual of the estimate (it holds statistical adjustments). INE's post-census revision of 2020-2021 (+201,000 persons)
# is in the municipal net migration of those years and left out of Eurostat's flows, so it is kept apart here and the
# municipal comparison uses 2012-2019 and 2022-2023 (2011 starts from the census).

# %%
import pandas as pd

from pthousing.analysis import demography as dem
from pthousing.data import interim
from pthousing.viz import charts, dashboard, style

style.apply_style()
panel = dashboard.load_panel()
euro = interim.read("eurostat_demography")
change = interim.read("ine_population_change")
balance = dem.national_balance(euro)
print(
    f"national {euro['year'].min()}-{euro['year'].max()}; municipal {change['year'].min()}-{change['year'].max()}, {change['muni_code'].nunique()} municipalities"
)

# %% [markdown]
# ## Step 1 — Thirty years nationally
# Until 2008 births still exceeded deaths, narrowly. Since 2009 they have not, and the gap widened to about 35,000
# a year. Net migration swings far more than natural change: it turned negative with the 2011-2014 crisis, recovered by
# 2017 and then reached 371,000 in 2022.

# %%
periods = [
    (1961, 1973), (1974, 1985), (1986, 1994), (1995, 2000), (2001, 2010),
    (2011, 2014), (2015, 2019), (2020, 2021), (2022, 2025), (1995, 2025),
]  # fmt: skip
summary = dem.period_balance(euro, periods)
style.save_table(summary.round(1).reset_index(names="period"), "p1", "population_change_by_period")
summary[
    [
        "natural_per_year_n",
        "migration_per_year_n",
        "revision_n",
        "total_change_n",
        "migration_share_of_change_pct",
    ]
].round(0)

# %% [markdown]
# ## Step 2 — Who grows: urban, intermediate and rural municipalities
# Rates per 1,000 residents a year in the first year of each window. 2012-2019 is the stagnation, 2022-2023 the surge.

# %%
windows = {"2012-19": (2012, 2019), "2022-23": (2022, 2023)}
by_density = {
    label: dem.municipal_balance(change, panel, a, b, by="density_class")
    for label, (a, b) in windows.items()
}
fig = charts.population_components(balance, by_density)
style.save_fig(fig, "p1", "population_components")
tbl = pd.concat(by_density, names=["window", "density_class"]).round(2)
style.save_table(tbl.reset_index(), "p1", "population_components_by_density")
tbl[["natural_per_1000_year", "migration_per_1000_year", "population_change_n"]]

# %%
by_coast = pd.concat(
    {
        label: dem.municipal_balance(change, panel, a, b, by="coast_class")
        for label, (a, b) in windows.items()
    },
    names=["window", "coast_class"],
).round(2)
style.save_table(by_coast.reset_index(), "p1", "population_components_by_coast")
by_coast[["natural_per_1000_year", "migration_per_1000_year", "population_change_n"]]

# %% [markdown]
# ## Step 3 — How municipalities grow
# Regimes: a municipality can grow on both counts, grow only because migrants offset natural decline, or shrink
# (migrants too few, or leaving). Population is that of the first year of the window.

# %%
regimes = pd.concat(
    {
        label: dem.growth_regimes(dem.municipal_balance(change, panel, a, b))
        for label, (a, b) in windows.items()
    },
    names=["window", "regime"],
).round(1)
style.save_table(regimes.reset_index(), "p1", "population_growth_regimes")
regimes

# %% [markdown]
# ## Key numbers

# %%
s = summary
r = regimes
print(
    f"1995-2025: natural change {s.loc['1995-2025', 'natural_change_n']:,.0f}, net migration {s.loc['1995-2025', 'net_migration_n']:,.0f}, "
    f"revision {s.loc['1995-2025', 'revision_n']:,.0f}, total {s.loc['1995-2025', 'total_change_n']:,.0f}"
)
print(
    f"deaths above births every year since {int(balance.index[balance['natural_change_n'] >= 0].max()) + 1}; "
    f"2025 natural {balance.loc[2025, 'natural_change_n']:,.0f}, net migration {balance.loc[2025, 'net_migration_n']:,.0f}; "
    f"peak migration {balance['net_migration_n'].max():,.0f} ({int(balance['net_migration_n'].idxmax())})"
)
for label in windows:
    print(label, r.loc[label][["municipalities_n", "share_of_municipalities_pct"]].to_dict("index"))
