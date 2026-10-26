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
# # P2.19 — Renovation of existing buildings
#
# **Question:** RQ2.8 (what role could renovation of existing buildings play in easing the shortage?). Companion of `p2_16`
# (vacant homes against the shortfall) and `p2_05`/`p2_17` (supply).
#
# INE counts buildings licensed (2002-2025) and completed (2011-2025) by type of project, municipality by municipality: new
# constructions, and "enlargements, changes and reconstructions", which is every work on an existing building, extensions included.
# The unit is the **building**, not the dwelling, and works that need no licence are not counted. So the series show the pace and
# the place of rehabilitation work, not the homes it returned to use: how many dwellings a renovated building holds, how many of
# them were empty and whether they were let afterwards is not in the data. "Could play" is therefore a question of scale: how
# long would today's pace take to touch the excess vacant stock of `p2_16`, under stated numbers of homes per building?

# %%
import pandas as pd

from pthousing.analysis import renovation, supply, vacancy
from pthousing.config import PROCESSED
from pthousing.data import interim, typology
from pthousing.viz import charts, style

style.apply_style()
works = interim.read("ine_building_works")
nat = renovation.national(works)
stock = supply.read_stock()
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
tab = vacancy.table(stock)
short = vacancy.shortfall(supply.balance(panel, stock))
tab["excess_2021_n"] = vacancy.excess(tab["vacant_2021_n"], tab["dwellings_2021_n"])
tab["excess_2021_per_1000"] = 1000 * tab["excess_2021_n"] / tab["dwellings_2021_n"]
tab["shortfall_per_1000"] = 1000 * short / tab["dwellings_2021_n"]
ty = typology.read().set_index("muni_code")
print(
    f"{nat.index.min()}-{nat.index.max()}; {len(tab)} municipalities; excess vacant homes {tab['excess_2021_n'].sum():,.0f}"
)

# %% [markdown]
# ## Step 1 — The pace nationally
# Family-housing buildings licensed and completed, new against works on existing buildings.

# %%
windows = {
    "crisis 2002-2014": (2002, 2014),
    "recovery 2014-2025": (2014, 2025),
}
cols = ["licensed_new_n", "licensed_alteration_n", "licensed_total_n"]
ch = renovation.changes(nat, windows, cols).round(0)
style.save_table(nat.round(1).reset_index(), "p2", "renovation_national")
style.save_table(ch.reset_index(names="window"), "p2", "renovation_changes")
nat.loc[[2002, 2008, 2011, 2014, 2017, 2020, 2023, 2025]].round(1)

# %% [markdown]
# ## Step 2 — Where the work is
# Completed works per 1,000 dwellings of the 2011 stock over the years between the censuses (2012-2021), by kind of place, and the
# share of works on existing buildings among all completed buildings (which does not depend on how many dwellings a building holds).

# %%
it = renovation.intensity(works, tab)
f = it.join(tab).join(ty[["coast_class", "density_class"]])
measures = [
    "completed_alteration_per_1000",
    "completed_new_per_1000",
    "alteration_share_completed_pct",
    "vacancy_2021_pct",
    "excess_2021_per_1000",
    "shortfall_per_1000",
]
by_density = renovation.group_summary(f, f["density_class"], measures).round(1)
by_coast = renovation.group_summary(f, f["coast_class"], measures).round(1)
style.save_table(by_density.reset_index(), "p2", "renovation_by_density")
style.save_table(by_coast.reset_index(), "p2", "renovation_by_coast")
fig = charts.renovation_works(nat, by_density.loc[["urban", "intermediate", "rural"]])
style.save_fig(fig, "p2", "renovation_works")
by_density

# %% [markdown]
# Is renovation where the vacancy is, or where the shortfall is? Spearman correlations across the 308 municipalities.

