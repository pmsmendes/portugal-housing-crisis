"""Buying versus renting: the yearly cost of owning a home as a share of its price, set against the rent.

Definitions are in docs/methodology.md. The owner's cost is the standard user cost of housing, expressed as a
percentage of the price per year and *before* any price gain: interest on the loan, the return forgone on the
deposit, property tax, maintenance and the one-off costs of buying spread over the holding period. Renting costs
the gross rent yield (a year of rent over the price). Owning beats renting when the expected yearly price growth
exceeds the difference, the break-even appreciation. Rates and shares are assumptions held in ``config.py``;
nothing here is estimated from data.
"""

import numpy as np
import pandas as pd

from pthousing.config import (
    BUYING_COSTS_PCT,
    EXPECTED_APPRECIATION_PCT,
    HOLDING_YEARS,
    IMI_TAXABLE_SHARE,
    MAINTENANCE_PCT,
    MORTGAGE_LTV,
    MORTGAGE_TERM_YEARS,
    OPPORTUNITY_RATE_PCT,
)
from pthousing.features import affordability as aff

COMPONENTS = ["interest", "deposit_return", "property_tax", "maintenance", "buying_costs"]


def gross_rent_yield_pct(rent_sqm_eur, price_sqm_eur):
    """Rent yield: 12 months of the per-m2 rent of new leases as a percentage of the per-m2 sale price."""
    return 100 * 12 * rent_sqm_eur / price_sqm_eur


def owner_cost_components(
    mortgage_rate_pct,
    imi_rate_pct,
    ltv=MORTGAGE_LTV,
    opportunity_rate_pct=OPPORTUNITY_RATE_PCT,
    maintenance_pct=MAINTENANCE_PCT,
    buying_costs_pct=BUYING_COSTS_PCT,
    holding_years=HOLDING_YEARS,
    imi_taxable_share=IMI_TAXABLE_SHARE,
) -> pd.DataFrame:
    """Yearly cost of owning, in % of the price, by component (before price gains).

    Interest is on the loan only (principal repaid is saving, not a cost); the deposit costs the return it
    could earn elsewhere; IMI is charged on the taxable value, a share of the market price; the one-off
    costs of buying (IMT, stamp duty, notary and registry) are spread over the years the home is held.
    """
    mortgage_rate, imi_rate = np.broadcast_arrays(
        np.atleast_1d(np.asarray(mortgage_rate_pct, dtype=float)),
        np.atleast_1d(np.asarray(imi_rate_pct, dtype=float)),
    )
    flat = np.ones_like(mortgage_rate)
    index = next(
        (t.index for t in (mortgage_rate_pct, imi_rate_pct) if isinstance(t, pd.Series)), None
    )
    return pd.DataFrame(
        {
            "interest": ltv * mortgage_rate,
            "deposit_return": (1 - ltv) * opportunity_rate_pct * flat,
            "property_tax": imi_taxable_share * imi_rate,
            "maintenance": maintenance_pct * flat,
            "buying_costs": buying_costs_pct / holding_years * flat,
        },
        index=index,
    )[COMPONENTS]


def owner_cost_rate_pct(mortgage_rate_pct, imi_rate_pct, **assumptions):
    """Yearly cost of owning as a % of the price, before price gains (sum of ``owner_cost_components``)."""
    cost = owner_cost_components(mortgage_rate_pct, imi_rate_pct, **assumptions).sum(
        axis=1, skipna=False
    )
    if any(isinstance(t, pd.Series) for t in (mortgage_rate_pct, imi_rate_pct)):
        return cost
    return cost.to_numpy() if cost.size > 1 else float(cost.iloc[0])


def breakeven_appreciation_pct(owner_cost_pct, rent_yield_pct):
    """Yearly nominal price growth at which owning costs the same as renting (negative: owning is cheaper
    even if prices fall)."""
    return owner_cost_pct - rent_yield_pct


def upfront_cash_years(pti_years, ltv=MORTGAGE_LTV, buying_costs_pct=BUYING_COSTS_PCT):
    """Cash needed on the day of purchase (deposit plus buying costs), in years of income."""
    return pti_years * ((1 - ltv) + buying_costs_pct / 100)


def owner_cash_cost_pct(
    mortgage_rate_pct,
    imi_rate_pct,
    ltv=MORTGAGE_LTV,
    term_years=MORTGAGE_TERM_YEARS,
    maintenance_pct=MAINTENANCE_PCT,
    imi_taxable_share=IMI_TAXABLE_SHARE,
):
    """Yearly cash an owner pays (loan payments, property tax, upkeep) as a % of the price.

    Unlike ``owner_cost_rate_pct`` it includes the principal repaid, so it is what leaves the bank account
    every month: the figure to set against the rent when asking what a household can pay.
    """
    payment = aff.mortgage_payment_monthly(ltv, mortgage_rate_pct, term_years)  # per unit of price
    return 100 * 12 * payment + imi_taxable_share * imi_rate_pct + maintenance_pct


