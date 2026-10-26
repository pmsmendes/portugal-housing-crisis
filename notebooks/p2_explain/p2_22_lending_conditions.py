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
# # P2.22 — Lending conditions: maturity, loan-to-value and the deposit
#
# **Questions:** RQ9.3 (how have credit availability and lending standards affected access to ownership?) and, for the first-home
# guarantee, RQ6.4 (how effective is first-home purchase support?). `p2_12` covered the credit stock (it fell while prices doubled);
# `p2_13` what wages and rates could finance. This notebook adds the **terms** of new loans.
#
# **What the data allow.** The Banco de Portugal publishes the loan-to-value (LTV), debt-service-to-income (DSTI) and maturity of new
# housing loans in a yearly monitoring report. The March 2025 report (covering 2024) is transcribed by hand in
# `data/external/lending_standards.csv`: a few points. The March 2026 report (covering 2025) comes with the data of its charts, read into
# `data/external/lending_series.csv`: yearly series from the third quarter of 2018 to 2025 (maturity quarterly), so the terms can be
# followed through the State guarantee. Two accounting exercises on top (`analysis/lending.py`): (1) at a fixed
# payment, the loan a household can carry grows with the term, by the ratio of annuity factors at the rate of the year; (2) the cash
# needed on the day of purchase (the part of the price not lent plus buying costs, `config.py`) in years of income, by LTV, and the
# payment burden by LTV and term. No behaviour, no estimate of who is turned down (rejected applications are not observed).
#
# **Reading rule, fixed before looking:** terms and LTV "explain" the rise of prices if the largest loan gain allowed by the longest
# legal term is of the same order as the real price rise since 2013; "access" is eased by the guarantee if it brings the median
# municipality's cash need below one year of income. The reports have nothing before the Recommendation of July 2018, so what they say
# about standards covers 2018-2025 only; the 2013-2018 part of the price rise (a third of the 2013-2024 rise) is not observed.

# %%
import pandas as pd

from pthousing.analysis import lending, macro
from pthousing.config import BUYING_COSTS_PCT, PROCESSED
from pthousing.data import interim
from pthousing.viz import charts, style

style.apply_style()
YEAR = 2024
table = lending.read()
series = lending.read_series()
long = pd.read_parquet(PROCESSED / "national_annual_long.parquet").set_index("year")
panel = pd.read_parquet(PROCESSED / "panel_municipality_year.parquet")
d = panel[panel["year"] == YEAR].set_index("muni_code")
rates = macro.annual_rates(interim.read("bp_mortgage"))
price_rise = 100 * (long.loc[2024, "hpi_real_b2015"] / long.loc[2013, "hpi_real_b2015"] - 1)
print(
    f"real prices {price_rise:.0f}% 2013-2024; mortgage rate 2013 {rates[2013]:.2f}%, 2021 {rates[2021]:.2f}%, 2024 {rates[2024]:.2f}%"
)

# %% [markdown]
# ## Step 1 — What the report says (2024)
# The Recommendation of the Banco de Portugal limits LTV (90% for the own permanent home, from July 2018), DSTI (50%, with exceptions,
# from April 2020) and the average term (30 years, from April 2022). The transcribed figures, by indicator.

# %%
shown = table.dropna(subset=["value"]).copy()
style.save_table(table, "p2", "lending_standards")
print(shown[["indicator", "period", "value", "unit"]].to_string(index=False))

# %% [markdown]
# ## Step 1b — The terms year by year, 2018-2025
# Loans above 90% of the value (the Recommendation's ceiling for the own home, with exceptions), high-risk loans (DSTI above 60% and/or LTV
# above 90%), mean LTV, mean actual DSTI, share of borrowers up to 35 and mean maturity, from the chart data of the March 2026 report.
# 2018 is the third quarter only. The 2024 DSTI of this report (29.7%) is not the 26.2% of the 2025 edition (a different definition), so
# the DSTI is read within this series only.

