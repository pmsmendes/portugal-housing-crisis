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
# # P2.10 — Big municipalities and their surroundings
#
# **Question:** RQ4.3 (are prices rising faster in major urban centres than in the municipalities around them?). `p2_01` found
# no outlier in the *change* in price-to-income against neighbours; here the question is asked directly on price growth.
#
# A centre is a municipality with at least 100,000 residents in 2021 (a size rule: it takes the two metropolitan cores and
# also their large suburbs). Distance is the number of border steps to the nearest centre. The first comparison is by
# distance from a centre; the second is only the two cores, Lisboa and Porto, against the rest of their metropolitan areas.
# Changes are 2016 to 2024 (the year the income data end), in real terms.

# %%
import pandas as pd

from pthousing.analysis import centres, descriptive, spatial
from pthousing.data import build_panel, harmonize, interim
from pthousing.viz import charts, style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
geo = interim.read("caop_municipalities")
cw = harmonize.read_crosswalk().set_index("muni_code")
names = geo.set_index("muni_code")["muni_name"]
w = spatial.build_weights(geo, "queen")

population = panel.query("year == 2021").set_index("muni_code")["population_n"]
big = centres.find_centres(population)
steps = centres.steps_from_centre(w, big)
print(f"{len(big)} centres: {', '.join(names[c] for c in big)}")
print(steps.value_counts(dropna=False).sort_index().to_string())

# %% [markdown]
# ## Step 1 — Price growth by distance from a centre

# %%
outcomes = {
    "price": descriptive.change(panel, "price_sqm_eur_real", 2016, 2024, "pct"),
    "income": descriptive.change(panel, "income_median_eur_real", 2016, 2024, "pct"),
    "pti": descriptive.change(panel, "pti_years", 2016, 2024, "pct"),
}
grad = centres.gradient(outcomes, steps)
style.save_table(grad.round(1).reset_index(), "p2", "centre_gradient")
grad["median"].unstack("outcome").round(1).join(
    grad.xs("price", level="outcome")["municipalities_n"].rename("n")
)

# %% [markdown]
# ## Step 2 — The same, with region effects
# The gradient could be regional (the big centres are on the coast near Lisboa and Porto). With NUTS 3 fixed effects the contrast
# is between a centre and the municipalities near it in the same region; it uses only regions with a centre.

# %%
region = cw["nuts3_name_2024"]
within = centres.gradient_within_regions(outcomes["price"], steps, region)
style.save_table(within.round(3).reset_index(), "p2", "centre_gradient_within_regions")
within_pti = centres.gradient_within_regions(outcomes["pti"], steps, region)
style.save_table(within_pti.round(3).reset_index(), "p2", "centre_gradient_within_regions_pti")
print("price:\n", within.round(2).to_string(), "\npti:\n", within_pti.round(2).to_string())

# %% [markdown]
# ## Step 3 — The two cores against their metropolitan areas
# Lisboa and Porto against the other municipalities of the metropolitan area (Grande Lisboa and Península de Setúbal; Área
# Metropolitana do Porto), 2016 to 2024.

# %%
metro = region.map(
    {
        "Grande Lisboa": "Lisbon area",
        "Península de Setúbal": "Lisbon area",
        "Área Metropolitana do Porto": "Porto area",
    }
)
cores = [c for c, n in names.items() if n in ("Lisboa", "Porto")]
core_tbl = pd.concat(
    {k: centres.core_vs_rest(v, cores, metro) for k, v in outcomes.items()}, names=["outcome"]
)
style.save_table(core_tbl.reset_index(), "p2", "core_vs_metro")
fig = charts.centres_and_surroundings(grad, core_tbl, names)
style.save_fig(fig, "p2", "centres_and_surroundings")
core_tbl

# %% [markdown]
# ## Key numbers

# %%
g = grad.xs("price", level="outcome")
print("price change by steps:", g["median"].round(0).to_dict(), g["municipalities_n"].to_dict())
print("pti change by steps:", grad.xs("pti", level="outcome")["median"].round(0).to_dict())
print("income change by steps:", grad.xs("income", level="outcome")["median"].round(0).to_dict())
for name, tbl in (("price", within), ("pti", within_pti)):
    print(
        name,
        {
            int(k): f"{r.diff_log_points:+.0f} [{r.ci_low:+.0f}, {r.ci_high:+.0f}]"
            for k, r in tbl.iterrows()
        },
        f"{int(tbl['regions_with_centre_n'].iloc[0])} regions with a centre",
    )
