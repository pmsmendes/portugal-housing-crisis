"""Portugal against peer countries: house prices, property taxation and housing spending (RQ6.5, partly).

Three comparable national indicators over one window: the change of the house price index, the recurrent property tax
(national accounts D29A, taxes on land, buildings and other structures) and housing support (housing development plus
housing allowances, ``spending``), the last two as shares of GDP averaged over the window. Transfer taxes are left out:
countries book them under different codes. Housing policy proper (rent regulation, tenure protection, planning rules) is
not in these data, so this says how much a country taxes and spends, not which policies it has. Functions take interim
tables; nothing here reads files.
"""

import pandas as pd

from pthousing.analysis import spending


def price_change(hpi: pd.DataFrame, start: int, end: int) -> pd.Series:
    """Percentage change of the annual mean house price index (nominal) from ``start`` to ``end``, by country."""
    annual = hpi.groupby(["geo", "year"])["hpi_index_b2015"].mean().unstack("year")
    return (100 * (annual[end] / annual[start] - 1)).rename("price_change_pct")


def property_tax_share(tax: pd.DataFrame, start: int, end: int) -> pd.Series:
    """Mean recurrent property tax (D29A) as a percentage of GDP over ``start`` to ``end``, by country."""
    d = tax[tax["year"].between(start, end)].copy()
    d["share"] = 100 * d["land_buildings_tax_eur_m"] / d["gdp_eur_m"]
    return d.groupby("geo")["share"].mean().rename("property_tax_gdp_pct")


def policy_mix(
    hpi: pd.DataFrame,
    tax: pd.DataFrame,
    housing: pd.DataFrame,
    start: int = 2015,
    end: int = 2024,
    exclude_spending: tuple[str, ...] = (),
) -> pd.DataFrame:
    """One row per country: price change, mean property tax and mean housing support, over ``start`` to ``end``.

    ``hpi`` is ``eurostat_hpi``, ``tax`` ``eurostat_property_tax_peers`` and ``housing`` ``eurostat_housing_spending``.
    Countries in ``exclude_spending`` get no housing-support value (their series is distorted in the window).
    """
    shares = (
        spending.support_shares(housing).loc[start:end].mean().rename("housing_support_gdp_pct")
    )
    out = pd.concat(
        [price_change(hpi, start, end), property_tax_share(tax, start, end), shares], axis=1
    )
    out.loc[[g for g in exclude_spending if g in out.index], "housing_support_gdp_pct"] = float(
        "nan"
    )
    return out.rename_axis("geo")
