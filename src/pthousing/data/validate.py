"""Schema, key-uniqueness and range checks for interim and processed tables.

``validate_all`` reads every table in ``data/interim`` and returns a report with one row per check
(table, check, ok, detail); with ``strict=True`` it raises if any check fails. Three layers:

* pandera schemas: column types, ranges, allowed categories, unique keys;
* grid checks: municipal tables hold all 308 CAOP municipalities in every period;
* consistency checks: totals equal the sum of their parts, rules of the source hold, and series that two
  sources publish agree (INE vs Eurostat).
"""

from collections.abc import Callable

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from pthousing.config import MUNI_KEY
from pthousing.data import build_panel, harmonize, interim

N_MUNICIPALITIES = 308
PUBLICATION_MIN_N = 33  # INE publishes a municipal median only from 33 observations


def _num(low: float, high: float, nullable: bool = True) -> Column:
    return Column(float, Check.in_range(low, high), nullable=nullable, coerce=True)


def _year(low: int = 1990, high: int = 2030) -> Column:
    return Column(int, Check.in_range(low, high), coerce=True)


def _cat(values: set[str]) -> Column:
    return Column(str, Check.isin(values))


def schemas() -> dict[str, DataFrameSchema]:
    codes = set(harmonize.read_crosswalk()[MUNI_KEY])
    muni = Column(str, Check.isin(codes))
    sizes = {"total", "br_0_1", "br_2", "br_3", "br_4plus"}
    return {
        "ine_median_price_sqm": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2016),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "category": _cat({"total", "new", "existing"}),
                "method": _cat({"2018", "2022"}),
                "price_sqm_eur": _num(50, 20_000),
                "sales_12m_n": _num(0, 100_000),
            },
            unique=[MUNI_KEY, "period_start", "category"],
            strict=True,
        ),
        "ine_median_rent_sqm": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2020),
                "rent_sqm_eur": _num(1, 40),
                "new_leases_n": _num(0, 100_000),
            },
            unique=[MUNI_KEY, "year"],
            strict=True,
        ),
        "ine_income": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2015, 2030),
                "income_mean_eur": _num(3_000, 60_000, nullable=False),
                "income_median_eur": _num(3_000, 60_000),
                "vintage": _cat({"2013", "2024"}),
            },
            unique=[MUNI_KEY, "year"],
            strict=True,
        ),
        "ine_construction": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(1995),
                "size": _cat(sizes),
                "licensed_n": _num(0, 50_000),
                "completed_n": _num(0, 50_000),
            },
            unique=[MUNI_KEY, "year", "size"],
            strict=True,
        ),
        "ine_bank_valuation": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2011),
                "month": Column(int, Check.in_range(1, 12), coerce=True),
                "type": _cat({"total", "flats", "villas"}),
                "valuation_sqm_eur": _num(100, 10_000),
            },
            unique=[MUNI_KEY, "period_start", "type"],
            strict=True,
        ),
        "ine_bank_valuation_annual": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2011),
                "type": _cat({"total", "flats", "villas"}),
                "valuation_sqm_eur": _num(100, 10_000),
            },
            unique=[MUNI_KEY, "year", "type"],
            strict=True,
        ),
        "ine_census": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "census_year": Column(int, Check.isin([2021]), coerce=True),
                "vacant_dwellings_pct": _num(0, 100, nullable=False),
                "occupied_dwellings_n": _num(1, 1_000_000, nullable=False),
                "owner_occupied_n": _num(0, 1_000_000, nullable=False),
                "rented_n": _num(0, 1_000_000, nullable=False),
                "other_tenure_n": _num(0, 1_000_000, nullable=False),
            },
            unique=[MUNI_KEY],
            strict=True,
        ),
        "ine_census_stock": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "census_year": Column(int, Check.isin([2011, 2021]), coerce=True),
                "dwellings_n": _num(1, 2_000_000, nullable=False),
                "dwellings_usual_n": _num(0, 2_000_000, nullable=False),
                "dwellings_secondary_n": _num(0, 2_000_000, nullable=False),
                "dwellings_vacant_n": _num(0, 2_000_000, nullable=False),
                "households_n": _num(1, 2_000_000, nullable=False),
                "dwelling_area_sqm": _num(40, 250, nullable=False),
            },
            unique=[MUNI_KEY, "census_year"],
            strict=True,
        ),
        "ine_population": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2011, 2030),
                "sex": _cat({"total", "m", "f"}),
                "age_group": Column(str, Check.str_matches(r"^(total|\d+-\d+|\d+\+)$")),
                "population_n": _num(0, 5_000_000, nullable=False),
            },
            unique=[MUNI_KEY, "year", "sex", "age_group"],
            strict=True,
        ),
        "aima_foreigners": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2014, 2030),
                "nationality": Column(str, Check.str_matches(r"^([a-z]{2}|other|total)$")),
                "foreign_residents_n": _num(0, 500_000, nullable=False),
            },
            unique=[MUNI_KEY, "year", "nationality"],
            strict=True,
        ),
        "ine_cpi": DataFrameSchema(
            {"year": _year(1948), "cpi_index_b2025": _num(0.1, 500, nullable=False)},
            unique=["year"],
            strict=True,
        ),
        "ine_cpi_monthly": DataFrameSchema(
            {
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(1948),
                "month": Column(int, Check.in_range(1, 12), coerce=True),
                "cpi_index_b2025": _num(0.1, 500, nullable=False),
            },
            unique=["period_start"],
            strict=True,
        ),
        "ine_hpi": DataFrameSchema(
            {
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2009),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "category": _cat({"total", "new", "existing"}),
                "hpi_index_b2025": _num(10, 500, nullable=False),
            },
            unique=["period_start", "category"],
            strict=True,
        ),
        "bp_mortgage": DataFrameSchema(
            {
                "date": Column("datetime64[ns]", coerce=True),
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2003),
                "month": Column(int, Check.in_range(1, 12), coerce=True),
                "mortgage_aprc_new_pct": _num(0, 15, nullable=False),
                "mortgage_rate_new_lt1y_pct": _num(0, 15, nullable=False),
                "mortgage_rate_stock_gt5y_pct": _num(0, 15, nullable=False),
                "mortgage_new_lt1y_volume_eur_m": _num(0, 10_000, nullable=False),
                "mortgage_rate_new_fixed_p50_pct": _num(0, 15),
            },
            unique=["date"],
            strict=True,
        ),
        "eurostat_hpi": DataFrameSchema(
            {
                "geo": _cat({"PT", "ES", "IT", "FR", "DE", "IE", "EU27_2020"}),
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2005),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "hpi_index_b2015": _num(10, 600, nullable=False),
            },
            unique=["geo", "period_start"],
            strict=True,
        ),
        "eurostat_hicp": DataFrameSchema(
            {
                "geo": _cat({"PT", "EU27_2020"}),
                "year": _year(1996),
                "hicp_index_b2015": _num(10, 300, nullable=False),
            },
            unique=["geo", "year"],
            strict=True,
        ),
        "rnal_al": DataFrameSchema(
            {
                "rnal_n": Column(int, Check.ge(1), coerce=True),
                "registered": Column("datetime64[ns]", coerce=True),
                "registered_before_2008": Column(bool),
                "opened": Column("datetime64[ns]", coerce=True, nullable=True),
                "modality": Column(str, nullable=True),
                "guests_n": _num(0, 5_000),
                MUNI_KEY: muni,
                # 4-digit municipality code + 2 chars; 66 units carry letters (e.g. '0302FG') instead of digits
                "parish_code": Column(str, Check.str_matches(r"^\d{4}[0-9A-Z]{2}$")),
                "parish_name": Column(str, nullable=True),
                "nuts3_name": Column(str, nullable=True),
                "geo_reliability": Column(
                    str, Check.isin({"reliable", "low", "unreliable"}), nullable=True
                ),
                "lon": _num(-9.6, -6.1, nullable=False),  # mainland bounding box
                "lat": _num(36.9, 42.2, nullable=False),
                "snapshot_date": Column("datetime64[ns]", coerce=True),
            },
            unique=["rnal_n"],
            strict=True,
        ),
    }


