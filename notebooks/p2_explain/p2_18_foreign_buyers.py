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
# # P2.18 — What foreign buyers pay, and where they buy
#
# **Question:** RQ5.2 (how has foreign investment in residential property evolved, and is it associated with higher regional prices?).
# `p2_05`, `p2_14` and `p2_06` already look at foreign *residents* and second homes; this notebook is about foreign *buyers*.
#
# INE gives the median sale price per m2 by the buyer's tax residence (national territory, EU, other countries) nationally and for each
# municipality, from 4Q2019. It gives no count of sales by buyer, and a cell is blank when there are too few transactions. So:
# the **premium** (foreign median over domestic median) is a price gap, not a measure of investment, and a municipality with a
# foreign-buyer price is one with enough foreign purchases, which is the only signal of **where** they buy. How much money came in is
# not measured: Banco de Portugal's real-estate direct investment was not found in BPstat (`config/sources.yaml`).

# %%
import pandas as pd

from pthousing.analysis import foreign_buyers as fb
from pthousing.analysis import supply
from pthousing.config import MUNI_KEY
from pthousing.data import interim
from pthousing.viz import charts, dashboard, style

style.apply_style()
buyer = interim.read("ine_price_by_buyer")
national = interim.read("ine_price_by_buyer_national")
sales = interim.read("ine_median_price_sqm")
panel = dashboard.load_panel()
info = (
    panel.drop_duplicates(MUNI_KEY)
    .set_index(MUNI_KEY)[["coast_class", "density_class", "tourist"]]
    .join(supply.area_of(panel).rename("area"))
)
premium = fb.national_premium(national)
markets = fb.foreign_markets(buyer, sales)
print(
    f"{premium.index.min():%Y-%m} to {premium.index.max():%Y-%m}; yearly snapshots are the 4th quarter"
)

# %% [markdown]
# ## Step 1 — The premium
# Foreign buyers pay more per m2 than domestic buyers. Nationally the gap is large and falling; inside a municipality it is smaller
# (the rest is geography: foreign buyers buy in the dearer places).

# %%
fig = charts.foreign_buyers(premium, markets)
style.save_fig(fig, "p2", "foreign_buyers")
yearly = premium[premium.index.month == 10].round(1)
style.save_table(yearly.reset_index(), "p2", "foreign_buyer_premium")
yearly[
    [
        "domestic",
        "eu",
        "other_foreign",
        "premium_foreign_pct",
        "premium_eu_pct",
        "premium_other_foreign_pct",
    ]
]

# %% [markdown]
# ## Step 2 — Where foreign buyers are active
# Municipalities with a foreign-buyer price each year, the share of all sales in them, and the within-municipality premium.

# %%
style.save_table(markets.round(1).reset_index(), "p2", "foreign_markets_by_year")
markets.round(1)

# %% [markdown]
# A **foreign market** is a municipality with a foreign-buyer price in at least four of the seven yearly snapshots (2019-2025). By kind of
# place, and the median growth of domestic buyers' prices (4Q2019 to 4Q2025, log points) in markets and elsewhere:

# %%
cross = fb.cross_section(buyer, sales, info)
groups = pd.concat(
    {
        c: fb.by_group(cross, c).rename_axis("class")
        for c in ("coast_class", "density_class", "tourist")
    },
    names=["typology"],
).round(1)
style.save_table(groups.reset_index(), "p2", "foreign_markets_by_typology")
print(f"{len(cross)} municipalities, {int(cross['foreign_market'].sum())} foreign markets")
groups

# %% [markdown]
# ## Step 3 — Are foreign markets where prices are higher, or rose more?
# Outcome: the change in domestic buyers' prices 2019-2025 (so foreign prices do not enter it) and the 2025 level. The flag is added to
# district effects, the log of 2019 sales (a foreign price needs enough sales, which also go with big markets) and the coast, density and
# tourist classes. Standard errors are clustered by district (20 areas).

