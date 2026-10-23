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
# # P1.05 — Foreign residents: how many, who, where
#
# **Question:** RQ3.2 (how has the foreign-resident population evolved and where is it located?). Context for RQ3.3
# (immigration and prices, `p2_02`).
#
# The series (`aima_foreigners`, INE) counts **foreign nationals holding a residence title on 31 December**, 2014 to 2023,
# by municipality and nationality. It is not the foreign-born population (people who took Portuguese nationality are
# not counted) and part of the 2023 jump may be administrative (`docs/data_quality.md`). Shares divide by INE's resident
# population estimate, so they are indicative. Nothing later than 2023 exists at municipal level.

# %%
import pandas as pd

from pthousing.analysis import demography as dem
from pthousing.data import interim
from pthousing.viz import charts, dashboard, maps, style

style.apply_style()
panel = dashboard.load_panel()
aima = interim.read("aima_foreigners")
geometry = maps.municipality_geometry()
d23 = panel[panel["year"] == 2023].set_index("muni_code")
names = panel.drop_duplicates("muni_code").set_index("muni_code")[["muni_name", "district"]]
totals = dem.national_totals(panel)
by_nat = dem.nationality_totals(aima)
print(
    f"{len(aima):,} rows; years {aima['year'].min()}-{aima['year'].max()}; total 2023 {totals['foreign_residents_n'].iloc[-1]:,.0f}"
)

# %% [markdown]
# ## Step 1 — The rise
# The count rose 2.7 times in nine years, with two steps: 2017-2019 and 2022-2023. The foreign share of residents
# rose faster in urban municipalities, where most of them live.

# %%
classes = (
    panel.dropna(subset=["foreign_residents_n"])
    .groupby(["year", "density_class"])[["foreign_residents_n", "population_n"]]
    .sum()
)
share_by_class = (100 * classes["foreign_residents_n"] / classes["population_n"]).unstack()
fig = charts.foreign_residents_trend(totals, by_nat["br"], share_by_class)
style.save_fig(fig, "p1", "foreign_residents_trend")
fig

# %%
growth = pd.DataFrame(
    {
        f"{a}-{b}": dem.growth_contribution(panel, a, b)
        for a, b in ((2014, 2019), (2019, 2022), (2022, 2023), (2014, 2023))
    }
).T.round(1)
nat_growth = pd.DataFrame(
    {
        "foreign_2014": by_nat.loc[2014],
        "foreign_2019": by_nat.loc[2019],
        "foreign_2023": by_nat.loc[2023],
    }
)
nat_growth["multiple_2014_2023"] = nat_growth["foreign_2023"] / nat_growth["foreign_2014"]
nat_growth["share_of_2023_total_pct"] = (
    100 * nat_growth["foreign_2023"] / nat_growth.loc["total", "foreign_2023"]
)
nat_growth.index = [dem.NATIONALITY_NAMES.get(i, "All foreign residents") for i in nat_growth.index]
nat_growth = nat_growth.round(2).sort_values("foreign_2023", ascending=False)
style.save_table(totals.round(2).reset_index(), "p1", "foreign_residents_totals")
style.save_table(
    nat_growth.reset_index(names="nationality"), "p1", "foreign_residents_by_nationality"
)
print(growth.to_string())
nat_growth

# %% [markdown]
# ## Step 2 — Where
# The share of residents in 2023 and how much it rose since 2019, in percentage points of the resident population.
# Hatched: no count.

# %%
share23 = d23["foreign_residents_pct"]
n20 = int((share23 > 20).sum())
lead = names.join(share23).sort_values("foreign_residents_pct").tail(3)["muni_name"].tolist()[::-1]
fig = maps.choropleth(
    share23, geometry, [2, 4, 8, 15, 25], style.SEQUENTIAL_6,
    f"Foreign residents are more than 15% of residents in {int((share23 > 15).sum())} municipalities, led by {', '.join(lead)}",
    "Foreign nationals with a residence title as a share of the resident population, 31 December 2023",
    "Source: INE (AIMA/SEF titles, resident population estimate), CAOP 2024; own calculations. Titles, not the foreign-born; shares are indicative.",
    "Share of residents", fmt="{:g}", suffix="%",
)  # fmt: skip
style.save_fig(fig, "p1", "foreign_residents_share_map_2023")
fig