# ---- consistency checks: each returns None when fine, else a message ------------------------------


def _grid(df: pd.DataFrame, by: list[str]) -> str | None:
    n = df.groupby(by)[MUNI_KEY].nunique()
    bad = n[n != N_MUNICIPALITIES]
    return (
        None
        if bad.empty
        else f"{len(bad)} of {len(n)} groups lack the {N_MUNICIPALITIES} municipalities"
    )


def _sum_equals(total: pd.Series, parts: pd.Series, tol: float = 0.0) -> str | None:
    diff = (total - parts).abs().dropna()
    return (
        None
        if diff.empty or diff.max() <= tol
        else f"max difference {diff.max():g} in {int((diff > tol).sum())} rows"
    )


def check_price(df: pd.DataFrame) -> list[str | None]:
    old_non_total = ((df["method"] == "2018") & (df["category"] != "total")).sum()
    sales_outside_total = df.loc[df["category"] != "total", "sales_12m_n"].notna().sum()
    last_2018 = df.loc[df["method"] == "2018", "period_start"].max()
    first_2022 = df.loc[df["method"] == "2022", "period_start"].min()
    return [
        _grid(df, ["period_start", "category"]),
        None if old_non_total == 0 else "2018 method rows exist for new / existing categories",
        None if sales_outside_total == 0 else "sales counts present outside the total category",
        None if last_2018 < first_2022 else "the 2018 and 2022 methods overlap in time",
    ]


