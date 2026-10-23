"""Merge data/interim into analysis-ready panels in data/processed.

* ``panel_municipality_year``: 308 municipalities x 1995-2025, one row per municipality-year.
* ``national_quarterly``: national time series by quarter, 2005 onwards.

Nominal columns end in ``_eur``; real values (constant ``BASE_YEAR`` euros, CPI deflator) in ``_eur_real``.
Affordability indicators are computed with ``features/affordability.py``.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from pthousing.config import (
    BASE_YEAR,
    BENCHMARK_AREA_SQM,
    MORTGAGE_LTV,
    MORTGAGE_TERM_YEARS,
    MUNI_KEY,
    PROCESSED,
)
from pthousing.data import harmonize, interim
from pthousing.features import affordability as aff

YEARS = range(1995, 2026)  # 2025 is the last full year of the municipal series
CENSUS_YEARS = (2011, 2021)
OLD_AGE_GROUPS = ["65-69", "70-74", "75-79", "80-84", "85+"]
PEERS = {
    "PT": "pt",
    "ES": "es",
    "IT": "it",
    "FR": "fr",
    "DE": "de",
    "IE": "ie",
    "EU27_2020": "eu27",
}
NATIONAL_START = "2005-01-01"


# ---- municipality-year ---------------------------------------------------------------------------


def _by_year(df: pd.DataFrame, **columns: str) -> pd.DataFrame:
    return df[[MUNI_KEY, "year", *columns]].rename(columns=columns)


def _annual_prices() -> pd.DataFrame:
    """Year-end (4th quarter) last-12-months median price per m2, i.e. the calendar-year median."""
    q4 = interim.read("ine_median_price_sqm").query("quarter == 4")
    wide = q4.pivot(index=[MUNI_KEY, "year"], columns="category", values="price_sqm_eur")
    wide = wide.rename(
        columns={
            "total": "price_sqm_eur",
            "existing": "price_existing_sqm_eur",
            "new": "price_new_sqm_eur",
        }
    ).reset_index()
    wide.columns.name = None
    sales = q4.query("category == 'total'")[[MUNI_KEY, "year", "sales_12m_n"]]
    return wide.merge(sales, on=[MUNI_KEY, "year"], how="left")


def _population() -> pd.DataFrame:
    pop = interim.read("ine_population").query("sex == 'total'")
    total = pop.query("age_group == 'total'").set_index([MUNI_KEY, "year"])["population_n"]
    old = (
        pop[pop["age_group"].isin(OLD_AGE_GROUPS)].groupby([MUNI_KEY, "year"])["population_n"].sum()
    )
    out = pd.DataFrame({"population_n": total, "pop_65plus_pct": 100 * old / total})
    return out.reset_index()


def _foreigners() -> pd.DataFrame:
    """Foreign residents with a legal residence title (total of all nationalities), 2014-2023."""
    f = interim.read("aima_foreigners").query("nationality == 'total'")
    return _by_year(f, foreign_residents_n="foreign_residents_n")


def _census_static() -> pd.DataFrame:
    """Census columns that do not change with the panel year (one value per municipality)."""
    stock = interim.read("ine_census_stock")
    wide = stock.pivot(index=MUNI_KEY, columns="census_year")
    out = pd.DataFrame(index=wide.index)
    for year in CENSUS_YEARS:
        out[f"dwellings_{year}_n"] = wide[("dwellings_n", year)]
        out[f"households_{year}_n"] = wide[("households_n", year)]
        out[f"dwelling_area_{year}_sqm"] = wide[("dwelling_area_sqm", year)]
    out["dwellings_secondary_2021_n"] = wide[("dwellings_secondary_n", 2021)]
    out["dwellings_vacant_2021_n"] = wide[("dwellings_vacant_n", 2021)]
    out["supply_gap_2011_2021_per_1000"] = aff.supply_gap_per_1000(
        out["dwellings_2011_n"],
        out["dwellings_2021_n"],
        out["households_2011_n"],
        out["households_2021_n"],
    )
    census = interim.read("ine_census").set_index(MUNI_KEY)
    out["vacant_dwellings_pct_2021"] = census["vacant_dwellings_pct"]
    out["owner_share_pct_2021"] = 100 * census["owner_occupied_n"] / census["occupied_dwellings_n"]
    out["rented_share_pct_2021"] = 100 * census["rented_n"] / census["occupied_dwellings_n"]
    return out.reset_index()


def _short_term_rentals(spine: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Registered short-term rental units (mainland only; islands stay NaN: the layer does not cover them).

    ``al_units_snapshot_n`` is today's registry; ``al_survivor_units_n`` is the cumulative number of those
    still-registered units by registration year, a lower bound of past stock (cancelled units are gone).
    """
    units = interim.read("rnal_al")
    mainland = set(crosswalk.loc[crosswalk["territory"] == "continente", MUNI_KEY])
    snapshot = units.groupby(MUNI_KEY).size()
    by_year = units.assign(year=units["registered"].dt.year).groupby([MUNI_KEY, "year"]).size()
    grid = spine[[MUNI_KEY, "year"]].copy()
    registered = grid.join(by_year.rename("registered_n"), on=[MUNI_KEY, "year"]).fillna(
        {"registered_n": 0}
    )
    before = units[units["registered"].dt.year < spine["year"].min()].groupby(MUNI_KEY).size()
    registered["survivors"] = registered.groupby(MUNI_KEY)["registered_n"].cumsum() + registered[
        MUNI_KEY
    ].map(before).fillna(0)
    out = grid.assign(al_survivor_units_n=registered["survivors"])
    out["al_units_snapshot_n"] = out[MUNI_KEY].map(snapshot).fillna(0)
    is_mainland = out[MUNI_KEY].isin(mainland)
    out.loc[~is_mainland, ["al_survivor_units_n", "al_units_snapshot_n"]] = np.nan
    return out


