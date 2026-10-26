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
# # P3.09 — Targeted exemptions against broad cuts
#
# **Question:** RQ7.5 (how do targeted exemptions for first-time buyers, new build and renovation compare with broad cuts?).
# Builds on `p3_05` (room for tax cuts), `p4_02` (the simulator) and `p4_07` (the scorecard).
#
# **What the data allow.** Three exemptions are sized: the IMT and stamp-duty exemption for young first-time buyers (observed cost
# and buyers, from press reports of the 2025 state accounts), an IMT exemption on the first sale of new dwellings (completions times
# the IMT of a new home) and an IMI exemption for renovated dwellings (buildings with works, `p2_19`, times the IMI of a dwelling and
# the years of exemption). Each is compared with the broad cut of one point of the price.
#
# **What the simulator can say.** Its price channel is a national average rate, so an exemption enters as the average cut that costs the
# same revenue. Per euro of revenue forgone, the price effect is then the same for a broad cut and a targeted exemption, bounded by
# no capitalisation (0) and full capitalisation (1). Targeting changes who gets the money and whether it can create homes; that
# second channel is not estimated, so the notebook solves for the **break-even**: the extra homes a year an exemption would have to
# cause for the 2035 price-to-income not to rise, and what each costs. Accounting and bounds, not a forecast; no behavioural
# response of buyers, builders or owners is estimated.
#
# **Reading rule, fixed before looking:** an exemption "pays for itself in affordability" only if the extra homes it would have to
# cause per home exempted are within what an exemption can plausibly do. No estimate of that share exists in the project, so the
# comparison is with the cost per additional home of a direct construction subsidy at the simulator's mid values.

# %%
import numpy as np
import pandas as pd

from pthousing.data import build_panel, interim
from pthousing.simulation import engine as E
from pthousing.simulation import exemptions as X
from pthousing.viz import charts, style

style.apply_style()
A, anc = E.load_inputs()
EX = X.load()
SCENARIO = "baseline"
panel = build_panel.read("panel_municipality_year")
stock = pd.read_parquet("../../data/interim/ine_census_stock.parquet")

# %% [markdown]
# ## Step 1 — The bases
# Value of dwellings sold in 2024 and the number of sales (panel, benchmark dwelling of 100 m2), IMT collected, completions in the
# start year, the premium of new over existing homes (`p1_08`), buildings with works on existing buildings (`p2_19`), and the IMI of
# an average dwelling (national IMI over the census stock).

# %%
value = anc.transaction_value_eur
sales = float(panel.loc[panel["year"] == 2024, "sales_12m_n"].sum())
imt = A.fiscal["imt_revenue_eur"]
imi = A.fiscal["imi_revenue_eur"]
imt_rate = X.average_imt_rate_pct(imt, value)
premium = float(
    pd.read_csv("../../reports/tables/p1/new_vs_existing.csv")
    .set_index("year")
    .loc[2025, "median_premium_pct"]
)
works = pd.read_csv("../../reports/tables/p2/renovation_national.csv").set_index("year")
buildings = float(works.loc[2015:2024, "completed_alteration_n"].mean())
dwellings_2021 = float(stock.loc[stock["census_year"] == 2021, "dwellings_n"].sum())
imi_per_dwelling = imi / dwellings_2021
sales_2025 = float(
    interim.read("ine_median_price_sqm")
    .query("category == 'total' and year == 2025 and quarter == 4")["sales_12m_n"]
    .sum()
)
bases = pd.Series(
    {
        "sales_value_bn_eur": value / 1e9,
        "sales_n_2024": sales,
        "value_per_sale_eur": value / sales,
        "imt_revenue_eur_m": imt / 1e6,
        "imt_over_sales_value_pct": imt_rate,
        "imi_revenue_eur_m": imi / 1e6,
        "imi_average_rate_pct": anc.imi_average_rate_pct,
        "completions_2025_n": anc.completions,
        "new_premium_2025_pct": premium,
        "renovation_buildings_a_year_2015_24": buildings,
        "imi_per_dwelling_eur": imi_per_dwelling,
        "sales_n_4q2025": sales_2025,
    }
)
style.save_table(
    bases.round(2).rename("value").rename_axis("base").reset_index(), "p3", "exemption_bases"
)
bases.round(2)

# %% [markdown]
# ## Step 2 — What each exemption costs
# Per year, in steady state, at the mid values of the assumed ranges (new homes sold 80% of completions; 3 dwellings per renovated
# building; three years of exemption).

