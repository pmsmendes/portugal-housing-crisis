"""New-build supply by dwelling size against households by size (RQ2.6).

Dwelling size is the number of bedrooms of completed family dwellings (INE: T0-T1, T2, T3, T4 or more); household size
is the number of persons in private households (census 2011 and 2021: 1, 2, 3, 4 or more). They are paired one to one,
``SIZE_PAIRS``: a nominal pairing, not a rule (a couple can live in a T3), so the comparison is of two mixes, not a
count of homes missing. Only flows are compared: the census stock by number of rooms is not in the data, so who lives
in what is not observed. Functions take interim tables; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import MUNI_KEY

SIZE_PAIRS = {"br_0_1": "1", "br_2": "2", "br_3": "3", "br_4plus": "4plus"}  # bedrooms -> persons
SMALL = ("1", "2")  # households of one or two persons, and the dwellings paired with them (T0-T2)


def household_sizes(households: pd.DataFrame) -> pd.DataFrame:
    """Households by size, one row per municipality and size, 2011 and 2021 side by side with the change."""
    wide = households.pivot_table(
        index=[MUNI_KEY, "size"], columns="census_year", values="households_n", aggfunc="sum"
    )
    wide.columns = [f"households_{c}_n" for c in wide.columns]
    wide["households_change_n"] = wide["households_2021_n"] - wide["households_2011_n"]
    return wide.reset_index()


def completions_by_size(construction: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Completed family dwellings by municipality and household-size label, over the years ``start`` to ``end``."""
    df = construction[
        construction["size"].isin(SIZE_PAIRS) & construction["year"].between(start, end)
    ].copy()
    df["size"] = df["size"].map(SIZE_PAIRS)
    out = df.groupby([MUNI_KEY, "size"])["completed_n"].sum(min_count=1)
    return out.rename("completed_n").reset_index()


def national_comparison(
    households: pd.DataFrame, construction: pd.DataFrame, start: int = 2011, end: int = 2021
) -> pd.DataFrame:
    """By size: households in the two censuses, their change, completions in between and the shares of each.

    ``households`` is ``ine_households_size``, ``construction`` is ``ine_construction``. Completions are those of the
    years ``start`` to ``end``; shares are of the column total (the change can be negative for a size).
    """
    hh = (
        household_sizes(households)
        .groupby("size")[["households_2011_n", "households_2021_n", "households_change_n"]]
        .sum()
    )
    done = completions_by_size(construction, start, end).groupby("size")["completed_n"].sum()
    out = hh.join(done)
    for col in ("households_2011_n", "households_2021_n", "households_change_n", "completed_n"):
        out[col.replace("_n", "_share_pct")] = 100 * out[col] / out[col].sum()
    return out.loc[list(SIZE_PAIRS.values())]


def small_share_by_year(construction: pd.DataFrame) -> pd.Series:
    """Share (%) of each year's completions that are T0-T2 (the dwellings paired with one- and two-person households)."""
    df = construction[construction["size"].isin(SIZE_PAIRS)].copy()
    df["small"] = df["size"].map(SIZE_PAIRS).isin(SMALL)
    by = df.groupby(["year", "small"])["completed_n"].sum().unstack("small", fill_value=0)
    return (100 * by[True] / by.sum(axis=1)).rename("small_dwellings_pct")


def small_dwelling_gap(
    households: pd.DataFrame,
    construction: pd.DataFrame,
    start: int = 2011,
    end: int = 2021,
    min_completions: int = 50,
) -> pd.DataFrame:
    """Per municipality, how far the mix of new dwellings lags the mix of households.

    ``small_households_pct`` is the share of 2021 households with one or two persons, ``small_households_change_pp`` its
    change since 2011, ``small_completions_pct`` the share of completions in ``start``-``end`` that are T0-T2, and
    ``small_gap_pp`` the first minus the third (positive: new building is bigger than the households that live
    in the municipality). Municipalities with fewer than ``min_completions`` completions are left NaN.
    """
    wide = household_sizes(households)
    wide["small"] = wide["size"].isin(SMALL)
    by = wide.groupby([MUNI_KEY, "small"])[["households_2011_n", "households_2021_n"]].sum()
    small = by.xs(True, level="small")
    total = by.groupby(level=MUNI_KEY).sum()
    out = pd.DataFrame(
        {
            "small_households_pct": 100 * small["households_2021_n"] / total["households_2021_n"],
            "small_households_change_pp": 100
            * (
                small["households_2021_n"] / total["households_2021_n"]
                - small["households_2011_n"] / total["households_2011_n"]
            ),
        }
    )
    done = completions_by_size(construction, start, end)
    done["small"] = done["size"].isin(SMALL)
    comp = done.groupby([MUNI_KEY, "small"])["completed_n"].sum(min_count=1).unstack("small")
    comp_total = comp.sum(axis=1, min_count=1)
    out["completions_n"] = comp_total
    out["small_completions_pct"] = (100 * comp[True] / comp_total).where(
        comp_total >= min_completions
    )
    out["small_gap_pp"] = out["small_households_pct"] - out["small_completions_pct"]
    out["small_gap_pp"] = out["small_gap_pp"].replace([np.inf, -np.inf], np.nan)
    return out.reset_index()
