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
# # P3.12 — What IMI and IMT bring each council
#
# **Questions:** RQ7.1 (how have IMI and IMT revenues evolved: the municipal side), RQ7.2 and RQ7.3 (who bears an IMI or IMT cut and how
# much room there is), RQ7.6 (checking the revenue of the vacant-home surcharge, `p3_08`). `p3_04` to `p3_08` worked from the national
# accounts and a bottom-up model of IMI; the receipts of municipal councils (DGAL via INE, 2021 to 2023, 307 of 308 councils, Penedono is
# missing) let the money be seen council by council.
#
# **What it is.** IMI is the council's own tax; IMT is paid to the council where the home is sold. Receipts are as published (thousands of
# euros converted to euros; basis not stated). Municipal IMI is about 90% of the national accounts' tax on land and buildings (the rest
# is the State's surcharge on high-value property, AIMI, which is not municipal) and municipal IMT about 102% of the national IMT, so the
# two sources agree.
#
# **Reading rules, fixed before looking:** a council *depends* on the property taxes if IMI plus IMT are more than a fifth of its current
# receipts; the bottom-up model of IMI per dwelling (`p3_08`) is *good enough for its use* (ranking places and spreading the national
# total) if its rank correlation with the actual IMI per dwelling is at least 0.8; the cost of cutting IMI to the floor is *small* for a
# council if under 1% of its current receipts.

# %%
import pandas as pd

from pthousing.analysis import municipal_revenue as mr
from pthousing.analysis import revenue, supply, vacancy
from pthousing.config import EXTERNAL, PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
YEAR = 2023
rev = interim.read("ine_municipal_revenue")
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
names = panel.drop_duplicates("muni_code").set_index("muni_code")["muni_name"]
typ = pd.read_csv(EXTERNAL / "muni_typology.csv", dtype={"muni_code": str}).set_index("muni_code")
tax = interim.read("eurostat_property_tax").set_index("year")
print(f"{rev['muni_code'].nunique()} councils, years {sorted(rev['year'].unique())}")

# %% [markdown]
# ## Step 1 — How much of a council's money is IMI and IMT
# Nationally, and for the median council, by year; then by kind of place (density class, coast and tourist flag of `typology`).

# %%
s = mr.shares(rev)
national = rev.groupby("year")[["imi_eur", "imt_eur", "current_receipts_eur"]].sum() / 1e6
national["imi_imt_share_pct"] = (
    100 * (national["imi_eur"] + national["imt_eur"]) / national["current_receipts_eur"]
)
national["median_council_share_pct"] = s.groupby("year")["imi_imt_share_pct"].median()
national["imi_vs_national_pct"] = (
    100 * national["imi_eur"] / tax["imi_revenue_eur_m"].reindex(national.index)
)
national["imt_vs_national_pct"] = (
    100 * national["imt_eur"] / tax["imt_revenue_eur_m"].reindex(national.index)
)
style.save_table(national.round(1).reset_index(), "p3", "municipal_tax_national")
print(national.round(1).to_string())
d23 = (
    s[s["year"] == YEAR]
    .set_index("muni_code")
    .join(typ[["density_class", "coast_class", "tourist"]])
)
cols = ["imi_share_pct", "imt_share_pct", "imi_imt_share_pct"]
dims = ("density_class", "coast_class", "tourist")
by = pd.concat({c: d23.groupby(c)[cols].median() for c in dims})
by["councils_n"] = pd.concat({c: d23.groupby(c).size() for c in dims})
style.save_table(
    by.round(1).reset_index(names=["dimension", "class"]), "p3", "municipal_tax_by_place"
)
print(by.round(1).to_string())
dependent = 100 * (d23["imi_imt_share_pct"] > 20).mean()
print(
    f"{dependent:.0f}% of councils draw more than a fifth of current receipts from IMI plus IMT in {YEAR}"
)
print(
    d23.sort_values("imi_imt_share_pct", ascending=False)
    .head(8)[cols]
    .join(names)
    .round(1)
    .to_string()
)

# %% [markdown]
# ## Step 2 — How much each council could cut IMI inside the law
# The urban rate cannot go below 0.30%. Cutting to the floor gives up `IMI * (rate - 0.30) / rate`, the cost falling on the council
# (base held fixed). IMI received in a year is the bill of the tax year before, so the rate of `year - 1` is used (the rate of the same
# year as a check).

# %%
room = mr.floor_room(rev, panel, YEAR)
room_same = mr.floor_room(rev, panel, YEAR, rate_year=YEAR)


