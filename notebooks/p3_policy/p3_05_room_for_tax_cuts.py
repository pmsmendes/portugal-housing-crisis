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
# # P3.05 — Room for IMI and IMT cuts, and who pays
#
# **Questions:** RQ7.2 (what would IMI/IMT rate cuts do to central and municipal revenue?), RQ7.3 (could more transactions or
# construction offset the loss?). Builds on `p3_04` (revenue) and the simulator's two tax levers (`p4_02`).
#
# Three checks that the simulator's accounting does not make. (1) **Who gets the revenue:** IMI and IMT are municipal revenue under
# the Local Finance Law (art. 14 of Lei 73/2013, as quoted in the press), so a cut falls on councils, not on the central budget.
# (2) **How far a council can cut:** the urban IMI rate has a legal floor of 0.30%, and most councils are already on it.
# (3) **What growth would pay for a cut:** revenue is rate times base, so a cut of a share c of the bill is recovered only if the base
# grows by c / (1 - c) at the new rate.

# %%
import pandas as pd

from pthousing.analysis import revenue
from pthousing.config import IMI_URBAN_MIN_PCT, PROCESSED
from pthousing.data import interim
from pthousing.viz import style

style.apply_style()
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
tax = interim.read("eurostat_property_tax").set_index("year")
print(
    f"floor {IMI_URBAN_MIN_PCT}%; lowest rate observed 2012-2025: {panel['imi_urban_pct'].min()}%"
)

# %% [markdown]
# ## Step 1 — Who receives the revenue
# National accounts (general government) against what municipalities collected in 2023 according to press reports of the municipal
# execution data (IMI 1,504 and IMT 1,695 EUR m; not read from the source). The IMT series is the same measure within 1%; the
# national-accounts IMI is 161 EUR m higher, about the size of a tax collected by the State (the additional IMI, AIMI), which is not
# verified here. A rate cut is a municipal decision for IMI and a change of law for IMT, but in both cases the money lost is the councils'.

# %%
press = pd.Series({"imi_eur_m": 1504.0, "imt_eur_m": 1695.0})
who = pd.DataFrame(
    {
        "national_accounts_2023": tax.loc[
            2023, ["imi_revenue_eur_m", "imt_revenue_eur_m"]
        ].to_numpy(),
        "municipal_press_2023": press.to_numpy(),
    },
    index=["IMI", "IMT"],
)
who["difference_eur_m"] = who["national_accounts_2023"] - who["municipal_press_2023"]
style.save_table(who.round(1).reset_index(names="tax"), "p3", "who_receives_revenue")
who.round(1)

# %% [markdown]
# ## Step 2 — How far can councils cut the IMI rate?
# Weighted average (2021 dwellings) of each council's gap to the 0.30% floor. A council on the floor cannot cut; the headroom is
# the largest cut of the national bill that councils can make without a change of the law.

# %%
years = range(2012, 2026)
room = pd.DataFrame({y: revenue.imi_headroom(panel, y) for y in years}).T.rename_axis("year")
room["headroom_eur_m"] = room["headroom_share"] * tax["imi_revenue_eur_m"].reindex(room.index)
style.save_table(room.round(4).reset_index(), "p3", "imi_headroom")
room.round(3)

# %% [markdown]
# ## Step 3 — The simulator's cut against the headroom
# The IMI package of `p4_02` cuts the average rate by 0.05 pp. Each council cutting by a given amount, but none below the floor,
# delivers:

# %%
rows = {f"{cut:.2f} pp": revenue.capped_cut(panel, 2025, cut) for cut in (0.01, 0.02, 0.03, 0.05)}
capped = pd.DataFrame(rows).T.rename_axis("uniform cut")
capped["revenue_lost_eur_m"] = capped["average_cut_share"] * tax.loc[2025, "imi_revenue_eur_m"]
style.save_table(capped.round(4).reset_index(), "p3", "imi_capped_cuts")
capped.round(3)

# %% [markdown]
# ## Step 4 — What growth would pay for a cut?
# **IMI.** Base growth needed to recover a cut of the full headroom and of the simulator's 0.05 pp (15% of the bill), set against the
# yearly growth of the stock of dwellings (2024 completions over the 2021 census stock). New dwellings are taken to carry the average bill.
#
# **IMT.** The base is the value of dwellings sold (panel, benchmark dwelling of 100 m², constant euros). A cut of 1 pp of the price is
# 1% of that value. Revenue over that value is an upper bound of the effective rate on dwellings (the national-accounts figure also
# holds land, other buildings and stamp duty), so the growth in dwelling sales that would pay for the cut is at least what is shown.

