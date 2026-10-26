import numpy as np
import pandas as pd
import pytest

from pthousing.data import interim


def _ine(rows):
    """Frame shaped like a parsed INE indicator restricted to municipalities."""
    df = pd.DataFrame(rows)
    df["period_start"] = pd.to_datetime(df["period_start"])
    df["year"] = df["period_start"].dt.year
    return df


def _patch_municipal(monkeypatch, frames):
    monkeypatch.setattr(interim, "_municipal", lambda code: frames[code].copy())


@pytest.mark.parametrize(
    ("label", "expected"),
    [("0 - 4 years", "0-4"), ("85 and more years", "85+"), ("Total", "total")],
)
def test_age_group(label, expected):
    assert interim._age_group(label) == expected


def test_age_group_rejects_unknown_label():
    with pytest.raises(ValueError):
        interim._age_group("Unknown")


def test_price_uses_2018_method_before_2022_series_starts_and_joins_sales_to_total_only(
    monkeypatch,
):
    new = _ine(
        [
            {"muni_code": "0101", "period_start": "2019-10-01", "dim_3": "H1", "value": 900.0},
            {"muni_code": "0101", "period_start": "2019-10-01", "dim_3": "H11", "value": 1100.0},
            {"muni_code": "0101", "period_start": "2020-01-01", "dim_3": "H12", "value": 950.0},
        ]
    )
    old = _ine(
        [
            {"muni_code": "0101", "period_start": "2019-07-01", "value": 880.0},
            {"muni_code": "0101", "period_start": "2019-10-01", "value": 905.0},  # overlap: dropped
        ]
    )
    sales = _ine([{"muni_code": "0101", "period_start": "2019-10-01", "value": 120.0}])
    _patch_municipal(monkeypatch, {"0012234": new, "0009490": old, "0014363": sales})
    out = interim.build_ine_median_price_sqm()
    assert out[["period_start", "category", "method"]].astype(str).values.tolist() == [
        ["2019-07-01", "total", "2018"],
        ["2019-10-01", "new", "2022"],
        ["2019-10-01", "total", "2022"],
        ["2020-01-01", "existing", "2022"],
    ]
    by = out.set_index(["period_start", "category"])
    assert (
        by.loc[(pd.Timestamp("2019-10-01"), "total"), "price_sqm_eur"] == 900.0
    )  # 2022 value kept
    assert by.loc[(pd.Timestamp("2019-10-01"), "total"), "sales_12m_n"] == 120.0
    assert pd.isna(by.loc[(pd.Timestamp("2019-10-01"), "new"), "sales_12m_n"])
    assert out["quarter"].tolist() == [3, 4, 4, 1]


def test_income_splices_vintages_at_2018(monkeypatch):
    def frame(values):
        return _ine(
            [{"muni_code": "0101", "period_start": f"{y}-01-01", "value": v} for y, v in values]
        )

    _patch_municipal(
        monkeypatch,
        {
            "0009933": frame([(2017, 10.0), (2018, 11.0)]),
            "0009934": frame([(2017, 8.0), (2018, 9.0)]),
            "0012748": frame([(2018, 11.0), (2019, 12.0)]),
            "0012749": frame([(2018, 9.0), (2019, 10.0)]),
        },
    )
    out = interim.build_ine_income()
    assert out[["year", "income_mean_eur", "vintage"]].values.tolist() == [
        [2017, 10.0, "2013"],
        [2018, 11.0, "2024"],
        [2019, 12.0, "2024"],
    ]


def test_construction_masks_municipalities_before_they_existed_and_labels_sizes(monkeypatch):
    def frame(value):
        rows = [
            {"muni_code": code, "period_start": f"{y}-01-01", "dim_3": d, "value": value}
            for code in ("0101", "0314")  # Vizela exists from 1998
            for y in (1997, 1998)
            for d in ("T", "1")
        ]
        return _ine(rows)

    _patch_municipal(monkeypatch, {"0000087": frame(5.0), "0000076": frame(3.0)})
    out = interim.build_ine_construction().set_index(["muni_code", "year", "size"])
    assert pd.isna(out.loc[("0314", 1997, "total"), "licensed_n"])
    assert pd.isna(out.loc[("0314", 1997, "br_0_1"), "completed_n"])
    assert out.loc[("0314", 1998, "total"), "licensed_n"] == 5.0
    assert out.loc[("0101", 1997, "total"), "completed_n"] == 3.0


