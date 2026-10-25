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
# # P2.14 — Which foreign residents go with rising prices? Nationality groups
#
# **Question:** RQ3.3 (population growth, immigration and prices) — `p2_02` used the change in *all* foreign residents; it left
# nationalities unsplit. Here the same fixed-effects regression of log price-to-income, with the foreign-resident change split
# into six groups: Brazil, the Portuguese-speaking African countries (Angola, Cabo Verde, Guinea-Bissau, São Tomé and Príncipe),
# Eastern Europe (Romania, Moldova, Ukraine), China, the United Kingdom and all other nationalities.
#
# Same design as `p2_02` (municipality fixed effects; year effects, or NUTS 3 × year effects; errors clustered by municipality;
# 2016 to 2023), same controls. Nationality is a *marker* of who arrives, not a mechanism: groups differ in where they settle,
# in income and in what they buy, and a coefficient mixes all of that. Adjusted associations, not effects.

# %%
import pandas as pd

from pthousing.analysis import demography as dem
from pthousing.analysis import panel as pn
from pthousing.config import MUNI_KEY, YEAR_KEY
from pthousing.data import build_panel, interim
from pthousing.viz import charts, style

style.apply_style()
panel = build_panel.read("panel_municipality_year")
aima = interim.read("aima_foreigners")
frame = pn.build_frame(panel)
population = panel.set_index([MUNI_KEY, YEAR_KEY])["population_n"]
changes = dem.group_changes(aima, population)
frame = frame.join(changes)
GROUPS = list(changes.columns)
print(
    f"{len(GROUPS)} groups, {frame[GROUPS].notna().all(axis=1).sum()} municipality-years with every group"
)

# %% [markdown]
# ## Step 1 — The groups
# Residents with a title by group, 2014 and 2023: the groups differ in size and in growth.

# %%
totals = dem.nationality_totals(aima)
rows = {}
for name, codes in dem.NATIONALITY_GROUPS.items():
    s = totals[codes].sum(axis=1)
    rows[name] = {
        "residents_2014_n": s.loc[2014],
        "residents_2023_n": s.loc[2023],
        "growth_pct": 100 * (s.loc[2023] / s.loc[2014] - 1),
        "share_2023_pct": 100 * s.loc[2023] / totals["total"].loc[2023],
    }
sizes = pd.DataFrame(rows).T
style.save_table(sizes.round(1).reset_index(names="group"), "p2", "nationality_group_sizes")
sizes.round(1)

# %% [markdown]
# ## Step 2 — The regressions
# Each group's change enters in the same unit (pp of last year's population), so coefficients compare directly; the chart scales
# them by each group's within-municipality standard deviation, because a group that is small everywhere (China) has a large
# coefficient per point and a small effect per typical change. Checks: NUTS 3 × year effects, stopping in 2022 (before the jump
# in titles), and without Lisboa, Setúbal and Porto.

# %%
X = ["pop_change_ex_foreign_pct", *GROUPS, "completions_per_1000", "pop_65plus_pct"]
metro = {"exclude_district": ["Lisboa", "Setúbal", "Porto"]}
SPECS = {
    "Municipality + year effects": pn.Spec("log_pti", X),
    "Municipality + region-year effects": pn.Spec("log_pti", X, effects="region_year"),
    "Through 2022": pn.Spec("log_pti", X, years=(2016, 2022)),
    "Without Lisboa, Setúbal, Porto": pn.Spec("log_pti", X, sample=metro),
}
MAIN, COMPARE = "Municipality + year effects", "Municipality + region-year effects"
fits = {name: pn.fit(frame, spec) for name, spec in SPECS.items()}
ladder = pd.concat([pn.coef_table(res, name) for name, res in fits.items()], ignore_index=True)
style.save_table(ladder, "p2", "nationality_regressions_pti")
labels = {
    "fc_brazil_pct": "Brazil (pp of pop.)",
    "fc_palop_pct": "Lusophone Africa (pp of pop.)",
    "fc_east_europe_pct": "Eastern Europe (pp of pop.)",
    "fc_china_pct": "China (pp of pop.)",
    "fc_uk_pct": "United Kingdom (pp of pop.)",
    "fc_other_pct": "All other (pp of pop.)",
}
fig = charts.coef_ladder(ladder, labels, MAIN, COMPARE, "price-to-income", lower_label=False)
style.save_fig(fig, "p2", "nationality_coefficients_pti")
show = ladder[ladder["term"].isin(labels)].assign(term=lambda d: d["term"].map(labels))
show[["spec", "term", "coef", "se", "p", "coef_per_sd", "n_obs", "n_munis"]].round(4)

# %% [markdown]
# ## Step 3 — Do the groups differ?
# A Wald test that the six coefficients are equal, in each specification, against the single-coefficient model of `p2_02`.

# %%
tests = pd.DataFrame({name: pn.equal_coefficients(res, GROUPS) for name, res in fits.items()}).T
one = pn.coef_table(
    pn.fit(
        frame,
        pn.Spec(
            "log_pti",
            [
                "pop_change_ex_foreign_pct",
                "foreign_change_pct",
                "completions_per_1000",
                "pop_65plus_pct",
            ],
        ),
    ),
    "All foreign residents together",
)
style.save_table(tests.round(4).reset_index(names="spec"), "p2", "nationality_equality_tests")
print(
    one.loc[one["term"] == "foreign_change_pct", ["coef", "se", "p"]]
    .round(4)
    .to_string(index=False)
)
tests.round(4)

# %% [markdown]
# ## Key numbers

# %%
for spec in (MAIN, COMPARE):
    d = ladder[(ladder["spec"] == spec) & ladder["term"].isin(labels)]
    print(spec)
    for r in d.itertuples():
        print(
            f"  {labels[r.term].split(' (')[0]}: {100 * r.coef:+.1f}% per pp [{100 * r.ci_low:+.1f}, {100 * r.ci_high:+.1f}], "
            f"{100 * r.coef_per_sd:+.2f}% per sd, p={r.p:.3f}"
        )
    t = tests.loc[spec]
    print(f"  equal coefficients: chi2({t['df']:.0f}) = {t['statistic']:.1f}, p = {t['p']:.3f}")
print(sizes.round(1).to_string())
