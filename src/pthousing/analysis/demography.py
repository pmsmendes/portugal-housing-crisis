"""Population change and foreign residents: what moves the population, and who and where they are (RQ3.1, RQ3.2).

Population change splits into natural change (births minus deaths) and net migration (``national_balance``,
``period_balance``, ``municipal_balance``, ``growth_regimes``; RQ3.1). The national series is Eurostat's, from
1960; the municipal one is INE's, 2011-2023. Net migration is a residual of the estimate, so it also holds
statistical adjustments, and the municipal series carries INE's 2020-2021 post-census revision (``revision_n``
nationally) as net migration.

Foreign residents: how many, of which nationalities, and where they live (RQ3.2).

Foreign residents are foreign nationals with a residence title on 31 December (``aima_foreigners``), not the
foreign-born population: people who acquired Portuguese nationality are not counted, and part of a jump can be
administrative. Shares use the INE resident population estimate of the same year, so they are indicative.
Functions take the municipality-year panel (with the typology columns, see ``viz.dashboard.load_panel``) or the
interim nationality table; nothing here reads files.
"""

import numpy as np
import pandas as pd

from pthousing.config import MUNI_KEY, YEAR_KEY

NATIONALITY_NAMES = {
    "br": "Brazil",
    "cn": "China",
    "cv": "Cabo Verde",
    "gb": "United Kingdom",
    "gw": "Guinea-Bissau",
    "md": "Moldova",
    "ro": "Romania",
    "st": "São Tomé and Príncipe",
    "ua": "Ukraine",
    "ao": "Angola",
    "other": "All other",
}


def national_totals(panel: pd.DataFrame) -> pd.DataFrame:
    """Foreign residents, resident population and the foreign share by year (years with a count)."""
    d = panel.dropna(subset=["foreign_residents_n"]).groupby(YEAR_KEY)[
        ["foreign_residents_n", "population_n"]
    ]
    out = d.sum()
    out["foreign_share_pct"] = 100 * out["foreign_residents_n"] / out["population_n"]
    return out


def nationality_totals(aima: pd.DataFrame) -> pd.DataFrame:
    """Foreign residents by year (rows) and nationality (columns), with the total as the last column."""
    wide = aima.pivot_table(
        index=YEAR_KEY, columns="nationality", values="foreign_residents_n", aggfunc="sum"
    )
    names = [c for c in wide.columns if c != "total"]
    return wide[names + ["total"]]


def group_distribution(panel: pd.DataFrame, year: int, column: str) -> pd.DataFrame:
    """Where foreign residents live by group of ``column``, against where the population lives.

    ``foreign_share_of_total_pct`` and ``population_share_of_total_pct`` add to 100; a group whose first exceeds
    its second hosts more foreign residents than its population weight. ``foreign_share_pct`` is the group's own
    foreign share of its population.
    """
    d = panel[panel[YEAR_KEY] == year].dropna(subset=["foreign_residents_n", column])
    g = d.groupby(column)[["foreign_residents_n", "population_n"]].sum()
    out = pd.DataFrame(
        {
            "foreign_residents_n": g["foreign_residents_n"],
            "population_n": g["population_n"],
            "foreign_share_of_total_pct": 100
            * g["foreign_residents_n"]
            / g["foreign_residents_n"].sum(),
            "population_share_of_total_pct": 100 * g["population_n"] / g["population_n"].sum(),
            "foreign_share_pct": 100 * g["foreign_residents_n"] / g["population_n"],
        }
    )
    return out.sort_values("foreign_residents_n", ascending=False)


def concentration(
    panel: pd.DataFrame, year: int, ns: tuple[int, ...] = (1, 5, 10, 30)
) -> pd.DataFrame:
    """Share of all foreign residents living in the ``n`` municipalities with the most, against their population."""
    d = panel[panel[YEAR_KEY] == year].dropna(subset=["foreign_residents_n"])
    d = d.sort_values("foreign_residents_n", ascending=False)
    rows = []
    for n in ns:
        top = d.head(n)
        rows.append(
            {
                "top_municipalities": n,
                "foreign_share_of_total_pct": 100
                * top["foreign_residents_n"].sum()
                / d["foreign_residents_n"].sum(),
                "population_share_of_total_pct": 100
                * top["population_n"].sum()
                / d["population_n"].sum(),
            }
        )
    return pd.DataFrame(rows)


def nationality_location(
    aima: pd.DataFrame, panel: pd.DataFrame, year: int, column: str, groups: list[str]
) -> pd.DataFrame:
    """Share of each nationality's residents living in each of ``groups`` of ``column`` (the rest: ``other``).

    Rows are nationalities (total included), columns the groups plus ``other``; rows add to 100.
    """
    attrs = panel[panel[YEAR_KEY] == year].drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)[column]
    d = aima[aima[YEAR_KEY] == year].copy()
    d[column] = d[MUNI_KEY].map(attrs)
    d["group"] = np.where(d[column].isin(groups), d[column], "other")
    wide = d.pivot_table(
        index="nationality", columns="group", values="foreign_residents_n", aggfunc="sum"
    )
    wide = wide.reindex(columns=[*groups, "other"]).fillna(0.0)
    return 100 * wide.div(wide.sum(axis=1), axis=0)


