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
# # P3.07 — Portugal against its peers: prices, property tax and housing spending
#
# **Question:** RQ6.5 (how do other European countries' housing policies compare, and which could transfer to Portugal?), partly.
#
# Three comparable national indicators for Portugal, Spain, Italy, France, Germany and Ireland: the change in the house price index
# 2015 to 2024 (nominal), the recurrent property tax (national accounts D29A, taxes on land, buildings and other structures) and
# housing support (`p3_06`: housing development plus housing allowances), the last two as a share of GDP averaged over 2015-2024.
# Transfer taxes are left out because countries book them under different codes (Germany's is 0.00% of GDP in D214C). What these
# data do **not** hold is the policies themselves (rent regulation, tenant protection, planning, public-housing stock), so this
# compares how much countries tax and spend, not which instruments they use. Six countries cannot support an inference: the table
# and chart are a comparison, not a test of what lowers prices.

# %%

from pthousing.analysis import peers
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
mix = peers.policy_mix(
    interim.read("eurostat_hpi"),
    interim.read("eurostat_property_tax_peers"),
    interim.read("eurostat_housing_spending"),
    start=2015,
    end=2024,
    exclude_spending=("IT", "EU27_2020"),
)
mix.round(2)

# %% [markdown]
# ## Step 1 — The three indicators
# Sorted by price change. Italy has no housing-support value: its 2022-2023 spending is far above trend (probably renovation tax
# credits booked as expenditure, see `p3_06`).

# %%
names = {
    "PT": "Portugal",
    "ES": "Spain",
    "IT": "Italy",
    "FR": "France",
    "DE": "Germany",
    "IE": "Ireland",
}
fig = charts.peers_policy_mix(mix, names)
style.save_fig(fig, "p3", "peer_policy_mix")
style.save_table(mix.round(2).reset_index(), "p3", "peer_policy_mix")
mix.loc[list(names)].sort_values("price_change_pct", ascending=False).round(2)

# %% [markdown]
# ## Step 2 — How far apart are they over the years?
# The recurrent property tax as a share of GDP for the six countries at five dates.

# %%
tax = interim.read("eurostat_property_tax_peers")
tax_share = (
    100
    * tax.set_index(["geo", "year"])["land_buildings_tax_eur_m"]
    / tax.set_index(["geo", "year"])["gdp_eur_m"]
).unstack("geo")
over_time = tax_share.loc[[2000, 2007, 2013, 2019, 2024], ["PT", "ES", "IT", "FR", "DE", "IE"]]
style.save_table(over_time.round(2).reset_index(), "p3", "recurrent_property_tax_gdp")
over_time.round(2)

# %% [markdown]
# ## Key numbers

# %%
m = mix.loc[list(names)]
pt = m.loc["PT"]
print(
    "price change 2015-2024: "
    + ", ".join(
        f"{names[g]} {v:+.0f}%"
        for g, v in m["price_change_pct"].sort_values(ascending=False).items()
    )
)
print(
    "recurrent property tax, mean % of GDP: "
    + ", ".join(
        f"{names[g]} {v:.2f}"
        for g, v in m["property_tax_gdp_pct"].sort_values(ascending=False).items()
    )
)
print(
    "housing support, mean % of GDP: "
    + ", ".join(
        f"{names[g]} {v:.2f}"
        for g, v in m["housing_support_gdp_pct"].dropna().sort_values(ascending=False).items()
    )
)
print(
    f"Portugal: prices {pt.price_change_pct:+.0f}% (peer median {m.drop('PT')['price_change_pct'].median():+.0f}%), property tax {pt.property_tax_gdp_pct:.2f}% of GDP "
    f"(peer median {m.drop('PT')['property_tax_gdp_pct'].median():.2f}%), housing support {pt.housing_support_gdp_pct:.2f}% (peer median {m.drop('PT')['housing_support_gdp_pct'].median():.2f}%)"
)
print(
    "property tax over time (PT): "
    + ", ".join(f"{y} {over_time.loc[y, 'PT']:.2f}%" for y in over_time.index)
)
