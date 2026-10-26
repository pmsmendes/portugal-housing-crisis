"""Cleaned per-dataset interim tables: ``data/raw`` -> ``data/interim/<table>.parquet``.

One builder per table. Municipal tables keep the full 308-municipality grid; cells that the source
suppresses stay NaN (never zero). Values are nominal, in the unit given by the column suffix; real values
and indicators are built later (``harmonize.py`` deflator, ``features/``).
"""

import re
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from pthousing.config import INTERIM, MUNI_KEY
from pthousing.data import harmonize
from pthousing.data.sources import aima, at, bis, bportugal, caop, eurostat, ine, oecd, rnal

OECD_COLUMNS = {
    "HPI": "hpi_nominal_b2015",
    "RHP": "hpi_real_b2015",
    "RPI": "rent_index_b2015",
    "HPI_RPI": "price_to_rent_b2015",
    "HPI_YDH": "price_to_income_b2015",
    "HPI_RPI_AVG": "price_to_rent_std",
    "HPI_YDH_AVG": "price_to_income_std",
}

SIZE = {"T": "total", "1": "br_0_1", "2": "br_2", "3": "br_3", "4": "br_4plus"}
PRICE_CATEGORY = {"H1": "total", "H11": "new", "H12": "existing"}
COST_FACTOR = {"T": "total", "1": "materials", "2": "labour"}
PROJECT = {"T": "total", "1": "new", "2": "alteration"}
PURPOSE = {"T": "total", "1": "family_housing", "2": "other"}
BUYER = {"T": "total", "1": "domestic", "2": "foreign", "21": "eu", "22": "other_foreign"}
VALUATION_TYPE = {"T": "total", "1": "flats", "2": "villas"}
SEX = {"T": "total", "1": "m", "2": "f"}
NATIONALITY_SPECIAL = {"T": "total", "TOP": "other"}  # the other codes are ISO 3166 alpha-2
BP_COLUMNS = {
    "new_housing_aprc": "mortgage_aprc_new_pct",
    "new_housing_rate_lt1y": "mortgage_rate_new_lt1y_pct",
    "stock_housing_rate_gt5y": "mortgage_rate_stock_gt5y_pct",
    "new_housing_volume_lt1y": "mortgage_new_lt1y_volume_eur_m",
    "new_fixed_rate_p50": "mortgage_rate_new_fixed_p50_pct",
}
BP_DEBT_COLUMNS = {
    "housing_loans_stock": "housing_loans_stock_eur_m",
    "housing_loans_gdp": "housing_loans_gdp_pct",
    "housing_loans_growth": "housing_loans_growth_pct",
    "household_debt_stock": "household_debt_stock_eur_m",
    "household_debt_gdp": "household_debt_gdp_pct",
    "household_debt_income": "household_debt_income_pct",
}


def _municipal(code: str) -> pd.DataFrame:
    """Municipality rows (308 CAOP municipalities) of a raw INE indicator."""
    return harmonize.keep_municipalities(ine.read_indicator(code))


def _national(code: str, dim_3: str = "T") -> pd.DataFrame:
    df = ine.read_indicator(code)
    return df[(df["geocod"] == "PT") & (df["dim_3"] == dim_3)]


