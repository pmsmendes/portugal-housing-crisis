import numpy as np
import pandas as pd
import pytest

from pthousing.config import DENSITY_RURAL_PER_KM2, DENSITY_URBAN_PER_KM2, TOURIST_AL_PER_1000
from pthousing.data import typology


def test_density_classes_use_the_configured_thresholds():
    density = pd.Series(
        [
            DENSITY_RURAL_PER_KM2 - 1,
            DENSITY_RURAL_PER_KM2,
            DENSITY_URBAN_PER_KM2 - 1,
            DENSITY_URBAN_PER_KM2,
            np.nan,
        ]
    )
    assert typology.classify_density(density).tolist()[:4] == [
        "rural",
        "intermediate",
        "intermediate",
        "urban",
    ]
    assert pd.isna(typology.classify_density(density).iloc[4])


def test_tourist_flag_marks_missing_registry_coverage_as_unknown():
    al = pd.Series([TOURIST_AL_PER_1000 - 0.1, TOURIST_AL_PER_1000, np.nan])
    assert typology.classify_tourist(al).tolist() == ["other", "tourist", "unknown"]


def test_build_typology_takes_2021_values_and_the_coast_class():
    rows = []
    for code, name, pop, area, al, territory in (
        ("0101", "A", 60_000, 10_000, 40.0, "continente"),  # 600 per km2, tourist
        ("3101", "B", 5_000, 20_000, np.nan, "madeira"),  # 25 per km2, no registry
    ):
        for year in (2020, 2021):
            rows.append(
                {"muni_code": code, "year": year, "muni_name": name, "territory": territory,
                 "population_n": pop * (1.5 if year == 2020 else 1), "area_ha": area,
                 "al_units_per_1000_dwellings_2021": al, "dwellings_secondary_2021_n": 100,
                 "dwellings_2021_n": 400}
            )  # fmt: skip
    coast = pd.Series({"0101": "coast", "3101": "inland"}, name="coast_class")
    out = typology.build_typology(pd.DataFrame(rows), coast).set_index("muni_code")
    assert out.loc["0101", "density_per_km2_2021"] == pytest.approx(600.0)
    assert out.loc["0101", ["coast_class", "density_class", "tourist"]].tolist() == [
        "coast",
        "urban",
        "tourist",
    ]
    assert out.loc["3101", ["density_class", "tourist"]].tolist() == ["rural", "unknown"]
    assert out.loc["0101", "second_homes_pct_2021"] == pytest.approx(25.0)
    assert list(out.reset_index().columns) == typology.COLUMNS
