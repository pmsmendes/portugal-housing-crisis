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


def test_build_writes_parquet_and_read_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(interim, "INTERIM", tmp_path)
    monkeypatch.setitem(interim.BUILDERS, "toy", lambda: pd.DataFrame({"a": [1, 2]}))
    path = interim.build("toy")
    assert path == tmp_path / "toy.parquet"
    assert interim.read("toy")["a"].tolist() == [1, 2]
    with pytest.raises(FileNotFoundError, match="interim.build"):
        interim.read("missing")


def test_download_calls_each_chosen_source_and_rejects_unknown(monkeypatch):
    from pthousing.data.sources import aima, at, bportugal, caop, eurostat, ine, rnal

    calls = []
    monkeypatch.setattr(
        ine,
        "fetch_indicator",
        lambda code, filters=None, refresh=False: calls.append(("ine", code, filters)),
    )
    monkeypatch.setattr(bportugal, "fetch_all", lambda refresh=False: calls.append(("bportugal",)))
    monkeypatch.setattr(eurostat, "fetch", lambda ds, refresh=False: calls.append(("eurostat", ds)))
    monkeypatch.setattr(rnal, "fetch", lambda refresh=False: calls.append(("rnal",)))
    monkeypatch.setattr(aima, "fetch", lambda refresh=False: calls.append(("aima",)))
    monkeypatch.setattr(at, "fetch", lambda refresh=False: calls.append(("at",)))
    monkeypatch.setattr(caop, "download", lambda refresh=False: calls.append(("caop",)))

    interim.download(["eurostat", "rnal"])
    assert calls == [("eurostat", "eurostat_hpi"), ("eurostat", "eurostat_hicp"), ("rnal",)]
    calls.clear()
    interim.download()
    expected = [("ine", code, None) for code in interim.INE_CODES]
    expected += [("ine", code, flt) for code, flt in interim.INE_FILTERED.items()]
    assert [c for c in calls if c[0] == "ine"] == expected
    assert {c[0] for c in calls} == set(interim.SOURCES)
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
