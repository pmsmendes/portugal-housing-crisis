"""Public spending on housing, Portugal and peers (RQ8.1; peer comparison for RQ6.5).

General-government expenditure by function (COFOG), annual: housing development (GF0601, public housing included) and
housing in social protection (GF1006, housing allowances and rent subsidies). Their sum is "housing support" here.
It leaves out tax expenditures (IRS deductions, IMT and IMI exemptions), loan guarantees and the part of programmes
financed and spent by other bodies; housing and community amenities (GF06) also holds water supply and street lighting, so
it is not used as housing spending. Functions take interim tables; nothing here reads files.
"""

import pandas as pd

from pthousing.data.harmonize import annual_deflator

PARTS = ("housing_development_eur_m", "housing_benefits_eur_m")


def support_shares(spending: pd.DataFrame) -> pd.DataFrame:
    """Housing support (development plus benefits) as a percentage of GDP, years as rows and countries as columns.

    ``spending`` is the ``eurostat_housing_spending`` interim table. A country-year is NaN if either part is missing.
    """
    d = spending.assign(support=spending[list(PARTS)].sum(axis=1, min_count=2))
    d["support_gdp_pct"] = 100 * d["support"] / d["gdp_eur_m"]
    return d.pivot(index="year", columns="geo", values="support_gdp_pct")


def portugal_frame(
    spending: pd.DataFrame, cpi: pd.DataFrame, tax: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Portugal's housing spending in current and constant euros, as a share of GDP, and against property-tax revenue.

    ``cpi`` is the ``ine_cpi`` table (constant ``BASE_YEAR`` euros); ``tax`` the ``eurostat_property_tax`` table, whose
    IMI and IMT revenue (``property_tax_eur_m``) is set beside the spending as ``spending_per_tax_pct``.
    """
    d = spending[spending["geo"] == "PT"].set_index("year").drop(columns="geo")
    d["support_eur_m"] = d[list(PARTS)].sum(axis=1, min_count=2)
    deflator = annual_deflator(cpi).reindex(d.index)
    for col in (*PARTS, "support_eur_m"):
        d[col.replace("_eur_m", "_real_eur_m")] = d[col] * deflator
    d["support_gdp_pct"] = 100 * d["support_eur_m"] / d["gdp_eur_m"]
    if tax is not None:
        t = tax.set_index("year")
        d["property_tax_eur_m"] = (t["imi_revenue_eur_m"] + t["imt_revenue_eur_m"]).reindex(d.index)
        d["spending_per_tax_pct"] = 100 * d["support_eur_m"] / d["property_tax_eur_m"]
    return d
