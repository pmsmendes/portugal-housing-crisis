import numpy as np
import pandas as pd
import pytest

from pthousing.data import harmonize


def _caop():
    return pd.DataFrame(
        {
            "muni_code": ["0101", "1106"],
            "muni_name": ["Águeda", "Lisboa"],
            "district": ["Aveiro", "Lisboa"],
            "territory": ["continente", "continente"],
            "nuts3_name_2024": ["Região de Aveiro", "Lisboa"],
            "nuts2_name_2024": ["Centro", "Grande Lisboa"],
        }
    )


def _ine(prefixes: dict[str, str], extra=()):
    rows = [
        {"geocod": f"{p}{c}", "geo_level": "municipality", "muni_code": c}
        for c, p in prefixes.items()
    ]
    rows += list(extra)
    return pd.DataFrame(rows)


def test_build_crosswalk_maps_nuts_codes_per_vintage():
    cw = harmonize.build_crosswalk(
        _caop(), _ine({"0101": "16D", "1106": "170"}), _ine({"0101": "191", "1106": "1A0"})
    )
    row = cw.set_index("muni_code")
    assert row.loc["1106", "nuts3_2013"] == "170"
    assert row.loc["1106", "nuts3_2024"] == "1A0"
    assert row.loc["1106", "nuts2_2024"] == "1A"
    assert row.loc["0101", "nuts2_2013"] == "16"
    assert row.loc["0101", "muni_name"] == "Águeda"


def test_nuts_prefixes_ignores_non_caop_codes_such_as_cities():
    city = {"geocod": "1920047", "geo_level": "municipality", "muni_code": "0047"}
    out = harmonize.nuts_prefixes(_ine({"0101": "191"}, extra=[city]), {"0101"}, "nuts3")
    assert out.to_dict() == {"0101": "191"}


def test_nuts_prefixes_rejects_missing_and_ambiguous_municipalities():
    with pytest.raises(ValueError, match="not found"):
        harmonize.nuts_prefixes(_ine({"0101": "191"}), {"0101", "1106"}, "nuts3")
    ambiguous = _ine(
        {"0101": "191"},
        extra=[{"geocod": "1610101", "geo_level": "municipality", "muni_code": "0101"}],
    )
    with pytest.raises(ValueError, match="more than one"):
        harmonize.nuts_prefixes(ambiguous, {"0101"}, "nuts3")


def test_keep_municipalities_and_unmatched_codes():
    cw = harmonize.build_crosswalk(
        _caop(), _ine({"0101": "16D", "1106": "170"}), _ine({"0101": "191", "1106": "1A0"})
    )
    df = pd.DataFrame(
        [
            {
                "geocod": "1911106",
                "geo_name": "Lisboa",
                "geo_level": "municipality",
                "muni_code": "1106",
            },
            {
                "geocod": "1A00067",
                "geo_name": "Amadora city",
                "geo_level": "municipality",
                "muni_code": "0067",
            },
            {"geocod": "1A0110601", "geo_name": "parish", "geo_level": "parish", "muni_code": None},
            {"geocod": "PT", "geo_name": "Portugal", "geo_level": "region", "muni_code": None},
        ]
    )
    assert harmonize.keep_municipalities(df, cw)["muni_code"].tolist() == ["1106"]
    unmatched = harmonize.unmatched_codes(df, cw)
    assert unmatched["geo_name"].tolist() == ["Amadora city"]


def test_crosswalk_marks_municipalities_created_after_1995():
    cw = harmonize.build_crosswalk(
        _caop().assign(muni_code=["0101", "0314"]),
        _ine({"0101": "16D", "0314": "16B"}),
        _ine({"0101": "191", "0314": "1D1"}),
    )
    valid_from = cw.set_index("muni_code")["valid_from_year"]
    assert pd.isna(valid_from["0101"])
    assert valid_from["0314"] == 1998


def test_mask_pre_creation_only_touches_new_municipalities_before_their_first_year():
    cw = pd.DataFrame({"muni_code": ["0101", "0314"], "valid_from_year": [None, "1998"]})
    df = pd.DataFrame(
        {
            "muni_code": ["0101", "0101", "0314", "0314", "0314"],
            "year": [1995, 1998, 1995, 1997, 1998],
            "value": [5.0, 6.0, 0.0, 0.0, 8.0],
        }
    )
    out = harmonize.mask_pre_creation(df, cw)
    assert out["value"].isna().tolist() == [False, False, True, True, False]
    assert out["value"].dropna().tolist() == [5.0, 6.0, 8.0]
    assert df["value"].notna().all()  # input untouched


# ---- CPI deflation --------------------------------------------------------------------------------


def test_annual_deflator_is_cpi_of_base_year_over_cpi_of_year():
    cpi = pd.DataFrame({"year": [2023, 2024, 2025], "cpi_index_b2025": [95.0, 97.5, 100.0]})
    d = harmonize.annual_deflator(cpi, base_year=2024)
    assert d[2024] == 1.0
    assert d[2023] == pytest.approx(97.5 / 95.0)  # 2023 euros are worth more in 2024 euros
    assert d[2025] == pytest.approx(0.975)
    with pytest.raises(ValueError, match="not in the CPI"):
        harmonize.annual_deflator(cpi, base_year=1990)


def test_quarterly_deflator_uses_quarter_means_and_drops_incomplete_quarters():
    months = pd.date_range("2024-01-01", "2025-02-01", freq="MS")  # Q1 2025 has two months only
    cpi = pd.DataFrame(
        {"period_start": months, "cpi_index_b2025": [100.0 + i for i in range(len(months))]}
    )
    d = harmonize.quarterly_deflator(cpi, base_year=2024)
    base = sum(100.0 + i for i in range(12)) / 12
    assert d[pd.Timestamp("2024-01-01")] == pytest.approx(base / 101.0)  # mean of 100, 101, 102
    assert pd.Timestamp("2025-01-01") not in d.index
    with pytest.raises(ValueError, match="12 monthly"):
        harmonize.quarterly_deflator(cpi, base_year=2025)


def test_to_real_multiplies_by_the_deflator_of_each_period_and_keeps_missing():
    deflator = pd.Series({2023: 1.1, 2024: 1.0})
    nominal = pd.Series([100.0, 100.0, np.nan, 100.0])
    years = pd.Series([2023, 2024, 2024, 1900])
    real = harmonize.to_real(nominal, deflator, years)
    assert real.iloc[:2].tolist() == pytest.approx([110.0, 100.0])
    assert real.iloc[2:].isna().all()  # missing value and unknown year stay missing