def _imi_rates() -> pd.DataFrame:
    """Municipal urban IMI rate per tax year (2012-2025) and its change on the previous year.

    ``imi_urban_pct`` is NaN where the municipality has parish-specific rates (no single value), and
    ``imi_change_pp`` is NaN whenever either year is missing, so a gap never reads as a change.
    """
    rates = interim.read("at_imi_rates").sort_values([MUNI_KEY, "year"])
    rates = rates.assign(imi_change_pp=rates.groupby(MUNI_KEY)["imi_urban_pct"].diff().round(4))
    # diff() across a missing year would span two years: keep only consecutive years
    gap = rates.groupby(MUNI_KEY)["year"].diff() != 1
    rates.loc[gap, "imi_change_pp"] = np.nan
    return rates.rename(
        columns={"parish_rates": "imi_parish_rates", "deduction_link": "imi_deduction_link"}
    )[
        [
            MUNI_KEY,
            "year",
            "imi_urban_pct",
            "imi_change_pp",
            "imi_parish_rates",
            "imi_deduction_link",
        ]
    ]


def _municipality_areas() -> pd.DataFrame:
    """Municipality area in hectares (CAOP), read without the geometry."""
    return pd.read_parquet(
        interim.interim_path("caop_municipalities"), columns=[MUNI_KEY, "area_ha"]
    )


