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
# # P2.07 — Synthesis: how much does each explanation account for?
#
# **Questions:** RQ3.6 (do demand changes explain regional differences in price growth?) and RQ5.4 (can the drivers
# be separated?), with one view across the whole phase.
#
# P2.01 to P2.06 each tested one explanation. Here they enter **one cross-section** of the mainland municipalities,
# outcome the log change of price-to-income 2016 to 2024, in blocks:
# * **Geography:** district, coast class, density class (P2.04);
# * **Demand:** foreign residents and other population change 2016 to 2023 (% of the 2016 population, P2.02) and
#   household growth 2011 to 2021 (P2.05);
# * **Supply:** dwelling growth 2011 to 2021 (P2.05) and completions 2017 to 2023 per 1,000 dwellings (P2.02);
# * **Tourism:** registered short-term rentals per 1,000 dwellings (P2.02);
# * **Second homes:** secondary-residence share 2021 (P2.06).
#
# The question is how much of the variation across municipalities each block accounts for, not a causal ranking:
# blocks overlap (dense coastal places also gain foreign residents) and the order they are added in matters, so
# the ladder is also run in the reverse order.

# %%
import numpy as np
import pandas as pd

from pthousing.analysis import descriptive as desc
from pthousing.analysis import supply
from pthousing.data import build_panel, typology
from pthousing.viz import charts, style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
stock = supply.read_stock()
ty = typology.read().set_index("muni_code")
frame = supply.synthesis_frame(panel, stock, ty)
print(frame.shape, frame["dlog_pti"].notna().sum(), "with an outcome")
print(frame.describe().round(2).T.to_string())

# %% [markdown]
# ## Step 1 — Variance explained, block by block

# %%
GEO = ["C(district)", "C(coast_class)", "C(density_class)"]
DEMAND = ["foreign_change_pct", "other_pop_change_pct", "households_change_pct"]
SUPPLY = ["dwellings_change_pct", "completions_per_1000"]
TOURISM = ["rentals_per_1000"]
SECOND = ["secondary_2021_pct"]
BLOCKS = {
    "Geography (district, coast, density)": GEO,
    "Demand (foreign residents, population, households)": DEMAND,
    "Supply (dwellings, completions)": SUPPLY,
    "Tourism (short-term rentals)": TOURISM,
    "Second homes": SECOND,
}
ladder = desc.block_r2(frame, "dlog_pti", BLOCKS)
style.save_table(ladder, "p2", "synthesis_r2_ladder")
print(ladder.round(3).to_string(index=False))
fig = charts.r2_ladder(ladder, "price-to-income")
style.save_fig(fig, "p2", "synthesis_r2_ladder")
fig

# %% [markdown]
# **Finer geography and the reverse order.** District alone, then the classes; and the drivers first, geography last.

# %%
fine = desc.block_r2(
    frame,
    "dlog_pti",
    {"District": ["C(district)"], "+ coast and density class": GEO[1:]},
)
reverse = desc.block_r2(
    frame,
    "dlog_pti",
    {
        "Demand": DEMAND, "+ supply": SUPPLY, "+ tourism": TOURISM, "+ second homes": SECOND,
        "+ geography": GEO,
    },
)  # fmt: skip
style.save_table(
    pd.concat([fine.assign(order="geography"), reverse.assign(order="drivers first")]),
    "p2",
    "synthesis_r2_order_check",
)
print(fine.round(3).to_string(index=False))
print(reverse.round(3).to_string(index=False))

# %% [markdown]
# ## Step 2 — What survives in one model? (per standard deviation)
# All drivers together, with district intercepts and then with coast and density class, HC3 errors; the
# coefficient is the % change in price-to-income associated with one standard deviation of the driver.

# %%
drivers = [*DEMAND, *SUPPLY, *TOURISM, *SECOND]
models = pd.concat(
    [
        supply.associations(frame, "dlog_pti", drivers, fixed_effects="district", label="Same district"),
        supply.associations(
            frame, "dlog_pti", drivers, fixed_effects="district",
            categorical=["coast_class", "density_class"], label="Same district, coast and density",
        ),
    ],
    ignore_index=True,
)  # fmt: skip
models["pct_per_sd"] = 100 * np.expm1(models["coef_per_sd"])
style.save_table(models, "p2", "synthesis_joint_model")
print(
    models[["spec", "term", "coef", "p", "pct_per_sd", "n_obs", "r2"]]
    .round(3)
    .to_string(index=False)
)
print(frame[drivers].corr().round(2).to_string())

# %% [markdown]
# ## Findings
#
# 1. **Geography accounts for most of where affordability worsened (RQ3.6).** District, coast class and density
#    class explain 53% of the variation in the change of price-to-income across 271 mainland municipalities
#    (district alone 43%, the classes add 9.7 points). Demand, supply, tourism and second homes added together add
#    1.7 points (0.8, 0.5, 0.1, 0.2); adjusted R2 does not move (49.0% to 49.4%).
# 2. **The drivers are mostly the geography seen another way.** Alone, demand explains 29% and all the drivers 35%,
#    but added after the drivers geography still adds 19.6 points: places that gained foreign residents, households
#    and dwellings are the dense coastal ones, so the two cannot be separated with these data. Demand, supply and
#    second homes are correlated with each other (0.4 to 0.7 for population, households, completions).
# 3. **Within a region nothing stands out in one model.** With district intercepts, one standard deviation of
#    foreign-resident change goes with +5.9% (p = 0.11), dwelling growth with −3.2% (p = 0.09) and second homes with
#    −3.1% (p = 0.14); with coast and density class added all fall to between −2.3% and +3.5% (p ≥ 0.18). Each was
#    significant on its own in P2.02, P2.05 and P2.06: the single-driver results partly measure one another.
#
# **What this does and does not say.** The drivers explain little *beyond where a municipality is*, not that they do
# not matter: a desirable place draws people, foreign residents and construction and sees prices rise, so place
# and driver move together, and 271 municipalities and a single 2016 to 2024 change are too little variation to
# separate them. The panel regressions of P2.02 use changes within a municipality over time and find the same
# order of magnitude (drivers explain 1.6% to 6.8% of the within variation). A causal answer needs a design with a
# credible comparison, which is the aim of phase 3.