def check_rent(df: pd.DataFrame) -> list[str | None]:
    published = df.dropna(subset=["rent_sqm_eur"])
    below = (
        published["new_leases_n"].isna() | (published["new_leases_n"] < PUBLICATION_MIN_N)
    ).sum()
    return [
        _grid(df, ["year"]),
        None
        if below == 0
        else f"{below} rents published with fewer than {PUBLICATION_MIN_N} new leases",
    ]


def check_income(df: pd.DataFrame) -> list[str | None]:
    both = df.dropna(subset=["income_median_eur"])
    below = (both["income_mean_eur"] < both["income_median_eur"]).sum()
    return [
        _grid(df, ["year"]),
        None if below == 0 else f"{below} municipality-years with mean income below the median",
        None if df["year"].nunique() == 10 else "income years are not the 10 years 2015-2024",
    ]


def check_construction(df: pd.DataFrame) -> list[str | None]:
    wide = df.pivot(index=[MUNI_KEY, "year"], columns="size", values=["licensed_n", "completed_n"])
    parts = ["br_0_1", "br_2", "br_3", "br_4plus"]
    msgs = [_grid(df, ["year", "size"])]
    msgs.append(
        _sum_equals(
            wide[("licensed_n", "total")], wide["licensed_n"][parts].sum(axis=1, min_count=1)
        )
    )
    # Completions: the size split is incomplete before 2003 (parts below the total, never above); from
    # 2003 on it must reconcile except for a handful of cells.
    diff = (
        wide[("completed_n", "total")] - wide["completed_n"][parts].sum(axis=1, min_count=1)
    ).dropna()
    recent = diff[diff.index.get_level_values("year") >= 2003]
    recent_total = wide[("completed_n", "total")].loc[recent.index].sum()
    share = recent.sum() / recent_total
    msgs.append(
        "size categories of completions exceed the total"
        if (diff < 0).any()
        else None
        if share < 0.001
        else f"completions size split misses {share:.2%} of dwellings since 2003"
    )
    nan_munis = set(df.loc[df["licensed_n"].isna(), MUNI_KEY])
    expected = set(harmonize.VALID_FROM_YEAR)
    msgs.append(
        None
        if nan_munis == expected
        else f"missing licences outside Vizela/Trofa/Odivelas: {sorted(nan_munis - expected)}"
    )
    return msgs


def check_valuation(df: pd.DataFrame) -> list[str | None]:
    return [_grid(df, ["period_start", "type"])]


def check_valuation_annual(df: pd.DataFrame) -> list[str | None]:
    return [_grid(df, ["year", "type"])]


def check_census(df: pd.DataFrame) -> list[str | None]:
    parts = df[["owner_occupied_n", "rented_n", "other_tenure_n"]].sum(axis=1)
    return [_grid(df, ["census_year"]), _sum_equals(df["occupied_dwellings_n"], parts)]


def check_census_stock(df: pd.DataFrame) -> list[str | None]:
    parts = df[["dwellings_usual_n", "dwellings_secondary_n", "dwellings_vacant_n"]].sum(axis=1)
    ratio = df["dwellings_usual_n"] / df["households_n"]
    return [
        _grid(df, ["census_year"]),
        _sum_equals(df["dwellings_n"], parts),
        None
        if ratio.between(0.7, 1.05).all()
        else "dwellings of usual residence and households differ by more than 30% in some municipality",
    ]


