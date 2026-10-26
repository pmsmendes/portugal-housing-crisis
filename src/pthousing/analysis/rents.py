"""Rents of new leases across municipalities, 2020-2024: where they rose and what goes with it (RQ3.3, RQ5.1).

INE publishes the median rent per m2 of new leases only where enough leases were signed, so the sample is the municipalities
that publish in both the first and the last year (the larger and more urban ones, not a random draw), and the window is
short. This module builds one row per municipality with the log change of the real rent, the log change of the real
transaction price over the same years, and the candidate drivers; the regressions are ``supply.associations``. Functions take
tables; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import MUNI_KEY, YEAR_KEY


def _wide(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    return panel.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column)


def change_frame(
    panel: pd.DataFrame, start: int = 2020, end: int = 2024, demography_end: int = 2023
) -> pd.DataFrame:
    """One row per municipality with a rent in both ``start`` and ``end``.

    Columns: ``dlog_rent`` and ``dlog_price`` (log change of the real rent and the real price per m2 over the same years;
    the price is NaN where it is not published), ``dlog_price_to_rent`` (their difference: how much faster the price rose
    than the rent), ``foreign_change_pp`` (foreign residents, points of the population, ``start`` to ``demography_end``,
    the last year the register covers), ``population_change_pct`` (the same years), ``completions_per_1000`` (dwellings
    completed after ``start`` up to ``end``, per 1,000 dwellings of the 2021 census), ``al_per_1000`` (registered
    short-term rentals per 1,000 dwellings, today's registry), ``rent_start_log`` and ``price_start_log`` (logs of the
    real rent and price in ``start``, to separate catching up from the rest).
    """
    rent = _wide(panel, "rent_sqm_eur_real")
    price = _wide(panel, "price_sqm_eur_real")
    foreign = _wide(panel, "foreign_residents_pct")
    pop = _wide(panel, "population_n")
    done = _wide(panel, "completed_n")
    one = panel.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)
    out = pd.DataFrame(index=rent.index)
    out["dlog_rent"] = np.log(rent[end] / rent[start])
    out["dlog_price"] = np.log(price[end] / price[start])
    out["dlog_price_to_rent"] = out["dlog_price"] - out["dlog_rent"]
    out["foreign_change_pp"] = foreign[demography_end] - foreign[start]
    out["population_change_pct"] = 100 * (pop[demography_end] / pop[start] - 1)
    out["completions_per_1000"] = (
        1000 * done.loc[:, start + 1 : end].sum(axis=1, min_count=1) / one["dwellings_2021_n"]
    )
    out["al_per_1000"] = one["al_units_per_1000_dwellings_2021"]
    out["rent_start_log"] = np.log(rent[start])
    out["price_start_log"] = np.log(price[start])
    return out.dropna(subset=["dlog_rent"])


def sample_share(panel: pd.DataFrame, frame: pd.DataFrame, year: int = 2021) -> float:
    """Share (%) of the national population in the municipalities of ``frame``, in ``year``."""
    pop = _wide(panel, "population_n")[year]
    return 100 * pop.reindex(frame.index).sum() / pop.sum()