# %%
ftb, nb, rn = EX["first_time_buyers"], EX["new_build"], EX["renovation"]


def new_build(share):
    return X.new_build_exemption(anc.completions, share, value / sales, premium, imt_rate)


def renovation(per_building):
    return X.renovation_exemption(buildings, per_building, rn["exemption_years"], imi_per_dwelling)


options = {
    "Broad IMT cut, 1 pp of the price": {
        "tax": "IMT",
        "homes_n": sales,
        "cost_eur": 0.01 * value,
    },
    "First-time buyers (IMT Jovem, as in force)": {
        "tax": "IMT",
        "homes_n": ftb["buyers_per_year"],
        "cost_eur": ftb["cost_eur"],
    },
    "New homes exempt from IMT": {"tax": "IMT", **new_build(nb["sold_share_of_completions"].mid)},
    "Renovated homes exempt from IMI": {
        "tax": "IMI",
        **renovation(rn["dwellings_per_building"].mid),
    },
}
rows = {}
for name, o in options.items():
    base_tax = imt if o["tax"] == "IMT" else imi
    rows[name] = {
        "tax": o["tax"],
        "homes_reached_n": o["homes_n"],
        "per_home_eur": o["cost_eur"] / o["homes_n"],
        "cost_eur_m": o["cost_eur"] / 1e6,
        "share_of_tax_pct": 100 * o["cost_eur"] / base_tax,
        "equivalent_cut_pp": X.equivalent_imt_cut_pp(o["cost_eur"], value)
        if o["tax"] == "IMT"
        else X.equivalent_imi_cut_pp(o["cost_eur"], imi, anc.imi_average_rate_pct),
    }
cost = pd.DataFrame(rows).T
cost["homes_per_eur_m"] = cost["homes_reached_n"] / cost["cost_eur_m"]
for c in cost.columns.drop("tax"):
    cost[c] = cost[c].astype(float)
style.save_table(cost.round(2).reset_index(names="option"), "p3", "exemption_costs")
cost.round(2)

# %% [markdown]
# ## Step 3 — Price-to-income in 2035 and the homes needed to break even
# For each exemption: the change of the 2035 median price-to-income (baseline scenario, years of income; positive is worse) at no
# capitalisation, at the simulator's mid and at full capitalisation, then the extra homes a year that bring the full-capitalisation
# rise to zero (`break_even_homes`), as a share of the homes exempted and the revenue forgone per extra home. The comparison cost
# is a direct construction subsidy at mid values: 25,000 EUR per supported unit over 0.75 additionality.

# %%
direct = (
    A.ranges["construction_boost.cost_per_unit_eur"].mid
    / A.ranges["construction_boost.additionality"].mid
)


def evaluate(row):
    kw = (
        {"imt_cut_pp": row["equivalent_cut_pp"]}
        if row["tax"] == "IMT"
        else {"imi_cut_pp": row["equivalent_cut_pp"]}
    )
    out = {
        f"pti_change_cap{int(100 * c)}": X.tax_price_effect(
            A, anc, SCENARIO, capitalisation=c, **kw
        )
        for c in (0, 0.5, 1)
    }
    homes = X.break_even_homes(A, anc, SCENARIO, capitalisation=1.0, **kw)
    out["break_even_homes_n"] = homes
    out["break_even_pct_of_homes_reached"] = 100 * homes / row["homes_reached_n"]
    out["forgone_per_extra_home_eur"] = row["cost_eur_m"] * 1e6 / homes
    return pd.Series(out)


effects = cost.apply(evaluate, axis=1)
effects["direct_subsidy_per_extra_home_eur"] = direct
effects["homes_to_match_direct_pct"] = (
    100 * (cost["cost_eur_m"] * 1e6 / direct) / cost["homes_reached_n"]
)
score = cost.join(effects)
style.save_table(score.round(3).reset_index(names="option"), "p3", "exemption_scorecard")
print(
    score[
        [
            "cost_eur_m",
            "equivalent_cut_pp",
            "pti_change_cap0",
            "pti_change_cap50",
            "pti_change_cap100",
        ]
    ]
    .round(3)
    .to_string()
)
print(
    score[
        [
            "break_even_homes_n",
            "break_even_pct_of_homes_reached",
            "forgone_per_extra_home_eur",
            "direct_subsidy_per_extra_home_eur",
        ]
    ]
    .round(0)
    .to_string()
)