# %%
assoc = renovation.association(
    f,
    "completed_alteration_per_1000",
    [
        "vacancy_2021_pct",
        "vacancy_change_pp",
        "excess_2021_per_1000",
        "shortfall_per_1000",
        "completed_new_per_1000",
    ],
).round(2)
share_assoc = renovation.association(
    f,
    "alteration_share_completed_pct",
    ["vacancy_2021_pct", "excess_2021_per_1000", "shortfall_per_1000"],
).round(2)
style.save_table(assoc.reset_index(), "p2", "renovation_association")
style.save_table(share_assoc.reset_index(), "p2", "renovation_share_association")
print(assoc.to_string())
print(share_assoc.to_string())

# %% [markdown]
# ## Step 3 — How long at this pace?
# Excess vacant homes (above a 5% frictional level, `p2_16`) against the buildings of family housing with works on existing buildings
# completed a year (average 2015-2024), if each building returned a given number of vacant homes. An upper bound: some of the
# homes were occupied, some are not let or sold afterwards. Compared with the simulator's renovation lever (`config/scenarios.yaml`).

# %%
pace = nat.loc[2015:2024, "completed_alteration_n"].mean()
excess_n = tab["excess_2021_n"].sum()
years = renovation.years_to_clear(excess_n, pace, [1, 3, 10], [0.25, 0.5, 1.0]).round(0)
style.save_table(years.reset_index(), "p2", "renovation_years_to_clear")
print(
    f"pace {pace:,.0f} completed buildings a year (licensed {nat.loc[2015:2024, 'licensed_alteration_n'].mean():,.0f}); excess {excess_n:,.0f}"
)
years

# %% [markdown]
# ## Key numbers

# %%
print(
    f"licensed works on existing family-housing buildings: {nat.loc[2002, 'licensed_alteration_n']:,.0f} (2002), {nat.loc[2014, 'licensed_alteration_n']:,.0f} (2014), "
    f"{nat.loc[2025, 'licensed_alteration_n']:,.0f} (2025); new constructions {nat.loc[2002, 'licensed_new_n']:,.0f}, {nat.loc[2014, 'licensed_new_n']:,.0f}, {nat.loc[2025, 'licensed_new_n']:,.0f}"
)
print(
    f"share of works on existing buildings in licences: {nat.loc[2002, 'alteration_share_licensed_pct']:.0f}% (2002), peak {nat['alteration_share_licensed_pct'].max():.0f}% ({nat['alteration_share_licensed_pct'].idxmax()}), "
    f"{nat.loc[2025, 'alteration_share_licensed_pct']:.0f}% (2025); completed {nat.loc[2011, 'alteration_share_completed_pct']:.0f}% (2011), {nat.loc[2025, 'alteration_share_completed_pct']:.0f}% (2025)"
)
print(
    "share of completed works that are on existing buildings, by place (median): "
    + ", ".join(
        f"{k} {by_density.loc[k, 'alteration_share_completed_pct']:.0f}%"
        for k in ("urban", "intermediate", "rural")
    )
)
print(
    f"correlation of renovation per 1,000 dwellings with vacancy {assoc.loc['vacancy_2021_pct', 'spearman']:+.2f}, "
    f"with shortfall per 1,000 {assoc.loc['shortfall_per_1000', 'spearman']:+.2f} (p {assoc.loc['shortfall_per_1000', 'p_value']:.3f}); "
    f"share of works with shortfall {share_assoc.loc['shortfall_per_1000', 'spearman']:+.2f}"
)
print(
    f"years at {pace:,.0f} buildings a year to reach {excess_n:,.0f} excess vacant homes: with one home per building {years.loc[1, '25% usable']:.0f} years for a quarter usable, "
    f"{years.loc[1, '100% usable']:.0f} for all; three per building {years.loc[3, '25% usable']:.0f} and {years.loc[3, '100% usable']:.0f}; ten per building {years.loc[10, '25% usable']:.0f} and {years.loc[10, '100% usable']:.0f}"
)
