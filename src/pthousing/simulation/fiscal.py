"""Direct fiscal effects of IMI/IMT reforms and housing expenditure (accounting effects only).

Signs: a cost or revenue loss is positive ("cost to the budget"), a revenue gain negative. Amounts are in
constant euros of the base year and national: no municipal revenue series exists (docs/data_quality.md).
The price effects of a tax change (capitalisation) are behavioural; they are returned as a share of the
price and applied by the engine, never mixed into the revenue figures. Revenue is held at the level of the
base (no change in transactions or in assessed values), the usual accounting convention.
"""


def spending(units, cost_per_unit_eur):
    """Public cost of ``units`` dwellings at ``cost_per_unit_eur`` each (supply levers)."""
    return units * cost_per_unit_eur


def imi_revenue_loss(rate_change_pp, average_rate_pct, revenue_eur):
    """Revenue lost to a change of the national average IMI rate by ``rate_change_pp`` (a cut is positive).

    Proportional: the bill moves with the rate, so a cut of x pp on an average rate of r pp changes the
    revenue by x / r. The average rate is the simple mean of the municipal urban rates, not weighted by the
    tax base, so this is an order of magnitude, not a forecast of receipts.
    """
    return -rate_change_pp / average_rate_pct * revenue_eur


def imt_revenue_loss(rate_change_pp, transaction_value_eur):
    """Revenue lost to a change of the average IMT rate on dwelling purchases (a cut is positive).

    ``transaction_value_eur`` is the value of dwellings sold in a year; the volume is held fixed.
    """
    return -rate_change_pp / 100 * transaction_value_eur


def imi_capitalisation(rate_change_pp, share, tax_value_ratio, discount_rate):
    """Price change (fraction) if ``share`` of a permanent IMI change is capitalised into prices.

    Full capitalisation of a cut is the present value of the tax saved per euro of price:
    cut x (assessed value / price) / discount rate, the benchmark of ``reports/p3_policy.md`` (0.19% of the
    price for a 0.01 pp cut at the mid values). A cut raises prices; an increase lowers them.
    """
    return -rate_change_pp / 100 * tax_value_ratio / discount_rate * share


def imt_capitalisation(rate_change_pp, share):
    """Price change (fraction) if ``share`` of an IMT change is capitalised: a cut of x pp can lift the price by up to x%."""
    return -rate_change_pp / 100 * share
