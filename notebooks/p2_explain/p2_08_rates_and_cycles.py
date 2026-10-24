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
# # P2.08 — Mortgage rates and the price cycle
#
# **Questions:** RQ1.7 (how have mortgage rates affected ownership affordability?), RQ9.2 (rates and prices), RQ9.5 (how
# did crises and monetary shifts affect affordability and construction?). Complements `p1_01`/`p1_02`, which show that the
# rate drives the *burden* of buying; here the question is whether it also moves the *price*.
#
# National quarterly series, 2003 to 2026: real and nominal house price index (BIS, INE's from 2009), the agreed rate on new
# housing loans (Banco de Portugal) and the payment it implies. Association in time only: the rate is set for the euro area,
# is persistent, and 23 years hold two or three regimes. Total new lending is not available (the loan volume we hold covers
# loans fixed for up to a year), so credit supply is not tested (RQ9.3 stays open).

# %%
import pandas as pd

from pthousing.analysis import macro, supply
from pthousing.data import interim
from pthousing.viz import charts, dashboard, style

style.apply_style()
frame = macro.quarterly_frame(interim.read("bis_spp"), interim.read("bp_mortgage"))
changes = macro.add_changes(frame)
completions = supply.national_flows(dashboard.load_panel())["completed_n"]
print(
    f"{frame.index.min():%Y-Q}{frame.index.min().quarter} to {frame.index.max():%Y}-Q{frame.index.max().quarter}, {len(frame)} quarters"
)

# %% [markdown]
# ## Step 1 — Episodes
# Boundaries come from the data, not from the outcome: the quarter before the 2008 financial crisis broke out (Q3 2008), the
# low of the real price index, the low of the rate after it, the rate's peak and the last quarter.

# %%
price, rate = frame["hpi_real_b2010"], frame["mortgage_rate_new_lt1y_pct"]
crisis = "2008Q3"
trough = price.loc["2008-07-01":].idxmin()
rate_low = rate.loc[trough:].idxmin()
rate_high = rate.loc[rate_low:].idxmax()
q = lambda t: f"{t.year}Q{t.quarter}"  # noqa: E731
last = q(frame.index[-1])
windows = {
    "before the crisis": ("2003Q1", "2008Q2"),
    "crisis and troika": (crisis, q(trough)),
    "recovery, falling rates": (q(trough), q(rate_low)),
    "rate shock": (q(rate_low), q(rate_high)),
    "since the peak": (q(rate_high), last),
}
epis = macro.episodes(frame, windows, completions)
style.save_table(epis.round(1).reset_index(names="episode"), "p2", "rate_episodes")
epis.round(1)

# %% [markdown]
# ## Step 2 — Does a rate change time the price?
# Correlation of a year's real price growth with the rate change over the year `k` quarters earlier. With overlapping annual
# changes there is about one independent observation a year, so the band is wide.

# %%
profile = macro.lag_profile(changes, "growth_real_pct", "rate_change_pp", range(-4, 9))
fig = charts.rates_and_cycles(frame, epis, profile)
style.save_fig(fig, "p2", "rates_and_cycles")
style.save_table(profile.round(3), "p2", "rate_lag_profile")
profile.round(2).T

# %% [markdown]
# ## Step 3 — A pre-specified timing test
# Price growth over a year on the rate change over the year before (the lag equals the window, so the two do not overlap; chosen
# before looking at the profile), Newey-West standard errors. Add last year's price growth (momentum), a placebo (the rate
# change of the year *after*), nominal prices (real prices fall mechanically when inflation jumps), and the two halves of the
# sample.

# %%
specs = {
    "rate change only": {},
    "+ last year's growth": {"own_lag": True},
    "+ placebo: next year's rate change": {"own_lag": True, "lead": True},
    "nominal prices": {"y": "growth_nominal_pct", "own_lag": True},
    "2003-2013": {"own_lag": True, "sample": ("2003", "2013")},
    "2014-2026": {"own_lag": True, "sample": ("2014", "2026")},
}
timing = pd.DataFrame({k: macro.rate_timing(changes, **v) for k, v in specs.items()}).T
style.save_table(timing.round(3).reset_index(names="specification"), "p2", "rate_timing")
timing.round(3)

# %% [markdown]
# ## Key numbers

# %%
e = epis
shock = e.loc["rate shock"]
print(
    f"rate shock {shock['start']}-{shock['end']}: rate {shock['rate_start_pct']:.1f}% to {shock['rate_end_pct']:.1f}%, "
    f"payment {shock['payment_change_pct']:+.0f}%, real price {shock['real_price_change_pct']:+.0f}% "
    f"(nominal {shock['nominal_price_change_pct']:+.0f}%)"
)
print(
    "crisis: real price",
    f"{e.loc['crisis and troika', 'real_price_change_pct']:+.0f}%, completions per year",
    f"{e.loc['crisis and troika', 'completions_per_year_n']:,.0f} against {e.loc['before the crisis', 'completions_per_year_n']:,.0f} before",
)
for name, row in timing.iterrows():
    print(
        f"{name}: {row['coef_pct_per_pp']:+.2f} points per pp [{row['ci_low']:+.2f}, {row['ci_high']:+.2f}], p={row['p_value']:.2f}, n={int(row['n'])}"
    )