def test_census_pivots_tenure_totals_over_years_of_residence(monkeypatch):
    vacant = _ine([{"muni_code": "0101", "period_start": "2021-01-01", "value": 12.5}])
    rows = []
    for dim_3, total in (("T", 100.0), ("1", 60.0), ("3", 30.0), ("4", 10.0)):
        rows.append(
            {
                "muni_code": "0101",
                "period_start": "2021-01-01",
                "dim_3": dim_3,
                "dim_4": "T",
                "value": total,
            }
        )
        rows.append(
            {
                "muni_code": "0101",
                "period_start": "2021-01-01",
                "dim_3": dim_3,
                "dim_4": "1",
                "value": 1.0,
            }
        )
    _patch_municipal(monkeypatch, {"0012517": vacant, "0012531": _ine(rows)})
    out = interim.build_ine_census().iloc[0]
    assert out["census_year"] == 2021 and out["vacant_dwellings_pct"] == 12.5
    assert (
        out["occupied_dwellings_n"],
        out["owner_occupied_n"],
        out["rented_n"],
        out["other_tenure_n"],
    ) == (100.0, 60.0, 30.0, 10.0)


def test_population_labels_sex_and_age(monkeypatch):
    rows = [
        {"muni_code": "0101", "period_start": "2023-01-01", "dim_3": s, "dim_4_t": a, "value": 1.0}
        for s in ("T", "1", "2")
        for a in ("Total", "0 - 4 years", "85 and more years")
    ]
    _patch_municipal(monkeypatch, {"0008273": _ine(rows)})
    out = interim.build_ine_population()
    assert set(out["sex"]) == {"total", "m", "f"}
    assert set(out["age_group"]) == {"total", "0-4", "85+"}
    assert len(out) == 9


def test_population_change_joins_the_three_components_one_row_per_municipality_year(monkeypatch):
    def frame(values):
        return _ine(
            [
                {"muni_code": c, "period_start": f"{y}-01-01", "value": v}
                for c, y, v in zip(
                    ("0101", "0101", "0102"), (2022, 2023, 2022), values, strict=True
                )
            ]
        )

    _patch_municipal(
        monkeypatch,
        {
            "0008271": frame([5.0, -3.0, 2.0]),
            "0008270": frame([-1.0, -2.0, 1.0]),
            "0008269": frame([6.0, -1.0, 1.0]),
        },
    )
    out = interim.build_ine_population_change().set_index(["muni_code", "year"])
    assert len(out) == 3
    assert out.loc[("0101", 2023)].to_dict() == {
        "population_change_n": -3.0,
        "natural_increase_n": -2.0,
        "net_migration_n": -1.0,
    }
    assert (out["population_change_n"] == out["natural_increase_n"] + out["net_migration_n"]).all()


def test_eurostat_demography_names_columns_and_splits_out_the_revision(monkeypatch):
    rows = []
    jan = {2019: 100.0, 2020: 110.0, 2021: 125.0}
    flows = {2019: (10.0, -2.0, 12.0), 2020: (5.0, -2.0, 7.0)}  # change, natural, migration
    for year, value in jan.items():
        rows.append({"indic_de": "JAN", "year": year, "value": value})
    for year, (grow, nat, mig) in flows.items():
        rows += [
            {"indic_de": "GROW", "year": year, "value": grow},
            {"indic_de": "NATGROW", "year": year, "value": nat},
            {"indic_de": "CNMIGRAT", "year": year, "value": mig},
            {"indic_de": "LBIRTH", "year": year, "value": 8.0},
            {"indic_de": "DEATH", "year": year, "value": 10.0},
        ]
    monkeypatch.setattr(interim.eurostat, "read", lambda ds: pd.DataFrame(rows))
    out = interim.build_eurostat_demography().set_index("year")
    assert list(out.index) == [2019, 2020]  # 2021 has no flow yet
    assert out.loc[2019, "revision_n"] == 0.0
    assert out.loc[2020, "revision_n"] == 10.0  # 125 - 110 - 5
    kept = ["natural_change_n", "net_migration_n", "births_n", "deaths_n"]
    assert out.loc[2020, kept].tolist() == [-2.0, 7.0, 8.0, 10.0]


