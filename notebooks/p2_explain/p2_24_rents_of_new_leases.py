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
# # P2.24 — Rents of new leases, 2020-2024: where they rose and what goes with it
#
# **Questions:** RQ3.3 (population growth, immigration and prices *or rents*) and RQ5.1 (short-term rentals and local
# prices *and rents*). `p2_02` and `p2_14` explain price-to-income and said "rents not analysed". INE publishes the median
# rent per m2 of new leases for 2020-2024 wherever enough leases were signed (191 municipalities with a value in both
# years), which is enough for one cross-section of changes.
#
# **Method.** The log change of the real rent per m2 2020-2024 (`analysis/rents.py`), set against the change of the
# foreign-resident share (2020-2023, the register ends in 2023), population change (same years), dwellings completed
# 2021-2024 per 1,000 dwellings, and registered short-term rentals per 1,000 dwellings, with the starting rent to separate
# catching up from the rest. Mainland municipalities, same-district comparisons, HC3 errors (`supply.associations`). The
# same specifications are then run on the real *price* change in the same municipalities, to see whether rents and prices
# go with the same things.
#
# **Reading rule, fixed before looking:** a driver "matters" for rents if its coefficient keeps its sign and is below
# p = 0.05 in the joint specification both within district and with coast and density added. The sample is the places where
# rents are published (larger, more urban, 94% of residents) and the window is four years, so a null is not evidence of no
# effect. The registry of short-term rentals is today's survivors, not the 2020 stock. Associations, not effects.

# %%
import numpy as np
import pandas as pd

from pthousing.analysis import rents, supply
from pthousing.data import build_panel, typology
from pthousing.viz import charts, style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
ty = typology.read().set_index("muni_code")
ty["coast"] = ty["coast_class"].replace({"estuary": "coast"})
ty["segment"] = ty["coast"] + " / " + ty["density_class"]
frame = rents.change_frame(panel, 2020, 2024)
frame = frame.join(ty[["segment", "coast", "density_class", "territory"]])
frame["district"] = supply.area_of(panel)
main = frame[frame["territory"] == "continente"]
pct = lambda x: 100 * (np.exp(x) - 1)  # noqa: E731  (log points to per cent)

# %% [markdown]
# ## Step 1 — The sample and the national picture
# Municipalities with a rent in 2020 and in 2024, and what rents and prices did in them.

# %%
both = frame.dropna(subset=["dlog_price"])
national = pd.DataFrame(
    {
        "value": [
            len(frame),
            len(main),
            rents.sample_share(panel, frame, 2021),
            pct(frame["dlog_rent"].median()),
            pct(frame["dlog_price"].median()),
            pct(frame["dlog_price_to_rent"].median()),
            (frame["dlog_rent"] > 0).mean() * 100,
            frame["dlog_rent"].corr(frame["dlog_price"], method="spearman"),
        ]
    },
    index=[
        "municipalities_n",
        "mainland_n",
        "population_share_2021_pct",
        "median_rent_change_pct",
        "median_price_change_pct",
        "median_price_over_rent_change_pct",
        "municipalities_with_rising_rent_pct",
        "rank_correlation_rent_price_change",
    ],
)
style.save_table(national.round(3).reset_index(names="measure"), "p2", "rents_sample_and_change")
print(national.round(3).to_string())
print("prices published in both years:", len(both), "of", len(frame))

# %% [markdown]
# ## Step 2 — By kind of place
# Median change of the real rent and price by coast and density class.

# %%
by_class = (
    frame.groupby("segment")
    .agg(
        municipalities_n=("dlog_rent", "size"),
        rent_pct=("dlog_rent", lambda s: pct(s.median())),
        price_pct=("dlog_price", lambda s: pct(s.median())),
    )
    .round(1)
    .sort_values("rent_pct", ascending=False)
)
style.save_table(by_class.reset_index(), "p2", "rents_by_class")
by_class

# %% [markdown]
# ## Step 3 — What goes with the rise in rents (mainland)
# Each driver alone, then all together with the starting rent. Within district, with and without coast and density classes.

# %%
DRIVERS = [
    "foreign_change_pp",
    "al_per_1000",
    "population_change_pct",
    "completions_per_1000",
]
LABEL = {
    "foreign_change_pp": "Foreign residents (points)",
    "al_per_1000": "Short-term rentals per 1,000 dwellings",
    "population_change_pct": "Population change (%)",
    "completions_per_1000": "Completions per 1,000 dwellings",
    "rent_start_log": "Starting rent (log)",
    "price_start_log": "Starting price (log)",
}
GEO = ["coast", "density_class"]


def run(outcome: str, start: str) -> pd.DataFrame:
    joint = [*DRIVERS, start]
    specs = {f"{LABEL[x]}, same district": ([x], None) for x in DRIVERS}
    specs |= {f"{LABEL[x]}, + coast and density": ([x], GEO) for x in DRIVERS}
    specs["All together, same district"] = (joint, None)
    specs["All together, + coast and density"] = (joint, GEO)
    return pd.concat(
        [
            supply.associations(
                main, outcome, xs, fixed_effects="district", categorical=cats, label=name
            )
            for name, (xs, cats) in specs.items()
        ],
        ignore_index=True,
    )


