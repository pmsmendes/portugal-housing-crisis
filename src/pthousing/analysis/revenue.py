"""IMI and IMT revenue against house prices and the IMI rate (RQ7.1).

National annual series only, 1995 to 2025: general-government revenue from taxes on land and buildings (IMI) and
from taxes on capital transactions (IMT with stamp duty), both from the national accounts, so on an accrual basis.
Municipal receipts exist for 2021-2023 only (``municipal_revenue``, ``ine_municipal_revenue``).

IMI revenue is the product of a rate chosen by each council and an assessed base that follows the tax value of
homes, not their market price; IMT revenue is a rate schedule applied to the value of homes sold, so it moves with
prices and with the number of sales. Neither is split here into its parts beyond what the data allow: the rate is
observed (2012 onward, weighted by the stock of dwellings), the base is what is left, and the number of sales is not
observed in the national series. Functions take interim tables or the frame from ``annual_frame``; nothing here
reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import (
    BENCHMARK_AREA_SQM,
    IMI_TAXABLE_SHARE,
    IMI_URBAN_MIN_PCT,
    MUNI_KEY,
    VACANT_IMI_MULTIPLE,
)
from pthousing.data.harmonize import annual_deflator

BASE = 2015  # index base of the annual frame, as in ``macro.annual_frame``


def weighted_imi_rate(panel: pd.DataFrame, weight: str = "dwellings_2021_n") -> pd.Series:
    """Average municipal urban IMI rate by year, weighted by a fixed stock of dwellings.

    Municipalities without a single rate in a year (parish-specific rates, or no value) are left out of that
    year and the weights renormalised; a fixed weight keeps the change in the average to the change in rates.
    """
    d = panel.dropna(subset=["imi_urban_pct", weight])
    return (
        d.groupby("year")
        .apply(lambda g: np.average(g["imi_urban_pct"], weights=g[weight]), include_groups=False)
        .rename("imi_rate_pct")
    )


def annual_frame(
    tax: pd.DataFrame,
    cpi: pd.DataFrame,
    long: pd.DataFrame,
    rate: pd.Series | None = None,
) -> pd.DataFrame:
    """Revenue in current and constant euros, as a share of GDP, and against the price level.

    ``tax`` is the ``eurostat_property_tax`` interim table, ``cpi`` the ``ine_cpi`` table (constant ``BASE_YEAR``
    euros), ``long`` the ``national_annual_long`` panel (house price indices, 2015 = 100) and ``rate`` the yearly
    average IMI rate from ``weighted_imi_rate``. Adds ``imi_real_b2015`` and ``imt_real_b2015`` (real revenue,
    2015 = 100) next to the real price index, and, with a rate, ``imi_base_b2015``: revenue over the rate, an index
    of the tax base the rate is applied to.
    """
    d = tax.set_index("year").rename(
        columns={"imi_revenue_eur_m": "imi_eur_m", "imt_revenue_eur_m": "imt_eur_m"}
    )
    deflator = annual_deflator(cpi)
    for name in ("imi", "imt"):
        d[f"{name}_real_eur_m"] = d[f"{name}_eur_m"] * deflator.reindex(d.index)
        d[f"{name}_gdp_pct"] = 100 * d[f"{name}_eur_m"] / d["gdp_eur_m"]
        real = d[f"{name}_real_eur_m"]
        d[f"{name}_real_b2015"] = 100 * real / real.loc[BASE]
    d = d.join(long.set_index("year")[["hpi_nominal_b2015", "hpi_real_b2015"]])
    if rate is not None:
        d["imi_rate_pct"] = rate
        base = d["imi_eur_m"] / d["imi_rate_pct"]
        d["imi_base_b2015"] = 100 * base / base.loc[BASE]
    return d


def changes(
    frame: pd.DataFrame, windows: dict[str, tuple[int, int]], columns: list[str]
) -> pd.DataFrame:
    """Percentage change of each column between the first and last year of each window; one row per window."""
    rows = {
        label: {c: 100 * (frame.loc[end, c] / frame.loc[start, c] - 1) for c in columns}
        for label, (start, end) in windows.items()
    }
    return pd.DataFrame(rows).T.rename_axis("window")


def decompose_imi(frame: pd.DataFrame, start: int, end: int) -> pd.Series:
    """Log-point change of IMI revenue between two years, split into the rate and the base (revenue over rate).

    ``frame`` needs the rate (``annual_frame`` with ``rate``). Also reports the nominal house price and the
    ``gap``: how far the tax base lags the price (base minus price; negative when prices rose faster).
    """
    d = frame.loc[[start, end]]
    log = np.log(d)
    change = log.loc[end] - log.loc[start]
    base = change["imi_eur_m"] - change["imi_rate_pct"]
    return 100 * pd.Series(
        {
            "revenue": change["imi_eur_m"],
            "rate": change["imi_rate_pct"],
            "base": base,
            "price": change["hpi_nominal_b2015"],
            "gap": base - change["hpi_nominal_b2015"],
        }
    )


def imi_headroom(
    panel: pd.DataFrame,
    year: int,
    weight: str = "dwellings_2021_n",
    floor: float = IMI_URBAN_MIN_PCT,
) -> pd.Series:
    """How far councils can cut the urban IMI rate within the legal floor, nationally, in a year.

    Municipalities with a single rate that year, weighted by ``weight``. Returns the number of municipalities, how many
    sit at the floor, the average rate, the headroom (average of rate minus floor, in pp) and that headroom as a share
    of the average rate: the largest cut of the bill that councils can make without a change of the law.
    """
    d = panel.loc[panel["year"] == year].dropna(subset=["imi_urban_pct", weight])
    average = np.average(d["imi_urban_pct"], weights=d[weight])
    room = np.average((d["imi_urban_pct"] - floor).clip(lower=0), weights=d[weight])
    return pd.Series(
        {
            "municipalities_n": len(d),
            "at_floor_n": int((d["imi_urban_pct"] <= floor + 1e-9).sum()),
            "average_rate_pct": average,
            "headroom_pp": room,
            "headroom_share": room / average,
        }
    )


def dwelling_sales_value(panel: pd.DataFrame, year: int) -> float:
    """Value of dwellings sold in a year, EUR in constant base-year euros.

    Transactions over twelve months times the median price per m² times the benchmark dwelling of
    ``BENCHMARK_AREA_SQM``: a benchmark, not the registered value of sales, and dwellings only. NaN when the
    year has no sales (the panel has them from 2019).
    """
    sold = panel.loc[panel["year"] == year]
    value = (sold["sales_12m_n"] * sold["price_sqm_eur_real"]).sum(min_count=1)
    return float(value * BENCHMARK_AREA_SQM)


def offset_growth(cut_share: float) -> float:
    """Growth of the base that restores the revenue lost to a cut of ``cut_share`` of the bill (a fraction).

    Revenue is rate times base, so a cut of a share c of the bill needs the base to grow by c / (1 - c).
    """
    return cut_share / (1 - cut_share)


def capped_cut(
    panel: pd.DataFrame,
    year: int,
    cut_pp: float,
    weight: str = "dwellings_2021_n",
    floor: float = IMI_URBAN_MIN_PCT,
) -> pd.Series:
    """Average cut that results if every council cuts its urban IMI rate by ``cut_pp`` but none goes below the floor.

    Returns the number of municipalities that can make the whole cut, the weighted average cut (pp) and that cut as a
    share of the weighted average rate: what a uniform cut of ``cut_pp`` delivers inside the current law.
    """
    d = panel.loc[panel["year"] == year].dropna(subset=["imi_urban_pct", weight])
    cut = np.minimum(cut_pp, (d["imi_urban_pct"] - floor).clip(lower=0))
    average = np.average(cut, weights=d[weight])
    return pd.Series(
        {
            "full_cut_n": int((cut >= cut_pp - 1e-9).sum()),
            "average_cut_pp": average,
            "average_cut_share": average / np.average(d["imi_urban_pct"], weights=d[weight]),
        }
    )


def imi_per_dwelling(
    panel: pd.DataFrame, year: int, taxable_share: float = IMI_TAXABLE_SHARE
) -> pd.Series:
    """Yearly IMI of a typical dwelling in each municipality, EUR: taxable share x price per m2 x mean area x urban rate.

    The census mean area of the municipality's dwellings times the median transaction price per m2 of ``year`` gives a
    market value; ``taxable_share`` converts it to the assessed value (VPT). A bottom-up figure for the average dwelling, not
    the bill of any one home: old homes are assessed far below the market and some are exempt, which ``calibration``
    corrects nationally. NaN where the price or a single urban rate is missing.
    """
    d = panel.loc[panel["year"] == year].set_index(MUNI_KEY)
    value = taxable_share * d["price_sqm_eur"] * d["dwelling_area_sqm"]
    return (value * d["imi_urban_pct"] / 100).rename("imi_per_dwelling_eur")


def calibration(per_dwelling: pd.Series, dwellings: pd.Series, national_eur_m: float) -> float:
    """Factor that scales the bottom-up IMI of all dwellings to the national-accounts revenue.

    Municipalities without a per-dwelling figure are given the dwelling-weighted average of the others. The national
    revenue covers all land and buildings (commercial and rustic too), so the factor attributes all of it to dwellings
    and is an upper bound on the scale of residential IMI.
    """
    ok = per_dwelling.notna()
    average = np.average(per_dwelling[ok], weights=dwellings[ok])
    bottom_up = average * dwellings.sum()
    return national_eur_m * 1e6 / bottom_up


def vacant_surcharge(
    per_dwelling: pd.Series,
    excess_n: pd.Series,
    legal_share: float,
    scale: float = 1.0,
    multiple: float = VACANT_IMI_MULTIPLE,
) -> pd.Series:
    """Extra IMI a year per municipality, EUR, if the rate on legally vacant homes is ``multiple`` times the normal one.

    ``excess_n`` are vacant dwellings above the frictional level (``vacancy.excess``); ``legal_share`` is the share of
    them a council could classify as vacant under the law (empty over a year, shown by consumption of water and power):
    unobserved, so varied. Accounting only: owners who let, sell or repair in response pay less, and are what the
    surcharge is for. Municipalities without a per-dwelling figure get the average of the others.
    """
    unit = per_dwelling.fillna(per_dwelling.mean())
    return (excess_n * legal_share * (multiple - 1) * unit * scale).rename("surcharge_eur")


def surcharge_bite(
    per_dwelling: pd.Series,
    scale: float,
    panel: pd.DataFrame,
    year: int,
    multiple: float = VACANT_IMI_MULTIPLE,
) -> pd.Series:
    """The extra yearly IMI of a typical dwelling as a share of the yearly rent it could earn (new-lease median).

    ``rent_sqm_eur`` x mean area x 12 months; NaN where rents are not published (small rental markets). A small share
    means the surcharge costs the owner little against what letting would bring in, so it would not change much.
    """
    d = panel.loc[panel["year"] == year].set_index(MUNI_KEY)
    rent = d["rent_sqm_eur"] * d["dwelling_area_sqm"] * 12
    return ((multiple - 1) * per_dwelling * scale / rent).rename("surcharge_share_of_rent")