def add_indicators(panel: pd.DataFrame, **assumptions) -> pd.DataFrame:
    """Copy of the municipality-year panel with the rent-vs-buy columns.

    ``rent_yield_pct``, ``owner_cost_pct``, ``breakeven_pct`` (need a published rent), ``cash_cost_vs_rent``
    (yearly owner cash outlay over the rent: above 1 means the monthly bill is higher than the rent) and
    ``upfront_cash_years`` (needs ``pti_years``). Municipalities without one urban IMI rate (parish rates)
    take the mean rate of the year, kept in ``imi_filled_pct``. ``assumptions`` override the config values.
    """
    d = panel.copy()
    d["imi_filled_pct"] = d["imi_urban_pct"].fillna(
        d.groupby("year")["imi_urban_pct"].transform("mean")
    )
    cash_keys = {"ltv", "maintenance_pct", "imi_taxable_share"}
    d["rent_yield_pct"] = gross_rent_yield_pct(d["rent_sqm_eur"], d["price_sqm_eur"])
    d["owner_cost_pct"] = owner_cost_rate_pct(
        d["mortgage_rate_new_lt1y_pct"], d["imi_filled_pct"], **assumptions
    )
    d["breakeven_pct"] = breakeven_appreciation_pct(d["owner_cost_pct"], d["rent_yield_pct"])
    cash = owner_cash_cost_pct(
        d["mortgage_rate_new_lt1y_pct"],
        d["imi_filled_pct"],
        **{k: v for k, v in assumptions.items() if k in cash_keys},
    )
    d["cash_cost_vs_rent"] = cash / d["rent_yield_pct"]
    d["upfront_cash_years"] = upfront_cash_years(
        d["pti_years"], **{k: v for k, v in assumptions.items() if k in {"ltv", "buying_costs_pct"}}
    )
    return d


def breakeven_sensitivity(panel: pd.DataFrame, year: int, grid: dict[str, list]) -> pd.DataFrame:
    """Median break-even appreciation of the municipalities with a rent in ``year``, one assumption at a time.

    ``grid`` maps an assumption name (a keyword of ``owner_cost_components``) to the values to try. The first
    row is the base case. Also reports the share of municipalities where owning is cheaper than renting at
    ``EXPECTED_APPRECIATION_PCT`` of price growth.
    """
    rows = [("base", None)] + [(name, value) for name, values in grid.items() for value in values]
    out = []
    for name, value in rows:
        d = add_indicators(
            panel[panel["year"] == year], **({} if name == "base" else {name: value})
        )
        be = d["breakeven_pct"].dropna()
        out.append(
            {
                "assumption": name,
                "value": value,
                "median_owner_cost_pct": d.loc[be.index, "owner_cost_pct"].median(),
                "median_breakeven_pct": be.median(),
                "share_owning_cheaper_pct": 100 * (be < EXPECTED_APPRECIATION_PCT).mean(),
            }
        )
    return pd.DataFrame(out)


def calibrate_yield_scale(measured_yield_pct: pd.Series, price_to_rent: pd.Series) -> float:
    """Constant ``k`` such that ``k / price_to_rent`` matches the measured rent yield best over the overlap years.

    Geometric mean of yield x price-to-rent, so no single year decides the level.
    """
    both = pd.concat([measured_yield_pct, price_to_rent], axis=1, join="inner").dropna()
    return float(np.exp(np.log(both.iloc[:, 0] * both.iloc[:, 1]).mean()))


def national_breakeven(
    price_to_rent,
    mortgage_rate_pct,
    imi_rate_pct,
    yield_scale: float,
    **assumptions,
) -> pd.DataFrame:
    """Break-even appreciation for the whole country by year.

    The OECD gives price-to-rent as an index, whose level is not a rent yield, so the yield is
    ``yield_scale / price_to_rent`` with the scale taken from municipal data (``calibrate_yield_scale``).
    Series are indexed by year; years missing from any input drop out.
    """
    table = pd.concat(
        {
            "price_to_rent": price_to_rent,
            "mortgage_rate_pct": mortgage_rate_pct,
            "imi_rate_pct": imi_rate_pct,
        },
        axis=1,
    ).dropna()
    table["rent_yield_pct"] = yield_scale / table["price_to_rent"]
    components = owner_cost_components(
        table["mortgage_rate_pct"].to_numpy(), table["imi_rate_pct"].to_numpy(), **assumptions
    ).set_index(table.index)
    table = table.join(components)
    table["owner_cost_pct"] = components.sum(axis=1, skipna=False)
    table["breakeven_pct"] = breakeven_appreciation_pct(
        table["owner_cost_pct"], table["rent_yield_pct"]
    )
    return table.drop(columns="price_to_rent")
