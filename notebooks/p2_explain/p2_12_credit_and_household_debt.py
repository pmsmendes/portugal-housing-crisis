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
# # P2.12 — Mortgage credit, household debt and the price cycle
#
# **Questions:** RQ9.2 (rates, mortgage lending, household debt and prices; `p2_08` covered the rates), RQ9.3 (did credit
# availability shape access to ownership?). Companion of `p2_08` and `p2_09`.
#
# National quarterly series, 2007 Q4 to 2026 Q2: the stock of household loans for house purchase and total household debt
# (Banco de Portugal, domain 18, all lenders), against the BIS real and nominal house price index. Both are deflated with the
# price index's own deflator. Lending standards (loan-to-value, maturity, income multiples) are not available, so this
# describes how much credit there was, not how easy it was to get. Association in time only, two credit regimes in 18 years.

# %%
import pandas as pd

from pthousing.analysis import credit, macro
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
frame = credit.quarterly_frame(interim.read("bis_spp"), interim.read("bp_household_debt"))
changes = credit.add_changes(frame)
print(
    f"{frame.index.min():%Y}-Q{frame.index.min().quarter} to {frame.index.max():%Y}-Q{frame.index.max().quarter}, {len(frame)} quarters"
)

# %% [markdown]
# ## Step 1 — Episodes
# Boundaries come from the credit and price series, not from an outcome: the peak of the real housing-loan stock, the low of
# the real price index after it, the low of the real loan stock, and the last quarter.

# %%
loans, price = frame["housing_loans_real_eur_m"], frame["hpi_real_b2010"]
peak = loans.idxmax()
price_low = price.loc[peak:].idxmin()
loans_low = loans.loc[price_low:].idxmin()
q = lambda t: f"{t.year}Q{t.quarter}"  # noqa: E731
first, last = q(frame.index[0]), q(frame.index[-1])
windows = {
    "credit still growing": (first, q(peak)),
    "crisis and troika": (q(peak), q(price_low)),
    "prices recover, credit shrinks": (q(price_low), q(loans_low)),
    "credit revives": (q(loans_low), last),
}
epis = credit.episodes(frame, windows)
style.save_table(epis.round(1).reset_index(names="episode"), "p2", "credit_episodes")
epis.round(1)

# %% [markdown]
# ## Step 2 — Which comes first, price growth or credit growth?
# Correlation of a year's real price growth with housing-loan growth (transactions-based, so write-offs and sales of loans do not
# count) shifted by each lag. A positive lag is credit growth that came earlier, a negative lag credit growth that came later.
# With overlapping annual changes there is about one independent observation a year, so the band is wide.

# %%
profile = macro.lag_profile(changes, "growth_real_pct", credit.GROWTH_COLUMN, range(-8, 13))
fig = charts.credit_and_prices(frame, profile)
style.save_fig(fig, "p2", "credit_and_prices")
style.save_table(profile.round(3), "p2", "credit_lag_profile")
profile.round(2).T

# %% [markdown]
# ## Step 3 — A pre-specified timing test
# As in `p2_08`: price growth over a year on credit growth over the year before (the lag equals the window, so the two do not
# overlap), Newey-West errors. Added in turn: last year's price growth (momentum), a placebo (credit growth of the year *after*),
# the same year, the stock in real terms instead of the flow, and the two halves of the sample. A credit fall that precedes a
# price rise is a regime pattern (credit shrank in 2011-2019 while prices recovered), not evidence that credit cuts prices.

# %%
specs = {
    "credit growth a year earlier": {},
    "+ last year's price growth": {"own_lag": True},
    "+ placebo: next year's credit growth": {"own_lag": True, "lead": True},
    "same year": {"lag": 0},
    "real stock instead of flow": {"x_col": "loans_real_growth_pct", "own_lag": True},
    "2008-2015": {"own_lag": True, "sample": ("2008", "2015")},
    "2016-2026": {"own_lag": True, "sample": ("2016", "2026")},
}
timing = pd.DataFrame({k: credit.credit_timing(changes, **v) for k, v in specs.items()}).T
style.save_table(timing.round(3).reset_index(names="specification"), "p2", "credit_timing")
timing.round(3)

# %% [markdown]
# ## Key numbers

# %%
e = epis
for name, row in e.iterrows():
    print(
        f"{name} {row['start']}-{row['end']}: real price {row['real_price_change_pct']:+.0f}%, real housing loans "
        f"{row['loans_real_change_pct']:+.0f}% (nominal {row['loans_nominal_change_pct']:+.0f}%), loans per unit of price "
        f"{row['loans_per_price_change_pct']:+.0f}%, loans/GDP {row['loans_gdp_change_pp']:+.1f} pp, debt/income "
        f"{row['debt_income_start_pct']:.0f}% to {row['debt_income_end_pct']:.0f}%"
    )
f0, f1 = frame.iloc[0], frame.iloc[-1]
print(
    f"{first} to {last}: housing loans {f0['housing_loans_gdp_pct']:.0f}% to {f1['housing_loans_gdp_pct']:.0f}% of GDP, "
    f"household debt {f0['household_debt_income_pct']:.0f}% to {f1['household_debt_income_pct']:.0f}% of disposable income, "
    f"nominal housing loans €{f0['housing_loans_stock_eur_m'] / 1000:.0f}bn to €{f1['housing_loans_stock_eur_m'] / 1000:.0f}bn, "
    f"real price {100 * (f1['hpi_real_b2010'] / f0['hpi_real_b2010'] - 1):+.0f}%"
)
band = profile["band"].iloc[0]
print(
    "lags outside the band:",
    profile.loc[profile["corr"].abs() > band, ["lag_quarters", "corr"]].round(2).to_dict("records"),
)
for name, row in timing.iterrows():
    extra = (
        f", placebo {row['lead_coef_pct_per_pp']:+.2f} (p={row['lead_p_value']:.2f})"
        if pd.notna(row.get("lead_coef_pct_per_pp"))
        else ""
    )
    print(
        f"{name}: {row['coef_pct_per_pp']:+.2f} points per pp [{row['ci_low']:+.2f}, {row['ci_high']:+.2f}], p={row['p_value']:.2f}, n={int(row['n'])}{extra}"
    )
