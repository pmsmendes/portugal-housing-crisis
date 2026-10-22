"""Municipality typology for the group comparisons: ``data/external/muni_typology.csv``.

Three transparent proxies, built from the CAOP boundaries and the processed panel (all values are properties of
the municipality, not of a year):

* ``coast_class``: ``coast`` (a CAOP shoreline segment), ``estuary`` (only a water boundary: the tidal Tejo and
  Sado, e.g. Lisboa) or ``inland`` (``sources/caop.py``);
* ``density_class``: ``urban`` / ``intermediate`` / ``rural`` from residents per km2 in 2021, with the thresholds
  of ``config.py``. This is a density proxy, **not** the INE parish typology (TIPAU);
* ``tourist``: ``tourist`` / ``other`` from registered short-term rentals per 1,000 dwellings (mainland only; the
  island municipalities are ``unknown``). The registry is today's survivors, so the flag describes the present.
"""

import numpy as np
import pandas as pd

from pthousing.config import (
    DENSITY_RURAL_PER_KM2,
    DENSITY_URBAN_PER_KM2,
    EXTERNAL,
    MUNI_KEY,
    TOURIST_AL_PER_1000,
)

PATH = EXTERNAL / "muni_typology.csv"
COLUMNS = [
    MUNI_KEY,
    "muni_name",
    "territory",
    "coast_class",
    "density_per_km2_2021",
    "density_class",
    "al_per_1000_dwellings",
    "tourist",
    "second_homes_pct_2021",
]


def classify_density(density: pd.Series) -> pd.Series:
    """``urban`` from DENSITY_URBAN_PER_KM2, ``rural`` below DENSITY_RURAL_PER_KM2, else ``intermediate``."""
    out = pd.Series("intermediate", index=density.index, dtype=object)
    out[density >= DENSITY_URBAN_PER_KM2] = "urban"
    out[density < DENSITY_RURAL_PER_KM2] = "rural"
    out[density.isna()] = np.nan
    return out


def classify_tourist(al_per_1000: pd.Series) -> pd.Series:
    """``tourist`` from TOURIST_AL_PER_1000, ``other`` below, ``unknown`` where the registry has no coverage."""
    out = pd.Series(
        np.where(al_per_1000 >= TOURIST_AL_PER_1000, "tourist", "other"), index=al_per_1000.index
    )
    return out.mask(al_per_1000.isna(), "unknown")


def build_typology(panel: pd.DataFrame, coast: pd.Series) -> pd.DataFrame:
    """Typology table from the municipality-year panel (2021 rows) and the coast classification."""
    y = panel.loc[panel["year"] == 2021].set_index(MUNI_KEY)
    out = pd.DataFrame(index=y.index)
    out["muni_name"] = y["muni_name"]
    out["territory"] = y["territory"]
    out["coast_class"] = coast.reindex(out.index)
    out["density_per_km2_2021"] = y["population_n"] / (y["area_ha"] / 100)
    out["density_class"] = classify_density(out["density_per_km2_2021"])
    out["al_per_1000_dwellings"] = y["al_units_per_1000_dwellings_2021"]
    out["tourist"] = classify_tourist(out["al_per_1000_dwellings"])
    out["second_homes_pct_2021"] = 100 * y["dwellings_secondary_2021_n"] / y["dwellings_2021_n"]
    return out.reset_index()[COLUMNS]


def build() -> pd.DataFrame:
    """Build and write ``data/external/muni_typology.csv`` (needs the CAOP download and the processed panel)."""
    from pthousing.data import build_panel
    from pthousing.data.sources import caop

    typology = build_typology(build_panel.read("panel_municipality_year"), caop.coast_class())
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    typology.round(3).to_csv(PATH, index=False, encoding="utf-8", lineterminator="\n")
    return typology


def read() -> pd.DataFrame:
    return pd.read_csv(PATH, dtype={MUNI_KEY: str}, encoding="utf-8")