# %% [markdown]
# ## Step 4 — What a supply response could be: an illustration, not an estimate
# `p2_17` found that completions follow the real price (3.0 log points per log point a year later, 2.1 to 4.0, an association between
# yearly changes over two cycles). Treat it as the response of builders to the price they receive and ask how many extra homes a year
# each exemption would then bring if its saving were capitalised in full. For the new-build exemption the saving is a rise of the
# price of new homes by the IMT of a new home; for the broad cut and the youth exemption it is a rise of all prices by the cut
# (applied to completions). There is no estimate for renovation. This is an upper-bound illustration: the coefficient is not causal,
# builders do not receive the whole capitalised saving, and the 3.0 comes from two cycles of a national series.

# %%
resp = pd.read_csv("../../reports/tables/p2/construction_supply_response.csv")
resp = resp[
    (resp["term"] == "dlog_price")
    & (resp["outcome"] == "completed_n")
    & (resp["lag_years"] == 1)
    & (resp["sample"] == "all years")
].iloc[0]
new_price = value / sales * (1 + premium / 100)
rise = pd.Series(
    {
        "Broad IMT cut, 1 pp of the price": score.loc[
            "Broad IMT cut, 1 pp of the price", "equivalent_cut_pp"
        ],
        "First-time buyers (IMT Jovem, as in force)": score.loc[
            "First-time buyers (IMT Jovem, as in force)", "equivalent_cut_pp"
        ],
        "New homes exempt from IMT": 100
        * score.loc["New homes exempt from IMT", "per_home_eur"]
        / new_price,
    }
)
for tag, coef in (("", resp["coef"]), ("_low", resp["ci_low"]), ("_high", resp["ci_high"])):
    score[f"association_extra_homes{tag}_n"] = [
        X.extra_homes_from_price(coef, rise[o], anc.completions) if o in rise else np.nan
        for o in score.index
    ]
score["association_over_break_even"] = (
    score["association_extra_homes_n"] / score["break_even_homes_n"]
)
score["forgone_per_extra_home_association_eur"] = (
    score["cost_eur_m"] * 1e6 / score["association_extra_homes_n"]
)
score["price_rise_builders_pct"] = rise.reindex(score.index)
style.save_table(score.round(3).reset_index(names="option"), "p3", "exemption_scorecard")
print(f"coefficient {resp['coef']:.2f} ({resp['ci_low']:.2f} to {resp['ci_high']:.2f})")
print(
    score[
        [
            "price_rise_builders_pct",
            "association_extra_homes_low_n",
            "association_extra_homes_n",
            "association_extra_homes_high_n",
            "break_even_homes_n",
            "association_over_break_even",
            "forgone_per_extra_home_association_eur",
        ]
    ]
    .round(2)
    .to_string()
)

# %%
fig = charts.exemptions(score)
style.save_fig(fig, "p3", "targeted_exemptions")
fig

# %% [markdown]
# ## Step 5 — Sensitivity to the assumed ranges
# The new-build exemption over the share of completions that are sold, the renovation exemption over dwellings per building and years
# of exemption, and the first-time buyers' cost against the ministry's earlier estimate of 50 million EUR a year.

# %%
rows = []
for label, share in (
    ("low", nb["sold_share_of_completions"].low),
    ("mid", nb["sold_share_of_completions"].mid),
    ("high", nb["sold_share_of_completions"].high),
):
    o = new_build(share)
    rows.append(
        (
            "New homes exempt from IMT",
            f"sold share {share:.1f} ({label})",
            o["homes_n"],
            o["cost_eur"],
        )
    )
for label in ("low", "mid", "high"):
    for years in (3, 8):
        o = X.renovation_exemption(
            buildings, rn["dwellings_per_building"].at(label), years, imi_per_dwelling
        )
        rows.append(
            (
                "Renovated homes exempt from IMI",
                f"{rn['dwellings_per_building'].at(label):.0f} homes a building, {years} years",
                o["homes_n"],
                o["cost_eur"],
            )
        )
sens = pd.DataFrame(rows, columns=["option", "case", "homes_reached_n", "cost_eur"])
sens["cost_eur_m"] = sens["cost_eur"] / 1e6
sens["share_of_tax_pct"] = (
    100 * sens["cost_eur"] / sens["option"].map(lambda o: imt if "IMT" in o else imi)
)
sens = sens.drop(columns="cost_eur")
style.save_table(sens.round(2), "p3", "exemption_sensitivity")
sens.round(2)

# %% [markdown]
# ## Step 6 — Who gets the money
# The first-time-buyer exemption per beneficiary against the price and the deposit of a typical purchase, and what reaches the buyer
# if the saving is capitalised into the price.