def build_municipality_year() -> pd.DataFrame:
    crosswalk = harmonize.read_crosswalk()
    caop = _municipality_areas()
    attrs = crosswalk[
        [MUNI_KEY, "muni_name", "district", "territory", "nuts3_name_2024", "nuts2_name_2024"]
    ]
    attrs = attrs.merge(caop, on=MUNI_KEY, validate="one_to_one")

    spine = pd.MultiIndex.from_product([attrs[MUNI_KEY], YEARS], names=[MUNI_KEY, "year"]).to_frame(
        index=False
    )
    panel = spine.merge(attrs, on=MUNI_KEY, validate="many_to_one")

    construction = interim.read("ine_construction").query("size == 'total'")
    income = interim.read("ine_income")
    valuation = interim.read("ine_bank_valuation_annual").query("type == 'total'")
    parts = [
        _annual_prices(),
        _by_year(
            interim.read("ine_median_rent_sqm"),
            rent_sqm_eur="rent_sqm_eur",
            new_leases_n="new_leases_n",
        ),
        _by_year(income, income_mean_eur="income_mean_eur", income_median_eur="income_median_eur"),
        _by_year(valuation, valuation_sqm_eur="valuation_sqm_eur"),
        _by_year(construction, licensed_n="licensed_n", completed_n="completed_n"),
        _population(),
        _foreigners(),
        _short_term_rentals(spine, crosswalk),
        _imi_rates(),
    ]
    for part in parts:
        panel = panel.merge(part, on=[MUNI_KEY, "year"], how="left", validate="one_to_one")
    panel = panel.merge(_census_static(), on=MUNI_KEY, how="left", validate="many_to_one")
    imi_flags = [
        "imi_parish_rates",
        "imi_deduction_link",
    ]  # NaN outside 2012-2025: nullable boolean
    panel[imi_flags] = panel[imi_flags].astype("boolean")

    # dwelling size: mean useful area of dwellings of usual residence, interpolated between the censuses
    t = ((panel["year"] - CENSUS_YEARS[0]) / (CENSUS_YEARS[1] - CENSUS_YEARS[0])).clip(0, 1)
    panel["dwelling_area_sqm"] = panel["dwelling_area_2011_sqm"] + t * (
        panel["dwelling_area_2021_sqm"] - panel["dwelling_area_2011_sqm"]
    )

    # real values: constant BASE_YEAR euros
    deflator = harmonize.annual_deflator(interim.read("ine_cpi"))
    panel["deflator_to_base_year"] = panel["year"].map(deflator)
    for col in (
        "price_sqm_eur",
        "price_existing_sqm_eur",
        "price_new_sqm_eur",
        "rent_sqm_eur",
        "valuation_sqm_eur",
        "income_mean_eur",
        "income_median_eur",
    ):
        panel[f"{col}_real"] = harmonize.to_real(panel[col], deflator, panel["year"])
    panel = panel.merge(_mortgage_rate_by_year(), on="year", how="left", validate="many_to_one")

    # affordability indicators (ratios of same-year nominal values)
    area, income_med = panel["dwelling_area_sqm"], panel["income_median_eur"]
    panel["pti_years"] = aff.price_to_income(panel["price_sqm_eur"], area, income_med)
    panel["pti_years_100sqm"] = aff.price_to_income(
        panel["price_sqm_eur"], BENCHMARK_AREA_SQM, income_med
    )
    panel["pti_years_mean_income"] = aff.price_to_income(
        panel["price_sqm_eur"], area, panel["income_mean_eur"]
    )
    panel["rti_pct"] = aff.rent_to_income_pct(panel["rent_sqm_eur"], area, income_med)
    panel["rti_pct_100sqm"] = aff.rent_to_income_pct(
        panel["rent_sqm_eur"], BENCHMARK_AREA_SQM, income_med
    )
    rate = panel[
        "mortgage_rate_new_lt1y_pct"
    ]  # contract rate, not the APRC (which adds fees and insurance)
    panel["mortgage_burden_pct"] = aff.mortgage_burden_pct(
        panel["price_sqm_eur"], area, income_med, rate
    )
    panel["mortgage_burden_pct_100sqm"] = aff.mortgage_burden_pct(
        panel["price_sqm_eur"], BENCHMARK_AREA_SQM, income_med, rate
    )
    panel["foreign_residents_pct"] = 100 * panel["foreign_residents_n"] / panel["population_n"]
    panel["al_units_per_1000_dwellings_2021"] = (
        1000 * panel["al_units_snapshot_n"] / panel["dwellings_2021_n"]
    )
    return panel.sort_values([MUNI_KEY, "year"], ignore_index=True)


