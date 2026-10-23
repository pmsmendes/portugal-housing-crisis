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
# # P4.03 — Which regions are likely to worsen further? A validated regional outlook
#
# **Question:** RQ10.2. The national forecast (p4_01) and the simulator (p4_02) say how affordability may move for the
# median municipality; this notebook asks *where* it is likely to move more or less.
#
# **What can be validated.** A municipality has nine annual points (2016 to 2024) and a noisy published level (the 12-month
# median price rests on few sales; year-on-year growth has a lag-1 autocorrelation of -0.3 to -0.6). ETS or ARIMA per
# municipality cannot be tested on that, so the methods are straight-line trends of growing complexity on the log of
# price-to-income (`analysis/regional_forecast.py`): **naive** (no change), **national drift**, **national trend**,
# **own trend**, trend of the municipality's **NUTS 3 region**, of its **coast x density class**, and the own trend **shrunk**
# toward the region's by empirical Bayes. No machine learning: a more complex model has to beat these first.
#
# **Validation:** rolling origin. At each origin from 2019 to 2023 every method sees only years up to it and forecasts one and
# two years ahead; all methods are scored on the same municipalities. Scores: RMSE (log points), and how well the predicted
# change ranks the actual change (Spearman, and the share of the predicted top fifth that is in the actual top fifth; chance is
# 20%), for municipalities and aggregated to the 24 NUTS 3 regions and the six classes. **Selection rule, fixed before
# looking:** lowest mean municipal RMSE over both horizons; a tie within 1% goes to the simpler method. Intervals are
# empirical quantiles of the errors from other origins, checked by leaving each origin out.
#
# **What the outlook is, and is not.** Because the common swing (2023's jump, the 2025 price surge) is not predictable from
# municipal history and the simulator already carries the national path, the outlook is expressed **relative to the median
# municipality**. It ranks places; it does not give their level.

# %%
import numpy as np
import pandas as pd

from pthousing.analysis import regional_forecast as R
from pthousing.config import TABLES
from pthousing.viz import charts, dashboard, maps, style

style.apply_style()
panel = dashboard.load_panel()
y, groups = R.history(panel)
print(f"{len(y)} mainland municipalities, {y.columns.min()} to {y.columns.max()}")
print("with a value per year:", y.notna().sum().to_dict())
print("regions:", groups["region"].nunique(), "| classes:", groups["segment"].nunique())

# %% [markdown]
# ## Step 1 — Rolling-origin validation
# Municipal scores first. `rmse_vs_naive` is the method's RMSE over the naive forecast's (below 1 = better).

# %%
bt = R.backtest(y, groups)
print(bt.groupby(["origin", "h"])["muni_code"].nunique().unstack())
muni_acc = R.accuracy(bt)
naive = muni_acc[muni_acc["method"] == "naive"].set_index("h")["rmse"]
muni_acc["rmse_vs_naive"] = muni_acc["rmse"] / muni_acc["h"].map(naive)
muni_acc.round(3)

# %% [markdown]
# ### The same forecasts aggregated to regions and classes
# For a group, the predicted and the actual change are the median over its municipalities. `rmse_relative` removes the
# cross-group mean first: it scores *which groups move more than the others*, not the common swing.

# %%
level_acc = {"municipality": muni_acc}
for name, by in (("NUTS 3 region", "region"), ("coast x density class", "segment")):
    level_acc[name] = R.group_accuracy(R.group_backtest(bt, groups, by))
table = (
    pd.concat(level_acc, names=["level"])
    .reset_index(level=0)
    .drop(columns="level_1", errors="ignore")
)
style.save_table(table.round(4), "p4", "regional_accuracy")
pivot = table.pivot_table(
    index=["level", "method"], columns="h", values=["rmse", "spearman", "top_precision"]
)
pivot.round(3)

# %% [markdown]
# ### Selection and intervals

# %%
chosen = R.select_method(muni_acc)
print("selected:", chosen)
errors = bt[bt["method"] == chosen].assign(error=lambda d: d["actual"] - d["forecast"])
cover = R.interval_coverage(errors).groupby("h")["coverage"].mean()
q = R.error_quantiles(errors)
print("80% coverage, leaving each origin out:", cover.round(3).to_dict())
q.round(3)

# %%
fig = charts.regional_skill(
    {
        "Municipalities": level_acc["municipality"],
        "NUTS 3 regions": level_acc["NUTS 3 region"],
        "Coast x density classes": level_acc["coast x density class"],
    }
)
style.save_fig(fig, "p4", "regional_skill")
fig

# %% [markdown]
# ## Step 2 — The outlook, relative to the median municipality
# Fitted on all data to 2024. The relative change of a group is its median forecast change minus the median
# municipality's, with an 80% interval from the relative errors of the backtest (aggregated the same way).