def growth_contribution(panel: pd.DataFrame, start: int, end: int) -> pd.Series:
    """How much of the change in resident population between two years is the change in foreign residents.

    Titles and the population estimate are different measures, so the remainder (``other_change_n``) also
    holds foreign-born people without a title count, new citizens and natural change. The share is
    missing when the population did not grow (it would not be a share of anything).
    """
    both = panel[panel[YEAR_KEY].isin([start, end])].dropna(subset=["foreign_residents_n"])
    t = both.groupby(YEAR_KEY)[["population_n", "foreign_residents_n"]].sum()
    population = t.loc[end, "population_n"] - t.loc[start, "population_n"]
    foreign = t.loc[end, "foreign_residents_n"] - t.loc[start, "foreign_residents_n"]
    return pd.Series(
        {
            "population_change_n": population,
            "foreign_change_n": foreign,
            "other_change_n": population - foreign,
            "foreign_share_of_change_pct": 100 * foreign / population if population > 0 else np.nan,
        }
    )


def national_balance(euro: pd.DataFrame) -> pd.DataFrame:
    """Annual national balance with rates per 1,000 of the 1 January population and the revision split out.

    ``euro`` is the interim ``eurostat_demography`` table. Net migration here is the flow (plus statistical
    adjustment); ``revision_n`` (2020-2021) is shown on its own so the flows are not mixed with it.
    """
    d = euro.set_index(YEAR_KEY).copy()
    for col in ("natural_change", "net_migration", "revision", "population_change"):
        d[f"{col}_per_1000"] = 1000 * d[f"{col}_n"] / d["population_jan_n"]
    d["total_change_n"] = d["population_change_n"] + d["revision_n"]
    return d


def period_balance(euro: pd.DataFrame, periods: list[tuple[int, int]]) -> pd.DataFrame:
    """Sums over inclusive year ranges: natural change, net migration, revision, and migration's share of the change.

    ``migration_share_of_change_pct`` is net migration over total change (flows plus revision); it is missing when
    the total did not grow, since it would not be a share of anything. ``years_with_decline_n`` counts the years
    in which natural change was negative.
    """
    d = euro.set_index(YEAR_KEY)
    rows = {}
    for start, end in periods:
        t = d.loc[start:end]
        natural, migration, revision = (
            t["natural_change_n"].sum(),
            t["net_migration_n"].sum(),
            t["revision_n"].sum(),
        )
        total = natural + migration + revision
        rows[f"{start}-{end}"] = {
            "years_n": len(t),
            "natural_change_n": natural,
            "net_migration_n": migration,
            "revision_n": revision,
            "total_change_n": total,
            "natural_per_year_n": natural / len(t),
            "migration_per_year_n": migration / len(t),
            "migration_share_of_change_pct": 100 * migration / total if total > 0 else np.nan,
            "years_with_decline_n": int((t["natural_change_n"] < 0).sum()),
        }
    return pd.DataFrame(rows).T


def municipal_balance(
    change: pd.DataFrame, panel: pd.DataFrame, start: int, end: int, by: str | None = None
) -> pd.DataFrame:
    """Natural increase and net migration summed over ``start``-``end`` (inclusive), per municipality or group.

    Rates are per 1,000 residents in the first year of the period, per year. Population of the first year comes
    from the panel; ``by`` is a panel column (density_class, coast_class, district), otherwise one row per
    municipality.
    """
    c = (
        change[change[YEAR_KEY].between(start, end)]
        .groupby(MUNI_KEY)[["natural_increase_n", "net_migration_n", "population_change_n"]]
        .sum()
    )
    attrs = panel.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)
    c["population_start_n"] = panel[panel[YEAR_KEY] == start].set_index(MUNI_KEY)["population_n"]
    if by is not None:
        c[by] = attrs[by]
        c = c.groupby(by)[
            ["natural_increase_n", "net_migration_n", "population_change_n", "population_start_n"]
        ].sum()
    years = end - start + 1
    c["natural_per_1000_year"] = 1000 * c["natural_increase_n"] / c["population_start_n"] / years
    c["migration_per_1000_year"] = 1000 * c["net_migration_n"] / c["population_start_n"] / years
    return c


def growth_regimes(balance: pd.DataFrame) -> pd.DataFrame:
    """Municipalities by how they changed, from ``municipal_balance`` (one row per municipality).

    ``natural_growth`` and ``migration_gain`` need both signs to be positive; a place can lose people while
    births still exceed deaths (``migration_loss``), or grow only because migrants offset natural decline
    (``migration_offsets_decline``). Counts, the population in the first year and the total change per regime.
    """
    natural, migration = balance["natural_increase_n"], balance["net_migration_n"]
    regime = np.select(
        [
            (natural >= 0) & (migration >= 0),
            (natural < 0) & (migration >= 0) & (natural + migration >= 0),
            (natural < 0) & (migration >= 0),
            natural >= 0,
        ],
        [
            "natural_and_migration_gain",
            "migration_offsets_decline",
            "migration_too_small",
            "migration_loss",
        ],
        default="decline_both",
    )
    d = balance.assign(regime=regime)
    out = d.groupby("regime").agg(
        municipalities_n=("regime", "size"),
        population_start_n=("population_start_n", "sum"),
        population_change_n=("population_change_n", "sum"),
    )
    out["share_of_municipalities_pct"] = 100 * out["municipalities_n"] / len(d)
    return out.sort_values("municipalities_n", ascending=False)
