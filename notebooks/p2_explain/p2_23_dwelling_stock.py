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
# # P2.23 — The dwelling stock: how much of what was built shows up in the count, and the stock between censuses
#
# **Questions:** RQ2.4 (how the housing stock evolved) and, for 2001-2011, RQ2.3 and RQ3.4 (dwellings against households).
# `p2_05` has the composition (usual, secondary, vacant) and the households balance for 2011-2021; the 2001 census
# (`ine_census_stock`, INE 0000729 and 0000676) adds a decade. Completions of new family dwellings are observed every year
# since 1995.
#
# **Method.** (1) For each municipality and each decade, the net change of the census count of dwellings against the
# dwellings completed in the years in between; the gap is what completions do not explain
# (`analysis/stock_reconciliation.py`). (2) The gap by coast and density class and for the largest municipalities, and
# against population change (2011-2021 only: population by municipality is not held for 2001). (3) Composition and
# households across the three censuses. (4) The stock rolled along completions, each decade at its own retention so the path
# meets all three censuses, with a band before 2001 and after 2021 where the retention is extrapolated.
#
# **History of this notebook.** A first version had only the 2011 and 2021 censuses, held the retention at 0.89 (or 1)
# throughout, and said the pre-2011 path would probably be too low for the boom years. The 2001 census shows the reverse:
# the count rose faster than completions in 2002-2011 (1.25 per completion). The decade comparison was added after that
# and has no reading rule fixed before looking; the 2011-2021 reading rule below was fixed in the first version.
#
# **Reading rule (2011-2021), fixed before looking:** a gap is "local" if its sign differs between classes of place (the
# national total is not enough to say completions are or are not counted), and it is "tied to demand" only if it differs
# between the thirds of municipalities by population change. The gap is an accounting residual: demolitions, merged
# and split dwellings, conversions to and from other uses, works on existing buildings and what each census counts all
# sit in it, and nothing here separates them.

# %%
import numpy as np
import pandas as pd

from pthousing.analysis import stock_reconciliation as sr
from pthousing.analysis import supply
from pthousing.data import build_panel, harmonize, typology
from pthousing.viz import charts, style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
stock = supply.read_stock()
ty = typology.read().set_index("muni_code")
ty["coast"] = ty["coast_class"].replace({"estuary": "coast"})
ty["segment"] = ty["coast"] + " / " + ty["density_class"]
names = pd.read_csv(harmonize.CROSSWALK_PATH, dtype=str).set_index("muni_code")["muni_name"]
DECADES = {"2002-2011": (2001, 2011), "2012-2021": (2011, 2021)}
rec = {label: sr.reconcile(panel, stock, years) for label, years in DECADES.items()}
late = rec["2012-2021"]

# %% [markdown]
# ## Step 1 — The national balance, both decades
# Census count at each end, the net addition, and the completions in between.

# %%
rows = {}
for label, table in rec.items():
    n = sr.aggregate(table).loc["Portugal"]
    rows[label] = {
        "dwellings_start_n": n["dwellings_start_n"],
        "dwellings_end_n": n["dwellings_end_n"],
        "net_addition_n": n["added_n"],
        "completions_n": n["completions_n"],
        "gap_n": n["gap_n"],
        "retention": n["retention"],
        "municipalities_losing_dwellings_n": n["losing_n"],
        "municipalities_counting_more_than_completed_n": (
            table["added_n"] > table["completions_n"]
        ).sum(),
    }
national = pd.DataFrame(rows)
style.save_table(national.round(3).reset_index(names="measure"), "p2", "dwelling_stock_national")
print(national.round(3).to_string())

# %% [markdown]
# ## Step 2 — Where completions do and do not show up
# Sums by coast and density class (counts summed, then the ratios rebuilt), both decades; then the municipalities with
# the largest gaps in 2011-2021.

# %%
by_class = {label: sr.aggregate(t, ty["segment"]) for label, t in rec.items()}
style.save_table(
    by_class["2012-2021"].sort_values("gap_per_1000").round(2).reset_index(names="segment"),
    "p2",
    "dwelling_stock_by_class",
)
style.save_table(
    by_class["2002-2011"].sort_values("gap_per_1000").round(2).reset_index(names="segment"),
    "p2",
    "dwelling_stock_by_class_2001_2011",
)
retention_by_class = pd.DataFrame(
    {
        "retention_2002_2011": by_class["2002-2011"]["retention"],
        "retention_2012_2021": by_class["2012-2021"]["retention"],
    }
).sort_values("retention_2012_2021", ascending=False)
style.save_table(
    retention_by_class.round(3).reset_index(names="segment"),
    "p2",
    "dwelling_stock_retention_by_class",
)
retention_by_class.round(2)

