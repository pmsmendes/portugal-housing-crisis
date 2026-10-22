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
# # P2.06 — Second homes: do they go with where affordability worsened?
#
# **Questions:** RQ5.3 (second homes and the availability of permanent housing), RQ5.4 (separating the drivers: the
# missing piece was second homes).
#
# **Data:** the census counts *secondary residences* (dwellings used seasonally or occasionally) in 2011 and 2021
# (`ine_census_stock`), so second homes enter as a cross-section (share of conventional dwellings, 2021, and its
# change in points) and cannot be a time-varying driver in the panel: municipality effects would absorb them. Two
# uses: a cross-section of the 2016 to 2024 change (and the 2024 level) of price-to-income, and an interaction
# with the panel drivers of P2.02. Mainland only (the typology's second-home flag and rentals are mainland).
# Associations, not effects: the census cannot say who owns a second home, a foreign buyer or a family from the
# village.

# %%
import numpy as np
import pandas as pd

from pthousing.analysis import panel as pn
from pthousing.analysis import supply
from pthousing.data import build_panel, typology
from pthousing.viz import style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
stock = supply.read_stock()
ty = typology.read().set_index("muni_code")
sec = supply.secondary_share(stock)

d = sec.join(ty[["coast_class", "density_class", "tourist", "territory"]])
d["dlog_pti"] = supply.pti_change(panel, 2016, 2024)
d["log_pti_2024"] = np.log(panel[panel["year"] == 2024].set_index("muni_code")["pti_years"])
d["district"] = supply.area_of(panel)
d = d[d["territory"] == "continente"]
print(
    d[["secondary_2011_pct", "secondary_2021_pct", "secondary_change_pp"]]
    .describe()
    .round(1)
    .to_string()
)

# %% [markdown]
# ## Step 1 — Where are the second homes? (RQ5.3)

# %%
rows = []
for dim in ("coast_class", "density_class", "tourist"):
    g = d.groupby(dim)
    rows.append(
        pd.DataFrame(
            {
                "dimension": dim,
                "municipalities_n": g.size(),
                "secondary_2011_pct": g["secondary_2011_pct"].median(),
                "secondary_2021_pct": g["secondary_2021_pct"].median(),
                "pti_change_log_median": g["dlog_pti"].median(),
            }
        )
        .rename_axis("group")
        .reset_index()
    )
by_class = pd.concat(rows, ignore_index=True)
style.save_table(by_class, "p2", "second_homes_by_class")
print(by_class.round(2).to_string(index=False))
print(d[["secondary_2021_pct", "dlog_pti", "log_pti_2024"]].corr().round(2).to_string())

# %% [markdown]
# ## Step 2 — Second-home share and price-to-income (cross-section)
# Same-district comparisons, HC3 errors. Outcomes: the log change 2016 to 2024 and the 2024 level. The share is in
# percentage points; "coef_per_sd" is the effect of one standard deviation of the share (13.6 points).

# %%
MODELS = {
    "Change, same district": ("dlog_pti", ["secondary_2021_pct"], None),
    "Change, + coast and density": ("dlog_pti", ["secondary_2021_pct"], ["coast_class", "density_class"]),
    "Change, share and its 2011-21 change": (
        "dlog_pti", ["secondary_2021_pct", "secondary_change_pp"], ["coast_class", "density_class"],
    ),
    "Level 2024, same district": ("log_pti_2024", ["secondary_2021_pct"], None),
    "Level 2024, + coast and density": ("log_pti_2024", ["secondary_2021_pct"], ["coast_class", "density_class"]),
}  # fmt: skip
cross = pd.concat(
    [
        supply.associations(d, y, xs, fixed_effects="district", categorical=cats, label=name)
        for name, (y, xs, cats) in MODELS.items()
    ],
    ignore_index=True,
)
style.save_table(cross, "p2", "second_homes_cross_section")
print(
    cross[["spec", "term", "coef", "se", "p", "coef_per_sd", "n_obs", "r2"]]
    .round(4)
    .to_string(index=False)
)

# %% [markdown]
# **Subsamples:** the share's coefficient on the change within the coastal and estuary municipalities, within the
# urban and intermediate ones, and within the 34 tourist ones, each with density class and district.

# %%
subsets = {
    "Coast and estuary": d[d["coast_class"] != "inland"],
    "Urban and intermediate": d[d["density_class"] != "rural"],
    "Tourist": d[d["tourist"] == "tourist"],
    "Inland": d[d["coast_class"] == "inland"],
}
sub = pd.concat(
    [
        supply.associations(
            s, "dlog_pti", ["secondary_2021_pct"], fixed_effects="district",
            categorical=["density_class"], label=name,
        )
        for name, s in subsets.items()
    ],
    ignore_index=True,
)  # fmt: skip
style.save_table(sub, "p2", "second_homes_subsamples")
print(sub[["spec", "coef", "se", "p", "coef_per_sd", "n_obs"]].round(4).to_string(index=False))