# %%
wide = panel[panel["year"].isin([2019, 2023])].pivot(
    index="muni_code", columns="year", values="foreign_residents_pct"
)
rise = (wide[2023] - wide[2019]).dropna()
fig = maps.choropleth(
    rise, geometry, [0, 1, 2, 4, 8], style.SEQUENTIAL_6,
    f"The foreign share rose in {int((rise > 0).sum())} of {len(rise)} municipalities since 2019, by more than 4 points in {int((rise > 4).sum())}",
    "Change in the foreign share of residents, 2019 to 2023 (percentage points)",
    "Source: INE (AIMA/SEF titles, resident population estimate), CAOP 2024; own calculations. The 2023 count jumped 34% in one year (see data quality).",
    "Percentage points", fmt="{:g}", suffix="",
)  # fmt: skip
style.save_fig(fig, "p1", "foreign_residents_change_map_2019_2023")
fig

# %% [markdown]
# ### Concentration and type of place, 2023
# Share of all foreign residents against the share of the population, by municipality group.

# %%
conc = dem.concentration(panel, 2023).round(1)
dist = pd.concat(
    {
        "density": dem.group_distribution(panel, 2023, "density_class"),
        "coast": dem.group_distribution(panel, 2023, "coast_class"),
        "district": dem.group_distribution(panel, 2023, "district").head(6),
    },
    names=["dimension", "group"],
).round(1)
style.save_table(conc, "p1", "foreign_residents_concentration_2023")
style.save_table(dist.reset_index(), "p1", "foreign_residents_by_place_2023")
print(conc.to_string())
dist

# %%
top = (
    names.join(d23[["foreign_residents_n", "population_n", "foreign_residents_pct"]])
    .sort_values("foreign_residents_n", ascending=False)
    .reset_index()
)
style.save_table(top.round(2), "p1", "foreign_residents_by_municipality_2023")
top.head(10)

# %% [markdown]
# ## Step 3 — Who lives where
# Nationalities settle in different places: the share of each living in the three districts with most foreign residents.

# %%
districts = dem.group_distribution(panel, 2023, "district").index[:3].tolist()
location = dem.nationality_location(aima, panel, 2023, "district", districts)
labels = {d: d for d in districts} | {"other": "Rest of the country"}
lnames = dem.NATIONALITY_NAMES | {"total": "All foreign residents"}
fig = charts.nationality_location_bars(location, labels, lnames)
style.save_fig(fig, "p1", "foreign_residents_location_by_nationality")
style.save_table(location.round(1).reset_index(), "p1", "foreign_residents_location_by_nationality")
print(districts)
fig

# %% [markdown]
# ## Key numbers

# %%
t = totals
print(
    f"{t['foreign_residents_n'].iloc[0]:,.0f} (2014) -> {t.loc[2019, 'foreign_residents_n']:,.0f} (2019) -> {t.loc[2022, 'foreign_residents_n']:,.0f} (2022) -> {t.loc[2023, 'foreign_residents_n']:,.0f} (2023); "
    f"share {t['foreign_share_pct'].iloc[0]:.1f}% -> {t['foreign_share_pct'].iloc[-1]:.1f}%"
)
g = growth
print(
    f"2019-2023: population {g.loc['2019-2022', 'population_change_n'] + g.loc['2022-2023', 'population_change_n']:,.0f}, foreign residents {g.loc['2019-2022', 'foreign_change_n'] + g.loc['2022-2023', 'foreign_change_n']:,.0f}; "
    f"2014-2019 population {g.loc['2014-2019', 'population_change_n']:,.0f} with foreign residents {g.loc['2014-2019', 'foreign_change_n']:,.0f}"
)
print(conc.to_string())
print(
    f"municipalities above 15%: {int((share23 > 15).sum())}, above 20%: {n20}; max {share23.max():.0f}% ({top.sort_values('foreign_residents_pct').iloc[-1]['muni_name']})"
)
