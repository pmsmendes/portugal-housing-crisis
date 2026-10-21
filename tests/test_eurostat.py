import pandas as pd
import pytest

from pthousing.data.sources import eurostat


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1996", "1996-01-01"),
        ("2005-Q1", "2005-01-01"),
        ("2005-Q3", "2005-07-01"),
        ("2005-03", "2005-03-01"),
    ],
)
def test_parse_time(code, expected):
    assert eurostat.parse_time(code) == pd.Timestamp(expected)


def test_parse_time_rejects_unknown_code():
    with pytest.raises(ValueError):
        eurostat.parse_time("2005-S1")


def test_parse_dataset_sparse_values_sorted_by_geo_and_period():
    payload = {
        "id": ["geo", "time"],
        "size": [2, 3],
        "dimension": {
            "geo": {"category": {"index": ["PT", "ES"]}},
            "time": {"category": {"index": ["2020-Q1", "2020-Q2", "2020-Q3"]}},
        },
        "value": {"1": 101.0, "2": 102.0, "3": 201.0},  # PT Q2, PT Q3, ES Q1; the rest missing
        "status": {"1": "p"},
    }
    df = eurostat.parse_dataset(payload)
    assert df[["geo", "period"]].values.tolist() == [
        ["ES", "2020-Q1"],
        ["PT", "2020-Q2"],
        ["PT", "2020-Q3"],
    ]
    assert df["year"].tolist() == [2020, 2020, 2020]
    assert df["period_start"].dt.month.tolist() == [1, 4, 7]
    pt_status = df.loc[df.geo == "PT", "status"]
    assert pt_status.iloc[0] == "p" and pd.isna(pt_status.iloc[1])


def test_fetch_sends_configured_params_and_geo_list(tmp_path, monkeypatch):
    monkeypatch.setattr(eurostat, "RAW", tmp_path)
    monkeypatch.setattr(
        eurostat,
        "_entry",
        lambda _: {"dataset": "prc_x", "params": {"unit": "I15_Q"}, "geo": ["PT", "ES"]},
    )
    seen = {}

    class Resp:
        content = b'{"id": []}'

        def raise_for_status(self):
            pass

    def fake_get(url, params, timeout):
        seen.update(url=url, params=params)
        return Resp()

    monkeypatch.setattr(eurostat.requests, "get", fake_get)
    path = eurostat.fetch("eurostat_x")
    assert seen["url"].endswith("/prc_x")
    assert seen["params"]["geo"] == ["PT", "ES"] and seen["params"]["unit"] == "I15_Q"
    assert path.read_bytes() == b'{"id": []}'
