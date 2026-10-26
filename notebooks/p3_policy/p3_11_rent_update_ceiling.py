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
# # P3.11 — Sitting tenants and new tenants: the rent-update coefficient
#
# **Questions:** RQ6.1 (have rent-control measures reduced rents for affected tenants?) and RQ6.3 (who benefits from rent regulation, and
# who finds access harder?), in the one respect the data allow. Portugal does not cap the rent of a new lease; it caps the **yearly
# rise of an existing one** by a coefficient INE publishes (CPI without housing, 12 months to August), and in 2023 by an extraordinary
# ceiling of 2% in place of the formula's 5.43% (`data/external/rent_update_coefficients.csv`). Rent ceilings on new leases, their effect
# on rental supply, maintenance and conversion (RQ6.2), and the leases themselves are not in the data.
#
# **What is measured.** (1) For a lease signed at the median rent of new leases in 2020, the highest rent it can reach by 2024 under the
# coefficients, against the median rent of new leases, the price level and the rent without the 2023 ceiling. (2) The same by
# municipality (rents of new leases 2020 and 2024, `ine_median_rent_sqm`): the **gap** a new tenant pays above that sitting tenant. (3)
# How much of the let stock this touches: new leases a year per 100 rented dwellings (census 2021). Accounting from rules and observed
# rents, no behaviour.
#
# **Reading rule, fixed before looking:** a "dual market" is read if the new-lease rent exceeds the updated old rent in most
# municipalities (median gap above 10%) and the gap is not smaller where more homes are let. Whether it is *caused* by the update rule
# is not tested: a gap would also open with no rule if rents rose faster than the CPI.

# %%
import pandas as pd

from pthousing.analysis import incidence as inc
from pthousing.analysis import rent_update as ru
from pthousing.analysis import supply
from pthousing.config import PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
BASE, LAST = 2020, 2024
coef = ru.read()
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
rent = panel.loc[
    panel["rent_sqm_eur"].notna(), ["muni_code", "year", "rent_sqm_eur", "new_leases_n"]
]
cpi = interim.read("ine_cpi").set_index("year")["cpi_index_b2025"]
print(coef.loc[2020:2024, ["legal_coefficient", "formula_coefficient"]])

# %% [markdown]
# ## Step 1 — What the coefficients allow, nationally
# The median rent of new leases is the median over the municipalities that publish one, weighted by nothing (a typical municipality, as
# in `p1_01`). Each rise applies from the year after signing.

# %%
nat_rent = rent.groupby("year")["rent_sqm_eur"].median()
path = ru.national_path(coef, BASE, range(BASE, LAST + 1), nat_rent, cpi)
style.save_table(path.round(2).reset_index(), "p3", "rent_update_path")
print(path.round(1).to_string())
legal_rise = ru.allowed_rise_pct(coef, BASE, LAST, "legal_coefficient")
formula_rise = ru.allowed_rise_pct(coef, BASE, LAST, "formula_coefficient")
print(
    f"\nlease signed {BASE}: may rise {legal_rise:.1f}% to {LAST} ({formula_rise:.1f}% without the 2023 ceiling); "
    f"CPI {path.loc[LAST, 'cpi_index'] - 100:.1f}%; median new lease {path.loc[LAST, 'new_lease_rent_index'] - 100:.1f}%"
)
real = 100 * (path.loc[LAST, "legal_rent_index"] / path.loc[LAST, "cpi_index"] - 1)
print(
    f"real rent of the sitting tenant {real:.1f}%; the ceiling cut the 2023 rise from 5.43% to 2.00%"
)

# %% [markdown]
# ## Step 2 — The gap by municipality
# For each municipality with a rent of new leases in 2020 and in 2024 (about 190), the 2024 median against the 2020 median raised by
# the legal coefficients. The gap by third of 2024 price-to-income, and its link with the share of homes let.

# %%
cum = ru.cumulative(coef["legal_coefficient"], BASE + 1, LAST)
gap = ru.market_gap(rent, BASE, LAST, cum)
d = panel[panel["year"] == LAST].set_index("muni_code")
census = interim.read("ine_census")
stock = supply.read_stock()
uses = inc.dwellings_by_use(stock, census)
gap["rented_n"] = uses["rented"]
gap["dwellings_n"] = uses.sum(axis=1)
gap["rented_share_pct"] = 100 * gap["rented_n"] / gap["dwellings_n"]
gap["pti_years"] = d["pti_years"]
gap["new_leases_n"] = rent[rent["year"] == LAST].set_index("muni_code")["new_leases_n"]
gap["turnover"] = ru.turnover(gap["new_leases_n"], gap["rented_n"])
gap["pti_third"] = inc.terciles(gap["pti_years"], ("most affordable", "middle", "least affordable"))
print(
    f"{len(gap)} municipalities; share with a positive gap {100 * (gap['gap_pct'] > 0).mean():.0f}%"
)
print(
    gap[["market_rise_pct", "gap_pct", "rented_share_pct", "turnover"]]
    .describe()
    .round(1)
    .to_string()
)

