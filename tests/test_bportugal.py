import json

import pytest

from pthousing.data.sources import bportugal


def _raw(dates, values, status=None, series_id=1):
    n = len(dates)
    return {
        "series": {
            "id": series_id,
            "label": "Interest rate",
            "domain_ids": [21],
            "dataset_id": "abc",
        },
        "dataset": {
            "id": ["63", "reference_date"],
            "size": [1, n],
            "dimension": {
                "63": {"category": {"index": ["349"]}},
                "reference_date": {"category": {"index": dates}},
            },
            "value": values,
            "status": status or ["F"] * n,
        },
    }


def test_parse_series_dates_year_month_and_values():
    df = bportugal.parse_series(_raw(["2003-01-31", "2003-02-28"], [4.88, 4.76]))
    assert df["date"].dt.strftime("%Y-%m-%d").tolist() == ["2003-01-31", "2003-02-28"]
    assert df["year"].tolist() == [2003, 2003]
    assert df["month"].tolist() == [1, 2]
    assert df["value"].tolist() == [4.88, 4.76]
    assert df["series_id"].unique().tolist() == [1]


def test_parse_series_rejects_unfiltered_dataset():
    raw = _raw(["2003-01-31"], [1.0])
    raw["dataset"]["size"] = [2, 1]
    raw["dataset"]["dimension"]["63"]["category"]["index"] = ["349", "350"]
    raw["dataset"]["value"] = [1.0, 2.0]
    with pytest.raises(ValueError, match="not unique per date"):
        bportugal.parse_series(raw)


def test_fetch_series_stores_metadata_and_filtered_dataset_then_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(bportugal, "RAW", tmp_path)
    monkeypatch.setattr(bportugal, "_base_url", lambda: "https://bp.test/v1")
    calls = []

    def fake_get(url, params):
        calls.append((url, dict(params)))
        if url.endswith("/series/"):
            return [{"id": 7, "label": "L", "domain_ids": [21, 5], "dataset_id": "ds"}]
        return _raw(["2020-01-31"], [1.5])["dataset"]

    monkeypatch.setattr(bportugal, "_get_json", fake_get)
    path = bportugal.fetch_series(7)
    assert calls[1][0] == "https://bp.test/v1/domains/21/datasets/ds"
    assert calls[1][1]["series_ids"] == 7
    assert json.loads(path.read_text(encoding="utf-8"))["series"]["id"] == 7
    assert bportugal.read_series(7)["value"].tolist() == [1.5]
    bportugal.fetch_series(7)
    assert len(calls) == 2  # cached


def test_read_series_missing_file_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(bportugal, "RAW", tmp_path)
    with pytest.raises(FileNotFoundError, match="fetch_series"):
        bportugal.read_series(99)


def test_series_ids_per_dataset_and_fetch_all_covers_both():
    mortgage = bportugal.series_ids()
    debt = bportugal.series_ids("bp_household_debt")
    assert "new_housing_aprc" in mortgage and "housing_loans_stock" in debt
    assert not set(mortgage.values()) & set(debt.values())
