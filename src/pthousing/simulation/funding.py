"""What a given yearly budget buys: the simulator's gain in price-to-income for money from an identified source.

Wraps ``engine.policy_for_budget`` and ``engine.run``: a budget (EUR a year from the policy start year) is split over
levers at mid unit costs, run against the same scenario and draws with and without it, and the fall in the
2035 median price-to-income is reported with its 80% range, next to the units bought and the drift of the baseline it is
set against. Accounting plus the simulator's modelled price response; the budget's source is not modelled.
"""

import numpy as np
import pandas as pd

from pthousing.simulation import engine as E

QUANTILES = (0.1, 0.5, 0.9)
UNIT_LEVERS = ("construction_boost_units", "vacant_renovation_units", "public_housing_units")


def gain_for_budget(
    a: E.Assumptions,
    anc: E.Anchors,
    scenario: str,
    p: dict[str, np.ndarray],
    budget_eur: float,
    shares: dict[str, float],
    drift: np.ndarray | None = None,
) -> pd.Series:
    """Gain in the end-year price-to-income (years of income) of spending ``budget_eur`` a year split by ``shares``.

    Returns the units a year bought per supply lever, the 10th, 50th and 90th percentile of the gain over the draws,
    the median gain as a share of the median rise of the baseline over the horizon (``gain_share_of_rise_pct``, NaN if the
    baseline does not rise), and
    the median cumulative cost.
    """
    drift = E.calibrate(a, anc, p) if drift is None else drift
    without = E.run(a, anc, scenario, None, p, drift)
    policy = E.policy_for_budget(a, anc, shares, budget_eur)
    with_ = E.run(a, anc, scenario, policy, p, drift)
    gain = without.end("pti_years") - with_.end("pti_years")
    rise = without.end("pti_years") - anc.pti_years
    lo, mid, hi = np.quantile(gain, QUANTILES)
    median_rise = float(np.median(rise))
    return pd.Series(
        {
            **{lever: getattr(policy, lever) for lever in UNIT_LEVERS},
            "gain_p10": lo,
            "gain_p50": mid,
            "gain_p90": hi,
            "gain_share_of_rise_pct": 100 * mid / median_rise if median_rise > 0 else np.nan,
            "cost_eur_p50": float(np.median(with_.end("cumulative_cost_eur"))),
        }
    )