def check_population(df: pd.DataFrame) -> list[str | None]:
    key = [MUNI_KEY, "year"]
    tot = df[(df["sex"] == "total") & (df["age_group"] == "total")].set_index(key)["population_n"]
    by_sex = (
        df[(df["sex"] != "total") & (df["age_group"] == "total")].groupby(key)["population_n"].sum()
    )
    by_age = (
        df[(df["sex"] == "total") & (df["age_group"] != "total")].groupby(key)["population_n"].sum()
    )
    return [
        _grid(df, ["year", "sex", "age_group"]),
        _sum_equals(tot, by_sex),
        _sum_equals(tot, by_age),
    ]


def check_aima_foreigners(df: pd.DataFrame) -> list[str | None]:
    key = [MUNI_KEY, "year"]
    tot = df[df["nationality"] == "total"].set_index(key)["foreign_residents_n"]
    parts = df[df["nationality"] != "total"].groupby(key)["foreign_residents_n"].sum()
    return [_grid(df, ["year", "nationality"]), _sum_equals(tot, parts)]


def check_cpi(df: pd.DataFrame) -> list[str | None]:
    base = df.loc[df["year"] == 2025, "cpi_index_b2025"]
    return [
        None
        if len(base) == 1 and abs(base.iloc[0] - 100) < 1e-6
        else "annual CPI is not 100 in the base year 2025",
        None if df["year"].diff().dropna().eq(1).all() else "annual CPI has gaps",
    ]


def check_cpi_monthly(df: pd.DataFrame) -> list[str | None]:
    return [
        None
        if df["period_start"].diff().dropna().le(pd.Timedelta(days=31)).all()
        else "monthly CPI has gaps"
    ]


def check_hpi(df: pd.DataFrame) -> list[str | None]:
    total = df[(df["category"] == "total") & (df["year"] == 2025)]["hpi_index_b2025"]
    return [
        None
        if len(total) == 4 and abs(total.mean() - 100) < 0.05
        else "HPI 2025 average is not 100 (base year)",
        _gaps_quarterly(df[df["category"] == "total"]["period_start"]),
    ]


def _gaps_quarterly(s: pd.Series) -> str | None:
    return (
        None
        if s.sort_values().diff().dropna().le(pd.Timedelta(days=92)).all()
        else "quarterly series has gaps"
    )


def check_bp(df: pd.DataFrame) -> list[str | None]:
    months = df["date"].dt.to_period("M")
    full = pd.period_range(months.min(), months.max(), freq="M")
    return [
        None
        if len(months) == len(full) and months.is_unique
        else f"{len(full) - len(months)} months missing"
    ]


def check_eurostat_hpi(df: pd.DataFrame) -> list[str | None]:
    pt = df[df["geo"] == "PT"]["period_start"]
    return [
        _gaps_quarterly(pt),
        None if {"PT", "EU27_2020"} <= set(df["geo"]) else "PT or EU27 missing",
    ]


def check_rnal(df: pd.DataFrame) -> list[str | None]:
    future = (df["registered"] > df["snapshot_date"]).sum()
    islands = df[MUNI_KEY].str[:2].astype(int) >= 31
    return [
        None if future == 0 else f"{future} registrations after the snapshot date",
        None
        if not islands.any()
        else f"{int(islands.sum())} island units appear (layer was mainland only)",
    ]


CHECKS: dict[str, Callable[[pd.DataFrame], list[str | None]]] = {
    "ine_median_price_sqm": check_price,
    "ine_median_rent_sqm": check_rent,
    "ine_income": check_income,
    "ine_construction": check_construction,
    "ine_bank_valuation": check_valuation,
    "ine_bank_valuation_annual": check_valuation_annual,
    "ine_census": check_census,
    "ine_census_stock": check_census_stock,
    "ine_population": check_population,
    "aima_foreigners": check_aima_foreigners,
    "ine_cpi": check_cpi,
    "ine_cpi_monthly": check_cpi_monthly,
    "ine_hpi": check_hpi,
    "bp_mortgage": check_bp,
    "eurostat_hpi": check_eurostat_hpi,
    "rnal_al": check_rnal,
}


# ---- cross-source checks --------------------------------------------------------------------------