def test_eurostat_macro_divides_compensation_by_employees(monkeypatch):
    def series(dataset_id):
        values = {
            "eurostat_gdp": {1996: 3.0, 1997: 4.0},
            "eurostat_unemployment": {1995: 7.0, 1996: 7.5, 1997: 6.5},
            "eurostat_compensation": {
                1995: 90_000.0,
                1996: 100_000.0,
                1997: 110_000.0,
            },  # EUR million
            "eurostat_employees": {1995: 4_500.0, 1996: 4_500.0, 1997: 5_000.0},  # thousand
        }[dataset_id]
        return pd.DataFrame({"year": list(values), "value": list(values.values())})

    monkeypatch.setattr(interim.eurostat, "read", series)
    out = interim.build_eurostat_macro().set_index("year")
    assert out.loc[1996, "compensation_per_employee_eur"] == pytest.approx(100_000 * 1000 / 4_500)
    assert out.loc[1997, "compensation_per_employee_eur"] == pytest.approx(22_000.0)
    assert np.isnan(out.loc[1995, "gdp_growth_pct"])  # growth starts a year later
    assert list(out.columns) == [
        "gdp_growth_pct",
        "unemployment_pct",
        "compensation_per_employee_eur",
    ]


def test_eurostat_property_tax_names_the_taxes_and_adds_gdp(monkeypatch):
    taxes = pd.DataFrame(
        [
            {"year": y, "na_item": item, "value": v + y - 2020}
            for y in (2020, 2021)
            for item, v in (("D29A", 1_500.0), ("D214C", 1_000.0))
        ]
    )
    gdp = pd.DataFrame(
        {
            "geo": ["PT", "PT", "ES"],
            "year": [2020, 2021, 2020],
            "value": [200_000.0, 210_000.0, 9.0],
        }
    )
    monkeypatch.setattr(
        interim.eurostat, "read", lambda d: taxes if d == "eurostat_property_tax" else gdp
    )
    out = interim.build_eurostat_property_tax().set_index("year")
    assert out.loc[2021, "imi_revenue_eur_m"] == 1_501.0
    assert out.loc[2020, "gdp_eur_m"] == 200_000.0
    assert list(out.columns) == ["imi_revenue_eur_m", "imt_revenue_eur_m", "gdp_eur_m"]


def test_aima_foreigners_labels_nationalities_and_keeps_the_total(monkeypatch):
    rows = [
        {"muni_code": "0101", "period_start": "2023-01-01", "dim_3": code, "value": v}
        for code, v in (("T", 6.0), ("BR", 3.0), ("TOP", 2.0), ("UA", 1.0))
    ]
    _patch_municipal(monkeypatch, {"0010247": _ine(rows)})
    out = interim.build_aima_foreigners()
    assert dict(zip(out["nationality"], out["foreign_residents_n"], strict=True)) == {
        "total": 6.0, "br": 3.0, "other": 2.0, "ua": 1.0,
    }  # fmt: skip
    assert list(out.columns) == ["muni_code", "year", "nationality", "foreign_residents_n"]


