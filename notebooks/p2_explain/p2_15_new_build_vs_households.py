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
# # P2.15 — New dwellings against households, by size
#
# **Question:** RQ2.6 (how has new-build supply compared with demand for different property types?). Companion of `p2_05` (supply
# against households in total).
#
# Supply is completed family dwellings by number of bedrooms (INE: T0-T1, T2, T3, T4 or more); demand is private households by
# number of persons (census 2011 and 2021). The two are paired one to one (T0-T1 with 1 person, T2 with 2, T3 with 3, T4+ with 4 or
# more). That is a nominal pairing, not a rule: a couple can live in a T3 and a family can share a T2. So this compares two mixes, not
# a count of homes missing, and only flows: the stock of dwellings by number of rooms is not in the data, so who lives in what is not
# observed. Municipal values are 2011-2021 sums of completions against the two censuses.

# %%
import numpy as np
import pandas as pd
from scipy import stats

from pthousing.analysis import housing_mix
from pthousing.config import PROCESSED
from pthousing.data import interim, typology
from pthousing.viz import charts, style

style.apply_style()
households = interim.read("ine_households_size")
construction = interim.read("ine_construction")
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")

# %% [markdown]
# ## Step 1 — The national mix
# Households grew only at the small end. Completions between the censuses were mostly T3 and larger.

# %%
comparison = housing_mix.national_comparison(households, construction)
small_share = housing_mix.small_share_by_year(construction)
small_households = {
    year: 100
    * households[(households["census_year"] == year) & households["size"].isin(housing_mix.SMALL)][
        "households_n"
    ].sum()
    / households.loc[households["census_year"] == year, "households_n"].sum()
    for year in (2011, 2021)
}
fig = charts.new_build_vs_households(comparison, small_share, small_households)
style.save_fig(fig, "p2", "new_build_vs_households")
style.save_table(comparison.round(1).reset_index(), "p2", "households_and_completions_by_size")
comparison.round(1)

# %% [markdown]
# ## Step 2 — Completions by size over thirty years
# The small share of completions fell from 44% in 1995 to a low of 27% in 2017 and has been rising since, to 45% in 2025: the mix is
# now moving the way households did.

# %%
by_size = construction[construction["size"].isin(housing_mix.SIZE_PAIRS)]
shares = (
    by_size.groupby(["year", "size"])["completed_n"]
    .sum()
    .unstack("size")
    .pipe(lambda t: 100 * t.div(t.sum(axis=1), axis=0))
)
style.save_table(shares.round(1).reset_index(), "p2", "completion_shares_by_bedrooms")
shares.loc[[1995, 2000, 2005, 2010, 2015, 2020, 2025]].round(1)

# %% [markdown]
# ## Step 3 — Where does new building lag households most?
# Per municipality, `small_gap_pp` is the share of 2021 households with one or two persons minus the share of 2011-2021 completions
# with up to two bedrooms (municipalities with fewer than 50 completions are left out). By density class, and against prices.

# %%
gap = housing_mix.small_dwelling_gap(households, construction).merge(
    typology.read()[["muni_code", "density_class", "coast_class", "tourist"]], on="muni_code"
)
latest, before = (
    panel[panel["year"] == 2024].set_index("muni_code"),
    panel[panel["year"] == 2019].set_index("muni_code"),
)
gap["pti_years_2024"] = gap["muni_code"].map(latest["pti_years"])
gap["real_price_change_2019_2024_pct"] = gap["muni_code"].map(
    100 * np.log(latest["price_sqm_eur_real"] / before["price_sqm_eur_real"])
)
order = pd.CategoricalDtype(["urban", "intermediate", "rural"], ordered=True)
by_density = (
    gap.assign(density_class=gap["density_class"].astype(order))
    .groupby("density_class", observed=True)[
        ["small_households_pct", "small_completions_pct", "small_gap_pp", "pti_years_2024"]
    ]
    .median()
)
by_density["municipalities_n"] = gap.groupby("density_class")["small_gap_pp"].count()
style.save_table(by_density.round(1).reset_index(), "p2", "small_dwelling_gap_by_density")
by_density.round(1)

# %%
rows = {}
for col in ("pti_years_2024", "real_price_change_2019_2024_pct"):
    d = gap[["small_gap_pp", col]].dropna()
    rho, p = stats.spearmanr(d["small_gap_pp"], d[col])
    rows[col] = {"spearman_rho": rho, "p_value": p, "n": len(d)}
assoc = pd.DataFrame(rows).T
gap["gap_tercile"] = pd.qcut(
    gap["small_gap_pp"], 3, labels=["smallest gap", "middle", "largest gap"]
)
terciles = gap.groupby("gap_tercile", observed=True)[
    [
        "small_gap_pp",
        "small_households_pct",
        "small_completions_pct",
        "pti_years_2024",
        "real_price_change_2019_2024_pct",
    ]
].median()
terciles["urban_n"] = (
    gap[gap["density_class"] == "urban"].groupby("gap_tercile", observed=True)["muni_code"].count()
)
style.save_table(
    assoc.round(3).reset_index(names="outcome"), "p2", "small_dwelling_gap_association"
)
style.save_table(terciles.round(1).reset_index(), "p2", "small_dwelling_gap_terciles")
print(assoc.round(3).to_string())
terciles.round(1)

# %% [markdown]
# ## Key numbers

# %%
c = comparison
print(
    f"households 2011-2021: 1 person {c.loc['1', 'households_change_n']:+,.0f}, 2 persons {c.loc['2', 'households_change_n']:+,.0f}, "
    f"3 persons {c.loc['3', 'households_change_n']:+,.0f}, 4+ {c.loc['4plus', 'households_change_n']:+,.0f}; "
    f"one- and two-person share {small_households[2011]:.1f}% -> {small_households[2021]:.1f}%"
)
print(
    f"completions 2011-2021 (T0-T1, T2, T3, T4+): {', '.join(f'{v:,.0f} ({s:.0f}%)' for v, s in zip(c['completed_n'], c['completed_share_pct'], strict=True))}; "
    f"up to two bedrooms {c.loc[['1', '2'], 'completed_share_pct'].sum():.0f}% against {small_households[2021]:.0f}% of households"
)
print(
    f"small share of completions: 1995 {small_share.loc[1995]:.0f}%, low {small_share.min():.0f}% ({small_share.idxmin()}), 2021 {small_share.loc[2021]:.0f}%, 2025 {small_share.loc[2025]:.0f}%"
)
print(
    f"municipal gap (n {gap['small_gap_pp'].count()}): median {gap['small_gap_pp'].median():.0f} pp, positive in {100 * (gap['small_gap_pp'] > 0).sum() / gap['small_gap_pp'].count():.0f}%"
)
for name, r in by_density.iterrows():
    print(
        f"  {name}: households {r.small_households_pct:.0f}%, completions {r.small_completions_pct:.0f}%, gap {r.small_gap_pp:.0f} pp, price-to-income {r.pti_years_2024:.1f}, n {int(r.municipalities_n)}"
    )
for name, r in assoc.iterrows():
    print(f"  Spearman gap vs {name}: {r.spearman_rho:+.2f} (p {r.p_value:.3f}, n {int(r.n)})")
