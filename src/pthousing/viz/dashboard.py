"""Data access and indicator definitions shared by the dashboard pages (``app/``).

Pages only import from here: the indicator catalogue, the panel with the typology attached, the web
geometry, the values behind the map and the p2 report tables. Everything reads committed files
(``data/processed``, ``data/external``, ``reports/tables``), never ``data/raw`` or ``data/interim``.
"""

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pthousing.analysis import descriptive
from pthousing.config import MUNI_KEY, TABLES, YEAR_KEY
from pthousing.data import build_panel, typology
from pthousing.viz import maps, style

MIN_MUNIS = (
    100  # a year is offered for an indicator only if at least this many municipalities have a value
)
TERRITORIES = {"continente": "Mainland", "azores": "Azores", "madeira": "Madeira"}
GROUPS = {"coast_class": "Coast", "density_class": "Density", "tourist": "Tourism"}


@dataclass(frozen=True)
class Indicator:
    """One mappable column. ``tone`` says which direction is worse for affordability: ``worse_high``
    (prices, burdens), ``better_high`` (income, completions) or ``neutral`` (population, tax rates)."""

    label: str
    column: str
    unit: str
    fmt: str
    tone: str
    group: str
    note: str = ""


INDICATORS: dict[str, Indicator] = {
    i.column: i
    for i in (
        Indicator("Price-to-income", "pti_years", "years of income", "{:.1f}", "worse_high",
                  "Affordability", "Price of a home of the municipality's average size over median income per tax household."),
        Indicator("Rent-to-income", "rti_pct", "% of income", "{:.0f}", "worse_high",
                  "Affordability", "Yearly rent of an average-size home over median income. Municipalities with published rents only."),
        Indicator("Mortgage burden", "mortgage_burden_pct", "% of income", "{:.0f}", "worse_high",
                  "Affordability", "Yearly payments on an 80% loan over 30 years at the year's new-loan rate, over median income."),
        Indicator("Sale price per m²", "price_sqm_eur_real", "EUR per m², 2024 prices", "{:,.0f}", "worse_high",
                  "Prices and income", "Median sale price over the last 12 months, deflated with the consumer price index."),
        Indicator("Rent per m²", "rent_sqm_eur_real", "EUR per m² a month, 2024 prices", "{:.2f}", "worse_high",
                  "Prices and income", "Median rent of new leases, deflated."),
        Indicator("Median income", "income_median_eur_real", "EUR a year, 2024 prices", "{:,.0f}", "better_high",
                  "Prices and income", "Median gross income per tax household."),
        Indicator("Completions per 1,000 dwellings", "completed_per_1000", "dwellings per 1,000 (2011 stock)", "{:.1f}", "better_high",
                  "Supply and demand", "New dwellings completed in the year over the 2011 census stock. Small municipalities are noisy year to year."),
        Indicator("Population", "population_n", "residents", "{:,.0f}", "neutral",
                  "Supply and demand", "Resident population, INE estimate (to 2023)."),
        Indicator("Residents aged 65+", "pop_65plus_pct", "% of residents", "{:.1f}", "neutral",
                  "Supply and demand", "Share of residents aged 65 or more (to 2023)."),
        Indicator("Foreign residents", "foreign_residents_pct", "% of residents", "{:.1f}", "neutral",
                  "Supply and demand", "Foreign nationals with a legal residence title (AIMA), 2014 to 2023. Reflects where titles are issued."),
        Indicator("Urban IMI rate", "imi_urban_pct", "% of assessed value", "{:.2f}", "neutral",
                  "Policy", "Municipal rate on urban property; the legal range is 0.30% to 0.45%."),
    )
}  # fmt: skip

TREND_GROUPS = list(dict.fromkeys(i.group for i in INDICATORS.values()))


def load_panel() -> pd.DataFrame:
    """Municipality-year panel with the typology columns and ``completed_per_1000`` attached."""
    panel = build_panel.read("panel_municipality_year")
    panel["completed_per_1000"] = 1000 * panel["completed_n"] / panel["dwellings_2011_n"]
    typ = typology.read()[
        [MUNI_KEY, "coast_class", "density_class", "tourist", "second_homes_pct_2021"]
    ]
    return panel.merge(typ, on=MUNI_KEY, how="left")


def load_national() -> pd.DataFrame:
    return build_panel.read("national_quarterly")


def load_geometry() -> dict:
    """Municipality outlines as a GeoJSON dict (``properties.muni_code``)."""
    with open(maps.WEB_GEOMETRY, encoding="utf-8") as f:
        return json.load(f)


def years_with_data(panel: pd.DataFrame, column: str) -> list[int]:
    n = panel.groupby(YEAR_KEY)[column].count()
    return [int(y) for y in n[n >= MIN_MUNIS].index]