def _mortgage_rate_by_year() -> pd.DataFrame:
    """National mortgage rates on new housing loans, average of the months of each full year.

    ``mortgage_rate_new_lt1y_pct`` (agreed rate, floating loans with initial fixation up to 1 year) feeds
    the payment calculation; ``mortgage_aprc_new_pct`` (APRC, includes fees) is kept for reference.
    """
    bp = interim.read("bp_mortgage")
    cols = ["mortgage_rate_new_lt1y_pct", "mortgage_aprc_new_pct"]
    grouped = bp.groupby("year")
    return grouped[cols].mean()[grouped["date"].count() == 12].reset_index()


# ---- national quarterly --------------------------------------------------------------------------


def _quarterly_mortgage() -> pd.DataFrame:
    bp = interim.read("bp_mortgage")
    bp = bp.assign(period_start=bp["period_start"].dt.to_period("Q").dt.to_timestamp())
    rates = [c for c in bp.columns if c.endswith("_pct")]
    grouped = bp.groupby("period_start")
    full = grouped["date"].count() == 3  # only complete quarters
    out = grouped[rates].mean()
    out["mortgage_new_lt1y_volume_eur_m"] = grouped["mortgage_new_lt1y_volume_eur_m"].sum()
    return out[full].reset_index()


def build_national_quarterly() -> pd.DataFrame:
    eurostat = interim.read("eurostat_hpi")
    quarters = pd.date_range(NATIONAL_START, eurostat["period_start"].max(), freq="QS")
    panel = pd.DataFrame({"period_start": quarters})
    panel["year"] = panel["period_start"].dt.year
    panel["quarter"] = panel["period_start"].dt.quarter

    hpi = interim.read("ine_hpi").pivot(
        index="period_start", columns="category", values="hpi_index_b2025"
    )
    hpi = hpi.rename(columns=lambda c: f"hpi_{c}_b2025").reset_index()
    hpi.columns.name = None
    es = eurostat.pivot(index="period_start", columns="geo", values="hpi_index_b2015")
    es = es.rename(columns=lambda g: f"hpi_{PEERS[g]}_b2015").reset_index()
    es.columns.name = None

    deflator = harmonize.quarterly_deflator(interim.read("ine_cpi_monthly"))
    cpi = interim.read("ine_cpi_monthly")
    cpi_q = cpi.groupby(cpi["period_start"].dt.to_period("Q").dt.to_timestamp())[
        "cpi_index_b2025"
    ].agg(["mean", "count"])
    cpi_q = cpi_q[cpi_q["count"] == 3]["mean"].rename("cpi_index_b2025").reset_index()
    cpi_q["deflator_to_base_year"] = cpi_q["period_start"].map(deflator)

    for part in (hpi, es, cpi_q, _quarterly_mortgage()):
        panel = panel.merge(part, on="period_start", how="left", validate="one_to_one")

    for col in ("hpi_total_b2025", "hpi_new_b2025", "hpi_existing_b2025"):
        panel[col.replace("_b2025", "_real_b2025")] = panel[col] * panel["deflator_to_base_year"]
    panel["hpi_pt_real_b2015"] = panel["hpi_pt_b2015"] * panel["deflator_to_base_year"]
    panel["mortgage_payment_100k_eur"] = aff.mortgage_payment_monthly(
        100_000, panel["mortgage_rate_new_lt1y_pct"], MORTGAGE_TERM_YEARS
    )
    return panel


# ---- writing -------------------------------------------------------------------------------------

BUILDERS = {
    "panel_municipality_year": build_municipality_year,
    "national_quarterly": build_national_quarterly,
}


def processed_path(name: str) -> Path:
    return PROCESSED / f"{name}.parquet"


def build(name: str) -> Path:
    df = BUILDERS[name]()
    path = processed_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def build_all() -> dict[str, Path]:
    return {name: build(name) for name in BUILDERS}


def read(name: str) -> pd.DataFrame:
    path = processed_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not in data/processed; run build_panel.build('{name}') first"
        )
    return pd.read_parquet(path)


__all__ = ["BASE_YEAR", "MORTGAGE_LTV", "build", "build_all", "read"]
