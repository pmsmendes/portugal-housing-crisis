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
# # P2.16 — Vacant dwellings against housing pressure
#
# **Question:** RQ2.5 (how many vacant dwellings could realistically return to residential use?). Companion of `p2_05` (supply
# against households) and `p2_06` (second homes).
#
# The census counts vacant conventional dwellings per municipality (2011, 2021) but not their condition, owner, price or whether they
# are for sale or rent. So "realistically" is bounded by two things the data do show. (1) Only vacancy above a frictional level counts:
# homes between tenants, being sold, inherited or repaired are vacant in any market (assumed 5% of the stock, with 3% and 8% as checks).
# (2) A vacant home cannot be moved: it helps only where households are short. The shortfall of a municipality is its implied new
# households of 2021-2023 minus its completions (the `p2_05` proxy), floored at zero, and what its excess vacancy could house is the
# smaller of the two. How much of the excess is habitable and worth repairing is not in the data, so it is varied, not assumed.

# %%
import pandas as pd
from scipy import stats

from pthousing.analysis import supply, vacancy
from pthousing.config import FRICTIONAL_VACANCY_PCT, PROCESSED
from pthousing.data import typology
from pthousing.viz import charts, style

style.apply_style()
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
stock = supply.read_stock()
ty = typology.read().set_index("muni_code")
bal = supply.balance(panel, stock)
tab = vacancy.table(stock)
short = vacancy.shortfall(bal)
tab["excess_2021_n"] = vacancy.excess(tab["vacant_2021_n"], tab["dwellings_2021_n"])

# %% [markdown]
# ## Step 1 — How many are vacant, and where
# Vacant dwellings barely moved between the censuses, but they left the cities and gathered in the countryside.

# %%
national = pd.DataFrame(
    {
        year: {
            "dwellings_n": tab[f"dwellings_{year}_n"].sum(),
            "vacant_n": tab[f"vacant_{year}_n"].sum(),
        }
        for year in (2011, 2021)
    }
).T
national["vacancy_pct"] = 100 * national["vacant_n"] / national["dwellings_n"]
print(national.round(1).to_string())

by_density = vacancy.by_group(tab, short, ty["density_class"]).loc[
    ["urban", "intermediate", "rural"]
]
by_density["vacant_change_n"] = by_density["vacant_2021_n"] - by_density["vacant_2011_n"]
by_coast = vacancy.by_group(tab, short, ty["coast_class"])
cols = ["vacancy_2011_pct", "vacancy_2021_pct", "vacant_change_n", "excess_n", "shortfall_n"]
style.save_table(by_density[cols].round(1).reset_index(), "p2", "vacancy_by_density")
by_density[cols].round(1)

# %% [markdown]
# ## Step 2 — Is vacancy where prices are high?
# Municipalities in terciles of 2024 price-to-income. Vacancy is highest where prices are lowest: the association is negative.

# %%
pti = panel[panel["year"] == 2024].set_index("muni_code")["pti_years"].dropna()
tercile = pd.qcut(pti, 3, labels=["low", "middle", "high"])
rho, p = stats.spearmanr(tab.loc[pti.index, "vacancy_2021_pct"], pti)
groups = vacancy.by_group(tab.loc[pti.index], short, tercile)
groups["vacancy_change_pp"] = groups["vacancy_2021_pct"] - groups["vacancy_2011_pct"]
gcols = [
    "vacancy_2011_pct",
    "vacancy_2021_pct",
    "vacancy_change_pp",
    "excess_n",
    "shortfall_n",
    "covered_n",
    "coverage_pct",
]
style.save_table(
    groups[gcols].round(1).reset_index(names="price_to_income"), "p2", "vacancy_by_price_pressure"
)
print(f"Spearman, vacancy rate 2021 vs price-to-income 2024: {rho:+.2f} (p {p:.3g}, n {len(pti)})")
groups[gcols].round(1)