def cross_checks(tables: dict[str, pd.DataFrame]) -> list[tuple[str, str | None]]:
    """Series that two sources publish must agree: Eurostat vs INE house price index and CPI vs HICP."""
    out: list[tuple[str, str | None]] = []
    ine_hpi = (
        tables["ine_hpi"].query("category == 'total'").set_index("period_start")["hpi_index_b2025"]
    )
    ref = ine_hpi[ine_hpi.index.year == 2015].mean()
    rebased = ine_hpi / ref * 100
    es = tables["eurostat_hpi"].query("geo == 'PT'").set_index("period_start")["hpi_index_b2015"]
    both = pd.concat([rebased.rename("ine"), es.rename("es")], axis=1, sort=True).dropna()
    gap = (both["ine"] - both["es"]).abs().max()
    out.append(
        (
            "eurostat_hpi_vs_ine_hpi",
            None if len(both) > 60 and gap < 0.1 else f"max gap {gap:.3f} on {len(both)} quarters",
        )
    )

    cpi = tables["ine_cpi"].set_index("year")["cpi_index_b2025"]
    cpi15 = cpi / cpi[2015] * 100
    hicp = tables["eurostat_hicp"].query("geo == 'PT'").set_index("year")["hicp_index_b2015"]
    ratio = (hicp / cpi15).dropna()
    out.append(
        (
            "eurostat_hicp_vs_ine_cpi",
            None
            if len(ratio) > 20 and ratio.between(0.98, 1.02).all()
            else f"ratio range {ratio.min():.3f}-{ratio.max():.3f}",
        )
    )

    pop = tables["ine_population"].query("sex == 'total' and age_group == 'total'")
    out.append(("population_covers_all_municipalities", _grid(pop, ["year"])))
    return out


# ---- processed panels -----------------------------------------------------------------------------

PANEL_YEARS = list(range(1995, 2026))
REAL_PAIRS = [
    "price_sqm_eur",
    "price_existing_sqm_eur",
    "price_new_sqm_eur",
    "rent_sqm_eur",
    "valuation_sqm_eur",
    "income_mean_eur",
    "income_median_eur",
]
FIRST_YEAR = {
    "price_sqm_eur": 2016,
    "rent_sqm_eur": 2020,
    "income_median_eur": 2015,
    "population_n": 2011,
    "foreign_residents_n": 2014,
}


def panel_schemas() -> dict[str, DataFrameSchema]:
    """Key columns, ranges and uniqueness of the processed panels (other columns are not constrained)."""
    codes = set(harmonize.read_crosswalk()[MUNI_KEY])
    return {
        "panel_municipality_year": DataFrameSchema(
            {
                MUNI_KEY: Column(str, Check.isin(codes)),
                "year": Column(int, Check.in_range(1995, 2025), coerce=True),
                "territory": _cat({"continente", "madeira", "azores"}),
                "price_sqm_eur": _num(50, 20_000),
                "rent_sqm_eur": _num(1, 40),
                "income_median_eur": _num(3_000, 60_000),
                "dwelling_area_sqm": _num(50, 200, nullable=False),
                "deflator_to_base_year": _num(0.5, 3, nullable=False),
                "pti_years": _num(0.5, 60),
                "pti_years_100sqm": _num(0.5, 60),
                "rti_pct": _num(5, 300),
                "mortgage_burden_pct": _num(1, 400),
                "mortgage_rate_new_lt1y_pct": _num(0, 15),  # BPstat starts in 2003
            },
            unique=[MUNI_KEY, "year"],
            strict=False,
        ),
        "national_quarterly": DataFrameSchema(
            {
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": Column(int, Check.in_range(2005, 2030), coerce=True),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "hpi_pt_b2015": _num(10, 600),
                "hpi_eu27_b2015": _num(10, 600, nullable=False),
                "cpi_index_b2025": _num(10, 500),
                "deflator_to_base_year": _num(0.5, 3),
                "mortgage_rate_new_lt1y_pct": _num(0, 15),
                "mortgage_payment_100k_eur": _num(100, 1_500),
            },
            unique=["period_start"],
            strict=False,
        ),
    }


def _rel_diff(a: pd.Series, b: pd.Series) -> float:
    both = pd.concat([a, b], axis=1).dropna()
    return (
        0.0
        if both.empty
        else float(((both.iloc[:, 0] - both.iloc[:, 1]).abs() / both.iloc[:, 1].abs()).max())
    )