def test_bp_mortgage_one_column_per_series_with_month_start(monkeypatch):
    from pthousing.data.sources import bportugal

    dates = pd.to_datetime(["2003-01-31", "2003-02-28"])
    frames = [
        pd.DataFrame({"date": dates, "value": [i + 1.0, i + 2.0], "series_key": key})
        for i, key in enumerate(interim.BP_COLUMNS)
    ]
    monkeypatch.setattr(bportugal, "read_all", lambda: pd.concat(frames, ignore_index=True))
    out = interim.build_bp_mortgage()
    assert set(interim.BP_COLUMNS.values()) <= set(out.columns)
    assert out["period_start"].dt.strftime("%Y-%m-%d").tolist() == ["2003-01-01", "2003-02-01"]
    assert out["mortgage_aprc_new_pct"].tolist() == [1.0, 2.0]
    assert out["month"].tolist() == [1, 2]


def test_bp_household_debt_keeps_quarter_end_months(monkeypatch):
    from pthousing.data.sources import bportugal

    dates = pd.to_datetime(["2020-02-29", "2020-03-31", "2020-04-30", "2020-06-30"])
    frames = [
        pd.DataFrame({"date": dates, "value": [i + 1.0] * 4, "series_key": key})
        for i, key in enumerate(interim.BP_DEBT_COLUMNS)
    ]
    monkeypatch.setattr(
        bportugal, "read_all", lambda dataset_id="x": pd.concat(frames, ignore_index=True)
    )
    out = interim.build_bp_household_debt()
    assert out["period_start"].dt.strftime("%Y-%m-%d").tolist() == ["2020-01-01", "2020-04-01"]
    assert out["quarter"].tolist() == [1, 2]
    assert set(interim.BP_DEBT_COLUMNS.values()) <= set(out.columns)


def test_build_writes_parquet_and_read_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(interim, "INTERIM", tmp_path)
    monkeypatch.setitem(interim.BUILDERS, "toy", lambda: pd.DataFrame({"a": [1, 2]}))
    path = interim.build("toy")
    assert path == tmp_path / "toy.parquet"
    assert interim.read("toy")["a"].tolist() == [1, 2]
    with pytest.raises(FileNotFoundError, match="interim.build"):
        interim.read("missing")


def test_download_calls_each_chosen_source_and_rejects_unknown(monkeypatch):
    from pthousing.data.sources import aima, at, bis, bportugal, caop, eurostat, ine, oecd, rnal

    calls = []
    monkeypatch.setattr(
        ine,
        "fetch_indicator",
        lambda code, filters=None, refresh=False: calls.append(("ine", code, filters)),
    )
    monkeypatch.setattr(bportugal, "fetch_all", lambda refresh=False: calls.append(("bportugal",)))
    monkeypatch.setattr(eurostat, "fetch", lambda ds, refresh=False: calls.append(("eurostat", ds)))
    monkeypatch.setattr(bis, "fetch", lambda ds, refresh=False: calls.append(("bis", ds)))
    monkeypatch.setattr(oecd, "fetch", lambda ds, refresh=False: calls.append(("oecd", ds)))
    monkeypatch.setattr(rnal, "fetch", lambda refresh=False: calls.append(("rnal",)))
    monkeypatch.setattr(aima, "fetch", lambda refresh=False: calls.append(("aima",)))
    monkeypatch.setattr(at, "fetch", lambda refresh=False: calls.append(("at",)))
    monkeypatch.setattr(caop, "download", lambda refresh=False: calls.append(("caop",)))

    interim.download(["eurostat", "rnal"])
    assert calls == [
        ("eurostat", "eurostat_hpi"),
        ("eurostat", "eurostat_hicp"),
        ("eurostat", "eurostat_demography"),
        ("eurostat", "eurostat_gdp"),
        ("eurostat", "eurostat_unemployment"),
        ("eurostat", "eurostat_compensation"),
        ("eurostat", "eurostat_employees"),
        ("eurostat", "eurostat_property_tax"),
        ("eurostat", "eurostat_gdp_nominal"),
        ("eurostat", "eurostat_housing_spending"),
        ("eurostat", "eurostat_property_tax_peers"),
        ("rnal",),
    ]
    calls.clear()
    interim.download()
    expected = [("ine", code, None) for code in interim.INE_CODES]
    expected += [("ine", code, flt) for code, flt in interim.INE_FILTERED.items()]
    expected += [("ine", code, flt) for code, flt in interim.INE_HOUSEHOLD_SIZE.items()]
    assert [c for c in calls if c[0] == "ine"] == expected
    assert {c[0] for c in calls} == set(interim.SOURCES)
    assert ("bis", "bis_spp") in calls and ("oecd", "oecd_house_prices") in calls
    with pytest.raises(ValueError, match="Unknown source"):
        interim.download(["nope"])