def _summary(r: pd.DataFrame) -> dict:
    return {
        "councils_n": len(r),
        "at_floor_n": int((r["room_eur"] == 0).sum()),
        "room_eur_m": r["room_eur"].sum() / 1e6,
        "room_share_of_imi_pct": 100 * r["room_eur"].sum() / r["imi_eur"].sum(),
        "max_share_of_current_pct": r["room_share_of_current_pct"].max(),
        "over_one_pct_of_current_n": int((r["room_share_of_current_pct"] > 1).sum()),
    }


summary = pd.DataFrame(
    {"rate of the year before": _summary(room), "rate of the same year": _summary(room_same)}
).T
style.save_table(summary.round(2).reset_index(names="rate"), "p3", "municipal_floor_room")
print(summary.round(1).T.to_string())
print(room.sort_values("room_eur", ascending=False).head(8).join(names).round(1).to_string())

# %% [markdown]
# ## Step 3 — The IMT windfall of 2021-2023
# IMT follows prices and sales; between 2021 and 2023 it rose. Per council, in euros and as a share of its 2021 current receipts, against
# the room to cut IMI of Step 2.

# %%
w = mr.imt_windfall(rev, 2021, 2023).join(room["room_eur"])
wind = pd.Series(
    {
        "imt_2021_eur_m": rev.loc[rev["year"] == 2021, "imt_eur"].sum() / 1e6,
        "imt_2023_eur_m": rev.loc[rev["year"] == 2023, "imt_eur"].sum() / 1e6,
        "change_eur_m": w["imt_change_eur"].sum() / 1e6,
        "change_pct": 100 * w["imt_change_eur"].sum() / w["imt_start_eur"].sum(),
        "median_council_change_pct": w["imt_change_pct"].median(),
        "councils_with_a_rise_pct": 100 * (w["imt_change_eur"] > 0).mean(),
        "median_change_share_of_current_pct": w["imt_change_share_of_current_pct"].median(),
        "rise_over_floor_room_total": w["imt_change_eur"].sum() / room["room_eur"].sum(),
        "councils_where_rise_exceeds_room_pct": 100 * (w["imt_change_eur"] > w["room_eur"]).mean(),
    }
)
style.save_table(
    wind.round(2).rename("value").rename_axis("measure").reset_index(),
    "p3",
    "municipal_imt_windfall",
)
print(wind.round(1).to_string())
print(
    w.sort_values("imt_change_eur", ascending=False)
    .head(6)[["imt_start_eur", "imt_end_eur", "imt_change_pct"]]
    .join(names)
    .round(0)
    .to_string()
)

# %% [markdown]
# ## Step 4 — Does the bottom-up IMI of `p3_08` hold up?
# `p3_08` built the IMI of a typical dwelling from the price, the mean area, a taxable share and the rate, and scaled it to the national
# accounts. The receipts give the actual IMI per dwelling (all IMI of the council over the census stock of dwellings, so commercial and
# rustic property are in it). The scaling factor against the national accounts (which include AIMI) and against the municipal total,
# and the revenue of the surcharge with the actual IMI per dwelling in place of the model.

# %%
dwellings = panel[panel["year"] == YEAR].set_index("muni_code")["dwellings_2021_n"]
actual = mr.actual_imi_per_dwelling(rev, dwellings, YEAR)
modelled = revenue.imi_per_dwelling(panel, YEAR)
check = mr.bottom_up_check(actual, modelled)
imi_2023 = rev.loc[rev["year"] == YEAR, "imi_eur"].sum() / 1e6
scale_national = revenue.calibration(modelled, dwellings, float(tax.loc[YEAR, "imi_revenue_eur_m"]))
scale_municipal = revenue.calibration(modelled, dwellings, imi_2023)
print(check.round(2).to_string())
print(
    f"scale to the national accounts {scale_national:.3f}, to the municipal receipts {scale_municipal:.3f} "
    f"({100 * (scale_municipal / scale_national - 1):+.0f}%)"
)
tab = vacancy.table(supply.read_stock())
excess = vacancy.excess(tab["vacant_2021_n"], tab["dwellings_2021_n"])
rows = {}
for share in (0.25, 0.5, 1.0):
    rows[share] = {
        "model_national_scale_eur_m": revenue.vacant_surcharge(
            modelled, excess, share, scale_national
        ).sum()
        / 1e6,
        "model_municipal_scale_eur_m": revenue.vacant_surcharge(
            modelled, excess, share, scale_municipal
        ).sum()
        / 1e6,
        "actual_per_dwelling_eur_m": revenue.vacant_surcharge(actual, excess, share).sum() / 1e6,
    }