def map_frame(
    panel: pd.DataFrame, column: str, year: int, since: int | None = None, relative: bool = False
) -> pd.DataFrame:
    """One row per municipality with ``value``: the level in ``year``, or the change since ``since``
    (percent when ``relative``). Names and territory come from the panel."""
    names = panel.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)[
        ["muni_name", "district", "territory"]
    ]
    if since is None:
        value = panel[panel[YEAR_KEY] == year].set_index(MUNI_KEY)[column]
    else:
        value = descriptive.change(panel, column, since, year, "pct" if relative else "diff")
    out = names.join(value.rename("value"))
    out.index.name = MUNI_KEY
    return out.reset_index()


def colour_scale(tone: str, change: bool) -> tuple[list[str], float | None]:
    """Plotly colour scale and midpoint. Red is always the direction that is worse for affordability."""
    if change:
        ramp = style.diverging_ramp(3)  # blue (fall) ... red (rise)
        if tone == "better_high":
            ramp = ramp[::-1]  # a fall in income or completions is the bad direction
        return ramp, 0.0
    return style.SEQUENTIAL_6, None


def trend_band(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    """Median and 10th-90th percentile across municipalities by year (years with enough municipalities)."""
    q = descriptive.yearly_quantiles(panel, column)
    return q[q["n"] >= MIN_MUNIS]


def group_trend(panel: pd.DataFrame, column: str, by: str) -> pd.DataFrame:
    """Median of ``column`` by year for each class of ``by``, over the municipalities with a value in
    every year the indicator has data (so a line never moves because the sample changed)."""
    years = years_with_data(panel, column)
    d = panel[panel[YEAR_KEY].isin(years)].dropna(subset=[column, by])
    d = d[d[by] != "unknown"]
    full = d.groupby(MUNI_KEY)[YEAR_KEY].nunique()
    d = d[d[MUNI_KEY].isin(full[full == len(years)].index)]
    return descriptive.group_median(d, column, by)


def driver_frame(panel: pd.DataFrame, start: int = 2016, end: int = 2024) -> pd.DataFrame:
    """Mainland municipalities with the change in price-to-income and candidate explanations (for the
    scatter on the explanatory page). Changes are log-percent for the outcome; levels are fixed in time."""
    d = panel[panel["territory"] == "continente"]
    wide = d.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="pti_years")
    out = d.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)[
        ["muni_name", "district", "coast_class", "density_class", "tourist", "second_homes_pct_2021",
         "vacant_dwellings_pct_2021", "supply_gap_2011_2021_per_1000", "al_units_per_1000_dwellings_2021"]
    ].copy()  # fmt: skip
    out["pti_change_pct"] = 100 * (wide[end] / wide[start] - 1)
    out["density_per_km2"] = typology.read().set_index(MUNI_KEY)["density_per_km2_2021"]
    fr = d.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="foreign_residents_pct")
    out["foreign_residents_change_pp"] = fr[2023] - fr[2014]
    comp = d[d[YEAR_KEY].between(start, end - 1)].groupby(MUNI_KEY)["completed_per_1000"].sum()
    out["completions_per_1000"] = comp
    return out.dropna(subset=["pti_change_pct"]).reset_index()


DRIVERS = {
    "density_per_km2": "Population density, 2021 (residents per km², log scale)",
    "foreign_residents_change_pp": "Change in foreign residents, 2014 to 2023 (pp of population)",
    "completions_per_1000": "Completions 2016 to 2023 (per 1,000 dwellings in 2011)",
    "supply_gap_2011_2021_per_1000": "Housing balance 2011 to 2021 (dwellings added minus households added, per 1,000)",
    "second_homes_pct_2021": "Second homes, 2021 (% of dwellings)",
    "vacant_dwellings_pct_2021": "Vacant dwellings, 2021 (% of dwellings)",
}


def fit_line(x: pd.Series, y: pd.Series, log_x: bool = False) -> dict:
    """OLS line of ``y`` on ``x`` (or ``log10(x)``) with the correlation and the number of points."""
    ok = x.notna() & y.notna() & ((x > 0) if log_x else True)
    xv = np.log10(x[ok]) if log_x else x[ok]
    slope, intercept = np.polyfit(xv, y[ok], 1)
    grid = np.linspace(xv.min(), xv.max(), 50)
    return {
        "x": 10**grid if log_x else grid,
        "y": intercept + slope * grid,
        "r": float(np.corrcoef(xv, y[ok])[0, 1]),
        "n": int(ok.sum()),
    }


def read_table(phase: str, name: str) -> pd.DataFrame:
    """A committed report table, ``reports/tables/<phase>/<name>.csv``."""
    return pd.read_csv(TABLES / phase / f"{name}.csv")