# %% [markdown]
# ## Step 3 — Excess vacancy against the shortfall, municipality by municipality
# In total there is more excess vacancy than shortfall, but the largest shortfalls are in the suburbs of Lisboa and Porto, where
# vacancy is lowest. The right panel lists them.

# %%
names = ty["muni_name"]
top = vacancy.largest_shortfalls(tab, short, names)
sens = vacancy.sensitivity(tab, short)
fig = charts.vacancy_vs_shortfall(groups.rename(index={"middle": "mid"}), top, sens)
style.save_fig(fig, "p2", "vacancy_vs_shortfall")
style.save_table(top.round(1).reset_index(), "p2", "vacancy_largest_shortfalls")
top.round(1)

# %% [markdown]
# ## Step 4 — How much would have to be usable?
# Coverage of the shortfall by frictional level and by the share of the excess that is habitable, for sale or let and worth repairing.
# The last column asks the opposite question: the usable share at which local coverage reaches half and three quarters.

# %%
style.save_table(sens.round(2), "p2", "vacancy_sensitivity")
needed = (
    pd.DataFrame(
        {
            pct: {
                target: vacancy.usable_share_for(
                    target,
                    vacancy.excess(tab["vacant_2021_n"], tab["dwellings_2021_n"], pct),
                    short,
                )
                for target in (50, 75)
            }
            for pct in (3.0, 5.0, 8.0)
        }
    )
    .T.rename_axis("frictional_pct")
    .rename(columns=lambda t: f"usable_share_for_{t}pct")
)
style.save_table(needed.round(3).reset_index(), "p2", "vacancy_usable_share_needed")
print(
    sens.pivot(index="frictional_pct", columns="usable_share", values="coverage_pct")
    .round(0)
    .to_string()
)
needed.round(2)

# %% [markdown]
# ## Key numbers

# %%
n = national
print(
    f"vacant dwellings {n.loc[2011, 'vacant_n']:,.0f} ({n.loc[2011, 'vacancy_pct']:.1f}%) -> {n.loc[2021, 'vacant_n']:,.0f} ({n.loc[2021, 'vacancy_pct']:.1f}%)"
)
for name, r in by_density.iterrows():
    print(
        f"  {name}: vacancy {r.vacancy_2011_pct:.1f}% -> {r.vacancy_2021_pct:.1f}%, vacant {r.vacant_change_n:+,.0f}, excess {r.excess_n:,.0f}, shortfall {r.shortfall_n:,.0f}, n {int(r.municipalities_n)}"
    )
default = sens[
    (sens["frictional_pct"] == FRICTIONAL_VACANCY_PCT) & (sens["usable_share"] == 1.0)
].iloc[0]
print(
    f"excess vacancy at {FRICTIONAL_VACANCY_PCT:.0f}%: {default.excess_n:,.0f}; shortfall {default.shortfall_n:,.0f}; "
    f"covered locally {default.covered_n:,.0f} ({default.coverage_pct:.0f}%)"
)
for name, r in groups.iterrows():
    print(
        f"  price-to-income {name}: vacancy {r.vacancy_2021_pct:.1f}% ({r.vacancy_change_pp:+.1f} pp), excess {r.excess_n:,.0f}, shortfall {r.shortfall_n:,.0f}, covered {r.coverage_pct:.0f}%"
    )
print(
    f"municipalities with excess below shortfall: {(tab['excess_2021_n'] < short).sum()} of {short.gt(0).sum()} with a shortfall; "
    f"top ten hold {100 * top['shortfall_n'].sum() / short.sum():.0f}% of the shortfall, covering {100 * (top[['excess_n', 'shortfall_n']].min(axis=1).sum()) / top['shortfall_n'].sum():.0f}% of it"
)
print(
    f"usable share needed (5%): half {needed.loc[5.0].iloc[0]:.2f}, three quarters {needed.loc[5.0].iloc[1]:.2f}"
)
