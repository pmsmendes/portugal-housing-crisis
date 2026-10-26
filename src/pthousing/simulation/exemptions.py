"""Targeted tax exemptions against broad cuts: what each costs, and what it would have to do to pay for itself in affordability (RQ7.5).

Three exemptions are sized from the project's data and press-reported facts (``config/scenarios.yaml``, block
``exemptions``): the IMT and stamp-duty exemption for young first-time buyers (observed cost and buyers), an IMT
exemption on new dwellings (completions times the IMT of a new home) and an IMI exemption for renovated dwellings
(buildings with works, dwellings per building, years of exemption). Accounting first: the revenue each forgoes, per
beneficiary and as a share of IMT or IMI.

The simulator's price channel is a national average rate (``fiscal``), so an exemption enters as the average IMT or IMI
cut that costs the same revenue: the price effect of a euro of revenue forgone is then the same for a broad cut and a
targeted exemption, bounded by no capitalisation and full capitalisation. What targeting changes is who receives the
money and whether it can create homes. That channel is not estimated: ``break_even_homes`` solves for the extra homes a year
the exemption would have to cause for the 2035 price-to-income not to rise. Functions take numbers; nothing here reads data
files (``load`` reads the yaml).
"""

import numpy as np
import yaml

from pthousing.config import SCENARIOS_YAML
from pthousing.simulation import engine as E
from pthousing.simulation.scenarios import Range


def load(path=SCENARIOS_YAML) -> dict:
    """The ``exemptions`` block: ``Range`` objects for low/mid/high entries, floats for the rest, ``notes`` for status and source."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)["exemptions"]
    out: dict = {"notes": {}}
    for group, node in raw.items():
        out["notes"][group] = {"status": node.get("status", ""), "source": node.get("source", "")}
        out[group] = {
            k: Range(v["low"], v["mid"], v["high"]) if isinstance(v, dict) else v
            for k, v in node.items()
            if k not in ("status", "source")
        }
    return out


def average_imt_rate_pct(imt_revenue_eur: float, sales_value_eur: float) -> float:
    """IMT revenue over the value of dwellings sold, %. The revenue also covers other properties and stamp duty, so an upper bound."""
    return 100 * imt_revenue_eur / sales_value_eur


def equivalent_imt_cut_pp(cost_eur: float, sales_value_eur: float) -> float:
    """The average IMT cut on all dwelling sales (pp of the price, positive) that costs ``cost_eur`` a year."""
    return 100 * cost_eur / sales_value_eur


def equivalent_imi_cut_pp(
    cost_eur: float, imi_revenue_eur: float, average_rate_pct: float
) -> float:
    """The average IMI rate cut (pp, positive) that costs ``cost_eur`` a year: the inverse of ``fiscal.imi_revenue_loss``."""
    return average_rate_pct * cost_eur / imi_revenue_eur


def new_build_exemption(
    completions: float,
    sold_share: float,
    value_per_sale_eur: float,
    new_premium_pct: float,
    imt_rate_pct: float,
) -> dict[str, float]:
    """Homes reached, exemption per home and yearly cost of exempting the first sale of new dwellings from IMT.

    A new home sells for the average sale value plus the new-build premium; its IMT is that value at the average IMT rate (the
    schedule is progressive, so the true rate of dearer homes is higher and of cheaper ones lower).
    """
    per_home = value_per_sale_eur * (1 + new_premium_pct / 100) * imt_rate_pct / 100
    base = completions * sold_share
    return {"homes_n": base, "per_home_eur": per_home, "cost_eur": base * per_home}


def renovation_exemption(
    buildings_a_year: float,
    dwellings_per_building: float,
    years: float,
    imi_per_dwelling_eur: float,
) -> dict[str, float]:
    """Dwellings entering the exemption a year, IMI saved per dwelling over its length, and the yearly cost once in steady state.

    In steady state ``years`` cohorts are exempt at once, so the yearly cost is the yearly flow times the years times the IMI of a
    dwelling.
    """
    homes = buildings_a_year * dwellings_per_building
    return {
        "homes_n": homes,
        "per_home_eur": imi_per_dwelling_eur * years,
        "cost_eur": homes * years * imi_per_dwelling_eur,
    }


def extra_homes_from_price(coefficient: float, price_rise_pct: float, completions: float) -> float:
    """Extra completions a year if they respond to the price builders receive as in the ``p2_17`` association.

    ``coefficient`` is the log-point rise in completions per log point rise in the real price (3.0 in ``p2_17``, an association
    between yearly changes over two cycles, not a supply elasticity), ``price_rise_pct`` the rise of the price builders
    get (the whole tax saving if it is capitalised in full) and ``completions`` the yearly flow it applies to. An illustration
    of the size of a supply response, not an estimate of one.
    """
    return coefficient * price_rise_pct / 100 * completions


def pti_change(
    a: E.Assumptions,
    anc: E.Anchors,
    scenario: str,
    policy: E.Policy,
    p: dict[str, np.ndarray],
    drift: np.ndarray | None = None,
) -> float:
    """Median change of the end-year price-to-income (years of income) from ``policy`` against no policy; positive is worse."""
    drift = E.calibrate(a, anc, p) if drift is None else drift
    without = E.run(a, anc, scenario, None, p, drift)
    with_ = E.run(a, anc, scenario, policy, p, drift)
    return float(np.median(with_.end("pti_years") - without.end("pti_years")))


def tax_price_effect(
    a: E.Assumptions,
    anc: E.Anchors,
    scenario: str,
    imt_cut_pp: float = 0.0,
    imi_cut_pp: float = 0.0,
    capitalisation: float | None = None,
) -> float:
    """Change of the 2035 price-to-income from an average cut (pp, positive) at a capitalisation share; positive is worse.

    ``capitalisation`` overrides the share for both taxes (0: none, 1: all of the saving ends up in the price); ``None`` keeps each
    tax's mid value. Central draw of every other parameter.
    """
    override = {}
    if capitalisation is not None:
        override = {
            "imt_reform__capitalisation_share": capitalisation,
            "imi_reform__capitalisation_share": capitalisation,
        }
    p = E.central(a, **override)
    policy = E.Policy(imt_rate_change_pp=-imt_cut_pp, imi_rate_change_pp=-imi_cut_pp)
    return pti_change(a, anc, scenario, policy, p)


def break_even_homes(
    a: E.Assumptions,
    anc: E.Anchors,
    scenario: str,
    imt_cut_pp: float = 0.0,
    imi_cut_pp: float = 0.0,
    capitalisation: float = 1.0,
    upper: float = 400_000,
) -> float:
    """Extra homes a year (from the policy start year) that cancel the tax's rise of the 2035 price-to-income.

    The tax runs at ``capitalisation``; the homes are extra completions that all add to supply (additionality 1), found by
    bisection. 0 if the tax does not raise the ratio; ``nan`` if even ``upper`` homes a year do not cancel it.
    """
    override = {
        "imt_reform__capitalisation_share": capitalisation,
        "imi_reform__capitalisation_share": capitalisation,
        "construction_boost__additionality": 1.0,
    }
    p = E.central(a, **override)
    drift = E.calibrate(a, anc, p)

    def net(units: float) -> float:
        policy = E.Policy(
            imt_rate_change_pp=-imt_cut_pp,
            imi_rate_change_pp=-imi_cut_pp,
            construction_boost_units=units,
        )
        return pti_change(a, anc, scenario, policy, p, drift)

    if net(0.0) <= 0:
        return 0.0
    if net(upper) > 0:
        return float("nan")
    lo, hi = 0.0, upper
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if net(mid) > 0 else (lo, mid)
    return (lo + hi) / 2
