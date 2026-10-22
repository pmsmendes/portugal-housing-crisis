import numpy as np
import pandas as pd
import pytest

from pthousing.data import build_panel, harmonize, interim

MUNIS = ["0101", "1106", "3101"]  # 3101 is on Madeira


def _crosswalk():
    return pd.DataFrame(
        {
            "muni_code": MUNIS,
            "muni_name": ["A", "B", "C"],
            "district": ["d1", "d2", "d3"],
            "territory": ["continente", "continente", "madeira"],
            "nuts3_name_2024": "n3",
            "nuts2_name_2024": "n2",
        }
    )


def _ts(date):
    return pd.Timestamp(date)


def _tables():
    price = pd.DataFrame(
        [
            {"muni_code": m, "period_start": _ts(f"{y}-{3 * q - 2:02d}-01"), "year": y, "quarter": q,
             "category": c, "method": "2022", "price_sqm_eur": 1000.0 * q + {"total": 0, "existing": 1000, "new": 2000}[c], "sales_12m_n": 50.0}
            for m in MUNIS for y in (2019, 2020) for q in (1, 4) for c in ("total", "existing", "new")
        ]
    )  # fmt: skip
    rent = pd.DataFrame(
        [{"muni_code": m, "year": 2020, "rent_sqm_eur": 10.0, "new_leases_n": 40.0} for m in MUNIS]
    )
    income = pd.DataFrame(
        [{"muni_code": m, "year": 2020, "income_mean_eur": 15_000.0, "income_median_eur": 12_000.0, "vintage": "2024"} for m in MUNIS]
    )  # fmt: skip
    valuation = pd.DataFrame(
        [{"muni_code": m, "year": 2020, "type": "total", "valuation_sqm_eur": 900.0} for m in MUNIS]
    )
    construction = pd.DataFrame(
        [
            {"muni_code": m, "year": y, "size": s, "licensed_n": 10.0, "completed_n": 5.0}
            for m in MUNIS for y in range(1995, 2026) for s in ("total", "br_2")
        ]
    )  # fmt: skip
    rows = []
    for m in MUNIS:
        for age, n in (("total", 100.0), ("60-64", 10.0), ("65-69", 10.0), ("85+", 10.0)):
            rows.append(
                {"muni_code": m, "year": 2020, "sex": "total", "age_group": age, "population_n": n}
            )
        rows.append(
            {"muni_code": m, "year": 2020, "sex": "m", "age_group": "total", "population_n": 50.0}
        )
    population = pd.DataFrame(rows)
    foreigners = pd.DataFrame(
        [
            {"muni_code": m, "year": 2020, "nationality": n, "foreign_residents_n": v}
            for m in MUNIS for n, v in (("total", 10.0), ("br", 6.0), ("other", 4.0))
        ]
    )  # fmt: skip
    stock = pd.DataFrame(
        [
            {"muni_code": m, "census_year": y, "dwellings_n": d, "dwellings_usual_n": 0.0, "dwellings_secondary_n": 5.0,
             "dwellings_vacant_n": 15.0, "households_n": h, "dwelling_area_sqm": a}
            for m in MUNIS for y, d, h, a in ((2011, 1000.0, 800.0, 100.0), (2021, 1100.0, 850.0, 120.0))
        ]
    )  # fmt: skip
    census = pd.DataFrame(
        [{"muni_code": m, "census_year": 2021, "vacant_dwellings_pct": 1.5, "occupied_dwellings_n": 100.0,
          "owner_occupied_n": 70.0, "rented_n": 20.0, "other_tenure_n": 10.0} for m in MUNIS]
    )  # fmt: skip
    units = pd.DataFrame(
        {
            "muni_code": ["0101", "0101", "0101", "1106"],
            "registered": pd.to_datetime(["2005-06-01", "2020-03-01", "2026-02-01", "2020-05-01"]),
        }
    )
    cpi = pd.DataFrame({"year": range(1995, 2026), "cpi_index_b2025": np.linspace(50.0, 100.0, 31)})
    months = pd.date_range("2003-01-01", "2025-12-01", freq="MS")
    bp = pd.DataFrame(
        {
            "date": months + pd.offsets.MonthEnd(0),
            "period_start": months,
            "year": months.year,
            "mortgage_rate_new_lt1y_pct": 3.0,
            "mortgage_aprc_new_pct": 4.5,
            "mortgage_rate_stock_gt5y_pct": 2.0,
            "mortgage_new_lt1y_volume_eur_m": 100.0,
            "mortgage_rate_new_fixed_p50_pct": np.nan,
        }
    )
    bp.loc[bp["year"] == 2025, "mortgage_rate_new_lt1y_pct"] = [4.0] * 12
    bp = bp[~((bp["year"] == 2025) & (bp["period_start"].dt.month > 6))]  # 2025 is incomplete
    return {
        "ine_median_price_sqm": price, "ine_median_rent_sqm": rent, "ine_income": income,
        "ine_bank_valuation_annual": valuation, "ine_construction": construction,
        "ine_population": population, "aima_foreigners": foreigners, "ine_census_stock": stock, "ine_census": census,
        "rnal_al": units, "ine_cpi": cpi, "bp_mortgage": bp,
    }  # fmt: skip