rent_table = run("dlog_rent", "rent_start_log")
style.save_table(rent_table, "p2", "rents_associations")
print(
    rent_table[["spec", "term", "coef", "se", "p", "coef_per_sd", "n_obs", "r2"]]
    .round(3)
    .to_string(index=False)
)

# %% [markdown]
# ## Step 4 — The same specifications for prices, same places
# Do rents and prices go with the same things? The outcome is the real price change 2020-2024 in the same municipalities.

# %%
price_table = run("dlog_price", "price_start_log")
style.save_table(price_table, "p2", "rents_associations_prices")
joint = "All together, + coast and density"
both_tab = pd.concat(
    [
        rent_table[rent_table["spec"] == joint].assign(outcome="rent"),
        price_table[price_table["spec"] == joint].assign(outcome="price"),
    ]
)
print(
    both_tab[["outcome", "term", "coef", "p", "coef_per_sd", "n_obs"]]
    .round(3)
    .to_string(index=False)
)
print(
    "Price rise over rent rise, median:",
    round(pct(frame["dlog_price_to_rent"].median()), 1),
    "%; municipalities where prices rose more than rents:",
    int((frame["dlog_price_to_rent"] > 0).sum()),
    "of",
    int(frame["dlog_price_to_rent"].notna().sum()),
)

# %%
terms = [*DRIVERS, "rent_start_log"]
price_terms = {"rent_start_log": "price_start_log"}
rows = {}
for term in terms:
    r = rent_table[(rent_table["spec"] == joint) & (rent_table["term"] == term)].iloc[0]
    q = price_table[
        (price_table["spec"] == joint) & (price_table["term"] == price_terms.get(term, term))
    ].iloc[0]
    rows[LABEL[term].replace("Starting rent (log)", "Starting level (log)")] = {
        "rent": pct(r["coef_per_sd"]),
        "rent_low": pct(r["ci_low"] * r["sd"]),
        "rent_high": pct(r["ci_high"] * r["sd"]),
        "price": pct(q["coef_per_sd"]),
        "price_low": pct(q["ci_low"] * q["sd"]),
        "price_high": pct(q["ci_high"] * q["sd"]),
    }
coefs = pd.DataFrame(rows).T
style.save_table(coefs.round(2).reset_index(names="driver"), "p2", "rents_coefficients_per_sd")
coefs.round(2)

# %%
fig = charts.rents_and_prices(
    by_class[["rent_pct", "price_pct"]],
    coefs,
    pct(frame["dlog_rent"].median()),
)
style.save_fig(fig, "p2", "rents_of_new_leases")
fig

# %% [markdown]
# ## Findings
#
# 1. **Rents rose as much as prices in the median municipality.** 191 municipalities (180 on the mainland, 94% of
#    residents) publish a rent in 2020 and 2024. The median real rent of new leases rose 24.0% and the median real
#    price per m2 24.0% in the same places; rents rose in 96% of them, and prices rose faster than rents in 96 of 191.
#    The rank correlation of the two changes is 0.34.
# 2. **Rents rose more evenly than prices.** By kind of place the median rent rose from 21% (inland rural) to 34%
#    (coast rural), the price from 8% (inland rural) to 35% (coast urban). In coast urban prices rose 35% against
#    rents 24%; in inland rural rents rose 21% against prices 8%.
# 3. **Two drivers go with rents.** In the joint specification a point more of foreign residents (2020-2023) goes
#    with +1.6% on the rent (p = 0.026 within district, p = 0.023 with coast and density; +2.4% per standard
#    deviation) and 10 more registered short-term rentals per 1,000 dwellings with +1.0% (p = 0.018 and 0.025; +3.3%
#    per standard deviation). By the reading rule both matter. Population change (p = 0.26 to 0.31) and completions
#    (p = 0.74 to 0.86) do not; population change was significant alone (p = 0.03) and faded. Rents rose less where
#    they started higher (−8.7% and −12.4% per log point, p = 0.01 and 0.002): catching up.
# 4. **Short-term rentals go with rents, not prices.** The same joint specification for the price change: short-term
#    rentals +0.2% per 10 rentals (p = 0.71), foreign residents +1.8% per point (p = 0.076), completions +0.4% per unit
#    (p = 0.019, more building where prices rose, not a cause). R2 is 0.41 for rents (0.34 to 0.37 one driver at a
#    time), so most of the variation is left.
#
# **Limits.** Only municipalities where INE publishes a rent (larger and more urban); four years, one boom; the
# rent is the median of new leases, which mixes the kind of home let; the registry of short-term rentals is today's
# survivors and mainland only; foreign residents end in 2023, a year before the rents; the specifications cannot
# separate foreign demand from where they settle. Associations, not effects, and a null is not evidence of no effect.
