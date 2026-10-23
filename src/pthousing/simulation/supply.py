"""Housing balance: households formed by population change against dwellings that can house them.

Direct accounting only: counts of people, households and dwellings. How prices respond to the balance is
behavioural and lives in ``engine``. All functions are vectorised, so an array of parameter draws (one per
uncertainty run) goes through the same code as a single value.
"""

import numpy as np


def ramp(start: float, end: float, years: int, steps: int) -> np.ndarray:
    """Value in each of ``steps`` projection years: linear from ``start`` to ``end`` over ``years``, flat after."""
    k = np.arange(1, steps + 1)
    return start + (end - start) * np.minimum(k / years, 1.0)


def population_path(
    population_start: float, natural_change: float, net_migration: float, steps: int
) -> np.ndarray:
    """Population at the end of each projection year (length ``steps``): natural change plus net migration."""
    return population_start + np.arange(1, steps + 1) * (natural_change + net_migration)


def households(population: np.ndarray, persons_per_household: np.ndarray) -> np.ndarray:
    """Private households implied by the population and the household size."""
    return population / persons_per_household


def household_size_path(size_start: float, trend_per_year: float, steps: int) -> np.ndarray:
    """Persons per household in each projection year, following the census trend (never below 1.5)."""
    return np.maximum(size_start + trend_per_year * np.arange(1, steps + 1), 1.5)


def usable_additions(
    completions,
    extra_construction,
    renovations,
    public_units,
    *,
    net_ratio: float,
    usable_share,
    additionality,
    reoccupation,
    crowd_out,
):
    """Dwellings added in a year that can house households (counts).

    * baseline completions and the extra units of a construction boost count net of demolitions
      (``net_ratio``) and only the ``usable_share`` that becomes a usual residence; a boost counts only its
      ``additionality`` share;
    * renovated vacant dwellings count by their ``reoccupation`` share;
    * public units are rented as homes (count in full) but displace ``crowd_out`` private completions each.
    """
    private = usable_share * (net_ratio * completions + additionality * extra_construction)
    return private + reoccupation * renovations + (1.0 - crowd_out) * public_units


def balance_pressure(households_before, households_after, additions):
    """Households formed in the year beyond the dwellings that can house them, as a share of households.

    Positive: demand outran the usable stock (same sign convention as ``affordability.supply_gap_per_1000``
    reversed: there positive meant dwellings ahead of households).
    """
    return (households_after - households_before - additions) / households_before
