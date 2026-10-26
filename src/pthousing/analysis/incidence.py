"""Who gets a cut in IMI or IMT: by kind of owner, by municipal income and by how stretched local housing is (RQ7.4).

Municipal data only, so the groups are places and tenures, not households by income: a municipality's median income stands in for
who lives there. Two accounting exercises, no behaviour:

* **IMI** is paid by the owner of each dwelling. The bill of a typical dwelling (``revenue.imi_per_dwelling``, scaled to national
  IMI) is applied to every dwelling of the municipality, the same for a dwelling lived in by its owner, let, second or empty
  (the census does not give the assessed value by use, so owners of old homes, which are assessed low, are not told apart). The
  cut then falls on the dwellings in proportion: a tenant gains only if the landlord passes it on.
* **IMT** is paid by the buyer on each sale; the value of sales is transactions times the median price of a benchmark dwelling.

A cut is either a uniform number of percentage points of the rate capped by the legal floor (``capped``), or a share of the bill.
Functions take tables; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import BENCHMARK_AREA_SQM, IMI_URBAN_MIN_PCT, MUNI_KEY

USES = ("owner_occupied", "rented", "other_tenure", "secondary", "vacant")
USE_LABELS = {
    "owner_occupied": "lived in by the owner",
    "rented": "let to a tenant",
    "other_tenure": "lived in, other tenure",
    "secondary": "second home",
    "vacant": "vacant",
}


def dwellings_by_use(stock: pd.DataFrame, census: pd.DataFrame) -> pd.DataFrame:
    """Dwellings per municipality by use in 2021: owner-occupied, rented, other tenure, secondary and vacant.

    ``stock`` is ``ine_census_stock`` (usual, secondary, vacant dwellings); ``census`` is ``ine_census`` (usual dwellings
    by tenure). The usual dwellings of the stock are split by the tenure shares of the census, so the five uses add to
    the stock.
    """
    s = stock[stock["census_year"] == 2021].set_index(MUNI_KEY)
    c = census[census["census_year"] == 2021].set_index(MUNI_KEY)
    tenure = c[["owner_occupied_n", "rented_n", "other_tenure_n"]]
    share = tenure.div(tenure.sum(axis=1), axis=0)
    out = share.mul(s["dwellings_usual_n"], axis=0)
    out.columns = ["owner_occupied", "rented", "other_tenure"]
    out["secondary"] = s["dwellings_secondary_n"]
    out["vacant"] = s["dwellings_vacant_n"]
    return out[list(USES)]


def capped(rate_pct: pd.Series, cut_pp: float, floor: float = IMI_URBAN_MIN_PCT) -> pd.Series:
    """Cut each council can make if it lowers its rate by ``cut_pp`` but not below the legal floor (pp)."""
    return np.minimum(cut_pp, (rate_pct - floor).clip(lower=0)).rename("cut_pp")


def imi_cut_by_use(
    uses: pd.DataFrame, unit_eur: pd.Series, rate_pct: pd.Series, cut_pp: pd.Series
) -> pd.DataFrame:
    """EUR a year saved by the owners of each kind of dwelling in each municipality, given the council's cut in pp.

    The bill of a dwelling is ``unit_eur`` and moves in proportion with the rate, so a cut of ``cut_pp`` saves
    ``unit_eur * cut_pp / rate_pct`` per dwelling. Municipalities without a unit bill or a rate are left out.
    """
    per_dwelling = (unit_eur * cut_pp / rate_pct).rename("saving_per_dwelling_eur")
    out = uses.mul(per_dwelling, axis=0)
    return out.dropna(how="any")


def shares(table: pd.DataFrame) -> pd.Series:
    """Column totals as percentages of the grand total."""
    totals = table.sum()
    return 100 * totals / totals.sum()


def by_group(frame: pd.DataFrame, group: pd.Series, columns: dict[str, str]) -> pd.DataFrame:
    """Sum the named columns by group and add each group's share (%) of each total.

    ``columns`` maps a column of ``frame`` to its output name; the shares are named ``<name>_share_pct``.
    """
    sums = frame[list(columns)].rename(columns=columns).groupby(group, observed=True).sum()
    out = sums.copy()
    for name in sums:
        out[f"{name}_share_pct"] = 100 * sums[name] / sums[name].sum()
    return out


def terciles(values: pd.Series, labels: tuple[str, str, str]) -> pd.Series:
    """Label each municipality by the third of ``values`` it falls in (lowest first); NaN stays NaN."""
    return pd.qcut(values, 3, labels=list(labels)).rename(values.name)


def sales_value(panel: pd.DataFrame, year: int) -> pd.Series:
    """Value of dwellings sold per municipality in ``year``: transactions times median price per m2 times the benchmark area (EUR)."""
    d = panel[panel["year"] == year].set_index(MUNI_KEY)
    return (d["sales_12m_n"] * d["price_sqm_eur_real"] * BENCHMARK_AREA_SQM).rename(
        "sales_value_eur"
    )
