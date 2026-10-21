import numpy as np
import pandas as pd
import pytest

from pthousing.data import harmonize, interim, validate

CODES = sorted(harmonize.read_crosswalk()["muni_code"])


def _failures(table, df):
    return [r for r in validate.validate_table(table, df) if not r["ok"]]


def _rent(**override):
    df = pd.DataFrame(
        {
            "muni_code": CODES,
            "year": 2020,
            "rent_sqm_eur": 5.0,
            "new_leases_n": 50.0,
        }
    )
    for col, value in override.items():
        df[col] = value
    return df


def test_valid_rent_table_passes():
    assert _failures("ine_median_rent_sqm", _rent()) == []


def test_schema_rejects_out_of_range_duplicate_and_unknown_municipality():
    bad_range = _rent(rent_sqm_eur=500.0)
    dup = pd.concat([_rent(), _rent().iloc[:1]], ignore_index=True)
    unknown = _rent().assign(muni_code=["9999"] + CODES[1:])
    for df in (bad_range, dup, unknown):
        assert any(r["check"] == "schema" for r in _failures("ine_median_rent_sqm", df))


def test_schema_rejects_unexpected_column():
    assert any(
        r["check"] == "schema" for r in _failures("ine_median_rent_sqm", _rent().assign(extra=1))
    )


def test_grid_check_reports_missing_municipalities():
    df = _rent().iloc[:-1]
    assert [r["detail"] for r in _failures("ine_median_rent_sqm", df) if r["check"] != "schema"]


def test_rent_publication_rule_is_checked():
    df = _rent()
    df.loc[0, "new_leases_n"] = 10.0  # published with fewer than 33 leases
    assert any("fewer than 33" in r["detail"] for r in _failures("ine_median_rent_sqm", df))
    df.loc[0, "rent_sqm_eur"] = np.nan  # suppressed value: fine
    assert _failures("ine_median_rent_sqm", df) == []


def test_population_totals_must_equal_sum_of_parts():
    rows = [
        {"muni_code": c, "year": 2023, "sex": s, "age_group": a, "population_n": v}
        for c in CODES
        for s, a, v in [
            ("total", "total", 3.0),
            ("m", "total", 1.0),
            ("f", "total", 2.0),
            ("total", "0-4", 1.0),
            ("total", "85+", 2.0),
            ("m", "0-4", 1.0),
            ("m", "85+", 0.0),
            ("f", "0-4", 0.0),
            ("f", "85+", 2.0),
        ]
    ]
    df = pd.DataFrame(rows)
    assert _failures("ine_population", df) == []
    df.loc[(df.sex == "m") & (df.age_group == "total"), "population_n"] = 5.0
    assert any("max difference" in r["detail"] for r in _failures("ine_population", df))


def _construction(completed_total=10.0, completed_parts=(2.0, 2.0, 3.0, 3.0), year=2010):
    rows = []
    for c in CODES:
        for size, comp in zip(
            ["total", "br_0_1", "br_2", "br_3", "br_4plus"],
            (completed_total, *completed_parts),
            strict=True,
        ):
            rows.append(
                {
                    "muni_code": c,
                    "year": year,
                    "size": size,
                    "licensed_n": comp,
                    "completed_n": comp,
                }
            )
    df = pd.DataFrame(rows)
    # Vizela, Trofa, Odivelas must be the only municipalities with missing licences
    df.loc[df.muni_code.isin(harmonize.VALID_FROM_YEAR), "licensed_n"] = np.nan
    return df


def test_construction_checks_size_split_and_expected_missing_municipalities():
    assert _failures("ine_construction", _construction()) == []
    assert any(
        "exceed the total" in r["detail"]
        for r in _failures("ine_construction", _construction(completed_parts=(4.0, 4.0, 4.0, 4.0)))
    )
    no_nans = _construction().assign(licensed_n=lambda d: d["licensed_n"].fillna(1.0))
    assert any(
        "outside Vizela" in r["detail"] or "missing licences" in r["detail"]
        for r in _failures("ine_construction", no_nans)
    )


def test_cpi_base_year_must_be_100():
    ok = pd.DataFrame({"year": [2024, 2025], "cpi_index_b2025": [97.7, 100.0]})
    assert _failures("ine_cpi", ok) == []
    bad = ok.assign(cpi_index_b2025=[97.7, 101.0])
    assert any("base year" in r["detail"] for r in _failures("ine_cpi", bad))


def test_cross_source_check_flags_diverging_hpi():
    quarters = pd.date_range("2009-01-01", "2026-04-01", freq="QS")
    index = pd.Series(np.linspace(40, 114, len(quarters)))
    ine = pd.DataFrame(
        {
            "period_start": quarters,
            "category": "total",
            "hpi_index_b2025": index.values,
            "year": quarters.year,
        }
    )
    ref = ine.loc[ine.year == 2015, "hpi_index_b2025"].mean()
    es = pd.DataFrame(
        {"geo": "PT", "period_start": quarters, "hpi_index_b2015": index.values / ref * 100}
    )
    cpi = pd.DataFrame({"year": range(1996, 2026), "cpi_index_b2025": np.linspace(40, 100, 30)})
    hicp = pd.DataFrame(
        {
            "geo": "PT",
            "year": cpi["year"],
            "hicp_index_b2015": cpi["cpi_index_b2025"]
            / cpi.loc[cpi.year == 2015, "cpi_index_b2025"].item()
            * 100,
        }
    )
    pop = pd.DataFrame(
        [{"muni_code": c, "year": 2023, "sex": "total", "age_group": "total"} for c in CODES]
    )
    tables = {
        "ine_hpi": ine,
        "eurostat_hpi": es,
        "ine_cpi": cpi,
        "eurostat_hicp": hicp,
        "ine_population": pop,
    }
    assert all(msg is None for _, msg in validate.cross_checks(tables))
    tables["eurostat_hpi"] = es.assign(hpi_index_b2015=es["hpi_index_b2015"] * 1.05)
    results = dict(validate.cross_checks(tables))
    assert results["eurostat_hpi_vs_ine_hpi"] is not None


def test_validate_all_reports_failures_and_raises_only_in_strict_mode(monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    real_schema = validate.schemas()["ine_median_rent_sqm"]
    caop = gpd.GeoDataFrame(
        {"muni_code": CODES, "geometry": [box(0, 0, 1, 1)] * len(CODES)}, crs="EPSG:3763"
    )
    broken_rent = _rent(rent_sqm_eur=500.0)  # outside the allowed range
    tables = {"ine_median_rent_sqm": broken_rent, "caop_municipalities": caop}
    monkeypatch.setattr(validate, "schemas", lambda: {"ine_median_rent_sqm": real_schema})
    monkeypatch.setattr(interim, "read", lambda name: tables[name])
    monkeypatch.setattr(validate, "cross_checks", lambda _: [])

    report = validate.validate_all(strict=False)
    failed = report[~report["ok"]]
    assert failed["table"].tolist() == ["ine_median_rent_sqm"]
    assert failed["check"].iloc[0] == "schema"
    with pytest.raises(ValueError, match="Validation failed"):
        validate.validate_all(strict=True)


@pytest.mark.skipif(
    not all(interim.interim_path(t).exists() for t in interim.BUILDERS),
    reason="interim tables not built",
)
def test_real_interim_tables_pass_all_checks():
    report = validate.validate_all(strict=True)
    assert report["ok"].all() and len(report) >= 40