def test_at_imi_rates_renames_keeps_flags_and_sorts(monkeypatch):
    from pthousing.data.sources import at

    raw = pd.DataFrame(
        {
            "year": [2016, 2015],
            "urban_pct": [0.35, float("nan")],
            "rustic_pct": [0.8, 0.8],
            "parish_rates": [False, True],
            "deduction_link": [True, False],
            "muni_code": ["0102", "0101"],
        }
    )
    monkeypatch.setattr(at, "read", lambda: raw)
    out = interim.build_at_imi_rates()
    assert list(out.columns) == [
        "muni_code", "year", "imi_urban_pct", "imi_rustic_pct", "parish_rates", "deduction_link",
    ]  # fmt: skip
    assert out["muni_code"].tolist() == ["0101", "0102"]
    assert out["parish_rates"].tolist() == [True, False]


def test_households_size_merges_2011_sizes_into_four_or_more(monkeypatch):
    rows_2011 = [
        {"muni_code": "0101", "period_start": "2011-01-01", "dim_4": code, "value": v}
        for code, v in (
            ("T", 21.0),
            ("01", 5.0),
            ("02", 6.0),
            ("03", 4.0),
            ("04", 3.0),
            ("09", 3.0),
        )
    ]
    rows_2021 = [
        {"muni_code": "0101", "period_start": "2021-01-01", "dim_5": code, "value": v}
        for code, v in (("T", 20.0), ("1", 7.0), ("2", 6.0), ("3", 4.0), ("4", 3.0))
    ]
    _patch_municipal(monkeypatch, {"0006457": _ine(rows_2011), "0012856": _ine(rows_2021)})
    out = interim.build_ine_households_size().set_index(["census_year", "size"])["households_n"]
    assert out.loc[2011].to_dict() == {"1": 5.0, "2": 6.0, "3": 4.0, "4plus": 6.0}
    assert out.loc[2021].to_dict() == {"1": 7.0, "2": 6.0, "3": 4.0, "4plus": 3.0}


def test_census_stock_households_use_only_the_total_rows(monkeypatch):
    totals = interim._only_totals(
        pd.DataFrame({"dim_3": ["T", "T"], "dim_4": ["T", "01"], "value": [20.0, 5.0]})
    )
    assert totals["value"].tolist() == [20.0]


def test_eurostat_property_tax_peers_one_row_per_country_and_year(monkeypatch):
    taxes = pd.DataFrame(
        [
            {"geo": g, "year": 2020, "na_item": item, "value": v}
            for g in ("PT", "DE")
            for item, v in (("D29A", 1_500.0), ("D214C", 0.0 if g == "DE" else 900.0))
        ]
    )
    gdp = pd.DataFrame(
        {"geo": ["PT", "DE"], "year": [2020, 2020], "value": [200_000.0, 3_000_000.0]}
    )
    monkeypatch.setattr(
        interim.eurostat, "read", lambda d: taxes if d == "eurostat_property_tax_peers" else gdp
    )
    out = interim.build_eurostat_property_tax_peers().set_index("geo")
    assert out.loc["PT", "transaction_tax_eur_m"] == 900.0
    assert out.loc["DE", "gdp_eur_m"] == 3_000_000.0
    assert list(out.columns) == [
        "year",
        "land_buildings_tax_eur_m",
        "transaction_tax_eur_m",
        "gdp_eur_m",
    ]