@pytest.fixture
def panel(monkeypatch):
    tables = _tables()
    monkeypatch.setattr(interim, "read", lambda name: tables[name])
    monkeypatch.setattr(harmonize, "read_crosswalk", _crosswalk)
    monkeypatch.setattr(
        build_panel,
        "_municipality_areas",
        lambda: pd.DataFrame({"muni_code": MUNIS, "area_ha": [100.0, 200.0, 300.0]}),
    )
    return build_panel.build_municipality_year().set_index(["muni_code", "year"])


def test_grid_is_every_municipality_by_every_year(panel):
    assert len(panel) == 3 * 31
    assert panel.index.is_unique and panel.index.get_level_values("year").min() == 1995


def test_prices_are_year_end_quarters_and_missing_elsewhere(panel):
    row = panel.loc[("0101", 2019)]
    assert row["price_sqm_eur"] == 4000.0  # Q4 total
    assert row["price_existing_sqm_eur"] == 5000.0
    assert np.isnan(panel.loc[("0101", 2018), "price_sqm_eur"])
    assert (
        np.isnan(panel.loc[("0101", 2019), "rent_sqm_eur"])
        and panel.loc[("0101", 2020), "rent_sqm_eur"] == 10.0
    )


def test_real_values_use_the_annual_deflator(panel):
    row = panel.loc[("0101", 2020)]

    def cpi(year):  # the fixture's linear CPI
        return 50.0 + (year - 1995) * 50.0 / 30

    assert row["deflator_to_base_year"] == pytest.approx(cpi(2024) / cpi(2020))
    assert panel.loc[("0101", 2024), "deflator_to_base_year"] == pytest.approx(1.0)
    assert row["price_sqm_eur_real"] == pytest.approx(
        row["price_sqm_eur"] * row["deflator_to_base_year"]
    )
    assert row["income_median_eur_real"] == pytest.approx(12_000.0 * row["deflator_to_base_year"])


def test_population_total_and_old_age_share(panel):
    row = panel.loc[("0101", 2020)]
    assert row["population_n"] == 100.0
    assert row["pop_65plus_pct"] == pytest.approx(20.0)  # 65-69 and 85+ of 100


def test_foreign_residents_are_the_total_and_a_share_of_population(panel):
    row = panel.loc[("0101", 2020)]
    assert row["foreign_residents_n"] == 10.0  # the total, not the sum of all rows
    assert row["foreign_residents_pct"] == pytest.approx(10.0)  # 10 of 100 residents
    assert np.isnan(panel.loc[("0101", 2021), "foreign_residents_n"])
    assert np.isnan(panel.loc[("0101", 2021), "foreign_residents_pct"])


def test_dwelling_area_is_interpolated_between_censuses_and_flat_outside(panel):
    area = panel.loc["0101", "dwelling_area_sqm"]
    assert area[2005] == 100.0 and area[2011] == 100.0
    assert area[2016] == pytest.approx(110.0) and area[2021] == 120.0 and area[2025] == 120.0


def test_indicators_follow_their_definitions(panel):
    row = panel.loc[("0101", 2020)]
    area = 100 + 0.9 * 20  # 2020 is 90% of the way between the censuses
    assert row["dwelling_area_sqm"] == pytest.approx(area)
    assert row["pti_years"] == pytest.approx(row["price_sqm_eur"] * area / 12_000)
    assert row["pti_years_100sqm"] == pytest.approx(row["price_sqm_eur"] * 100 / 12_000)
    assert row["rti_pct"] == pytest.approx(100 * 10 * area * 12 / 12_000)
    assert row["mortgage_rate_new_lt1y_pct"] == pytest.approx(3.0)
    assert row["mortgage_burden_pct"] > 0
    assert np.isnan(panel.loc[("0101", 2018), "pti_years"])  # no price that year


def test_mortgage_rate_needs_a_full_year(panel):
    rates = panel.loc["0101", "mortgage_rate_new_lt1y_pct"]
    assert (
        rates[2003] == 3.0 and np.isnan(rates[2002]) and np.isnan(rates[2025])
    )  # 2025 has 6 months only


def test_census_static_columns_and_supply_gap(panel):
    row = panel.loc[("0101", 2020)]
    # dwellings +100, households +50 on 800 households: +62.5 per 1,000
    assert row["supply_gap_2011_2021_per_1000"] == pytest.approx(62.5)
    assert row["rented_share_pct_2021"] == pytest.approx(20.0)
    assert row["vacant_dwellings_pct_2021"] == 1.5


