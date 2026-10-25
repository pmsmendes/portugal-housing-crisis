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
# # P2.09 — Wages, unemployment, GDP and the price cycle
#
# **Questions:** RQ9.1 (how have wage growth, unemployment and GDP growth influenced prices?), RQ1.4 (affordability against wage
# growth, which `p1_03` covered only through the OECD's income per head). Companion of `p2_08` (mortgage rates).
#
# National annual series, 1995 to 2025: real and nominal house prices (BIS, INE), compensation per employee and GDP growth
# (Eurostat national accounts), the unemployment rate (Eurostat labour force survey). Thirty observations and one economy:
# co-movements, not causes. Real wages and real prices use the same deflator, so each check is repeated with nominal
# values and inflation.

# %%
import pandas as pd

from pthousing.analysis import macro
from pthousing.config import PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
long = pd.read_parquet(PROCESSED / "national_annual_long.parquet")
annual = macro.annual_frame(long, interim.read("eurostat_macro"))
print(f"{annual.index.min()}-{annual.index.max()}, {len(annual)} years")

# %% [markdown]
# ## Step 1 — Prices against wages
# Compensation per employee deflated with the CPI grew far less than house prices after 2013. The price-to-wage ratio is built
# like the price-to-income one (nominal price over nominal earnings) but from national accounts, so it reaches back to 1995 with
# a different earnings concept.

# %%
fig = charts.wages_and_prices(annual)
style.save_fig(fig, "p2", "wages_and_prices")
years = [1995, 2001, 2008, 2013, 2020, 2025]
levels = annual.loc[
    years,
    [
        "hpi_real_b2015",
        "wage_real_b2015",
        "price_to_wage_b2015",
        "price_to_income_b2015",
        "unemployment_pct",
    ],
]
style.save_table(levels.round(1).reset_index(), "p2", "wages_prices_levels")
levels.round(1)

# %% [markdown]
# ## Step 2 — What moves with price growth?
# Yearly real price growth on real wage growth, the change in unemployment (pp) and GDP growth. Newey-West errors. Within the
# year (`lag 0`) the labour market and prices move together; with the variables one year earlier (`lag 1`) the question becomes
# whether they lead. A nominal version (nominal prices on nominal wages, inflation and unemployment) removes the shared deflator.

# %%
real = ["wage_growth_real_pct", "unemployment_change_pp", "gdp_growth_pct"]
specs = {
    "lag 0: wages": dict(xs=real[:1]),
    "lag 0: wages, unemployment": dict(xs=real[:2]),
    "lag 0: wages, unemployment, GDP": dict(xs=real),
    "lag 0: ... + last year's growth": dict(xs=real, own_lag=True),
    "lag 0: without 2020-2022": dict(xs=real[:2], drop_years=(2020, 2021, 2022)),
    "lag 1: wages, unemployment, GDP": dict(xs=real, lag=1),
    "lag 1: ... + last year's growth": dict(xs=real, lag=1, own_lag=True),
    "nominal: wages, inflation, unemployment": dict(
        xs=["wage_growth_nominal_pct", "inflation_pct", "unemployment_change_pp"],
        y="price_growth_nominal_pct",
    ),
}
fits = pd.concat(
    {name: macro.fundamentals(annual, **kw) for name, kw in specs.items()},
    names=["specification"],
).reset_index()
style.save_table(fits.round(3), "p2", "price_growth_fundamentals")
fits.round(2)

# %% [markdown]
# ## Step 3 — And rents?
# The same regressions with the real growth of the OECD rent index as the outcome. The index covers every lease, old regulated
# ones included, so it moves slowly (see `data_quality.md`): it says how the rent of the whole stock of leases follows wages and
# unemployment, not what a new tenant pays.

# %%
rent_specs = {
    "lag 0: wages": dict(xs=real[:1]),
    "lag 0: wages, unemployment": dict(xs=real[:2]),
    "lag 0: wages, unemployment, GDP": dict(xs=real),
    "lag 1: wages, unemployment": dict(xs=real[:2], lag=1),
}
rent_fits = pd.concat(
    {
        name: macro.fundamentals(annual, y="rent_growth_real_pct", **kw)
        for name, kw in rent_specs.items()
    },
    names=["specification"],
).reset_index()
style.save_table(rent_fits.round(3), "p2", "rent_growth_fundamentals")
rent_fits.round(2)

# %% [markdown]
# ## Key numbers

# %%
a = annual
low = a["price_to_wage_b2015"].loc[2008:].idxmin()
print(
    f"since {low}: real prices {100 * (a['hpi_real_b2015'].iloc[-1] / a.loc[low, 'hpi_real_b2015'] - 1):+.0f}%, "
    f"real compensation per employee {100 * (a['wage_real_b2015'].iloc[-1] / a.loc[low, 'wage_real_b2015'] - 1):+.0f}%, "
    f"price-to-wage ratio {a['price_to_wage_b2015'].iloc[-1] / a.loc[low, 'price_to_wage_b2015']:.2f}x (2015 = 100: {a['price_to_wage_b2015'].iloc[-1]:.0f}; 1995 {a.loc[1995, 'price_to_wage_b2015']:.0f}, 2001 {a.loc[2001, 'price_to_wage_b2015']:.0f})"
)
for name, grp in fits.groupby("specification", sort=False):
    cells = ", ".join(
        f"{r.term} {r.coef:+.2f} [{r.ci_low:+.2f}, {r.ci_high:+.2f}]" for r in grp.itertuples()
    )
    print(f"{name} (R2 {grp['r2'].iloc[0]:.2f}, n {grp['n'].iloc[0]}): {cells}")
r = annual
print(
    f"real rents (all leases) since {low}: {100 * (r['rent_real_b2015'].iloc[-1] / r.loc[low, 'rent_real_b2015'] - 1):+.0f}% "
    f"against prices {100 * (a['hpi_real_b2015'].iloc[-1] / a.loc[low, 'hpi_real_b2015'] - 1):+.0f}%"
)
for name, grp in rent_fits.groupby("specification", sort=False):
    cells = ", ".join(
        f"{r_.term} {r_.coef:+.2f} [{r_.ci_low:+.2f}, {r_.ci_high:+.2f}]" for r_ in grp.itertuples()
    )
    print(f"rents, {name} (R2 {grp['r2'].iloc[0]:.2f}, n {grp['n'].iloc[0]}): {cells}")