# %%
sub = gap.dropna(subset=["pti_third"]).groupby("pti_third", observed=True)
by_third = pd.DataFrame(
    {
        "municipalities_n": sub.size(),
        "median_market_rise_pct": sub["market_rise_pct"].median(),
        "median_gap_pct": sub["gap_pct"].median(),
        "rented_share_pct": 100 * sub["rented_n"].sum() / sub["dwellings_n"].sum(),
        "median_new_leases_per_100_rented": sub["turnover"].median(),
    }
)
style.save_table(by_third.round(2).reset_index(), "p3", "rent_update_gap_by_third")
print(by_third.round(1).to_string())
rho = gap[["gap_pct", "rented_share_pct"]].corr(method="spearman").iloc[0, 1]
rho_pti = gap[["gap_pct", "pti_years"]].corr(method="spearman").iloc[0, 1]
rho_rise = gap[["gap_pct", "market_rise_pct"]].corr(method="spearman").iloc[0, 1]
print(f"rank correlation of the gap with share let {rho:.2f}, with price-to-income {rho_pti:.2f}")

# %% [markdown]
# ## Step 3 — How many leases the 2023 ceiling touched, and what it saved
# In 2023 the formula would have allowed 5.43%, the law 2.00%. For a lease at the 2022 median rent of its municipality and the average
# dwelling area, the monthly rent saved in 2023, and the stock of let dwellings this applies to (all rented homes, an upper bound: part
# of the stock is under older regimes or let at a rent that is not updated).

# %%
area = stock[stock["census_year"] == 2021].set_index("muni_code")["dwelling_area_sqm"]
r22 = rent[rent["year"] == 2022].set_index("muni_code")["rent_sqm_eur"]
saving = ru.ceiling_saving(
    r22,
    area.reindex(r22.index),
    coef.loc[2023, "legal_coefficient"],
    coef.loc[2023, "formula_coefficient"],
).dropna()
med = saving.median()
rented_total = float(uses["rented"].sum())
print(
    f"median lease before {med['rent_before_eur']:.0f} EUR a month; saving in 2023 {med['saving_eur_month']:.0f} EUR a month "
    f"({12 * med['saving_eur_month']:.0f} a year); {len(saving)} municipalities; {rented_total:,.0f} rented dwellings in 2021"
)
upper = 12 * med["saving_eur_month"] * rented_total / 1e6
print(f"upper bound for all rented dwellings at the median saving: {upper:,.0f} EUR m a year")
pd.DataFrame(
    {
        "median_rent_before_eur": [med["rent_before_eur"]],
        "saving_eur_month": [med["saving_eur_month"]],
        "rented_dwellings_n": [rented_total],
        "upper_bound_eur_m_year": [upper],
    }
).pipe(lambda t: style.save_table(t.round(2), "p3", "rent_ceiling_2023_saving"))

# %%
fig = charts.rent_update_gap(path, by_third)
style.save_fig(fig, "p3", "rent_update_gap")
fig

# %% [markdown]
# ## Findings
#
# 1. **A sitting tenant's real rent fell, a new tenant's rose (RQ6.1, RQ6.3).** A lease signed at the 2020 median could be raised by
#    9.5% by 2024 (coefficients 0.9997, 1.0043, 1.02, 1.0694), against consumer prices +16.7%: a fall of 6.1% in real terms. The median rent
#    of new leases rose 39.7%. The 2023 ceiling cut that year's allowed rise from 5.43% to 2.00% and the four-year rise from 13.2% to 9.5%.
# 2. **The gap is general and does not shrink where renting is common.** A new lease in 2024 costs 32% more than the 2020 median rent raised
#    by every allowed update in the median of 191 municipalities (98% have a positive gap; middle 50%: 26% to 38%). Rank correlation of
#    the gap with the share of homes let -0.04: no sign that a larger rental market narrows it. It is slightly larger in dearer places
#    (rank correlation 0.24 with price-to-income; 29% in the most affordable third, 34% and 33% in the other two).
# 3. **Most of the let stock is not repriced in a year.** New leases a year are 12 per 100 rented dwellings in the median municipality
#    (14 in the most affordable third, 11 in the least affordable), so about 88 of 100 let homes keep a rent bounded by the coefficients;
#    those who move face the market, which is a reason for the gap to matter for access, not only for who pays what.
# 4. **The 2023 ceiling was worth about 18 EUR a month to a typical lease.** At the 2022 median rent per m2 and the average dwelling area
#    it saved 18 EUR a month (217 a year; 527 EUR before the update) and 3.4% of the rent, at most 200 EUR m a year if it had touched all 923,000
#    rented dwellings; landlords were compensated through IRS and IRC, so part of the cost moved to the state budget (not estimated).
#
# **Reading rule:** the median gap (32%) is above 10% and does not fall with the share let, so the data read as a dual market, with sitting
# tenants protected by the coefficient and new tenants exposed to the market.
#
# **Limits.** Medians of new leases in about 190 municipalities that publish both years (selection towards towns with a rental market), not
# the rents of the same leases: composition of new leases, size and quality change, so part of the gap is not a like-for-like price. The
# coefficient is a ceiling and the update is optional; the median lease may have been raised less, or not at all; leases under older
# regimes (before 1990) and rents fixed by other rules are not told apart. The dwelling area is the average of all dwellings (rented ones
# are smaller), so the euro saving is an upper bound per lease; the national figure assumes every rented home was updated at the ceiling.
# No effect of the rule on rental supply, maintenance, new building or conversion (RQ6.2) can be read from these data, and the gap would
# also open without the rule if market rents outpaced prices; no comparison group. Coefficients are transcribed from published notices
# and secondary compilations (see the file's `note` column); check against the Diario da Republica before relying on a single year.