# %%
typical = value / sales
per_buyer = ftb["cost_eur"] / ftb["buyers_per_year"]
deposit = (1 - 0.8) * typical  # MORTGAGE_LTV in config.py is 0.80
who = pd.DataFrame(
    {
        "per_buyer_eur": [per_buyer],
        "typical_price_eur": [typical],
        "share_of_price_pct": [100 * per_buyer / typical],
        "share_of_deposit_pct": [100 * per_buyer / deposit],
        "buyers_share_of_sales_pct": [100 * ftb["buyers_per_year"] / sales_2025],
        "kept_by_buyer_at_cap0_eur": [per_buyer],
        "kept_by_buyer_at_cap50_eur": [0.5 * per_buyer],
        "kept_by_buyer_at_cap100_eur": [0.0],
    }
)
style.save_table(who.round(1), "p3", "exemption_first_time_buyers")
who.round(1).T

# %% [markdown]
# ## Findings
#
# 1. **The exemptions cost very different amounts (RQ7.5).** Per year: the broad cut of one point of the price 294 EUR m (17% of IMT,
#    1,942 EUR per sale, 151,593 sales); the youth exemption as in force 146 EUR m (8.4% of IMT) for 60,000 buyers, 36% of the 164,631
#    sales of 4Q2025, 2,427 EUR each; an IMT exemption on new homes 280 EUR m (16% of IMT; 210 to 350 over the share of completions
#    sold) for about 21,800 homes at 12,835 EUR each; an IMI exemption for renovated homes 5.5 EUR m (0.3% of IMI; 1.8 to 49 EUR m
#    over the ranges) for 6,700 homes at 819 EUR each over three years.
# 2. **In the simulator an exemption raises price-to-income exactly as much as a broad cut that costs the same.** Fully capitalised, the
#    2035 median ratio of the baseline (a 4.6-year rise) is 0.15 years higher with the broad cut (3%), 0.075 with the youth exemption,
#    0.145 with the new-home exemption and 0.003 with the renovation exemption; half that at the midpoint of the bound, nothing without
#    capitalisation. This is by construction (the price channel is an average rate), not a finding about targeting.
# 3. **What targeting could change is who gets the money.** A youth buyer saves 2,427 EUR, 1.2% of a typical 194,000 EUR price and 6.2%
#    of the 20% deposit; at full capitalisation none of it stays with the buyer, at half 1,213 EUR.
# 4. **To break even in affordability, an exemption must cause extra homes: about 70,000 EUR of revenue forgone per extra home at full
#    capitalisation.** 4,183 extra homes a year for the broad cut (2.8% of the homes it reaches), 2,074 for the youth exemption, 3,985
#    for new homes (18% of the homes exempted), 85 for renovation (1.3%). A direct construction subsidy at mid values costs 33,333 EUR
#    per extra home, so to match it the new-home exemption would have to cause one extra home per 39% of the homes it exempts, the
#    renovation exemption per 2.5%.
# 5. **The one exemption near break-even is the one aimed at new homes, under an illustration, not an estimate.** Applying the `p2_17`
#    association (3.0 log points of completions per log point of the price a year later, 2.1 to 4.0) to the 5.9% rise of the price of
#    new homes gives 4,880 extra homes a year (3,338 to 6,424), 1.2 times the break-even (0.8 to 1.6) and 57,000 EUR forgone per extra home,
#    against 355,000 for the broad cut and the youth exemption (0.2 times the break-even). So under this illustration the new-home exemption
#    could offset its own price effect and still be dearer per extra home than the direct subsidy.
# 6. **The renovation exemption is too small to matter for the aggregate:** 0.3% of IMI, 85 extra homes pay for it, but the project has no
#    estimate of the response and `p2_19` shows renovation flat near 3,800 buildings a year; the lever of value in renovation is the cost of the
#    works, which an IMI exemption does not touch.
#
# **Limits.** Assumed: the shares of completions sold, dwellings per renovated building, three years of exemption (ranges in
# `config/scenarios.yaml`). The youth exemption's cost and buyers are press reports of the 2025 state accounts, not checked against them.
# IMT revenue over sales value (5.9%) covers other properties and stamp duty, so the IMT of a new home is an upper bound; the schedule is
# progressive. The revenue is municipal. The simulator has one national price: an exemption on a segment is its average-rate equivalent.
# The supply illustration uses a national association of two cycles, not an elasticity. Eligibility rules, take-up beyond the observed
# one, fraud, price ceilings of the youth exemption and any exemption on rented homes are not modelled.
