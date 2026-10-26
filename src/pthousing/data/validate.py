"""Schema, key-uniqueness and range checks for interim and processed tables.

``validate_all`` reads every table in ``data/interim`` and returns a report with one row per check
(table, check, ok, detail); with ``strict=True`` it raises if any check fails. Three layers:

* pandera schemas: column types, ranges, allowed categories, unique keys;
* grid checks: municipal tables hold all 308 CAOP municipalities in every period;
* consistency checks: totals equal the sum of their parts, rules of the source hold, and series that two
  sources publish agree (INE vs Eurostat).
"""

from collections.abc import Callable

import numpy as np
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
        "ine_households_size": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "census_year": Column(int, Check.isin([2011, 2021]), coerce=True),
                "size": _cat({"1", "2", "3", "4plus"}),
                "households_n": _num(0, 1_000_000, nullable=False),
            },
            unique=[MUNI_KEY, "census_year", "size"],
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
        "ine_population_change": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2011, 2030),
                "population_change_n": _num(-50_000, 150_000, nullable=False),
                "natural_increase_n": _num(-10_000, 10_000, nullable=False),
                "net_migration_n": _num(-50_000, 150_000, nullable=False),
            },
            unique=[MUNI_KEY, "year"],
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
        "ine_construction_costs": DataFrameSchema(
            {
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2000),
                "month": Column(int, Check.in_range(1, 12), coerce=True),
                "factor": _cat({"total", "materials", "labour"}),
                "construction_cost_b2021": _num(10, 400, nullable=False),
            },
            unique=["period_start", "factor"],
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
        "bp_household_debt": DataFrameSchema(
            {
                "date": Column("datetime64[ns]", coerce=True),
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(2007),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "housing_loans_stock_eur_m": _num(50_000, 200_000, nullable=False),
                "housing_loans_gdp_pct": _num(10, 100),
                "housing_loans_growth_pct": _num(-15, 25),
                "household_debt_stock_eur_m": _num(80_000, 300_000, nullable=False),
                "household_debt_gdp_pct": _num(20, 120),
                "household_debt_income_pct": _num(30, 160),
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
        "bis_spp": DataFrameSchema(
            {
                "period_start": Column("datetime64[ns]", coerce=True),
                "year": _year(1988),
                "quarter": Column(int, Check.in_range(1, 4), coerce=True),
                "hpi_nominal_b2010": _num(10, 600, nullable=False),
                "hpi_real_b2010": _num(10, 600, nullable=False),
            },
            unique=["period_start"],
            strict=True,
        ),
        "oecd_house_prices": DataFrameSchema(
            {
                "year": _year(1959, 2030),
                "hpi_nominal_b2015": _num(10, 600),
                "hpi_real_b2015": _num(10, 600),
                "rent_index_b2015": _num(0.5, 400, nullable=False),
                "price_to_rent_b2015": _num(10, 600),
                "price_to_income_b2015": _num(10, 600),
                "price_to_rent_std": _num(10, 400),
                "price_to_income_std": _num(10, 400),
            },
            unique=["year"],
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
        "eurostat_demography": DataFrameSchema(
            {
                "year": _year(1960),
                "population_jan_n": _num(5e6, 15e6, nullable=False),
                "population_change_n": _num(-300_000, 600_000, nullable=False),
                "natural_change_n": _num(-100_000, 200_000, nullable=False),
                "net_migration_n": _num(-300_000, 600_000, nullable=False),
                "births_n": _num(50_000, 300_000, nullable=False),
                "deaths_n": _num(50_000, 200_000, nullable=False),
                "revision_n": _num(-300_000, 300_000, nullable=False),
            },
            unique=["year"],
            strict=True,
        ),
        "eurostat_macro": DataFrameSchema(
            {
                "year": _year(1970),
                "gdp_growth_pct": _num(-15, 15),
                "unemployment_pct": _num(2, 20),
                "compensation_per_employee_eur": _num(1_000, 60_000),
            },
            unique=["year"],
            strict=True,
        ),
        "eurostat_property_tax": DataFrameSchema(
            {
                "year": _year(1995),
                "imi_revenue_eur_m": _num(100, 5_000, nullable=False),
                "imt_revenue_eur_m": _num(100, 5_000, nullable=False),
                "gdp_eur_m": _num(50_000, 400_000, nullable=False),
            },
            unique=["year"],
            strict=True,
        ),
        "eurostat_property_tax_peers": DataFrameSchema(
            {
                "geo": _cat({"PT", "ES", "IT", "FR", "DE", "IE", "EU27_2020"}),
                "year": _year(1995),
                "land_buildings_tax_eur_m": _num(100, 500_000, nullable=False),
                "transaction_tax_eur_m": _num(0, 500_000),
                "gdp_eur_m": _num(10_000, 30_000_000, nullable=False),
            },
            unique=["geo", "year"],
            strict=True,
        ),
        "eurostat_housing_spending": DataFrameSchema(
            {
                "geo": _cat({"PT", "ES", "IT", "FR", "DE", "IE", "EU27_2020"}),
                "year": _year(1995),
                "housing_development_eur_m": _num(0, 200_000),
                "housing_benefits_eur_m": _num(0, 200_000),
                "housing_amenities_eur_m": _num(0, 300_000, nullable=False),
                "gdp_eur_m": _num(10_000, 30_000_000, nullable=False),
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
        "at_imi_rates": DataFrameSchema(
            {
                MUNI_KEY: muni,
                "year": _year(2012, 2025),
                "imi_urban_pct": _num(
                    0.3, 0.5
                ),  # CIMI art. 112: 0.30 to 0.45, 0.50 for some until 2023
                "imi_rustic_pct": _num(0.8, 0.8),  # one national rate
                "parish_rates": Column(bool),
                "deduction_link": Column(bool),
            },
            unique=[MUNI_KEY, "year"],
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


def check_households_size(df: pd.DataFrame) -> list[str | None]:
    return [_grid(df, ["census_year", "size"])]


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


def check_population_change(df: pd.DataFrame) -> list[str | None]:
    parts = df["natural_increase_n"] + df["net_migration_n"]
    return [_grid(df, ["year"]), _sum_equals(df["population_change_n"], parts)]


def check_eurostat_demography(df: pd.DataFrame) -> list[str | None]:
    years = df["year"]
    gaps = None if years.diff().dropna().eq(1).all() else "years are not consecutive"
    natural = df["births_n"] - df["deaths_n"]
    parts = df["natural_change_n"] + df["net_migration_n"]
    return [
        gaps,
        _sum_equals(df["natural_change_n"], natural),
        _sum_equals(df["population_change_n"], parts),
        None
        if df["revision_n"].abs().le(1).sum() >= len(df) - 3
        else "revisions in more than 3 years",
    ]


def check_eurostat_macro(df: pd.DataFrame) -> list[str | None]:
    years = df["year"]
    gaps = None if years.diff().dropna().eq(1).all() else "years are not consecutive"
    comp = df.set_index("year")["compensation_per_employee_eur"].dropna()
    jump = comp.pct_change().abs().max()
    return [gaps, None if jump < 0.25 else f"compensation per employee jumps {jump:.0%} in a year"]


def check_eurostat_property_tax(df: pd.DataFrame) -> list[str | None]:
    years = df["year"]
    gaps = None if years.diff().dropna().eq(1).all() else "years are not consecutive"
    jump = df[["imi_revenue_eur_m", "imt_revenue_eur_m"]].pct_change().abs().max().max()
    return [gaps, None if jump < 0.6 else f"a property tax series jumps {jump:.0%} in a year"]


def check_eurostat_property_tax_peers(df: pd.DataFrame) -> list[str | None]:
    gaps = df.groupby("geo")["year"].apply(lambda y: bool(y.diff().dropna().eq(1).all()))
    share = 100 * df["land_buildings_tax_eur_m"] / df["gdp_eur_m"]
    return [
        None if gaps.all() else f"years are not consecutive for {list(gaps[~gaps].index)}",
        None if share.between(0.1, 4).all() else "recurrent property tax outside 0.1% to 4% of GDP",
    ]


def check_eurostat_housing_spending(df: pd.DataFrame) -> list[str | None]:
    gaps = df.groupby("geo")["year"].apply(lambda y: bool(y.diff().dropna().eq(1).all()))
    inside = df["housing_development_eur_m"].isna() | (
        df["housing_development_eur_m"] <= df["housing_amenities_eur_m"] + 1e-6
    )
    return [
        None if gaps.all() else f"years are not consecutive for {list(gaps[~gaps].index)}",
        None if inside.all() else "housing development exceeds housing and community amenities",
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


def check_construction_costs(df: pd.DataFrame) -> list[str | None]:
    wide = df.pivot(index="period_start", columns="factor", values="construction_cost_b2021")
    base = wide[wide.index.year == 2021].mean()
    lo, hi = wide[["materials", "labour"]].min(axis=1), wide[["materials", "labour"]].max(axis=1)
    inside = ((wide["total"] >= lo - 0.5) & (wide["total"] <= hi + 0.5)).all()
    gaps = wide.index.to_series().diff().dropna().le(pd.Timedelta(days=31)).all()
    return [
        None
        if (base - 100).abs().max() < 0.5
        else "construction cost index does not average 100 in 2021",
        None if inside else "total cost index lies outside materials and labour",
        None if gaps else "monthly construction cost series has gaps",
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


def check_bp_household_debt(df: pd.DataFrame) -> list[str | None]:
    return [
        _gaps_quarterly(df["date"]),
        None
        if (df["housing_loans_stock_eur_m"] < df["household_debt_stock_eur_m"]).all()
        else "housing loans exceed total household debt",
    ]


def check_eurostat_hpi(df: pd.DataFrame) -> list[str | None]:
    pt = df[df["geo"] == "PT"]["period_start"]
    return [
        _gaps_quarterly(pt),
        None if {"PT", "EU27_2020"} <= set(df["geo"]) else "PT or EU27 missing",
    ]


def check_bis_spp(df: pd.DataFrame) -> list[str | None]:
    base = df[df["year"] == 2010]
    return [
        _gaps_quarterly(df["period_start"]),
        None
        if abs(base["hpi_nominal_b2010"].mean() - 100) < 0.05
        else "nominal index does not average 100 in 2010",
        None
        if df["year"].min() == 1988 and len(df) > 150
        else "BIS series is shorter than expected",
    ]


def check_oecd_house_prices(df: pd.DataFrame) -> list[str | None]:
    row = df.set_index("year").loc[2015]
    base_ok = all(
        abs(row[c] - 100) < 0.01
        for c in (
            "hpi_nominal_b2015",
            "hpi_real_b2015",
            "price_to_income_b2015",
            "rent_index_b2015",
        )
    )
    return [
        None if base_ok else "an index does not equal 100 in its base year 2015",
        None
        if df.dropna(subset=["price_to_income_b2015"])["year"].min() == 1995
        else "price-to-income should start in 1995",
        None if df["year"].is_monotonic_increasing and df["year"].is_unique else "years not unique",
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


def check_at_imi_rates(df: pd.DataFrame) -> list[str | None]:
    no_rate = df["imi_urban_pct"].isna()
    unexplained = (no_rate & ~df["parish_rates"]).sum()
    share = no_rate.mean()
    years = sorted(df["year"].unique())
    return [
        _grid(df, ["year"]),
        None if unexplained == 0 else f"{unexplained} missing urban rates without parish rates",
        None
        if share < 0.05
        else f"{100 * share:.1f}% of municipality-years have no single urban rate",
        None
        if years == list(range(2012, 2026))
        else f"years are {years[0]}-{years[-1]}, not 2012-2025",
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
    "ine_households_size": check_households_size,
    "ine_population": check_population,
    "ine_population_change": check_population_change,
    "aima_foreigners": check_aima_foreigners,
    "ine_cpi": check_cpi,
    "ine_cpi_monthly": check_cpi_monthly,
    "ine_hpi": check_hpi,
    "ine_construction_costs": check_construction_costs,
    "bp_mortgage": check_bp,
    "bp_household_debt": check_bp_household_debt,
    "eurostat_hpi": check_eurostat_hpi,
    "eurostat_demography": check_eurostat_demography,
    "eurostat_macro": check_eurostat_macro,
    "eurostat_property_tax": check_eurostat_property_tax,
    "eurostat_housing_spending": check_eurostat_housing_spending,
    "eurostat_property_tax_peers": check_eurostat_property_tax_peers,
    "bis_spp": check_bis_spp,
    "oecd_house_prices": check_oecd_house_prices,
    "rnal_al": check_rnal,
    "at_imi_rates": check_at_imi_rates,
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

    bis = tables["bis_spp"].set_index("period_start")
    ratio = (bis["hpi_nominal_b2010"] / ine_hpi).dropna()
    out.append(
        (
            "bis_hpi_equals_ine_hpi_from_2009",
            None
            if len(ratio) > 60 and ratio.max() / ratio.min() - 1 < 1e-4
            else f"BIS / INE ratio varies by {100 * (ratio.max() / ratio.min() - 1):.3f}% over {len(ratio)} quarters",
        )
    )
    annual = (
        bis.groupby("year")["hpi_real_b2010"].mean()
        / bis.groupby("year")["hpi_nominal_b2010"].mean()
    )
    implied = (annual / annual[2015]) * (cpi15 / 100)
    out.append(
        (
            "bis_real_uses_the_ine_cpi",
            None
            if implied.dropna().between(0.995, 1.005).all() and len(implied.dropna()) >= 30
            else f"implied deflator vs CPI range {implied.min():.3f}-{implied.max():.3f}",
        )
    )
    n = bis.groupby("year")["hpi_nominal_b2010"].agg(["mean", "count"])
    growth_bis = np.log(n[n["count"] == 4]["mean"]).diff()
    growth_oecd = np.log(tables["oecd_house_prices"].set_index("year")["hpi_nominal_b2015"]).diff()
    gap = (growth_bis - growth_oecd).abs().dropna()
    seam = gap.get(2009, 0.0)  # the join of two compilations: BIS and OECD treat it differently
    out.append(
        (
            "bis_vs_oecd_annual_growth",
            None
            if gap.drop(2009, errors="ignore").max() < 0.003 and seam < 0.02
            else f"max gap {gap.drop(2009, errors='ignore').max():.4f}, 2009: {seam:.4f}",
        )
    )

    if "ine_households_size" in tables:
        by_size = (
            tables["ine_households_size"].groupby([MUNI_KEY, "census_year"])["households_n"].sum()
        )
        stock = tables["ine_census_stock"].set_index([MUNI_KEY, "census_year"])["households_n"]
        out.append(
            (
                "households_by_size_sum_to_census_total",
                _sum_equals(stock, by_size.reindex(stock.index)),
            )
        )

    pop = tables["ine_population"].query("sex == 'total' and age_group == 'total'")
    out.append(("population_covers_all_municipalities", _grid(pop, ["year"])))
    if "ine_population_change" in tables and "eurostat_demography" in tables:
        out.append(
            (
                "ine_population_change_vs_eurostat",
                _population_change_vs_eurostat(
                    tables["ine_population_change"], tables["eurostat_demography"]
                ),
            )
        )
    return out


def _population_change_vs_eurostat(change: pd.DataFrame, euro: pd.DataFrame) -> str | None:
    """Municipal natural increase and population change add up to the national figures (2011 starts at the census)."""
    national = change.groupby("year")[["natural_increase_n", "population_change_n"]].sum()
    es = euro.set_index("year")
    years = [y for y in national.index if y > 2011 and y in es.index]
    natural = _rel_diff(
        national.loc[years, "natural_increase_n"], es.loc[years, "natural_change_n"]
    )
    # the municipal series carries the 2020-2021 revision, which Eurostat's flows leave out
    total = es.loc[years, "population_change_n"] + es.loc[years, "revision_n"]
    change_gap = _rel_diff(national.loc[years, "population_change_n"], total)
    if natural > 0.001 or change_gap > 0.001:
        return f"natural increase differs by {natural:.4f}, population change by {change_gap:.4f}"
    return None


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
    "imi_urban_pct": 2012,
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
        "national_annual_long": DataFrameSchema(
            {
                "year": Column(int, Check.in_range(1988, 2030), coerce=True),
                "hpi_nominal_b2015": _num(10, 600, nullable=False),
                "hpi_real_b2015": _num(10, 600, nullable=False),
                "cpi_index_b2015": _num(10, 300, nullable=False),
                "rent_index_b2015": _num(0.5, 400, nullable=False),
                "price_to_rent_b2015": _num(10, 600, nullable=False),
                "price_to_income_b2015": _num(10, 600),
            },
            unique=["year"],
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

    imi = tables["at_imi_rates"].set_index([MUNI_KEY, "year"])["imi_urban_pct"]
    in_panel = p.set_index([MUNI_KEY, "year"])["imi_urban_pct"].dropna()
    msgs.append(
        None
        if in_panel.equals(imi.dropna().reindex(in_panel.index))
        and len(in_panel) == imi.notna().sum()
        else "panel IMI rates differ from at_imi_rates"
    )
    change = p.sort_values([MUNI_KEY, "year"]).groupby(MUNI_KEY)["imi_urban_pct"].diff()
    recomputed = p.assign(c=change).sort_values([MUNI_KEY, "year"])
    bad = (recomputed["c"].fillna(0) - recomputed["imi_change_pp"].fillna(0)).abs() > 1e-9
    msgs.append(
        None
        if not bad.any() and p.loc[p["year"] == 2012, "imi_change_pp"].isna().all()
        else f"imi_change_pp is not the change on the previous year in {int(bad.sum())} rows"
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


def check_national_annual_long(
    a: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> list[str | None]:
    base = a.set_index("year").loc[2015]
    deflator = harmonize.annual_deflator(tables["ine_cpi"]).reindex(a["year"]).to_numpy()
    real = a["hpi_nominal_b2015"].to_numpy() * deflator
    real = real / real[a["year"].to_list().index(2015)] * 100
    bis = tables["bis_spp"]
    quarters = bis.groupby("year")["hpi_nominal_b2010"].count()
    complete = set(quarters[quarters == 4].index)
    return [
        None if a["year"].diff().dropna().eq(1).all() else "years are not consecutive",
        None
        if abs(base["hpi_nominal_b2015"] - 100) < 1e-9 and abs(base["hpi_real_b2015"] - 100) < 1e-9
        else "price indices do not equal 100 in 2015",
        None
        if np.allclose(a["hpi_real_b2015"], real, rtol=1e-9)
        else "real index differs from nominal x the project deflator",
        None if set(a["year"]) <= complete else "an incomplete BIS year is in the table",
        None
        if a["price_to_income_b2015"].notna().sum()
        == a["year"].between(1995, a["year"].max()).sum()
        else "price-to-income has gaps after 1995",
    ]


PANEL_CHECKS = {
    "panel_municipality_year": check_panel_municipality_year,
    "national_quarterly": check_national_quarterly,
    "national_annual_long": check_national_annual_long,
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