# %%
largest = (
    late.assign(name=names)
    .sort_values("gap_n")
    .pipe(lambda t: pd.concat([t.head(8), t.tail(6)]))[
        ["name", "dwellings_start_n", "added_n", "completions_n", "gap_n", "gap_per_1000"]
    ]
)
style.save_table(largest.round(1).reset_index(), "p2", "dwelling_stock_largest_gaps")
cu_idx = ty.index[ty["segment"] == "coast / urban"].intersection(late.index)
cu, rest = late.loc[cu_idx], late.drop(index=cu_idx)
print(
    f"coastal urban ({len(cu)} municipalities): completed {cu['completions_n'].sum():,.0f}, count grew "
    f"{cu['added_n'].sum():,.0f}; the other {len(rest)}: completed {rest['completions_n'].sum():,.0f}, "
    f"count grew {rest['added_n'].sum():,.0f}"
)
early_cu = rec["2002-2011"].loc[cu_idx]
print(
    f"2002-2011 coastal urban: completed {early_cu['completions_n'].sum():,.0f}, count grew "
    f"{early_cu['added_n'].sum():,.0f}"
)
print(
    "Lisboa and Porto 2011-2021: count",
    late.loc[["1106", "1312"], "added_n"].sum(),
    "completed",
    late.loc[["1106", "1312"], "completions_n"].sum(),
)
largest

# %% [markdown]
# ## Step 3 — Is the 2011-2021 gap tied to demand?
# Median gap per 1,000 dwellings by third of municipalities by population change 2011-2021.

# %%
pop = panel.pivot(index="muni_code", columns="year", values="population_n")
late = late.assign(population_change_pct=100 * (pop[2021] / pop[2011] - 1))
late["third"] = pd.qcut(
    late["population_change_pct"], 3, labels=["lost most", "middle third", "grew most"]
)
thirds = (
    late.groupby("third", observed=True)
    .agg(
        municipalities_n=("gap_n", "size"),
        population_change_median_pct=("population_change_pct", "median"),
        added_n=("added_n", "sum"),
        completions_n=("completions_n", "sum"),
        gap_per_1000_median=("gap_per_1000", "median"),
    )
    .assign(retention=lambda t: t["added_n"] / t["completions_n"])
    .round(2)
    .reset_index()
)
style.save_table(thirds, "p2", "dwelling_stock_by_population_change")
print(
    "rank correlation, gap per 1,000 and population change:",
    round(late["gap_per_1000"].corr(late["population_change_pct"], method="spearman"), 2),
)
thirds

# %% [markdown]
# ## Step 4 — Composition and households across three censuses (RQ2.4, RQ3.4)
# Share of dwellings that are usual, secondary or vacant, and dwellings against households, 2001, 2011, 2021.

# %%
comp = supply.composition(stock).drop(columns="group").set_index("census_year")
hh = stock.groupby("census_year")[["dwellings_n", "dwellings_usual_n", "households_n"]].sum()
three = comp.join(hh[["dwellings_usual_n", "households_n"]])
three["dwellings_change_pct"] = 100 * three["dwellings_n"].pct_change()
three["households_change_pct"] = 100 * three["households_n"].pct_change()
three["dwellings_per_household"] = three["dwellings_n"] / three["households_n"]
style.save_table(three.round(2).reset_index(), "p2", "dwelling_stock_three_censuses")
three.round(2)

# %% [markdown]
# ## Step 5 — The stock between and beyond the censuses
# Rolled from the 2021 count along national completions. Inside each decade the retention is the one observed there, so
# the path meets all three censuses; before 2001 and after 2021 either decade's retention is possible, so the central
# path takes the nearest decade's and a band is drawn between the two.

