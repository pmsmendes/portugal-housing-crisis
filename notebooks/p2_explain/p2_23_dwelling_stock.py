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
# **Question:** RQ2.4 (how the housing stock evolved). `p2_05` has the composition (usual, secondary, vacant) for the
# two censuses; between them the stock is not observed. Completions of new family dwellings are, every year since 1995.
#
# **Method.** (1) For each municipality, the net change of the census count of dwellings 2011-2021 against the dwellings
# completed in 2012-2021; the gap is what completions do not explain (`analysis/stock_reconciliation.py`). (2) The gap by
# coast and density class and for the largest municipalities, and against population change. (3) The stock rolled
# along completions from the 2021 census, backward to 1995 and forward to 2025, at the national retention of 2012-2021
# and at a retention of one.
#
# **Reading rule, fixed before looking:** a gap is "local" if its sign differs between classes of place (the national
# total is not enough to say completions are or are not counted), and it is "tied to demand" only if it differs
# between the thirds of municipalities by population change. The gap is an accounting residual: demolitions,
# merged and split dwellings, conversions to and from other uses, works on existing buildings and what each census
# counts all sit in it, and nothing here separates them.

# %%
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
rec = sr.reconcile(panel, stock)

# %% [markdown]
# ## Step 1 — The national balance
# Census count 2011 and 2021, the net addition, and the completions of 2012-2021.

# %%
nat = sr.aggregate(rec).loc["Portugal"]
national = pd.DataFrame(
    {
        "value": [
            nat["dwellings_start_n"],
            nat["dwellings_end_n"],
            nat["added_n"],
            nat["completions_n"],
            nat["gap_n"],
            nat["retention"],
            nat["losing_n"],
            (rec["added_n"] > rec["completions_n"]).sum(),
        ]
    },
    index=[
        "dwellings_2011_n",
        "dwellings_2021_n",
        "net_addition_n",
        "completions_2012_2021_n",
        "gap_n",
        "retention",
        "municipalities_losing_dwellings_n",
        "municipalities_counting_more_than_completed_n",
    ],
)
style.save_table(national.round(3).reset_index(names="measure"), "p2", "dwelling_stock_national")
print(national.round(3).to_string())

# %% [markdown]
# ## Step 2 — Where completions do not show up
# Sums by coast and density class (counts summed, then the ratios rebuilt), then the municipalities with the largest gaps.

# %%
by_class = sr.aggregate(rec, ty["segment"]).sort_values("gap_per_1000")
style.save_table(by_class.round(2).reset_index(names="segment"), "p2", "dwelling_stock_by_class")
by_class[
    [
        "municipalities_n",
        "losing_n",
        "added_n",
        "completions_n",
        "gap_n",
        "gap_per_1000",
        "retention",
    ]
].round(2)

# %%
order = by_class.sort_values("completions_per_1000", ascending=False).index
fig_groups = by_class.loc[order, ["completions_per_1000", "added_per_1000"]]
largest = (
    rec.assign(name=names)
    .sort_values("gap_n")
    .pipe(lambda t: pd.concat([t.head(8), t.tail(6)]))[
        ["name", "dwellings_start_n", "added_n", "completions_n", "gap_n", "gap_per_1000"]
    ]
)
style.save_table(largest.round(1).reset_index(), "p2", "dwelling_stock_largest_gaps")
largest

# %%
rest = rec.drop(index=ty.index[ty["segment"] == "coast / urban"].intersection(rec.index))
cu = rec.loc[ty.index[ty["segment"] == "coast / urban"].intersection(rec.index)]
print(
    f"coastal urban ({len(cu)} municipalities): completed {cu['completions_n'].sum():,.0f}, count grew "
    f"{cu['added_n'].sum():,.0f}; the other {len(rest)}: completed {rest['completions_n'].sum():,.0f}, "
    f"count grew {rest['added_n'].sum():,.0f}"
)
print(
    "Lisboa and Porto: count",
    rec.loc[["1106", "1312"], "added_n"].sum(),
    "completed",
    rec.loc[["1106", "1312"], "completions_n"].sum(),
)

# %% [markdown]
# ## Step 3 — Is the gap tied to demand?
# Median gap per 1,000 dwellings by third of municipalities by population change 2011-2021.