def test_short_term_rentals_survivors_snapshot_and_islands(panel):
    survivors = panel.loc["0101", "al_survivor_units_n"]
    assert (
        survivors[2004] == 0.0
        and survivors[2005] == 1.0
        and survivors[2020] == 2.0
        and survivors[2025] == 2.0
    )
    assert (
        panel.loc[("0101", 2020), "al_units_snapshot_n"] == 3.0
    )  # includes the unit registered in 2026
    assert panel.loc[("1106", 2020), "al_survivor_units_n"] == 1.0
    assert (
        panel.loc["3101", "al_survivor_units_n"].isna().all()
    )  # island: the layer does not cover it
    assert panel.loc[("0101", 2020), "al_units_per_1000_dwellings_2021"] == pytest.approx(
        1000 * 3 / 1100
    )


def test_construction_totals_only(panel):
    assert (
        panel.loc[("0101", 2000), "licensed_n"] == 10.0
        and panel.loc[("0101", 2000), "completed_n"] == 5.0
    )


# ---- national quarterly ---------------------------------------------------------------------------


@pytest.fixture
def national(monkeypatch):
    quarters = pd.date_range("2005-01-01", "2026-04-01", freq="QS")
    eurostat = pd.DataFrame(
        [
            {"geo": g, "period_start": q, "year": q.year, "quarter": q.quarter, "hpi_index_b2015": 100.0 + i}
            for g in ("PT", "EU27_2020") for i, q in enumerate(quarters) if not (g == "PT" and q.year < 2008)
        ]
    )  # fmt: skip
    ine = pd.DataFrame(
        [
            {"period_start": q, "year": q.year, "quarter": q.quarter, "category": c, "hpi_index_b2025": 50.0 + i}
            for c in ("total", "new", "existing") for i, q in enumerate(quarters) if q.year >= 2009
        ]
    )  # fmt: skip
    months = pd.date_range("2003-01-01", "2026-09-01", freq="MS")
    cpi = pd.DataFrame(
        {
            "period_start": months,
            "year": months.year,
            "month": months.month,
            "cpi_index_b2025": np.linspace(60.0, 105.0, len(months)),
        }
    )
    bp = pd.DataFrame(
        {
            "date": months + pd.offsets.MonthEnd(0), "period_start": months, "year": months.year,
            "mortgage_rate_new_lt1y_pct": np.linspace(1.0, 4.0, len(months)), "mortgage_aprc_new_pct": 5.0,
            "mortgage_rate_stock_gt5y_pct": 2.0, "mortgage_new_lt1y_volume_eur_m": 10.0,
            "mortgage_rate_new_fixed_p50_pct": np.nan,
        }
    )  # fmt: skip
    bp = bp[bp["period_start"] <= "2026-05-01"]  # 2026Q2 incomplete (June missing)
    tables = {"eurostat_hpi": eurostat, "ine_hpi": ine, "ine_cpi_monthly": cpi, "bp_mortgage": bp}
    monkeypatch.setattr(interim, "read", lambda name: tables[name])
    return build_panel.build_national_quarterly().set_index("period_start")


def test_national_spine_and_hpi_columns(national):
    assert national.index.min() == pd.Timestamp(
        "2005-01-01"
    ) and national.index.max() == pd.Timestamp("2026-04-01")
    assert (
        np.isnan(national.loc["2007-10-01", "hpi_pt_b2015"])
        and national.loc["2008-01-01", "hpi_pt_b2015"] > 0
    )
    assert np.isnan(national.loc["2008-10-01", "hpi_total_b2025"]) and not np.isnan(
        national.loc["2009-01-01", "hpi_total_b2025"]
    )
    assert {"hpi_eu27_b2015", "hpi_new_b2025", "hpi_existing_b2025"} <= set(national.columns)


def test_national_real_series_use_the_quarterly_deflator(national):
    row = national.loc["2015-01-01"]
    assert row["hpi_total_real_b2025"] == pytest.approx(
        row["hpi_total_b2025"] * row["deflator_to_base_year"]
    )
    assert row["deflator_to_base_year"] > 1  # prices before the base year were lower


def test_national_mortgage_quarters_need_all_three_months(national):
    assert not np.isnan(national.loc["2026-01-01", "mortgage_rate_new_lt1y_pct"])
    assert np.isnan(national.loc["2026-04-01", "mortgage_rate_new_lt1y_pct"])  # June 2026 missing
    assert national.loc["2010-01-01", "mortgage_new_lt1y_volume_eur_m"] == 30.0
    row = national.loc["2015-01-01"]
    assert row["mortgage_payment_100k_eur"] > 100_000 / 360  # interest on top of principal


def test_write_and_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(build_panel, "PROCESSED", tmp_path)
    monkeypatch.setitem(build_panel.BUILDERS, "toy", lambda: pd.DataFrame({"a": [1]}))
    assert build_panel.build("toy") == tmp_path / "toy.parquet"
    assert build_panel.read("toy")["a"].tolist() == [1]
    with pytest.raises(FileNotFoundError, match="build_panel.build"):
        build_panel.read("missing")