# %%
done = panel.groupby("year")["completed_n"].sum()
anchors = {
    y: float(stock.loc[stock["census_year"] == y, "dwellings_n"].sum()) for y in (2001, 2011, 2021)
}
observed = sr.interval_retentions(done, anchors)
lo, hi = float(observed.min()), float(observed.max())
central = sr.stock_path(done, anchors)
band = [sr.stock_path(done, anchors, outside=(r, r)) for r in (lo, hi)]
path = central.assign(
    stock_low_n=np.minimum(band[0]["stock_n"], band[1]["stock_n"]),
    stock_high_n=np.maximum(band[0]["stock_n"], band[1]["stock_n"]),
    growth_low_pct=np.minimum(band[0]["growth_pct"], band[1]["growth_pct"]),
    growth_high_pct=np.maximum(band[0]["growth_pct"], band[1]["growth_pct"]),
)
path["is_census"] = path.index.isin(anchors)
style.save_table(path.round(3).reset_index(names="year"), "p2", "dwelling_stock_path")
print(observed.round(3).to_dict())
print(path.loc[[1995, 2001, 2011, 2015, 2021, 2025]].round(3).T.to_string())

# %%
fig = charts.stock_reconciliation(
    retention_by_class.rename(
        columns={
            "retention_2002_2011": "retention_first",
            "retention_2012_2021": "retention_second",
        }
    ),
    path.dropna(subset=["growth_pct"]),
    ("2002-2011", "2012-2021"),
    (float(observed[2011]), float(observed[2021])),
)
style.save_fig(fig, "p2", "dwelling_stock")
fig

# %% [markdown]
# ## Findings
#
# 1. **The count rose by 1.25 dwellings per completion in 2002-2011 and by 0.89 in 2012-2021 (RQ2.4).** 2001: 5,019,425
#    conventional dwellings; 2011: 5,859,540 (+840,115 against 673,822 completed, a gap of +166,293); 2021: 5,970,677
#    (+111,137 against 124,572 completed, −13,435). 11 municipalities counted fewer dwellings in 2011 than in 2001, 66 in
#    2021 than in 2011. A constant retention is wrong: the first version of this notebook said the pre-2011 path would
#    probably be too low, and the 2001 census shows it would have been too high (5.26 million against 5.02 million in 2001).
# 2. **In 2002-2011 the count exceeded completions everywhere; in 2012-2021 it still did only in some places.** Retention
#    by coast and density class, 2002-2011 then 2012-2021: coast / intermediate 1.29 and 1.29, inland / intermediate 1.14
#    and 1.09, inland / urban 1.06 and 1.04, coast / rural 1.38 and 0.97, inland / rural 1.15 and 0.78, coast / urban 1.41
#    and 0.25. The 20 coastal urban municipalities completed 156,963 dwellings in 2002-2011 and the count grew by 221,070;
#    in 2012-2021 they completed 26,821 and the count grew by 6,748 (Lisboa and Porto together −7,109 against 5,783
#    completed). By the reading rule the 2011-2021 gap is local (its sign changes between classes).
# 3. **The 2011-2021 gap is not clearly tied to demand.** Median gap per 1,000 dwellings −3.6, −3.4 and 0.0 in the thirds
#    of municipalities by population change; rank correlation 0.09.
# 4. **Composition barely moved, households did.** Usual residences were 70.8%, 68.1% and 69.4% of dwellings in 2001, 2011
#    and 2021, secondary 18.4%, 19.3%, 18.5%, vacant 10.8%, 12.5%, 12.1%. In 2001-2011 dwellings grew 16.7% (+840,115)
#    against households 10.8% (+392,969), so dwellings per household went from 1.37 to 1.45; in 2011-2021 dwellings grew
#    1.9% and households 2.6% (1.44).
# 5. **The stock between the censuses.** Rolled with each decade's retention the path meets all three counts. Before 2001
#    it is 4.31 million (retention 1.25) to 4.51 million (0.89) in 1995; after 2021 it is 6.06 million (0.89) to 6.09 million
#    (1.25) in 2025, +85,000 to +119,000 since 2021. Yearly growth was about 3% in 2001-2002 (2.1% to 2.9% in 2001 across the
#    band), 0.11% in 2015 (the trough) and 0.40% to 0.56% in 2025.
#
# **Limits.** The gap is an accounting residual and cannot be split into demolitions, merged dwellings, conversions
# (offices and short-term rentals out, shops and attics in), works on existing buildings and census definitions or
# coverage; in particular the 1.25 of 2002-2011 may partly reflect a more complete count in 2011, which nothing here can
# tell. Completions of the calendar years against censuses of March. Households of 2001 are private households and of 2011
# classic families, and 2001 has no household sizes or municipal population in the data, so the size split of `p2_20` stays
# 2011-2021. Outside 2001-2021 the path takes the nearest decade's retention and a band between the two; the real value
# may lie outside it.
