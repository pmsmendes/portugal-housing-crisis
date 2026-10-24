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
# # P1.08 — Kinds of home and kinds of price
#
# **Questions:** RQ1.2 (prices by property type) and RQ1.8 (the gap between asking and transaction prices), each only in part.
# Prices by number of rooms (T0 to T4+) are not published, so the types here are the two the data give: **new against existing
# homes** (INE transaction values, 2019 onward) and **flats against villas** (bank appraisals, 2011 onward). Asking prices are
# not available either; the one gap between two price measures we can build is **appraisal against transaction price**.
#
# Appraisals are annual and suppressed for small municipalities, so trends use the same municipalities in every year; the
# series with all municipalities is shown beside it because the sample grows.

# %%
import pandas as pd

from pthousing.analysis import price_types as pt
from pthousing.data import harmonize, interim
from pthousing.viz import charts, dashboard, style

style.apply_style()
panel = dashboard.load_panel()
valuation = interim.read("ine_bank_valuation_annual")
deflator = harmonize.annual_deflator(interim.read("ine_cpi"))

# %% [markdown]
# ## Step 1 — New against existing homes
# Premium of the price per m² of new homes over existing ones, and real price indexes (2019 = 100), for municipalities that have
# both in every year 2019 to 2025. The premium by class is for 2019 and 2025, municipalities with both prices that year.

# %%
premium = pt.new_vs_existing(panel, 2019, 2025)
style.save_table(premium.round(2).reset_index(), "p1", "new_vs_existing")
by_class = pd.concat(
    {
        f"{by}, {year}": pt.premium_by_class(panel, year, by)
        for by in ("density_class", "coast_class")
        for year in (2019, 2025)
    },
    names=["grouping", "class"],
).round(1)
style.save_table(by_class.reset_index(), "p1", "new_premium_by_class")
print(premium.round(1).to_string())
by_class

# %% [markdown]
# ## Step 2 — Flats against villas
# Appraised value per m², real terms. Per year the median ratio over municipalities with both types (the sample changes, so the
# ratio, which is within a municipality, is the safe comparison); the change 2011 to 2025 over the municipalities with both
# types in both years.

# %%
flats = pt.flats_vs_villas(valuation, deflator)
change = pt.valuation_change(valuation, deflator, 2011, 2025)
style.save_table(flats.round(2).reset_index(), "p1", "flats_vs_villas")
style.save_table(change.round(1).reset_index(names="type"), "p1", "flats_vs_villas_change")
print(change.round(1).to_string())
flats.round(2).T

# %% [markdown]
# ## Step 3 — Appraisal against transaction price
# Appraised value over the median transaction value per m², same municipality, 2016 to 2025. The two differ in timing (appraisals
# are the year's, transactions the twelve months to the fourth quarter) and in what they measure, so the level of the ratio
# says little; its drift and whether appraisals lead or follow transaction prices say more.

# %%
appraisal = pt.appraisal_vs_transaction(panel, 2016, 2025)
leadlag = pt.growth_leadlag(panel, 2016, 2025, range(-2, 3))
style.save_table(appraisal.round(3).reset_index(), "p1", "appraisal_vs_transaction")
style.save_table(leadlag.round(3), "p1", "appraisal_growth_leadlag")
fig = charts.price_kinds(premium, flats, appraisal)
style.save_fig(fig, "p1", "price_kinds")
print(leadlag.round(2).T.to_string())
appraisal.round(2).T

# %% [markdown]
# ## Key numbers

# %%
p = premium
print(
    f"new-build premium {p['median_premium_pct'].iloc[0]:.1f}% (2019) to {p['median_premium_pct'].iloc[-1]:.1f}% (2025), {int(p['municipalities_n'].iloc[0])} municipalities; "
    f"new dearer in {p['share_new_dearer_pct'].iloc[0]:.0f}% then {p['share_new_dearer_pct'].iloc[-1]:.0f}%; real index 2025: new {p['new_real_index'].iloc[-1]:.0f}, existing {p['existing_real_index'].iloc[-1]:.0f}"
)
print(
    f"flats over villas {flats['flats_to_villas'].loc[2011]:.2f} (2011) to {flats['flats_to_villas'].iloc[-1]:.2f} ({flats.index[-1]}); "
    f"real change 2011-2025: flats {change.loc['flats', 'median_real_change_pct']:+.0f}%, villas {change.loc['villas', 'median_real_change_pct']:+.0f}% ({int(change['municipalities_n'].iloc[0])} municipalities)"
)
a = appraisal
print(
    f"appraisal over transaction: balanced {a['balanced_median'].iloc[0]:.2f} (2016) to {a['balanced_median'].iloc[-1]:.2f} (2025), n {int(a['balanced_n'].iloc[0])}; "
    f"all with both {a['all_median'].iloc[0]:.2f} to {a['all_median'].iloc[-1]:.2f} (n {int(a['all_n'].iloc[0])} to {int(a['all_n'].iloc[-1])})"
)