# %%
standards = lending.standards_by_year(series)
style.save_table(standards.round(2).reset_index(), "p2", "lending_series")
print(standards.round(1).to_string())
quarterly = (
    series[series["indicator"].isin(["maturity_weighted_mean", "maturity_weighted_mean_guarantee"])]
    .loc[lambda x: x["period"].str.contains("-Q")]
    .pivot(index="period", columns="indicator", values="value")
    .reindex(columns=["maturity_weighted_mean", "maturity_weighted_mean_guarantee"])
)
price_rise_2025 = 100 * (long.loc[2025, "hpi_real_b2015"] / long.loc[2024, "hpi_real_b2015"] - 1)
price_rise_1825 = 100 * (long.loc[2025, "hpi_real_b2015"] / long.loc[2018, "hpi_real_b2015"] - 1)
g = series.set_index(["indicator", "period"])["value"]
guarantee = pd.DataFrame(
    {
        "real_price_rise_2024_2025_pct": [price_rise_2025],
        "real_price_rise_2018_2025_pct": [price_rise_1825],
        "guarantee_share_contracts_pct": [g[("guarantee_share_contracts", "2025")]],
        "guarantee_share_amount_pct": [g[("guarantee_share_amount", "2025")]],
        "risk_high_no_guarantee_pct": [g[("risk_share_high_no_guarantee", "2025")]],
        "dsti_mean_guarantee_pct": [g[("dsti_actual_mean_guarantee", "2025")]],
        "ltv_mean_guarantee_pct": [g[("ltv_weighted_mean_guarantee", "2025")]],
        "maturity_mean_guarantee_years": [quarterly["maturity_weighted_mean_guarantee"].mean()],
        "quarters_above_30_years_n": [int((quarterly["maturity_weighted_mean"] > 30).sum())],
        "quarters_n": [len(quarterly)],
    }
)
style.save_table(guarantee.round(2), "p2", "lending_guarantee_2025")
print(guarantee.round(1).T.to_string(header=False))

# %%
fig = charts.lending_standards(standards, quarterly)
style.save_fig(fig, "p2", "lending_standards")
fig

# %% [markdown]
# ## Step 2 — What a longer term buys
# Loan carried by the same monthly payment against a 30-year term, at the mean agreed rate of new loans of 2013, 2021 and 2024. The
# peak mean term (33.7 years, January 2021) and the longest term the Recommendation allows for borrowers up to 30 (40 years).

# %%
TERMS = {"30 years": 30, "33.7 years (mean term, Jan 2021)": 33.7, "40 years (longest allowed)": 40}
maturity = lending.maturity_table(rates.loc[[2013, 2021, 2024]], TERMS, base="30 years")
style.save_table(maturity.round(2), "p2", "lending_maturity_capacity")
print(maturity.round(1).to_string(index=False))
rate_effect = lending.rate_effect_pct(rates[2021], rates[2024], 30)
print(
    f"the rate rise 2021 to 2024 alone cut what a payment carries by {rate_effect:.0f}% at a 30-year term"
)
term_2018 = lending.value(table, "maturity_weighted_mean", "2018-07")
term_2024 = lending.value(table, "maturity_weighted_mean", "2024-12")
term_effect = lending.capacity_gain_pct(rates[2024], term_2018, term_2024)
price_rise_1824 = 100 * (long.loc[2024, "hpi_real_b2015"] / long.loc[2018, "hpi_real_b2015"] - 1)
print(
    f"the fall of the mean term from {term_2018:.1f} to {term_2024:.1f} years changed what a payment carries by {term_effect:.1f}% at the 2024 rate; "
    f"real prices {price_rise_1824:.0f}% 2018-2024"
)
style.save_table(
    pd.DataFrame(
        {
            "real_price_rise_pct": [price_rise],
            "real_price_rise_2018_2024_pct": [price_rise_1824],
            "rate_rise_capacity_cut_pct": [rate_effect],
            "term_change_capacity_pct": [term_effect],
            "buying_costs_pct": [BUYING_COSTS_PCT],
        }
    ).round(1),
    "p2",
    "lending_headline",
)

# %% [markdown]
# ## Step 3 — The deposit and the payment, by loan-to-value
# Median municipality, 2024: cash needed on the day of purchase in years of income (the municipality's median home and median income;
# `pti_years`) at 80% (the project's assumption), 90% (the legal maximum for the own home) and 100% (the State guarantee for borrowers
# up to 35 covers up to 15% of the price), and the payment burden at the 2024 rate against the 50% DSTI cap (a rough proxy: DSTI is on
# net income and with a rate shock).

# %%
LTVS = {"80%": 0.8, "90% (limit)": 0.9, "100% (guarantee)": 1.0}
deposit = lending.deposit_years(d["pti_years"].dropna(), LTVS, BUYING_COSTS_PCT)
cash = lending.cash_summary(deposit)
style.save_table(cash.round(2).rename_axis("ltv").reset_index(), "p2", "lending_cash_needed")
print(cash.round(2).to_string())
burden = lending.burden_table(d, rates[YEAR], LTVS, {"30 years": 30, "40 years": 40}, limit_pct=50)
style.save_table(burden.round(2), "p2", "lending_burden")
print(burden.round(1).to_string(index=False))

# %%
fig = charts.lending_conditions(maturity, cash, price_rise, BUYING_COSTS_PCT)
style.save_fig(fig, "p2", "lending_conditions")
fig

