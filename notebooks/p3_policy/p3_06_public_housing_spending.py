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
# # P3.06 — What the State spends on housing
#
# **Questions:** RQ8.1 (how much does government spend on housing programmes, rental support, subsidies and public housing?),
# with a peer comparison that bears on RQ6.5.
#
# General-government expenditure by function (COFOG, national accounts, annual): **housing development** (GF0601, public housing
# included) and **housing in social protection** (GF1006, housing allowances and rent subsidies). Their sum is "housing support"
# here. What is not in it: tax expenditures (IRS deductions, IMT and IMI exemptions), loan guarantees, and anything booked under
# another function. Housing and community amenities (GF06) also holds water supply and street lighting, so it is not used.
# Programme-level cost-effectiveness (RQ8.2) needs administrative data that are not in the project.

# %%

from pthousing.analysis import spending
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
sp = interim.read("eurostat_housing_spending")
pt = spending.portugal_frame(sp, interim.read("ine_cpi"), interim.read("eurostat_property_tax"))
shares = spending.support_shares(sp)
print(f"{pt.index.min()}-{pt.index.max()}; countries {sorted(sp['geo'].unique())}")

# %% [markdown]
# ## Step 1 — Portugal
# Real spending (constant euros of the base year) by kind, and as a share of GDP.

# %%
peers = {"DE": "Germany", "ES": "Spain", "FR": "France", "IE": "Ireland"}
fig = charts.housing_spending(pt, shares, peers)
style.save_fig(fig, "p3", "housing_spending")
years = [1995, 2000, 2005, 2010, 2015, 2019, 2022, 2023, 2024]
cols = [
    "housing_development_real_eur_m",
    "housing_benefits_real_eur_m",
    "support_real_eur_m",
    "support_gdp_pct",
    "spending_per_tax_pct",
]
levels = pt.loc[years, cols]
style.save_table(levels.round(2).reset_index(), "p3", "housing_spending_levels")
levels.round(2)

# %% [markdown]
# ## Step 2 — Against the peers
# Housing support as a share of GDP. Italy (2022-2023: 3.0% and 4.1%) and the EU27 aggregate are far above their trend in those
# years; this is likely the booking of building-renovation tax credits as expenditure, which is not verified here, so they stay in the
# table but out of the figure and the averages.

# %%
table = shares.loc[[1995, 2000, 2005, 2010, 2015, 2019, 2022, 2023, 2024]]
average = shares.loc[2015:2024].drop(columns=["IT", "EU27_2020"]).mean().rename("mean_2015_2024")
style.save_table(table.round(2).reset_index(), "p3", "housing_support_peers")
style.save_table(
    average.round(2).rename_axis("geo").reset_index(), "p3", "housing_support_peer_means"
)
print(average.round(2).to_string())
table.round(2)

# %% [markdown]
# ## Step 3 — Scale against property-tax revenue
# For scale only: IMI and IMT revenue (`p3_04`) goes to councils, housing support is mostly central. Housing support has been 27%
# to 36% of what the two property taxes raise in 2013-2022 and 44% to 48% in 2023-2024.

# %%
scale = pt.loc[2013:, ["support_eur_m", "property_tax_eur_m", "spending_per_tax_pct"]]
style.save_table(scale.round(1).reset_index(), "p3", "housing_spending_vs_property_tax")
scale.round(1)

# %% [markdown]
# ## Key numbers

# %%
p = pt
print(
    f"2024: housing development {p.loc[2024, 'housing_development_eur_m']:,.0f} EUR m, allowances {p.loc[2024, 'housing_benefits_eur_m']:,.0f}, "
    f"together {p.loc[2024, 'support_eur_m']:,.0f} = {p.loc[2024, 'support_gdp_pct']:.2f}% of GDP"
)
low = p.loc[2010:, "support_gdp_pct"].idxmin()
print(
    f"share of GDP: 1995 {p.loc[1995, 'support_gdp_pct']:.2f}%, peak {p['support_gdp_pct'].max():.2f}% ({p['support_gdp_pct'].idxmax()}), "
    f"low since 2010 {p.loc[low, 'support_gdp_pct']:.2f}% ({low}), 2024 {p.loc[2024, 'support_gdp_pct']:.2f}%"
)
print(
    f"real housing development {p.loc[2015, 'housing_development_real_eur_m']:,.0f} (2015) -> {p.loc[2024, 'housing_development_real_eur_m']:,.0f} (2024) EUR m: {100 * (p.loc[2024, 'housing_development_real_eur_m'] / p.loc[2015, 'housing_development_real_eur_m'] - 1):+.0f}%; "
    f"allowances {p.loc[2015, 'housing_benefits_real_eur_m']:,.0f} -> {p.loc[2024, 'housing_benefits_real_eur_m']:,.0f}: {100 * (p.loc[2024, 'housing_benefits_real_eur_m'] / p.loc[2015, 'housing_benefits_real_eur_m'] - 1):+.0f}%; "
    f"2022 -> 2023 allowances {100 * (p.loc[2023, 'housing_benefits_eur_m'] / p.loc[2022, 'housing_benefits_eur_m'] - 1):+.0f}% nominal"
)
print(
    "2024 peers (% of GDP): "
    + ", ".join(
        f"{peers.get(g, g)} {shares.loc[2024, g]:.2f}"
        for g in ["DE", "ES", "FR", "IE", "IT", "EU27_2020"]
    )
    + f"; Portugal {shares.loc[2024, 'PT']:.2f}"
)
print(
    f"2015-2024 mean: Portugal {average['PT']:.2f}% against "
    + ", ".join(f"{peers[g]} {average[g]:.2f}%" for g in peers)
)
print(
    f"housing support as a share of IMI plus IMT: 2015 {p.loc[2015, 'spending_per_tax_pct']:.0f}%, 2022 {p.loc[2022, 'spending_per_tax_pct']:.0f}%, 2024 {p.loc[2024, 'spending_per_tax_pct']:.0f}%"
)