def check_panel_municipality_year(
    p: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> list[str | None]:
    msgs: list[str | None] = [
        _grid(p, ["year"]),
        None if sorted(p["year"].unique()) == PANEL_YEARS else "panel years are not 1995-2025",
    ]
    bad = [
        c for c in REAL_PAIRS if _rel_diff(p[f"{c}_real"], p[c] * p["deflator_to_base_year"]) > 1e-9
    ]
    msgs.append(None if not bad else f"real values differ from nominal x deflator: {bad}")
    base = p.loc[p["year"] == 2024, "deflator_to_base_year"]
    msgs.append(None if (base == 1).all() else "the deflator is not 1 in the base year 2024")
    msgs.append(
        None
        if all(p.loc[p["year"] < y, c].isna().all() for c, y in FIRST_YEAR.items())
        else "values appear before the first year each source covers"
    )
    rate_missing = set(p.loc[p["mortgage_rate_new_lt1y_pct"].isna(), "year"])
    msgs.append(
        None
        if rate_missing == set(range(1995, 2003))
        else f"mortgage rate missing in years {sorted(rate_missing)}"
    )

    # indicators recomputed with plain formulas (independent of features/affordability.py)
    area, income = p["dwelling_area_sqm"], p["income_median_eur"]
    pti = p["price_sqm_eur"] * area / income
    rti = 100 * p["rent_sqm_eur"] * area * 12 / income
    r, n = p["mortgage_rate_new_lt1y_pct"] / 1200, 12 * 30
    payment = 0.8 * p["price_sqm_eur"] * area * r / (1 - (1 + r) ** -n)
    burden = 100 * 12 * payment / income
    for name, expected in (("pti_years", pti), ("rti_pct", rti), ("mortgage_burden_pct", burden)):
        rel = _rel_diff(p[name], expected)
        msgs.append(
            None if rel < 1e-9 else f"{name} differs from its definition (max relative {rel:.2e})"
        )

    # the panel keeps the totals of the interim tables
    cons = (
        tables["ine_construction"]
        .query("size == 'total'")
        .groupby("year")[["licensed_n", "completed_n"]]
        .sum()
    )
    got = p.groupby("year")[["licensed_n", "completed_n"]].sum()
    msgs.append(
        None
        if (got - cons.reindex(got.index)).abs().max().max() == 0
        else "licensed / completed dwellings differ from the interim table"
    )
    pop = (
        tables["ine_population"]
        .query("sex == 'total' and age_group == 'total'")
        .groupby("year")["population_n"]
        .sum()
    )
    got_pop = p.groupby("year")["population_n"].sum(min_count=1).dropna()
    msgs.append(
        None
        if (got_pop - pop.reindex(got_pop.index)).abs().max() == 0
        else "population differs from the interim table"
    )

    foreign = (
        tables["aima_foreigners"]
        .query("nationality == 'total'")
        .groupby("year")["foreign_residents_n"]
        .sum()
    )
    got_foreign = p.groupby("year")["foreign_residents_n"].sum(min_count=1).dropna()
    msgs.append(
        None
        if (got_foreign - foreign.reindex(got_foreign.index)).abs().max() == 0
        else "foreign residents differ from the interim table"
    )

    static = p.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)
    computed = 100 * static["dwellings_vacant_2021_n"] / static["dwellings_2021_n"]
    gap = (computed - static["vacant_dwellings_pct_2021"]).abs().max()
    msgs.append(
        None if gap < 0.1 else f"census vacancy: published and computed differ by {gap:.2f} pp"
    )

    islands = p["territory"] != "continente"
    registered_2026 = int((tables["rnal_al"]["registered"].dt.year >= 2026).sum())
    survivors = p.loc[p["year"] == 2025, "al_survivor_units_n"].sum()
    snapshot = static["al_units_snapshot_n"].sum()
    msgs.append(
        None
        if p.loc[islands, "al_survivor_units_n"].isna().all()
        and p.loc[~islands, "al_survivor_units_n"].notna().all()
        else "short-term rentals are not NaN exactly for the island municipalities"
    )
    msgs.append(
        None
        if survivors + registered_2026 == snapshot
        else "rental units registered up to 2025 plus those of 2026 do not add up to the snapshot"
    )
    return msgs