# %%
HORIZON = 2
END_YEAR = int(y.columns.max()) + HORIZON
out = R.outlook(y, groups, chosen)
out["change"] = out["forecast"] - out["last"]
national = out[out["h"] == HORIZON]["change"].median()
mu = out[out["h"] == HORIZON].copy()
rel_muni = R.relative_errors(bt, chosen)
qm = rel_muni[rel_muni["h"] == HORIZON]["error"].quantile([0.1, 0.9])
mu["relative"] = 100 * (mu["change"] - national)
mu["relative_lo80"] = mu["relative"] + 100 * qm[0.1]
mu["relative_hi80"] = mu["relative"] + 100 * qm[0.9]
mu["pti_last"] = np.exp(mu["last"])
mu["pti_forecast"] = np.exp(mu["forecast"])
mu["change_pct"] = 100 * np.expm1(mu["change"])
cols = ["muni_code", "muni_name", "district", "region", "segment", "pti_last", "pti_forecast"]
cols += ["change_pct", "relative", "relative_lo80", "relative_hi80"]
munis = mu[cols].sort_values("relative", ascending=False)
style.save_table(munis.round(3), "p4", "regional_outlook_municipalities")
print(
    f"median municipality: {100 * np.expm1(national):+.1f}% in {HORIZON} years (trend of 2016-2024)"
)
munis.head(10).round(1)

# %%
by_region = R.outlook_summary(
    out, "region", HORIZON, R.relative_errors(bt, chosen, groups, "region")
)
by_segment = R.outlook_summary(
    out, "segment", HORIZON, R.relative_errors(bt, chosen, groups, "segment")
)
style.save_table(by_region.round(3), "p4", "regional_outlook_regions")
style.save_table(by_segment.round(3), "p4", "regional_outlook_classes")
by_segment.round(2)

# %%
fig = charts.outlook_ranking(
    by_region.rename(columns={"region": "label"}), "NUTS 3 region", "regions", HORIZON, END_YEAR
)
style.save_fig(fig, "p4", "regional_outlook_regions")
fig

# %%
fig = charts.outlook_ranking(
    by_segment.rename(columns={"segment": "label"}),
    "coast x density class",
    "classes",
    HORIZON,
    END_YEAR,
)
style.save_fig(fig, "p4", "regional_outlook_classes")
fig

# %%
geometry = maps.municipality_geometry()
values = munis.set_index("muni_code")["relative"]
fig = maps.choropleth(
    values, geometry, [-20, -10, 0, 10, 20], style.diverging_ramp(3),
    f"The expected pattern to {END_YEAR} is a coastal and urban premium, but single municipalities are noisy",
    f"Expected change in price-to-income {y.columns.max()} to {END_YEAR} relative to the median municipality (percentage points); blue: less than the median, red: more",
    "Source: INE, CAOP 2024; own calculations. Class trend of 2016-2024 (a boom). 80% interval of a municipality: -20 to +14 points. Islands not covered.",
    "Points vs median municipality", fmt="{:+g}",
)  # fmt: skip
style.save_fig(fig, "p4", "regional_outlook_map")
fig

# %% [markdown]
# ## Step 3 — Checks
# 1. **Does the choice of method change the ranking?** Rank correlation of the municipal outlooks between methods.
# 2. **Does the result depend on the 2023 origin** (the only origin whose target year is 2024, after the jump)?
# 3. **Is the national level consistent with the simulator?**

# %%
names = ("own_trend", "region_trend", "segment_trend", "shrunk_trend")
outs = {m: R.outlook(y, groups, m, (HORIZON,)).set_index("muni_code") for m in names}
chg = pd.DataFrame({m: o["forecast"] - o["last"] for m, o in outs.items()})
print("rank correlation of the predicted change between methods")
chg.corr(method="spearman").round(2)

# %%
alt_bt = R.backtest(y, groups, origins=(2019, 2020, 2021, 2022))
alt = R.accuracy(alt_bt)
alt_naive = alt[alt["method"] == "naive"].set_index("h")["rmse"]
alt["rmse_vs_naive"] = alt["rmse"] / alt["h"].map(alt_naive)
print("selected without the 2023 origin:", R.select_method(alt))
alt[alt["method"].isin(["naive", "region_trend", "segment_trend", "shrunk_trend"])].round(3)

# %%
paths = pd.read_csv(TABLES / "p4" / "scenario_paths.csv")
is_end = (paths["scenario"] == "baseline") & (paths["metric"] == "pti_years")
sim = paths[is_end & (paths["year"] == END_YEAR)]["p50"].iloc[0]
base = panel[panel["year"] == y.columns.max()]["pti_years"].median()
print(
    f"simulator baseline: {100 * (sim / base - 1):+.0f}% {y.columns.max()} to {END_YEAR} "
    "(pinned to the national forecast, which includes 2025's price rise)"
)
print(
    f"municipal trend of 2016-2024: {100 * np.expm1(national):+.0f}%: the level is the simulator's job"
)
# %% [markdown]
# ## What this says
# See `reports/p4_forecast.md` (regional outlook) for the reading and the limits. Tables: `reports/tables/p4/regional_*.csv`.