# %%
growth = fb.association(cross, "growth_log_pts")
level = fb.association(cross, "log_price_end")
style.save_table(growth.round(3).reset_index(), "p2", "foreign_markets_price_growth")
style.save_table(level.round(3).reset_index(), "p2", "foreign_markets_price_level")
display_cols = ["coef", "ci_low", "ci_high", "p_value", "n"]
print("growth (log points):")
print(growth[display_cols].round(2).to_string())
print("level (percent):")
print(level[display_cols].round(2).to_string())

# %% [markdown]
# ### Sensitivity to the definition of a foreign market
# One year or more, two, four (used) or all seven.

# %%
rows = []
for years in (1, 2, 4, 7):
    c = fb.cross_section(buyer, sales, info, min_years=years)
    for outcome, name in (("growth_log_pts", "growth"), ("log_price_end", "level")):
        a = fb.association(c, outcome)
        for spec in ("district", "district, sales, typology"):
            r = a.loc[spec]
            rows.append(
                {
                    "min_years": years,
                    "markets_n": int(c["foreign_market"].sum()),
                    "outcome": name,
                    "specification": spec,
                    "coef": r["coef"],
                    "ci_low": r["ci_low"],
                    "ci_high": r["ci_high"],
                }
            )
sens = pd.DataFrame(rows).round(2)
style.save_table(sens, "p2", "foreign_markets_sensitivity")
sens

# %% [markdown]
# ## Key numbers

# %%
nat = premium[premium.index.month == 10]
print(
    f"national premium of foreign over domestic buyers: {nat['premium_foreign_pct'].iloc[0]:.0f}% (4Q2019), {nat['premium_foreign_pct'].iloc[-1]:.0f}% (4Q2025), "
    f"{premium['premium_foreign_pct'].iloc[-1]:.0f}% (2Q2026); EU {nat['premium_eu_pct'].iloc[0]:.0f}% to {nat['premium_eu_pct'].iloc[-1]:.0f}%, "
    f"other countries {nat['premium_other_foreign_pct'].iloc[0]:.0f}% to {nat['premium_other_foreign_pct'].iloc[-1]:.0f}%"
)
print(
    f"domestic median {nat['domestic'].iloc[0]:,.0f} to {nat['domestic'].iloc[-1]:,.0f} EUR/m2 (+{100 * (nat['domestic'].iloc[-1] / nat['domestic'].iloc[0] - 1):.0f}%), "
    f"foreign {nat['foreign'].iloc[0]:,.0f} to {nat['foreign'].iloc[-1]:,.0f} (+{100 * (nat['foreign'].iloc[-1] / nat['foreign'].iloc[0] - 1):.0f}%)"
)
print(
    f"within a municipality: median premium {markets['median_premium_pct'].iloc[0]:.0f}% (2019), {markets['median_premium_pct'].iloc[-1]:.0f}% (2025); "
    f"foreign price in {markets['foreign_priced_n'].min()} to {markets['foreign_priced_n'].max()} of ~300 municipalities a year, holding {markets['share_of_sales_pct'].min():.0f}% to {markets['share_of_sales_pct'].max():.0f}% of sales"
)
tou = groups.loc["tourist"]
coast = groups.loc["coast_class"]
print(
    f"foreign markets: {int(cross['foreign_market'].sum())} municipalities; {coast.loc['coast', 'foreign_market_share_pct']:.0f}% of coastal, "
    f"{coast.loc['inland', 'foreign_market_share_pct']:.0f}% of inland; {tou.loc['tourist', 'foreign_market_share_pct']:.0f}% of tourist"
)
for name, a in (("growth", growth), ("level", level)):
    print(
        f"{name}: raw {a.loc['no controls', 'coef']:.1f} [{a.loc['no controls', 'ci_low']:.1f}, {a.loc['no controls', 'ci_high']:.1f}]; "
        f"district {a.loc['district', 'coef']:.1f} [{a.loc['district', 'ci_low']:.1f}, {a.loc['district', 'ci_high']:.1f}]; "
        f"district, sales, typology {a.loc['district, sales, typology', 'coef']:.1f} "
        f"[{a.loc['district, sales, typology', 'ci_low']:.1f}, {a.loc['district, sales, typology', 'ci_high']:.1f}]"
    )