# %% [markdown]
# ## Step 3 — Does the share change what the panel drivers do? (RQ5.4)
# P2.02's model (log price-to-income, 2016 to 2023, mainland) with each driver interacted with the second-home
# share (centred, per 10 points). The first rows are the drivers in a municipality with the average share; an
# interaction is the *difference* per 10 more points.

# %%
frame = pn.build_frame(panel).join(sec[["secondary_2021_pct"]], on="muni_code")
centred = (frame["secondary_2021_pct"] - sec["secondary_2021_pct"].mean()) / 10
X = ["pop_change_ex_foreign_pct", "foreign_change_pct", "completions_per_1000", "pop_65plus_pct"]
for driver, name in (
    ("foreign_change_pct", "foreign_x_second"),
    ("pop_change_ex_foreign_pct", "pop_x_second"),
    ("completions_per_1000", "completions_x_second"),
):
    frame[name] = frame[driver] * centred
SPECS = {
    "Foreign residents only": [*X, "foreign_x_second"],
    "All three interactions": [*X, "foreign_x_second", "pop_x_second", "completions_x_second"],
}
rows = []
for name, xs in SPECS.items():
    for effects, label in (
        ("year", "municipality + year"),
        ("region_year", "municipality + NUTS 3 x year"),
    ):
        res = pn.fit(
            frame, pn.Spec("log_pti", xs, effects=effects, sample={"territory": ["continente"]})
        )
        t = pn.coef_table(res, f"{name} | {label}")
        shown = [*X[:3], *(x for x in xs if x.endswith("_second"))]
        rows.append(t[t["term"].isin(shown)])
inter = pd.concat(rows, ignore_index=True)
style.save_table(inter, "p2", "second_homes_interactions")
print(
    inter[["spec", "term", "coef", "se", "p", "n_obs", "n_munis"]].round(4).to_string(index=False)
)

# %% [markdown]
# ## Findings
#
# 1. **Second homes are a rural and interior stock, and it barely moved (RQ5.3).** In 2021 the median share of
#    secondary residences was 34% in rural municipalities against 7.6% in urban ones, 27.6% inland against 21.4% on
#    the coast (12.3% in the estuary ones) and 39% in the 35 tourist municipalities against 25%. The mean share was
#    26.7% in 2011 and 26.8% in 2021 (median change −0.2 points); the national count fell by 28,000 (1.13 to 1.10
#    million). There is no sign of a wave of conversions of permanent homes into second homes in the census decade.
# 2. **A higher share goes with a smaller, not larger, rise in price-to-income.** Within a district one standard
#    deviation of the share (13.6 points) goes with −6.3% in the 2016 to 2024 change (p = 0.001), −3.6% with coast and
#    density class (p = 0.08), and −17% in the 2024 level (p < 0.001, with or without the classes). The change in the share between censuses has
#    no association (+1.7% per sd, p = 0.42). The share marks low-demand places (empty villages and family
#    houses), not pressure on permanent housing.
# 3. **The negative sign is a coastal feature.** Within coastal and estuary municipalities (66) one sd goes with −9.1%
#    (p = 0.003); in urban and intermediate ones −3.2% (p = 0.12), in tourist ones −3.3% (p = 0.36), inland −0.7%
#    (p = 0.79). Coastal places with many second homes rose less than coastal places with few.
# 4. **The foreign-resident association is weaker where second homes are common (RQ5.4).** With municipality and year
#    effects, a point of population added through foreign residents goes with +4.7% in a municipality with the average
#    share and 2.4 points less per 10 points more of second homes (p < 0.001); with NUTS 3 × year effects +3.2% and
#    −1.4 points per 10 (p < 0.001). The interactions with other population change (p = 0.17, 0.65) are nil and with
#    completions marginal (−0.23, p = 0.04 only with region-year effects). The foreign-resident association is a
#    feature of places where the stock is mostly permanent housing, in line with its being strongest in urban
#    municipalities (P2.04).
#
# **Limits.** The census category is "secondary residence": it includes holiday homes, inherited village houses and
# homes of the emigrant diaspora, and 2021 predates part of the recent short-term-rental and foreign-buyer boom, so
# it cannot show conversions after 2021. It is a cross-section (two census points), so the municipality fixed effects
# of the panel cannot use it except as an interaction. Registered short-term rentals (P2.02) are only the part
# of the second-home stock offered to tourists, and the overlap (tourist municipalities have 39% second homes) is
# not separated here. The cross-section regressions have 271 mainland municipalities and are associations, not effects.