sur = pd.DataFrame(rows).T.rename_axis("classified_vacant_share")
style.save_table(sur.round(1).reset_index(), "p3", "municipal_surcharge_check")
style.save_table(
    check.round(3).rename("value").rename_axis("measure").reset_index(),
    "p3",
    "municipal_bottom_up_check",
)
print(sur.round(0).to_string())

# %%
fig = charts.municipal_revenue(
    by.loc["density_class"].reindex(["urban", "intermediate", "rural"]),
    actual,
    modelled,
    check["rank_correlation"],
)
style.save_fig(fig, "p3", "municipal_tax_revenue")
fig

# %% [markdown]
# ## Findings
#
# 1. **IMI and IMT are a third of what councils collect, and half of it where the homes are (RQ7.1).** In 2021-2023 IMI plus IMT were
#    34.0%, 33.6% and 31.9% of the current receipts of all councils (1,480 + 1,345 million euros of 8,307 in 2021, 1,504 + 1,715 of 10,088 in
#    2023; the share falls because other receipts grew faster); the median council draws 15.6% (16.9% in 2021). In 2023 the median is 33.0% in
#    urban municipalities (IMI 17.1, IMT 13.3), 23.0% in intermediate and 10.7% in rural ones, 32.3% on the coast against 12.8% inland and
#    41.1% in tourist municipalities (IMT 22.5). 35% of councils draw more than a fifth of current receipts from the two taxes; the highest are
#    Portimao (69%), Loule (68%), Grandola (66%), Cascais (61%) and Lagos (61%), IMT above all (44% to 58% of receipts).
# 2. **The room to cut IMI inside the law is small in total and large in a few places (RQ7.2, RQ7.3).** Cutting every urban rate to the
#    0.30% floor would give up 124 to 139 million euros a year (8.5% to 9.5% of municipal IMI, with the rate of the year of the bill or of
#    the year before), in line with the 8% and 147 million of `p3_05`; 180 to 190 of about 297 councils are already at the floor. The cost is
#    under 1% of current receipts for 200 councils and above for 97 (up to 10.4%): Vila Nova de Gaia 9.0 million (4.9% of its receipts),
#    Mafra 6.6 (7.6%), Cascais 5.8 (1.9%), Portimao 5.5 (6.3%). The euros sit on the coast (61% of the room) and in urban and
#    intermediate councils (47% and 41%), but the 97 councils for which it exceeds 1% of their receipts are spread out (56 inland, 39
#    rural, 34 coastal, 7 on the estuaries). By the reading rule the cost is small for two councils in three, not for the rest.
# 3. **IMT grew far more than the room to cut IMI.** Between 2021 and 2023 IMT rose 369 million euros (+27.5%), 2.7 times the national
#    room of Step 2 and more than the council's own room in 65% of councils; 84% of councils gained, the median by 32.6% (1.6% of its
#    2021 current receipts), Portimao by 185%, Funchal 159%, Cascais 32%, Lisboa 16%. The largest rises are in coastal and tourist
#    councils (the Algarve, Cascais, Funchal), the ones that depend most on IMT. A cut costs a council what it collects, while the rise
#    came with prices and sales (RQ7.3 stays partly open: the response of transactions to a cut is not estimated).
# 4. **The bottom-up IMI of `p3_08` holds up (RQ7.6).** Its rank correlation with the actual IMI per dwelling is 0.88 (292 municipalities;
#    log correlation 0.88), above the reading rule's 0.8; the actual is 0.83 of the model in the median municipality (0.60 to 1.25 from the
#    10th to the 90th percentile). Scaled to the municipal receipts instead of the national accounts (which include the State's AIMI) the
#    factor is 0.702 instead of 0.777, 10% lower, so the revenue of a tripled IMI on excess vacant homes is 50 to 198 million euros (model,
#    municipal scale) and 51 to 203 (actual IMI per dwelling) for a quarter to all classified as vacant, against 55 to 220 in `p3_08`: the
#    range of `p3_08` was about 8% to 10% high, an upper bound as stated, with the same order across municipalities.
#
# **Limits.** Three years (2021-2023), one of them (2021) before the sales rise; receipts as published, basis not stated, and the data
# say nothing about which part of IMT is housing; IMI per dwelling includes commercial and rustic property (over the census stock of
# dwellings), so it overstates the bill of a home; the floor room is accounting with the base held fixed, the rate of the year of the
# bill is inferred (IMI is paid the year after the tax year) and councils with parish-specific rates have no row; Penedono is not in
# the source; the cost to a council is not compared with its budget balance, debt or transfers; no estimate of what a cut would do to
# prices or sales.
