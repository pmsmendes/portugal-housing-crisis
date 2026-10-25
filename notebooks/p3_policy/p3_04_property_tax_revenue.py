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
# # P3.04 — IMI and IMT revenue
#
# **Question:** RQ7.1 (how have IMI and IMT revenues evolved?). Groundwork for RQ7.2 (what a rate cut costs).
#
# No machine-readable municipal revenue exists (`docs/data_quality.md`), so this is national: general-government revenue from
# taxes on land and buildings (IMI) and from taxes on financial and capital transactions (IMT with stamp duty) in the national
# accounts, 1995 to 2025, on an accrual basis. IMI revenue is a rate times an assessed base that follows tax values, not market
# prices. IMT revenue applies a rate schedule to the value of homes sold, so it follows prices and the number of sales. The rate
# is observed from 2012 (`at_imi_rates`, weighted by the 2021 stock of dwellings); the base is revenue over rate, so it carries
# everything else: reassessments, exemptions, the additional IMI (AIMI) on high-value property and accrual timing.

# %%
import pandas as pd

from pthousing.analysis import revenue
from pthousing.config import PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
long = pd.read_parquet(PROCESSED / "national_annual_long.parquet")
rate = revenue.weighted_imi_rate(panel)
a = revenue.annual_frame(interim.read("eurostat_property_tax"), interim.read("ine_cpi"), long, rate)
print(
    f"{a.index.min()}-{a.index.max()}, {len(a)} years; rate observed {rate.index.min()}-{rate.index.max()}"
)

# %% [markdown]
# ## Step 1 — Revenue over thirty years
# Real revenue in euros of the base year, and both taxes next to the real house price index (2015 = 100).

# %%
fig = charts.property_tax_revenue(a)
style.save_fig(fig, "p3", "property_tax_revenue")
years = [1995, 2000, 2007, 2013, 2015, 2019, 2022, 2025]
levels = a.loc[
    years, ["imi_real_eur_m", "imt_real_eur_m", "imi_gdp_pct", "imt_gdp_pct", "hpi_real_b2015"]
]
style.save_table(levels.round(2).reset_index(), "p3", "property_tax_levels")
series = a[
    ["imi_real_eur_m", "imt_real_eur_m", "imi_real_b2015", "imt_real_b2015", "hpi_real_b2015"]
]
style.save_table(
    series.round(2).reset_index(), "p3", "property_tax_series"
)  # every year, for the dashboard
levels.round(2)

# %% [markdown]
# ## Step 2 — Episodes
# Percentage changes over the boom, the crisis and the recovery. IMT moves with the market (it fell by two thirds in real terms
# from 2007 to 2013 and has since passed its earlier peak); IMI did not fall in the crisis (it rose, the base was being reassessed:
# the general reassessment of urban buildings ran in 2011-2013, not modelled here) and has lagged prices since.

# %%
windows = {
    "1995-2007 boom": (1995, 2007),
    "2007-2013 crisis": (2007, 2013),
    "2013-2019 recovery": (2013, 2019),
    "2019-2025 price surge": (2019, 2025),
    "2013-2025": (2013, 2025),
}
cols = [
    "imi_eur_m",
    "imi_real_eur_m",
    "imt_eur_m",
    "imt_real_eur_m",
    "hpi_nominal_b2015",
    "hpi_real_b2015",
]
episodes = revenue.changes(a, windows, cols)
style.save_table(episodes.round(1).reset_index(), "p3", "property_tax_episodes")
episodes.round(1)

# %% [markdown]
# ## Step 3 — IMI: rate and base
# The weighted average rate fell from 2012 as councils cut and more sat at the 0.3% floor. The rest of the change in revenue is
# the base. Compared with the nominal house price, the gap shows how far the base lags the market: assessed values are revised
# on sale, on renewal and in general reassessments, not with the market.

# %%
windows_imi = {"2013-2019": (2013, 2019), "2019-2025": (2019, 2025), "2013-2025": (2013, 2025)}
parts = pd.DataFrame(
    {k: revenue.decompose_imi(a, *w) for k, w in windows_imi.items()}
).T.rename_axis("window")
style.save_table(parts.round(1).reset_index(), "p3", "imi_decomposition")
print("log points; base = revenue - rate; gap = base - nominal house price")
parts.round(1)

# %%
rate_path = a.loc[2012:, ["imi_rate_pct", "imi_eur_m", "imi_base_b2015", "hpi_nominal_b2015"]]
style.save_table(rate_path.round(3).reset_index(), "p3", "imi_rate_and_base")
rate_path.round(3)

# %% [markdown]
# ## Step 4 — Does this match the simulator's anchors?
# `config/scenarios.yaml` carries hand-entered 2024 anchors from press and the tax authority (IMI assessed 1,630 EUR m; IMT collected
# 1,732.8 EUR m). The national accounts are a different measure (accrual, not assessed or cash), so only the scale is compared.

# %%
anchors = {"imi_eur_m": 1630.0, "imt_eur_m": 1732.8}
check = pd.DataFrame(
    {
        "national_accounts_2024": [a.loc[2024, c] for c in anchors],
        "simulator_anchor_2024": list(anchors.values()),
    },
    index=list(anchors),
)
check["difference_pct"] = 100 * (
    check["national_accounts_2024"] / check["simulator_anchor_2024"] - 1
)
style.save_table(check.round(1).reset_index(names="tax"), "p3", "property_tax_anchor_check")
check.round(1)

# %% [markdown]
# ## Key numbers

# %%
e, p = episodes, parts
print(
    f"IMT: real {e.loc['2007-2013 crisis', 'imt_real_eur_m']:+.0f}% in 2007-2013, {e.loc['2013-2025', 'imt_real_eur_m']:+.0f}% in 2013-2025; "
    f"2025 {a.loc[2025, 'imt_real_eur_m']:,.0f} EUR m ({a.loc[2025, 'imt_gdp_pct']:.2f}% of GDP) against {a.loc[2007, 'imt_real_eur_m']:,.0f} in 2007 ({a.loc[2007, 'imt_gdp_pct']:.2f}%)"
)
print(
    f"IMI: real {e.loc['2013-2019 recovery', 'imi_real_eur_m']:+.0f}% in 2013-2019, {e.loc['2019-2025 price surge', 'imi_real_eur_m']:+.0f}% in 2019-2025; "
    f"share of GDP {a['imi_gdp_pct'].max():.2f}% ({a['imi_gdp_pct'].idxmax()}) -> {a.loc[2025, 'imi_gdp_pct']:.2f}% (2025)"
)
print(
    f"2013-2025 IMI in log points: revenue {p.loc['2013-2025', 'revenue']:+.0f} = rate {p.loc['2013-2025', 'rate']:+.0f} + base {p.loc['2013-2025', 'base']:+.0f}; "
    f"nominal house price {p.loc['2013-2025', 'price']:+.0f}, so the base lags it by {-p.loc['2013-2025', 'gap']:.0f}"
)
print(
    f"2019-2025: rate {p.loc['2019-2025', 'rate']:+.0f}, base {p.loc['2019-2025', 'base']:+.0f}, price {p.loc['2019-2025', 'price']:+.0f}"
)
print(
    f"rate {rate.loc[2012]:.3f}% (2012) -> {rate.loc[2025]:.3f}% (2025); a 0.01 pp cut of the average rate ~ "
    f"{a.loc[2025, 'imi_eur_m'] * 0.01 / rate.loc[2025]:.0f} EUR m of 2025 revenue (linear, nominal)"
)
print(check.round(1).to_string())