# %%
pop = panel.pivot(index="muni_code", columns="year", values="population_n")
rec["population_change_pct"] = 100 * (pop[2021] / pop[2011] - 1)
rec["third"] = pd.qcut(
    rec["population_change_pct"], 3, labels=["lost most", "middle third", "grew most"]
)
thirds = (
    rec.groupby("third", observed=True)
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
    round(rec["gap_per_1000"].corr(rec["population_change_pct"], method="spearman"), 2),
)
thirds

# %% [markdown]
# ## Step 4 — The stock between and beyond the censuses
# Rolled from the 2021 count along national completions, 1995-2025. At the observed retention the path meets the 2011
# count; at a retention of one it overshoots it by the national gap. The retention was measured in 2012-2021, a decade of
# low completions, so the same retention for the building boom of 1996-2011 is an extrapolation: the two paths are a range.

# %%
done = panel.groupby("year")["completed_n"].sum()
anchors = {2011: nat["dwellings_start_n"], 2021: nat["dwellings_end_n"]}
central = sr.stock_path(done, anchors, nat["retention"])
upper = sr.stock_path(done, anchors, 1.0)
path = pd.DataFrame(
    {
        "completed_n": done,
        "stock_n": central["stock_n"],
        "growth_pct": central["growth_pct"],
        "stock_upper_n": upper["stock_n"],
        "growth_upper_pct": upper["growth_pct"],
        "census_n": central["census_n"],
    }
)
style.save_table(path.round(3).reset_index(names="year"), "p2", "dwelling_stock_path")
pick = path.loc[[1995, 2001, 2011, 2015, 2021, 2025]].round(2)
print(pick.to_string())

# %%
fig = charts.stock_reconciliation(
    fig_groups.rename(index=lambda s: s), path.dropna(subset=["growth_pct"]), nat["retention"]
)
style.save_fig(fig, "p2", "dwelling_stock")
fig

# %% [markdown]
# ## Findings
#
# 1. **Nationally nine in ten completions show up in the count (RQ2.4).** The census count of dwellings rose
#    5,859,540 to 5,970,677 (+111,137, +1.9%) against 124,572 new family dwellings completed in 2012-2021: a gap of
#    −13,435 and a retention of 0.89. 66 municipalities counted fewer dwellings in 2021 than in 2011, all of them with
#    completions; 141 counted more than they completed.
# 2. **The national total hides offsetting local gaps.** In the 20 coastal urban municipalities 26,821 dwellings
#    were completed and the count grew by 6,748 (retention 0.25, −12 per 1,000 dwellings of 2011); in the other 288
#    municipalities 97,751 were completed and the count grew by 104,389. Lisboa and Porto together lost 7,109 on the
#    count against 5,783 completed (Porto −55.6 per 1,000). The gap is positive in coast / intermediate (+8,217,
#    retention 1.29): Albufeira, Portimão, Lagoa and Odemira count 1,000-1,700 dwellings more than they completed.
#    By the reading rule the gap is local: it changes sign between classes.
# 3. **It is not clearly tied to demand.** The median gap per 1,000 dwellings is −3.6 in the third of
#    municipalities that lost the most residents, −3.4 in the middle third and 0.0 in the third that grew most;
#    the rank correlation with population change is 0.09. The reading rule needs a difference between the thirds
#    and the two lower thirds do not differ.
# 4. **The stock between the censuses.** Rolled from the 2021 count, the stock was 4.60 to 4.75 million in 1995,
#    5.17 to 5.26 million in 2001, 5.90 million in 2015 and 6.06 to 6.07 million in 2025 (+85,000 to +95,000 since
#    2021). Its yearly growth was 2.0% to 2.3% in 2001, 0.11% to 0.12% in 2015 (the trough) and 0.40% to 0.45% in 2025.
#
# **Limits.** The gap is an accounting residual and cannot be split into demolitions, merged dwellings, conversions
# (offices and short-term rentals out, shops and attics in), works on existing buildings and census definitions.
# Completions of the calendar years 2012-2021 against censuses of March 2011 and 2021. Demolitions do not scale with
# completions, so a retention measured in a decade of low building probably understates it for the boom of 1996-2011:
# the two paths are a range, not a bound. The 2001 census count (not held) would test the backward path. Composition
# (usual, secondary, vacant) is not rolled: it is observed only in 2011 and 2021.
