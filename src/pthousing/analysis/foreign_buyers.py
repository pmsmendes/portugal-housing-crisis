"""Foreign buyers of homes: what they pay and where they buy (RQ5.2).

INE's local house price statistics give the median sale price per m2 by the buyer's tax residence (national territory,
European Union, other countries), quarterly from 4Q2019, nationally and for each municipality. They give no count of
sales by buyer, and a cell is blank when there are too few transactions. Two things follow:

* the foreign premium (foreign median over domestic median) is a price gap, not a measure of investment; it mixes
  location, size and quality of what is bought with what buyers pay for the same home;
* a municipality with a published foreign-buyer price is one with enough foreign purchases, so presence is the only
  signal of where foreign buying is concentrated; it favours places with many sales, which the count of all sales is
  used to hold constant.

Banco de Portugal's real-estate direct investment (the flow in euros) is not in the data, so "how much foreign money" is
not measured here. Everything is association; functions take interim tables, nothing here reads files.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from pthousing.config import MUNI_KEY

BUYERS = ("domestic", "foreign", "eu", "other_foreign", "total")
#: Number of yearly (4th-quarter) snapshots 2019 to 2025 in which a municipality needs a foreign price to count as a foreign market.
MIN_YEARS = 4


def national_premium(national: pd.DataFrame) -> pd.DataFrame:
    """National medians by buyer and the premium of each foreign group over domestic buyers, by quarter.

    ``national`` is the ``ine_price_by_buyer_national`` table. Premiums are percentages of the domestic median.
    """
    wide = national.pivot(index="period_start", columns="buyer", values="price_sqm_eur")[
        list(BUYERS)
    ]
    for group in ("foreign", "eu", "other_foreign"):
        wide[f"premium_{group}_pct"] = 100 * (wide[group] / wide["domestic"] - 1)
    return wide


def snapshots(buyer: pd.DataFrame, quarter: int = 4) -> pd.DataFrame:
    """Municipality x year prices (columns by buyer) for one quarter, whose 12 months are the year itself."""
    d = buyer[buyer["quarter"] == quarter]
    return d.pivot_table(index=[MUNI_KEY, "year"], columns="buyer", values="price_sqm_eur")


def foreign_markets(buyer: pd.DataFrame, sales: pd.DataFrame, quarter: int = 4) -> pd.DataFrame:
    """Municipalities with a foreign-buyer price each year, their share of all sales and their median premium.

    ``sales`` is ``ine_median_price_sqm`` (``sales_12m_n`` of the total category). ``share_of_sales_pct`` is the share of
    the year's sales (over municipalities with a total price) that took place in municipalities with a foreign price.
    """
    snap = snapshots(buyer, quarter).reset_index()
    s = sales[(sales["category"] == "total") & (sales["quarter"] == quarter)][
        [MUNI_KEY, "year", "sales_12m_n"]
    ]
    d = snap.merge(s, on=[MUNI_KEY, "year"], how="left")
    d["premium_pct"] = 100 * (d["foreign"] / d["domestic"] - 1)
    rows = {}
    for year, g in d.groupby("year"):
        f = g[g["foreign"].notna()]
        rows[year] = {
            "priced_n": int(g["total"].notna().sum()),
            "foreign_priced_n": len(f),
            "share_of_sales_pct": 100 * f["sales_12m_n"].sum() / g["sales_12m_n"].sum(),
            "median_premium_pct": f["premium_pct"].median(),
            "share_paying_more_pct": 100 * (f["premium_pct"] > 0).mean(),
        }
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("year")


def foreign_presence(
    buyer: pd.DataFrame, min_years: int = MIN_YEARS, quarter: int = 4
) -> pd.DataFrame:
    """Years (of the 4th-quarter snapshots) with a foreign price per municipality, and the foreign-market flag."""
    snap = snapshots(buyer, quarter)
    years = snap["foreign"].dropna().groupby(level=MUNI_KEY).size()
    out = pd.DataFrame({"foreign_years_n": years}).reindex(
        snap.index.get_level_values(MUNI_KEY).unique()
    )
    out["foreign_years_n"] = out["foreign_years_n"].fillna(0).astype(int)
    out["foreign_market"] = out["foreign_years_n"] >= min_years
    return out


def cross_section(
    buyer: pd.DataFrame,
    sales: pd.DataFrame,
    info: pd.DataFrame,
    start: int = 2019,
    end: int = 2025,
    min_years: int = MIN_YEARS,
) -> pd.DataFrame:
    """One row per municipality with a domestic-buyer price in both ``start`` and ``end``.

    ``info`` is indexed by municipality and holds ``area`` (district, or the island region) and the typology columns
    ``coast_class``, ``density_class`` and ``tourist``. Columns: the domestic-buyer prices, their log change in log points
    (domestic buyers' prices are used so that foreign prices do not enter the outcome), the log of 2019 sales, the
    foreign-market flag and the years with a foreign price.
    """
    snap = snapshots(buyer)
    dom = snap["domestic"].unstack("year")
    out = pd.DataFrame(
        {
            "domestic_start_eur": dom[start],
            "domestic_end_eur": dom[end],
        }
    ).dropna()
    out["growth_log_pts"] = 100 * np.log(out["domestic_end_eur"] / out["domestic_start_eur"])
    out["log_price_start"] = np.log(out["domestic_start_eur"])
    out["log_price_end"] = np.log(out["domestic_end_eur"])
    s = sales[(sales["category"] == "total") & (sales["year"] == start) & (sales["quarter"] == 4)]
    out["log_sales_start"] = np.log(s.set_index(MUNI_KEY)["sales_12m_n"].reindex(out.index))
    out = out.join(foreign_presence(buyer, min_years)).join(info)
    out[["foreign_years_n"]] = out[["foreign_years_n"]].fillna(0)
    out["foreign_market"] = out["foreign_years_n"] >= min_years
    return out.dropna(subset=["log_sales_start", "area"])


SPECS = {
    "no controls": "",
    "district": " + C(area)",
    "district, sales": " + C(area) + log_sales_start",
    "district, sales, typology": " + C(area) + log_sales_start + C(coast_class) + C(density_class) + C(tourist)",
}


def association(
    cross: pd.DataFrame, outcome: str = "growth_log_pts", term: str = "foreign_market"
) -> pd.DataFrame:
    """Coefficient on the foreign-market flag in the cross-section, by specification.

    ``outcome`` is the change in domestic-buyer prices (``growth_log_pts``, with the 2019 price level held fixed in the
    controlled specifications) or the end price level (``log_price_end``, times 100 so that coefficients read as percent).
    Controls are district (island region for the islands), the log of 2019 sales, and the coast, density and tourist
    classes; the last specification leaves out the 23 municipalities with an unknown tourist class (the islands, which
    the area effect already absorbs). Standard errors are clustered by district. Returns one row per specification with the
    coefficient, its 95% interval, p-value, R2 and n; the sign and size are an adjusted association between where foreign
    buyers are active and where domestic buyers' prices are higher or rose more.
    """
    d = cross.assign(
        foreign_market=cross["foreign_market"].astype(float),
        log_price_end=100 * cross["log_price_end"],
    )
    rows = {}
    for label, extra in SPECS.items():
        data = d[d["tourist"] != "unknown"] if "typology" in label else d
        rhs = f"foreign_market{extra}"
        if outcome == "growth_log_pts" and label not in ("no controls", "district"):
            rhs += " + log_price_start"
        res = smf.ols(f"{outcome} ~ {rhs}", data=data).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(data["area"])[0]}
        )
        ci = res.conf_int().loc[term]
        rows[label] = {
            "coef": res.params[term],
            "ci_low": ci[0],
            "ci_high": ci[1],
            "p_value": res.pvalues[term],
            "r2": res.rsquared,
            "n": int(res.nobs),
            "foreign_markets_n": int(data["foreign_market"].sum()),
        }
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("specification")


def by_group(cross: pd.DataFrame, column: str) -> pd.DataFrame:
    """Foreign markets by a typology column: count, share of the group and median domestic price growth, markets vs rest."""
    g = cross.groupby(column)
    out = pd.DataFrame(
        {
            "municipalities_n": g.size(),
            "foreign_markets_n": g["foreign_market"].sum(),
            "foreign_market_share_pct": 100 * g["foreign_market"].mean(),
        }
    )
    growth = cross.groupby([column, "foreign_market"])["growth_log_pts"].median().unstack()
    out["median_growth_markets"] = growth.get(True)
    out["median_growth_others"] = growth.get(False)
    return out
