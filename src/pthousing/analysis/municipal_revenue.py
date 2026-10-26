"""What IMI and IMT bring each council, 2021-2023 (RQ7.1, RQ7.2, RQ7.4, RQ7.6).

``ine_municipal_revenue`` (receipts of municipal councils by economic classification, DGAL via INE, euros) gives the
revenue of each of 307 councils. IMI is the council's own tax; IMT is shared out to the council where the home is
sold. Three uses, all accounting: how much of its current receipts a council draws from each tax; the revenue a
council could give up by cutting the urban IMI rate to the legal floor (the cost falls on the council); and a check of
the bottom-up IMI per dwelling of ``revenue.imi_per_dwelling`` against the actual receipts. Functions take tables;
nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import IMI_URBAN_MIN_PCT, MUNI_KEY


def shares(rev: pd.DataFrame) -> pd.DataFrame:
    """Add ``imi_share_pct``, ``imt_share_pct`` and ``imi_imt_share_pct``: each tax as a percent of current receipts."""
    out = rev.copy()
    out["imi_share_pct"] = 100 * out["imi_eur"] / out["current_receipts_eur"]
    out["imt_share_pct"] = 100 * out["imt_eur"] / out["current_receipts_eur"]
    out["imi_imt_share_pct"] = out["imi_share_pct"] + out["imt_share_pct"]
    return out


def actual_imi_per_dwelling(rev: pd.DataFrame, dwellings: pd.Series, year: int) -> pd.Series:
    """IMI received in ``year`` per dwelling (euros), indexed by municipality; ``dwellings`` is the census stock by municipality.

    All IMI of the council (commercial and rustic property too, not only homes), so it overstates the bill of a home.
    """
    r = rev.loc[rev["year"] == year].set_index(MUNI_KEY)["imi_eur"]
    return (r / dwellings.reindex(r.index)).rename("imi_actual_per_dwelling_eur")


def bottom_up_check(actual: pd.Series, modelled: pd.Series) -> pd.Series:
    """How well the modelled IMI per dwelling tracks the actual one across municipalities.

    Returns the number of municipalities, the rank correlation, the correlation of the logs and the median and the 10th and
    90th percentile of actual over modelled (the modelled figure is unscaled, so the level is read through the median).
    """
    j = pd.concat([actual.rename("a"), modelled.rename("m")], axis=1).dropna()
    j = j[(j > 0).all(axis=1)]
    ratio = j["a"] / j["m"]
    return pd.Series(
        {
            "municipalities_n": len(j),
            "rank_correlation": float(j["a"].corr(j["m"], method="spearman")),
            "log_correlation": float(np.corrcoef(np.log(j["a"]), np.log(j["m"]))[0, 1]),
            "ratio_median": float(ratio.median()),
            "ratio_p10": float(ratio.quantile(0.1)),
            "ratio_p90": float(ratio.quantile(0.9)),
        }
    )


def floor_room(
    rev: pd.DataFrame,
    panel: pd.DataFrame,
    year: int,
    rate_year: int | None = None,
    floor: float = IMI_URBAN_MIN_PCT,
) -> pd.DataFrame:
    """IMI each council could give up by cutting its urban rate to the legal floor, euros, and as a share of its current receipts.

    IMI received in ``year`` is the bill of the tax year before, so the rate is that of ``rate_year`` (default ``year`` - 1).
    The room is ``imi_eur * (rate - floor) / rate`` where the rate is above the floor: a cut of the rate takes the same
    share of the bill (base held fixed). Councils without a single urban rate that year have no row. Columns:
    ``imi_eur``, ``rate_pct``, ``room_eur``, ``room_share_of_imi_pct``, ``room_share_of_current_pct``.
    """
    rate_year = year - 1 if rate_year is None else rate_year
    rate = panel.loc[panel["year"] == rate_year].set_index(MUNI_KEY)["imi_urban_pct"].dropna()
    r = rev.loc[rev["year"] == year].set_index(MUNI_KEY)
    d = r[["imi_eur", "current_receipts_eur"]].join(rate.rename("rate_pct"), how="inner")
    cut = (d["rate_pct"] - floor).clip(lower=0) / d["rate_pct"]
    d["room_eur"] = d["imi_eur"] * cut
    d["room_share_of_imi_pct"] = 100 * cut
    d["room_share_of_current_pct"] = 100 * d["room_eur"] / d["current_receipts_eur"]
    return d.drop(columns="current_receipts_eur")


def imt_windfall(rev: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Change of each council's IMT between two years, euros and as a share of its current receipts in ``start``.

    Columns: ``imt_start_eur``, ``imt_end_eur``, ``imt_change_eur``, ``imt_change_pct`` (NaN where ``start`` is zero) and
    ``imt_change_share_of_current_pct``.
    """
    a = rev.loc[rev["year"] == start].set_index(MUNI_KEY)
    b = rev.loc[rev["year"] == end].set_index(MUNI_KEY)
    out = pd.DataFrame({"imt_start_eur": a["imt_eur"], "imt_end_eur": b["imt_eur"]}).dropna()
    out["imt_change_eur"] = out["imt_end_eur"] - out["imt_start_eur"]
    out["imt_change_pct"] = (
        100 * out["imt_change_eur"] / out["imt_start_eur"].where(out["imt_start_eur"] > 0)
    )
    out["imt_change_share_of_current_pct"] = (
        100 * out["imt_change_eur"] / a["current_receipts_eur"].reindex(out.index)
    )
    return out