# %% [markdown]
# ## Findings
#
# 1. **Standards tightened from 2018 to 2024, then loosened in 2025 (RQ9.3).** Since the Recommendation (July 2018) the mean term of
#    new housing loans fell from 33.4 to 31.0 years (peak 33.7 in January 2021, 29.7 in July 2024; EU countries with data 20 to 27), loans
#    above 90% of the value from 20.5% (third quarter of 2018) to 0.1% in 2024, and high-risk loans (DSTI above 60% and/or LTV above 90%)
#    from 31.6% to 6.1% in 2019 and 2.9% in 2024; the mean LTV fell from 77.9% to 69.9% (68.5% in 2023). In 2025 it reversed: loans above
#    90% of the value 19.4%, high-risk loans 21.4%, mean LTV 75.4%, mean term back to 31.9 years, while real prices rose 14.9% in the year
#    (70.7% since 2018). Without the State guarantee the high-risk share stayed at 2.6%, so the loosening is the guarantee's (loans
#    under it: mean LTV 99.2%, mean DSTI 33.7% against 29.6% for all loans, mean term 37.8 years). Mean actual DSTI rose from 25.3% to 29.7%
#    with rates (2018 to 2024). The mean term was above the 30-year reference of the Recommendation in all 29 quarters. The reports have
#    nothing before July 2018, so they cannot say whether standards fed the 34% rise of real prices in 2013-2018 (a third of the 2013-2024
#    rise of 100%).
# 2. **A longer term cannot account for the price rise.** At the mean rate of the year the longest term allowed (40 years, for borrowers up
#    to 30) carries a loan 17% larger than 30 years at the 2013 rate (3.3%), 29% at the 2021 rate (0.7%) and 13% at the 2024 rate (4.4%); the
#    2021 mean term of 33.7 years carries 7%, 11% and 6% more. That is a ceiling that was not reached: the actual mean term fell from 33.4 to
#    31.0 years between 2018 and 2024, which by itself cut what a payment carries by 3.4% at the 2024 rate. The rise in the rate from 0.7% to
#    4.4% cut it by 39% at a fixed 30 years. By the reading rule (a gain of the order of the 2013-2024 price rise), terms and LTV do not
#    explain it: the largest gain is under a third of it. Against the 49% of 2018-2024 the ceiling (13% to 29%) is less negligible, but the
#    realised term moved the other way.
# 3. **The deposit is the barrier that the guarantee removes; the payment is the one it leaves (RQ6.4, partly).** In the median
#    municipality cash on the day of purchase (deposit plus 6% costs) is 2.5 years of income at an 80% loan, 1.5 at the legal maximum
#    of 90% and 0.6 with the State guarantee for borrowers up to 35 (up to 15% of the price, loans up to 100% of it); 94%, 74% and 13% of
#    municipalities need more than a year. But the payment on a 100% loan is 57% of gross income in the median municipality at 30 years
#    (45% at 80%) and 50% at 40 years, with 57% and 50% of municipalities above 50% of gross income. The 40-year term is allowed only for
#    borrowers up to 30 (37 years up to 35), and the DSTI cap is on net income with a rate shock, so this is a rough proxy that probably
#    understates the test banks apply. Access eased by the guarantee by the reading rule (cash below one year), but it is bounded by the
#    payment.
# 4. **Young borrowers came into the market, through the guarantee.** The share of new loans to borrowers up to 35 was 37% to 43% in
#    2018-2024 and 54.0% in 2025, with the IMT and stamp-duty exemption of August 2024 (27% in July 2024, 47% in August) and the State
#    guarantee from the last quarter of 2024; the guarantee was 15.0% of new contracts and 19.8% of the amount lent in 2025 (16% to 17% and
#    21% to 23% from April). The coincidence in time of the loosening, the guarantee and a 14.9% rise of real prices in 2025 is not a test: one
#    year, national, and the exemption and the rate fall are also in it.
#
# **Limits.** The terms are a yearly series only from the third quarter of 2018 to 2025 (the first year is a quarter; maturity is
# quarterly), from one report's chart data; the DSTI of this edition differs from the 2025 edition's (29.7% against 26.2% for 2024), so
# it is read within the series; only loans granted are observed (applications turned down are not), and nothing is estimated over time:
# the 2025 loosening and the price rise are not linked by any design here; the capacity and cash figures are accounting at the national
# mean rate and the benchmark buying costs, not what households did; the burden proxy uses gross median income, a flat-rate annuity and
# no rate shock; the guarantee covers borrowers up to 35 only and its effect on prices is not estimated; the real price rise is the
# national index from BIS and OECD data, not local prices. The notebook cannot say whether credit rationing held prices down before
# 2018: no loan-level data.