# %%
stock = panel.loc[panel["year"] == 2021, "dwellings_2021_n"].sum()
stock_growth = panel.loc[panel["year"] == 2024, "completed_n"].sum() / stock
headroom_share = room.loc[2025, "headroom_share"]
simulator_share = 0.05 / room.loc[2025, "average_rate_pct"]
imi_rows = pd.DataFrame(
    {
        "share_of_bill": [headroom_share, simulator_share],
        "base_growth_needed": [revenue.offset_growth(s) for s in (headroom_share, simulator_share)],
    },
    index=["full headroom", "0.05 pp everywhere"],
)
imi_rows["years_of_completions"] = imi_rows["base_growth_needed"] / stock_growth
style.save_table(imi_rows.round(4).reset_index(names="cut"), "p3", "imi_offset_by_construction")
imi_rows.round(3)

# %%
span = range(2019, 2025)  # the municipal sales counts start in 2019
sales = pd.DataFrame(
    {
        "value_bn_eur": {y: revenue.dwelling_sales_value(panel, y) / 1e9 for y in span},
        "sales_n": {y: panel.loc[panel["year"] == y, "sales_12m_n"].sum() for y in span},
    }
).rename_axis("year")
sales["value_change_pct"] = 100 * sales["value_bn_eur"].pct_change()
sales["sales_change_pct"] = 100 * sales["sales_n"].pct_change()
total_change = 100 * (sales.loc[2024, "value_bn_eur"] / sales.loc[2019, "value_bn_eur"] - 1)
style.save_table(sales.round(2).reset_index(), "p3", "dwelling_sales_value")
value_2024 = sales.loc[2024, "value_bn_eur"] * 1e9
implied_rate = 100 * tax.loc[2024, "imt_revenue_eur_m"] * 1e6 / value_2024
cut_share = 1.0 / implied_rate
imt_rows = pd.DataFrame(
    {
        "revenue_over_sales_value_pct": [implied_rate],
        "cut_of_1pp_share_of_revenue": [cut_share],
        "value_growth_needed_at_least": [revenue.offset_growth(cut_share)],
        "largest_yearly_rise_pct": [sales["value_change_pct"].max()],
    },
    index=["IMT cut of 1 pp, 2024"],
)
style.save_table(imt_rows.round(3).reset_index(names="cut"), "p3", "imt_offset_by_sales")
print(sales.round(1).to_string())
imt_rows.round(3)

# %% [markdown]
# ## Key numbers

# %%
r = room.loc[2025]
print(
    f"2025: {int(r.at_floor_n)} of {int(r.municipalities_n)} councils at the {IMI_URBAN_MIN_PCT}% floor; weighted average rate {r.average_rate_pct:.3f}%; "
    f"headroom {r.headroom_pp:.3f} pp = {100 * r.headroom_share:.1f}% of the bill = {r.headroom_eur_m:.0f} EUR m a year (upper: includes AIMI)"
)
print(
    f"at the floor: 2012 {int(room.loc[2012, 'at_floor_n'])}, 2019 {int(room.loc[2019, 'at_floor_n'])}, 2025 {int(r.at_floor_n)}; "
    f"headroom share of the bill 2012 {100 * room.loc[2012, 'headroom_share']:.1f}% -> 2025 {100 * r.headroom_share:.1f}%"
)
c = capped.loc["0.05 pp"]
print(
    f"a uniform 0.05 pp cut: {int(c.full_cut_n)} councils can do it in full; the average cut is {c.average_cut_pp:.3f} pp "
    f"({100 * c.average_cut_share:.1f}% of the bill, {c.revenue_lost_eur_m:.0f} EUR m), against the simulator's 0.05 pp "
    f"({100 * simulator_share:.1f}%, ~{simulator_share * tax.loc[2025, 'imi_revenue_eur_m']:.0f} EUR m)"
)
print(
    f"IMI offset: headroom needs +{100 * imi_rows.iloc[0].base_growth_needed:.1f}% base = {imi_rows.iloc[0].years_of_completions:.0f} years of completions "
    f"({100 * stock_growth:.2f}% a year of the 2021 stock); 0.05 pp everywhere +{100 * imi_rows.iloc[1].base_growth_needed:.1f}% = {imi_rows.iloc[1].years_of_completions:.0f} years"
)
m = imt_rows.iloc[0]
print(
    f"IMT: 2024 revenue is {m.revenue_over_sales_value_pct:.1f}% of dwelling sales value; a 1 pp cut is {100 * m.cut_of_1pp_share_of_revenue:.0f}% of it "
    f"and needs sales value to rise at least {100 * m.value_growth_needed_at_least:.0f}%; largest yearly rise 2020-2024: {m.largest_yearly_rise_pct:.0f}% (2021, a rebound), 2019-2024 {total_change:+.0f}%"
)