def test_ine_construction_costs_names_the_factors_and_keeps_the_national_rows(monkeypatch):
    rows = [
        {"geocod": g, "dim_3": f, "period_start": "2020-03-01", "value": v}
        for g, f, v in [("PT", "T", 100.0), ("PT", "1", 90.0), ("PT", "2", 110.0), ("PT", "9", 5.0)]
    ] + [{"geocod": "1234567", "dim_3": "T", "period_start": "2020-03-01", "value": 1.0}]
    monkeypatch.setattr(interim.ine, "read_indicator", lambda code: _ine(rows))
    out = interim.build_ine_construction_costs().set_index("factor")
    assert sorted(out.index) == ["labour", "materials", "total"]
    assert out.loc["labour", "construction_cost_b2021"] == 110.0
    assert (out["month"] == 3).all()


def test_ine_price_by_buyer_national_names_the_buyers_and_drops_blank_cells(monkeypatch):
    rows = [
        {"geocod": "PT", "dim_3": "2", "period_start": "2025-10-01", "value": 2765.0},
        {"geocod": "PT", "dim_3": "1", "period_start": "2025-10-01", "value": 2051.0},
        {"geocod": "PT", "dim_3": "T", "period_start": "2025-10-01", "value": np.nan},
        {"geocod": "1234567", "dim_3": "2", "period_start": "2025-10-01", "value": 1.0},
    ]
    monkeypatch.setattr(interim.ine, "read_indicator", lambda code: _ine(rows))
    out = interim.build_ine_price_by_buyer_national().set_index("buyer")
    assert sorted(out.index) == ["domestic", "foreign"]  # the blank total is dropped
    assert out.loc["foreign", "price_sqm_eur"] == 2765.0 and (out["quarter"] == 4).all()


def test_ine_price_by_buyer_keeps_published_municipal_cells_only(monkeypatch):
    rows = [
        {"muni_code": "0101", "dim_3": "2", "period_start": "2025-10-01", "value": 2000.0},
        {"muni_code": "0101", "dim_3": "21", "period_start": "2025-10-01", "value": np.nan},
    ]
    monkeypatch.setattr(interim, "_municipal", lambda code: _ine(rows))
    out = interim.build_ine_price_by_buyer()
    assert out["buyer"].tolist() == ["foreign"]


def test_ine_building_works_names_projects_and_purposes_and_keeps_completed_from_2011(monkeypatch):
    lic = [
        {"muni_code": "0101", "dim_3": p, "dim_4": q, "year": 2010, "value": v}
        for p, q, v in (("1", "1", 5.0), ("2", "1", 2.0), ("T", "1", 7.0))
    ]
    comp = [
        {"muni_code": "0101", "dim_3": "1", "dim_4": "1", "year": 2011, "value": 4.0},
    ]
    frames = {"0013234": pd.DataFrame(lic), "0013247": pd.DataFrame(comp)}
    monkeypatch.setattr(interim, "_municipal", lambda code: frames[code].copy())
    out = interim.build_ine_building_works()
    first = out[(out["year"] == 2010) & (out["project"] == "alteration")].iloc[0]
    assert first["purpose"] == "family_housing" and first["licensed_buildings_n"] == 2.0
    assert np.isnan(first["completed_buildings_n"])
    late = out[out["year"] == 2011].iloc[0]
    assert late["completed_buildings_n"] == 4.0 and np.isnan(late["licensed_buildings_n"])


def test_municipal_revenue_converts_thousands_to_euros_and_picks_the_items(monkeypatch):
    rows = []
    for item, value in (("R", 120.0), ("R1", 100.0), ("R12", 10.0), ("R13", 25.0), ("R2", 20.0)):
        rows.append(
            {"muni_code": "0101", "period_start": "2022-01-01", "dim_3": item, "value": value}
        )
    _patch_municipal(monkeypatch, {"0013908": _ine(rows)})
    out = interim.build_ine_municipal_revenue()
    assert len(out) == 1 and "R2" not in out.columns
    row = out.iloc[0]
    assert row["imi_eur"] == 25_000.0 and row["imt_eur"] == 10_000.0
    assert row["current_receipts_eur"] == 100_000.0 and row["total_receipts_eur"] == 120_000.0