def _quarter(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(quarter=df["period_start"].dt.quarter)


# ---- INE municipal tables ------------------------------------------------------------------------


def build_ine_median_price_sqm() -> pd.DataFrame:
    """Median sale price per m2 (last 12 months) by municipality, quarter and dwelling category.

    Methodology 2018 until 3Q2019, methodology 2022 from 4Q2019 (the two agree on the overlap, median
    ratio 1.002, so the overlap quarters are taken from the 2022 series). Only 'total' exists before 2019.
    """
    new = _municipal("0012234")
    new = new.assign(category=new["dim_3"].map(PRICE_CATEGORY), method="2022")
    old = _municipal("0009490")
    old = old[old["period_start"] < new["period_start"].min()].assign(
        category="total", method="2018"
    )
    prices = pd.concat([old, new], ignore_index=True).rename(columns={"value": "price_sqm_eur"})

    sales = _municipal("0014363")[[MUNI_KEY, "period_start", "value"]].rename(
        columns={"value": "sales_12m_n"}
    )
    sales["category"] = "total"
    out = prices.merge(sales, on=[MUNI_KEY, "period_start", "category"], how="left")
    out = _quarter(out)
    cols = [MUNI_KEY, "period_start", "year", "quarter", "category", "method"]
    return out[[*cols, "price_sqm_eur", "sales_12m_n"]].sort_values(cols, ignore_index=True)


def build_ine_building_works() -> pd.DataFrame:
    """Buildings licensed (2002-2025) and completed (2011-2025) by municipality, year, type of project and purpose.

    ``project`` is new (new constructions), alteration (enlargements, changes and reconstructions: works on existing
    buildings, extensions included) or total; ``purpose`` is family_housing, other or total. Counts of buildings, not
    dwellings; works that need no licence are not counted. NUTS 2024 geography.
    """
    parts = []
    for code, column in (("0013234", "licensed_buildings_n"), ("0013247", "completed_buildings_n")):
        df = _municipal(code)
        df = df.assign(project=df["dim_3"].map(PROJECT), purpose=df["dim_4"].map(PURPOSE))
        parts.append(
            df.rename(columns={"value": column})[[MUNI_KEY, "year", "project", "purpose", column]]
        )
    keys = [MUNI_KEY, "year", "project", "purpose"]
    out = parts[0].merge(parts[1], on=keys, how="outer", validate="one_to_one")
    return out.sort_values(keys, ignore_index=True)


def build_ine_price_by_buyer() -> pd.DataFrame:
    """Median sale price per m2 (last 12 months) by municipality, quarter and tax residence of the buyer, 4Q2019 onward.

    ``buyer`` is total, domestic (national territory), foreign (EU plus other countries), eu or other_foreign. Cells
    with too few transactions are blank in the source and dropped here, so a municipality-quarter with a foreign price
    is one with enough foreign purchases; no counts by buyer are published.
    """
    df = _municipal("0012246")
    df = _quarter(df.assign(buyer=df["dim_3"].map(BUYER))).dropna(subset=["value"])
    df = df.rename(columns={"value": "price_sqm_eur"})
    cols = [MUNI_KEY, "period_start", "year", "quarter", "buyer"]
    return df[[*cols, "price_sqm_eur"]].sort_values(cols, ignore_index=True)


def build_ine_price_by_buyer_national() -> pd.DataFrame:
    """National median sale price per m2 (last 12 months) by tax residence of the buyer, quarterly from 4Q2019."""
    df = ine.read_indicator("0012246")
    df = df[(df["geocod"] == "PT") & df["dim_3"].isin(BUYER)]
    df = _quarter(df.assign(buyer=df["dim_3"].map(BUYER))).dropna(subset=["value"])
    df = df.rename(columns={"value": "price_sqm_eur"})
    cols = ["period_start", "year", "quarter", "buyer"]
    return df[[*cols, "price_sqm_eur"]].sort_values(cols, ignore_index=True)


def build_ine_median_rent_sqm() -> pd.DataFrame:
    """Median rent per m2 of new leases, annual, with the number of new leases (published from 33 leases)."""
    rent = _municipal("0012600")[[MUNI_KEY, "year", "value"]].rename(
        columns={"value": "rent_sqm_eur"}
    )
    leases = _municipal("0012601")[[MUNI_KEY, "year", "value"]].rename(
        columns={"value": "new_leases_n"}
    )
    out = rent.merge(leases, on=[MUNI_KEY, "year"], how="outer", validate="one_to_one")
    return out.sort_values([MUNI_KEY, "year"], ignore_index=True)


MUNICIPAL_REVENUE_ITEMS = {
    "R": "total_receipts_eur",
    "R1": "current_receipts_eur",
    "R11": "iuc_eur",
    "R12": "imt_eur",
    "R13": "imi_eur",
    "R14": "local_surcharge_eur",
    "R15": "local_funds_eur",
    "R16": "decentralisation_fund_eur",
    "R17": "sales_eur",
    "R18": "other_current_eur",
}


def build_ine_municipal_revenue() -> pd.DataFrame:
    """Revenue of municipal councils by economic classification (DGAL via INE), annual 2021-2023, in euros.

    INE publishes thousands of euros (``Potencia10`` 3); ``imi_eur`` is the municipal real estate tax (R13), ``imt_eur``
    the tax on onerous transfers of real estate (R12), ``iuc_eur`` the single circulation tax (R11). One municipality
    (Penedono) is not in the source. ``total_receipts_eur`` is the published total, which differs from current plus
    capital receipts by up to 9.5 million euros in some municipalities; shares are taken of ``current_receipts_eur``.
    """
    df = _municipal("0013908")
    df = df[df["dim_3"].isin(MUNICIPAL_REVENUE_ITEMS)]
    wide = df.pivot_table(
        index=[MUNI_KEY, "year"], columns="dim_3", values="value", aggfunc="first"
    )
    wide = (1000 * wide).rename(columns=MUNICIPAL_REVENUE_ITEMS)
    cols = list(MUNICIPAL_REVENUE_ITEMS.values())
    return (
        wide.reindex(columns=cols)
        .rename_axis(columns=None)
        .reset_index()
        .sort_values([MUNI_KEY, "year"], ignore_index=True)
    )


def build_ine_income() -> pd.DataFrame:
    """Gross reported income per tax household (IRS), mean and median, 2015-2024.

    NUTS 2013 vintage up to 2017, NUTS 2024 vintage from 2018 (identical on 2018-2021).
    """
    parts = []
    for mean_code, median_code, vintage, keep in (
        ("0009933", "0009934", "2013", lambda y: y < 2018),
        ("0012748", "0012749", "2024", lambda y: y >= 2018),
    ):
        mean = _municipal(mean_code)[[MUNI_KEY, "year", "value"]].rename(
            columns={"value": "income_mean_eur"}
        )
        median = _municipal(median_code)[[MUNI_KEY, "year", "value"]].rename(
            columns={"value": "income_median_eur"}
        )
        both = mean.merge(median, on=[MUNI_KEY, "year"], validate="one_to_one")
        parts.append(both[keep(both["year"])].assign(vintage=vintage))
    return pd.concat(parts, ignore_index=True).sort_values([MUNI_KEY, "year"], ignore_index=True)


def build_ine_construction() -> pd.DataFrame:
    """New family dwellings licensed and completed, by municipality, year and number of bedrooms.

    1995-2025 series (NUTS 2002 geography; identical to the NUTS 2024 series on the overlap). Years before
    Vizela, Trofa and Odivelas existed are NaN, not zero.
    """
    frames = []
    for code, name in (("0000087", "licensed_n"), ("0000076", "completed_n")):
        df = harmonize.mask_pre_creation(_municipal(code))
        df = df.assign(size=df["dim_3"].map(SIZE)).rename(columns={"value": name})
        frames.append(df[[MUNI_KEY, "year", "size", name]])
    out = frames[0].merge(
        frames[1], on=[MUNI_KEY, "year", "size"], how="outer", validate="one_to_one"
    )
    return out.sort_values([MUNI_KEY, "year", "size"], ignore_index=True)


def build_ine_bank_valuation() -> pd.DataFrame:
    """Median bank appraisal value per m2 by municipality and month (largely suppressed: ~64% NaN)."""
    df = _municipal("0012248")
    df = df.assign(type=df["dim_3"].map(VALUATION_TYPE), month=df["period_start"].dt.month)
    df = df.rename(columns={"value": "valuation_sqm_eur"})
    cols = [MUNI_KEY, "period_start", "year", "month", "type"]
    return df[[*cols, "valuation_sqm_eur"]].sort_values(cols, ignore_index=True)


def build_ine_bank_valuation_annual() -> pd.DataFrame:
    """Annual median bank appraisal value per m2 by municipality (INE computes it on all the year's appraisals)."""
    df = _municipal("0012256")
    df = df.assign(type=df["dim_3"].map(VALUATION_TYPE)).rename(
        columns={"value": "valuation_sqm_eur"}
    )
    cols = [MUNI_KEY, "year", "type"]
    return df[[*cols, "valuation_sqm_eur"]].sort_values(cols, ignore_index=True)


def build_ine_census() -> pd.DataFrame:
    """Census 2021: vacant dwellings (% of classic dwellings) and occupied dwellings by tenure."""
    vacant = _municipal("0012517")[[MUNI_KEY, "year", "value"]].rename(
        columns={"year": "census_year", "value": "vacant_dwellings_pct"}
    )
    tenure = _municipal("0012531")
    tenure = tenure[tenure["dim_4"] == "T"]  # total over years of residence
    names = {
        "T": "occupied_dwellings_n",
        "1": "owner_occupied_n",
        "3": "rented_n",
        "4": "other_tenure_n",
    }
    wide = tenure.pivot(index=[MUNI_KEY, "year"], columns="dim_3", values="value").rename(
        columns=names
    )
    wide = wide.reset_index().rename(columns={"year": "census_year"})
    wide.columns.name = None
    out = vacant.merge(wide, on=[MUNI_KEY, "census_year"], validate="one_to_one")
    cols = [MUNI_KEY, "census_year", "vacant_dwellings_pct", *names.values()]
    return out[cols].sort_values(MUNI_KEY, ignore_index=True)


def _only_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose extra dimensions (``dim_3`` to ``dim_5``, where present) are all the total ``T``."""
    keep = pd.Series(True, index=df.index)
    for col in ("dim_3", "dim_4", "dim_5"):
        if col in df:
            keep &= df[col] == "T"
    return df[keep]


HOUSEHOLD_SIZE_COLUMN = {
    "0006457": "dim_4",
    "0012856": "dim_5",
}  # census 2011 / 2021: dimension of household size


def build_ine_households_size() -> pd.DataFrame:
    """Census 2011 and 2021: private households by number of persons, per municipality.

    ``size`` is ``1``, ``2``, ``3`` or ``4plus`` (2021 stops at four or more, so 2011's 4 to 9 or more persons are
    added up); ``households_n`` counts private households (2011: classic families, as in ``ine_census``).
    """
    frames = []
    for code, column in HOUSEHOLD_SIZE_COLUMN.items():
        df = _municipal(code)
        df = df[df[column] != "T"].copy()
        size = df[column].str.lstrip("0")
        df["size"] = size.where(size.isin(["1", "2", "3"]), "4plus")
        grouped = df.groupby([MUNI_KEY, "year", "size"])["value"].sum(min_count=1)
        frames.append(grouped.rename("households_n").reset_index())
    out = pd.concat(frames).rename(columns={"year": "census_year"})
    return out.sort_values([MUNI_KEY, "census_year", "size"], ignore_index=True)


def build_ine_census_stock() -> pd.DataFrame:
    """Census 2001, 2011 and 2021: dwellings by occupancy, private households and mean useful area.

    ``dwellings_n`` are conventional dwellings; ``dwellings_vacant_n`` sums every vacant category (for
    sale, for rent, other reasons). ``households_n`` are private households (2011: classic families).
    ``dwelling_area_sqm`` is the mean useful area of dwellings of usual residence (2011 and 2021 only; NaN
    for 2001, where the area table was not located).
    """
    occupancy = {  # (census year, dim_3 code) -> column
        (2011, "T"): "dwellings_n",
        (2011, "11"): "dwellings_usual_n",
        (2011, "12"): "dwellings_secondary_n",
        (2011, "2"): "dwellings_vacant_n",
        (2021, "T"): "dwellings_n",
        (2021, "1"): "dwellings_usual_n",
        (2021, "2"): "dwellings_secondary_n",
        (2021, "3"): "dwellings_vacant_n",
        (2021, "4"): "dwellings_vacant_n",
        (2001, "T"): "dwellings_n",
        (2001, "11"): "dwellings_usual_n",
        (2001, "12"): "dwellings_secondary_n",
        (2001, "2"): "dwellings_vacant_n",  # the total of vacant; 21 to 24 are its parts
    }
    parts = []
    for code in ("0000729", "0006304", "0012502"):
        df = _municipal(code)
        df = df.assign(
            col=[occupancy.get((y, d)) for y, d in zip(df["year"], df["dim_3"], strict=True)]
        )
        df = df.dropna(subset=["col"]).groupby([MUNI_KEY, "year", "col"])["value"].sum(min_count=1)
        parts.append(df.unstack("col"))
    dwellings = pd.concat(parts)
    households = pd.concat(
        [
            _only_totals(_municipal(c)).set_index([MUNI_KEY, "year"])["value"]
            for c in ("0000676", "0006457", "0012856")
        ]
    ).rename("households_n")
    area = pd.concat(
        [_municipal(c).set_index([MUNI_KEY, "year"])["value"] for c in ("0006988", "0012518")]
    ).rename("dwelling_area_sqm")
    out = dwellings.join([households, area], how="outer").reset_index()
    out = out.rename(columns={"year": "census_year"})
    cols = [MUNI_KEY, "census_year", "dwellings_n", "dwellings_usual_n", "dwellings_secondary_n"]
    cols += ["dwellings_vacant_n", "households_n", "dwelling_area_sqm"]
    return out[cols].sort_values([MUNI_KEY, "census_year"], ignore_index=True)


def _age_group(label: str) -> str:
    if label == "Total":
        return "total"
    if m := re.fullmatch(r"(\d+) - (\d+) years", label):
        return f"{m[1]}-{m[2]}"
    if m := re.fullmatch(r"(\d+) and more years", label):
        return f"{m[1]}+"
    raise ValueError(f"Unrecognised age group label: {label!r}")


def build_ine_population() -> pd.DataFrame:
    """Resident population by municipality, year, sex and five-year age group (totals included)."""
    df = _municipal("0008273")
    df = df.assign(sex=df["dim_3"].map(SEX), age_group=df["dim_4_t"].map(_age_group))
    df = df.rename(columns={"value": "population_n"})
    cols = [MUNI_KEY, "year", "sex", "age_group"]
    return df[[*cols, "population_n"]].sort_values(cols, ignore_index=True)


def build_ine_population_change() -> pd.DataFrame:
    """Natural increase, net migration and total population change by municipality and year, 2011-2023.

    Counts of persons over the year (INE annual estimates): population change = natural increase (births minus
    deaths) + net migration.
    """
    parts = {
        "population_change_n": "0008271",
        "natural_increase_n": "0008270",
        "net_migration_n": "0008269",
    }
    out = None
    for column, code in parts.items():
        df = _municipal(code)[[MUNI_KEY, "year", "value"]].rename(columns={"value": column})
        out = df if out is None else out.merge(df, on=[MUNI_KEY, "year"], validate="one_to_one")
    return out.sort_values([MUNI_KEY, "year"], ignore_index=True)


def build_aima_foreigners() -> pd.DataFrame:
    """Foreign residents with a legal residence title by municipality, year and nationality, 2014-2023.

    ``nationality`` is the lower-case ISO alpha-2 code of ten named nationalities, 'other' for all remaining
    countries and 'total'. NUTS 2013 geography; all 308 municipalities existed throughout.
    """
    df = _municipal(aima.INDICATOR)
    nationality = df["dim_3"].map(lambda c: NATIONALITY_SPECIAL.get(c, c.lower()))
    df = df.assign(nationality=nationality).rename(columns={"value": "foreign_residents_n"})
    cols = [MUNI_KEY, "year", "nationality"]
    return df[[*cols, "foreign_residents_n"]].sort_values(cols, ignore_index=True)


# ---- INE national tables -------------------------------------------------------------------------


def build_ine_cpi() -> pd.DataFrame:
    """Consumer price index, all items, Portugal, annual (2025 = 100)."""
    df = _national("0014642")
    return df.rename(columns={"value": "cpi_index_b2025"})[["year", "cpi_index_b2025"]].sort_values(
        "year", ignore_index=True
    )


def build_ine_cpi_monthly() -> pd.DataFrame:
    """Consumer price index, all items, Portugal, monthly (2025 = 100)."""
    df = _national("0014640").assign(month=lambda d: d["period_start"].dt.month)
    return df.rename(columns={"value": "cpi_index_b2025"})[
        ["period_start", "year", "month", "cpi_index_b2025"]
    ].sort_values("period_start", ignore_index=True)


def build_ine_hpi() -> pd.DataFrame:
    """National house price index (2025 = 100), quarterly, total / new / existing dwellings."""
    df = ine.read_indicator("0014765")
    df = _quarter(df.assign(category=df["dim_3"].map(PRICE_CATEGORY)))
    df = df.rename(columns={"value": "hpi_index_b2025"})
    cols = ["period_start", "year", "quarter", "category"]
    return df[[*cols, "hpi_index_b2025"]].sort_values(cols, ignore_index=True)


def build_ine_construction_costs() -> pd.DataFrame:
    """Cost index of building new housing (2021 = 100), monthly, national, total / materials / labour."""
    df = ine.read_indicator("0011748")
    df = df[(df["geocod"] == "PT") & df["dim_3"].isin(COST_FACTOR)]
    df = df.assign(factor=df["dim_3"].map(COST_FACTOR), month=df["period_start"].dt.month)
    df = df.rename(columns={"value": "construction_cost_b2021"})
    cols = ["period_start", "year", "month", "factor"]
    return df[[*cols, "construction_cost_b2021"]].sort_values(cols, ignore_index=True)


# ---- other sources -------------------------------------------------------------------------------


def build_bp_mortgage() -> pd.DataFrame:
    """Monthly mortgage rates and new-loan volume, one column per series (month-end dates)."""
    df = bportugal.read_all()
    wide = df.pivot(index="date", columns="series_key", values="value").rename(columns=BP_COLUMNS)
    wide = wide.reset_index()
    wide.columns.name = None
    wide.insert(1, "period_start", wide["date"].dt.to_period("M").dt.to_timestamp())
    wide.insert(2, "year", wide["date"].dt.year)
    wide.insert(3, "month", wide["date"].dt.month)
    return wide.sort_values("date", ignore_index=True)


def build_bp_household_debt() -> pd.DataFrame:
    """Household debt by quarter: housing-loan and total stocks, shares of GDP and income, housing-loan growth.

    The stocks and the growth rate are monthly (quarterly in the first years), the ratios quarterly: every
    column is taken at the quarter-end month, so a quarter missing its last month (the current one) is dropped.
    """
    df = bportugal.read_all("bp_household_debt")
    df = df[df["date"].dt.month.isin([3, 6, 9, 12])]
    wide = df.pivot(index="date", columns="series_key", values="value").rename(
        columns=BP_DEBT_COLUMNS
    )
    wide = wide.reset_index()
    wide.columns.name = None
    wide.insert(1, "period_start", wide["date"].dt.to_period("Q").dt.to_timestamp())
    wide.insert(2, "year", wide["date"].dt.year)
    wide.insert(3, "quarter", wide["date"].dt.quarter)
    return wide.sort_values("date", ignore_index=True)


def build_eurostat_hpi() -> pd.DataFrame:
    """House price index (2015 = 100) for Portugal, peers and the EU27, quarterly."""
    df = eurostat.read("eurostat_hpi")
    df = _quarter(df).rename(columns={"value": "hpi_index_b2015"})
    cols = ["geo", "period_start", "year", "quarter"]
    return df[[*cols, "hpi_index_b2015"]].sort_values(cols, ignore_index=True)


def build_eurostat_hicp() -> pd.DataFrame:
    """HICP all-items annual average index (2015 = 100) for Portugal and the EU27."""
    df = eurostat.read("eurostat_hicp").rename(columns={"value": "hicp_index_b2015"})
    return df[["geo", "year", "hicp_index_b2015"]].sort_values(["geo", "year"], ignore_index=True)


def build_eurostat_demography() -> pd.DataFrame:
    """Portugal's demographic balance by year: population on 1 January, births, deaths, natural change, net migration.

    ``net_migration_n`` is Eurostat's net migration plus statistical adjustment, the residual of the flow
    ``population_change_n`` after natural change. ``revision_n`` is what the 1 January levels add beyond the
    flows (2020 and 2021: INE's post-census revision of the series); it is zero in every other year. Years are
    the calendar year the change occurs in; the latest may be provisional.
    """
    df = eurostat.read("eurostat_demography")
    names = {
        "JAN": "population_jan_n",
        "GROW": "population_change_n",
        "NATGROW": "natural_change_n",
        "CNMIGRAT": "net_migration_n",
        "LBIRTH": "births_n",
        "DEATH": "deaths_n",
    }
    wide = df.pivot(index="year", columns="indic_de", values="value").rename(columns=names)
    wide.columns.name = None
    jan = wide["population_jan_n"]
    wide["revision_n"] = jan.shift(-1) - jan - wide["population_change_n"]
    wide = wide.dropna(
        subset=["population_change_n"]
    )  # drops the latest 1 January, with no flow yet
    return (
        wide[[*names.values(), "revision_n"]].reset_index().sort_values("year", ignore_index=True)
    )


def build_bis_spp() -> pd.DataFrame:
    """BIS residential property price index for Portugal (2010 = 100), nominal and real, quarterly from 1988."""
    df = bis.read("bis_spp")
    df = df[df["unit"] == "628"]
    wide = df.pivot(index=["period_start", "year", "quarter"], columns="basis", values="value")
    wide = wide.rename(columns={"N": "hpi_nominal_b2010", "R": "hpi_real_b2010"}).reset_index()
    wide.columns.name = None
    return wide.sort_values("period_start", ignore_index=True)


def build_oecd_house_prices() -> pd.DataFrame:
    """OECD house price, rent, price-to-rent and price-to-income indices for Portugal (2015 = 100), annual."""
    df = oecd.read("oecd_house_prices")
    wide = df.pivot(index="year", columns="measure", values="value").rename(columns=OECD_COLUMNS)
    wide = wide[list(OECD_COLUMNS.values())].reset_index()
    wide.columns.name = None
    return wide.sort_values("year", ignore_index=True)


def build_rnal_al() -> pd.DataFrame:
    """Registered short-term rental units of the latest snapshot (mainland only)."""
    return rnal.read().sort_values("rnal_n", ignore_index=True)


def build_at_imi_rates() -> pd.DataFrame:
    """Municipal IMI rates by tax year, 2012-2025 (Portal das Financas), all 308 municipalities every year.

    ``imi_urban_pct`` is the urban rate in % of the assessed value (NaN where the portal shows no single rate,
    always with ``parish_rates`` True), ``imi_rustic_pct`` the rustic rate, ``parish_rates`` whether the
    "Taxas por freguesia" link is shown (meaning unverified: 71 to 79 municipalities a year in 2013-2024, 208
    in 2012, 8 in 2025) and ``deduction_link`` whether the household deduction page is linked (none before
    tax year 2016, 219 to 278 municipalities after: the IMI Familiar scheme). Nominal rates, not deflated.
    """
    df = at.read().rename(columns={"urban_pct": "imi_urban_pct", "rustic_pct": "imi_rustic_pct"})
    cols = [MUNI_KEY, "year"]
    keep = [*cols, "imi_urban_pct", "imi_rustic_pct", "parish_rates", "deduction_link"]
    return df[keep].sort_values(cols, ignore_index=True)


def build_caop_municipalities() -> pd.DataFrame:
    return caop.read_municipalities()


INE_CODES = (
    "0012234", "0009490", "0014363",  # sale prices (2022 method, 2018 method, sales count)
    "0012600", "0012601",  # rents, new leases
    "0009933", "0009934", "0012748", "0012749",  # income, NUTS 2013 and 2024 vintages
    "0000087", "0000076",  # dwellings licensed, completed (1995+)
    "0012248", "0012256",  # bank valuation, monthly and annual
    "0012517", "0012531",  # census 2021: vacancy, tenure
    "0006988", "0012518",  # census 2011 / 2021: mean useful area of dwellings of usual residence
    "0008273", "0014642", "0014640", "0014765",  # population, CPI annual / monthly, HPI
    "0008269", "0008270", "0008271",  # net migration, natural increase, population change
    "0011748",  # construction cost index of new housing, monthly
    "0012246",  # median price per m2 (12 months) by tax residence of the buyer
    "0013234", "0013247",  # buildings licensed, completed by type of project and purpose
    "0013908",  # revenue of municipal councils by economic classification (IMI, IMT, ...), 2021-2023
)  # fmt: skip


def build_eurostat_macro() -> pd.DataFrame:
    """Portugal's annual macro series: GDP growth, unemployment rate and compensation per employee.

    GDP growth is the change in chain-linked volumes (%); the unemployment rate is the labour force survey's
    (15 to 74); ``compensation_per_employee_eur`` is whole-economy compensation of employees over employees
    (domestic concept), nominal. Years without a value stay NaN (GDP growth starts in 1996).
    """

    def column(dataset_id: str, name: str) -> pd.Series:
        return eurostat.read(dataset_id).set_index("year")["value"].rename(name)

    comp = column("eurostat_compensation", "compensation_eur_m")
    employees = column("eurostat_employees", "employees_ths")
    out = pd.concat(
        [
            column("eurostat_gdp", "gdp_growth_pct"),
            column("eurostat_unemployment", "unemployment_pct"),
            (comp * 1000 / employees).rename("compensation_per_employee_eur"),
        ],
        axis=1,
    )
    return out.rename_axis("year").reset_index().sort_values("year", ignore_index=True)


def build_eurostat_property_tax() -> pd.DataFrame:
    """General-government revenue from property taxes and nominal GDP, one row per year.

    ``imi_revenue_eur_m`` and ``imt_revenue_eur_m`` are national-accounts D29A (taxes on land, buildings and other
    structures, in practice IMI) and D214C (taxes on financial and capital transactions: IMT plus stamp duty on them,
    accrual basis), current prices; ``gdp_eur_m`` is nominal GDP, the denominator for shares of GDP.
    """
    raw = eurostat.read("eurostat_property_tax")
    taxes = raw.pivot(index="year", columns="na_item", values="value").rename(
        columns={"D29A": "imi_revenue_eur_m", "D214C": "imt_revenue_eur_m"}
    )
    gdp = eurostat.read("eurostat_gdp_nominal")
    gdp = gdp[gdp["geo"] == "PT"].set_index("year")["value"].rename("gdp_eur_m")
    out = taxes.join(gdp, how="left").rename_axis(columns=None)
    return out[["imi_revenue_eur_m", "imt_revenue_eur_m", "gdp_eur_m"]].reset_index()


def build_eurostat_housing_spending() -> pd.DataFrame:
    """General-government spending on housing by country and year, with nominal GDP.

    ``housing_development_eur_m`` is COFOG GF0601 (housing development, public housing included),
    ``housing_benefits_eur_m`` GF1006 (housing allowances and rent subsidies in social protection) and
    ``housing_amenities_eur_m`` GF06 (housing and community amenities, a wider group that also holds water and street
    lighting); ``gdp_eur_m`` is nominal GDP. Tax expenditures are not part of COFOG.
    """
    raw = eurostat.read("eurostat_housing_spending")
    names = {
        "GF0601": "housing_development_eur_m",
        "GF1006": "housing_benefits_eur_m",
        "GF06": "housing_amenities_eur_m",
    }
    spending = raw.pivot_table(index=["geo", "year"], columns="cofog99", values="value").rename(
        columns=names
    )
    gdp = (
        eurostat.read("eurostat_gdp_nominal")
        .set_index(["geo", "year"])["value"]
        .rename("gdp_eur_m")
    )
    out = spending.join(gdp, how="left").rename_axis(columns=None).reset_index()
    cols = ["geo", "year", *names.values(), "gdp_eur_m"]
    return out[cols].sort_values(["geo", "year"], ignore_index=True)


def build_eurostat_property_tax_peers() -> pd.DataFrame:
    """Taxes on land and buildings (D29A) and on financial and capital transactions (D214C) by country and year, with GDP.

    ``land_buildings_tax_eur_m`` is the recurrent property tax; ``transaction_tax_eur_m`` is comparable only where a
    country books its transfer taxes there (Portugal does, Germany and Italy do not), so it is not used for comparisons.
    """
    raw = eurostat.read("eurostat_property_tax_peers")
    taxes = raw.pivot_table(index=["geo", "year"], columns="na_item", values="value").rename(
        columns={"D29A": "land_buildings_tax_eur_m", "D214C": "transaction_tax_eur_m"}
    )
    gdp = (
        eurostat.read("eurostat_gdp_nominal")
        .set_index(["geo", "year"])["value"]
        .rename("gdp_eur_m")
    )
    out = taxes.join(gdp, how="left").rename_axis(columns=None).reset_index()
    cols = ["geo", "year", "land_buildings_tax_eur_m", "transaction_tax_eur_m", "gdp_eur_m"]
    return out[cols].sort_values(["geo", "year"], ignore_index=True)


# Census tables that exceed INE's row limit as a whole: only the totals of the dimensions we do not split by.
INE_FILTERED = {
    "0000729": {
        "Dim4": "T"
    },  # conventional dwellings 2001 by occupancy status (all periods of construction)
    "0000676": {"Dim3": "T"},  # private households 2001 (all age groups of the reference person)
    "0006304": {"Dim4": "T", "Dim5": "T"},  # conventional dwellings 2011 by occupancy status
    "0012502": {"Dim4": "T", "Dim5": "T"},  # conventional dwellings 2021 by occupancy status
    "0006457": {"Dim3": "T", "Dim4": "T", "Dim5": "T"},  # private households 2011
    "0012856": {"Dim3": "T", "Dim4": "T", "Dim5": "T"},  # private households 2021
}
INE_HOUSEHOLD_SIZE = {  # the same two tables with the size dimension left open
    "0006457": {"Dim3": "T", "Dim5": "T"},
    "0012856": {"Dim3": "T", "Dim4": "T"},
}
EUROSTAT_DATASETS = (
    "eurostat_hpi",
    "eurostat_hicp",
    "eurostat_demography",
    "eurostat_gdp",
    "eurostat_unemployment",
    "eurostat_compensation",
    "eurostat_employees",
    "eurostat_property_tax",
    "eurostat_gdp_nominal",
    "eurostat_housing_spending",
    "eurostat_property_tax_peers",
)
SOURCES = ("ine", "aima", "at", "bportugal", "eurostat", "bis", "oecd", "rnal", "caop")


def download(sources: list[str] | None = None, refresh: bool = False) -> None:
    """Download the raw inputs of the interim tables (cached files are reused unless ``refresh``)."""
    chosen = set(sources or SOURCES)
    if unknown := chosen - set(SOURCES):
        raise ValueError(f"Unknown source ids {sorted(unknown)}; choose from {list(SOURCES)}")
    if "ine" in chosen:
        for code in INE_CODES:
            ine.fetch_indicator(code, refresh=refresh)
        for code, filters in INE_FILTERED.items():
            ine.fetch_indicator(code, filters=filters, refresh=refresh)
        for code, filters in INE_HOUSEHOLD_SIZE.items():
            ine.fetch_indicator(code, filters=filters, refresh=refresh)
    if "aima" in chosen:
        aima.fetch(refresh=refresh)
    if "at" in chosen:
        at.fetch(refresh=refresh)  # ~300 pages, one snapshot reused until refreshed
    if "bportugal" in chosen:
        bportugal.fetch_all(refresh=refresh)
    if "eurostat" in chosen:
        for dataset_id in EUROSTAT_DATASETS:
            eurostat.fetch(dataset_id, refresh=refresh)
    if "bis" in chosen:
        bis.fetch("bis_spp", refresh=refresh)
    if "oecd" in chosen:
        oecd.fetch("oecd_house_prices", refresh=refresh)
    if "rnal" in chosen:
        rnal.fetch(refresh=refresh)  # a new dated snapshot each day
    if "caop" in chosen:
        caop.download(refresh=refresh)


BUILDERS: dict[str, Callable[[], pd.DataFrame]] = {
    "ine_median_price_sqm": build_ine_median_price_sqm,
    "ine_median_rent_sqm": build_ine_median_rent_sqm,
    "ine_municipal_revenue": build_ine_municipal_revenue,
    "ine_income": build_ine_income,
    "ine_construction": build_ine_construction,
    "ine_bank_valuation": build_ine_bank_valuation,
    "ine_bank_valuation_annual": build_ine_bank_valuation_annual,
    "ine_census": build_ine_census,
    "ine_census_stock": build_ine_census_stock,
    "ine_population": build_ine_population,
    "ine_cpi": build_ine_cpi,
    "ine_cpi_monthly": build_ine_cpi_monthly,
    "ine_hpi": build_ine_hpi,
    "ine_construction_costs": build_ine_construction_costs,
    "ine_price_by_buyer": build_ine_price_by_buyer,
    "ine_building_works": build_ine_building_works,
    "ine_price_by_buyer_national": build_ine_price_by_buyer_national,
    "ine_population_change": build_ine_population_change,
    "ine_households_size": build_ine_households_size,
    "aima_foreigners": build_aima_foreigners,
    "bp_mortgage": build_bp_mortgage,
    "bp_household_debt": build_bp_household_debt,
    "eurostat_hpi": build_eurostat_hpi,
    "eurostat_hicp": build_eurostat_hicp,
    "eurostat_demography": build_eurostat_demography,
    "eurostat_macro": build_eurostat_macro,
    "eurostat_property_tax": build_eurostat_property_tax,
    "eurostat_housing_spending": build_eurostat_housing_spending,
    "eurostat_property_tax_peers": build_eurostat_property_tax_peers,
    "bis_spp": build_bis_spp,
    "oecd_house_prices": build_oecd_house_prices,
    "rnal_al": build_rnal_al,
    "at_imi_rates": build_at_imi_rates,
    "caop_municipalities": build_caop_municipalities,
}


def interim_path(table: str) -> Path:
    return INTERIM / f"{table}.parquet"


def build(table: str) -> Path:
    """Build one interim table and write it to ``data/interim/<table>.parquet``."""
    df = BUILDERS[table]()
    path = interim_path(table)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def build_all(tables: list[str] | None = None) -> dict[str, Path]:
    return {name: build(name) for name in (tables or BUILDERS)}


def read(table: str) -> pd.DataFrame:
    path = interim_path(table)
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not in data/interim; run interim.build('{table}') first"
        )
    if table == "caop_municipalities":
        import geopandas as gpd

        return gpd.read_parquet(path)
    return pd.read_parquet(path)