def check_national_quarterly(q: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> list[str | None]:
    steps = q["period_start"].diff().dropna()
    msgs: list[str | None] = [
        None
        if steps.between(pd.Timedelta(days=89), pd.Timedelta(days=92)).all()
        else "quarters are not consecutive"
    ]
    for real, nominal in (
        ("hpi_total_real_b2025", "hpi_total_b2025"),
        ("hpi_pt_real_b2015", "hpi_pt_b2015"),
    ):
        rel = _rel_diff(q[real], q[nominal] * q["deflator_to_base_year"])
        msgs.append(None if rel < 1e-9 else f"{real} differs from nominal x deflator")
    deflator_2024 = q.loc[q["year"] == 2024, "deflator_to_base_year"].mean()
    msgs.append(
        None
        if abs(deflator_2024 - 1) < 0.01
        else f"quarterly deflator averages {deflator_2024:.4f} in 2024"
    )
    ine = (
        tables["ine_hpi"].query("category == 'total'").set_index("period_start")["hpi_index_b2025"]
    )
    msgs.append(
        None
        if _rel_diff(
            q.set_index("period_start")["hpi_total_b2025"],
            ine.reindex(q["period_start"]).set_axis(q["period_start"]),
        )
        == 0
        else "INE HPI differs from the interim table"
    )
    rate_up = q.dropna(subset=["mortgage_rate_new_lt1y_pct"]).sort_values(
        "mortgage_rate_new_lt1y_pct"
    )
    msgs.append(
        None
        if rate_up["mortgage_payment_100k_eur"].is_monotonic_increasing
        else "the payment on a fixed loan does not rise with the rate"
    )
    return msgs


PANEL_CHECKS = {
    "panel_municipality_year": check_panel_municipality_year,
    "national_quarterly": check_national_quarterly,
}


def validate_panels(tables: dict[str, pd.DataFrame]) -> list[dict]:
    """Schema and consistency checks of the processed panels against the interim tables."""
    rows = []
    for name, schema in panel_schemas().items():
        panel = build_panel.read(name)
        try:
            schema.validate(panel, lazy=True)
            rows.append({"table": name, "check": "schema", "ok": True, "detail": ""})
        except pa.errors.SchemaErrors as exc:
            cases = exc.failure_cases.groupby(["column", "check"]).size()
            detail = "; ".join(f"{col}: {chk} ({n})" for (col, chk), n in cases.head(5).items())
            rows.append({"table": name, "check": "schema", "ok": False, "detail": detail})
        for i, msg in enumerate(PANEL_CHECKS[name](panel, tables)):
            rows.append(
                {
                    "table": name,
                    "check": f"consistency_{i + 1}",
                    "ok": msg is None,
                    "detail": msg or "",
                }
            )
    return rows


# ---- runner ---------------------------------------------------------------------------------------


def validate_table(name: str, df: pd.DataFrame) -> list[dict]:
    """Run the schema and the consistency checks of one table; one result dict per check."""
    results = []
    try:
        schemas()[name].validate(df, lazy=True)
        results.append({"table": name, "check": "schema", "ok": True, "detail": ""})
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases.groupby(["column", "check"]).size()
        detail = "; ".join(f"{col}: {chk} ({n})" for (col, chk), n in cases.head(5).items())
        results.append({"table": name, "check": "schema", "ok": False, "detail": detail})
    for i, msg in enumerate(CHECKS.get(name, lambda _: [])(df)):
        results.append(
            {"table": name, "check": f"consistency_{i + 1}", "ok": msg is None, "detail": msg or ""}
        )
    return results


def validate_all(strict: bool = True) -> pd.DataFrame:
    """Validate every interim table (and cross-source checks); raise on any failure when ``strict``."""
    tables = {name: interim.read(name) for name in schemas()}
    rows = [r for name, df in tables.items() for r in validate_table(name, df)]
    rows += [
        {"table": "cross_source", "check": name, "ok": msg is None, "detail": msg or ""}
        for name, msg in cross_checks(tables)
    ]
    rows += validate_panels(tables)
    geometry = interim.read("caop_municipalities")
    caop_ok = (
        len(geometry) == N_MUNICIPALITIES
        and geometry[MUNI_KEY].is_unique
        and bool(geometry.geometry.is_valid.all())
    )
    rows.append(
        {
            "table": "caop_municipalities",
            "check": "308_unique_valid",
            "ok": caop_ok,
            "detail": "" if caop_ok else "bad CAOP list",
        }
    )
    report = pd.DataFrame(rows)
    failed = report[~report["ok"]]
    if strict and not failed.empty:
        raise ValueError("Validation failed:\n" + failed.to_string(index=False))
    return report
