import json

import pandas as pd
import pytest

from pthousing.data.sources import ine


def _payload(data: dict) -> list[dict]:
    return [{"IndicadorCod": "0000001", "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]}, "Dados": data}]


ROWS_2024 = [
    {"geocod": "11E0410", "geodsg": "Vila Flor", "ind_string": "2,50", "valor": "2.5"},
    {"geocod": "11A010417", "geodsg": "Parish", "sinal_conv": "-", "ind_string": "-"},
    {"geocod": "PT", "geodsg": "Portugal", "valor": "7.9"},
]


@pytest.mark.parametrize(
    ("label", "start", "year"),
    [
        ("2024", "2024-01-01", 2024),
        ("2nd Semi-annual 2020", "2020-07-01", 2020),
        ("3rd Quarter 2021", "2021-07-01", 2021),
        ("1st Quarter 2026", "2026-01-01", 2026),
        ("August 2026", "2026-08-01", 2026),
    ],
)
def test_parse_period(label, start, year):
    assert ine.parse_period(label) == (pd.Timestamp(start), year)


def test_parse_period_rejects_unknown_label():
    with pytest.raises(ValueError):
        ine.parse_period("Spring 2024")


def test_parse_payload_levels_codes_and_suppression():
    df = ine.parse_payload(_payload({"2024": ROWS_2024}))
    by_geo = df.set_index("geocod")
    assert by_geo.loc["11E0410", "muni_code"] == "0410"
    assert by_geo.loc["11E0410", "geo_level"] == "municipality"
    assert by_geo.loc["11E0410", "value"] == 2.5
    assert by_geo.loc["11A010417", "geo_level"] == "parish"
    assert pd.isna(by_geo.loc["11A010417", "value"])  # '-' is missing, never zero
    assert pd.isna(by_geo.loc["11A010417", "muni_code"])
    assert by_geo.loc["PT", "geo_level"] == "region"
    assert pd.isna(by_geo.loc["PT", "muni_code"])


def test_parse_payload_census_style_four_char_code_kept_as_is():
    rows = [{"geocod": "0412", "geodsg": "Vinhais", "valor": "5.8"}]
    df = ine.parse_payload(_payload({"2021": rows}))
    assert df.loc[0, "muni_code"] == "0412"


def test_parse_payload_keeps_extra_dimensions():
    rows = [
        {"geocod": "11E0410", "geodsg": "Vila Flor", "valor": "1", "dim_3": "T", "dim_3_t": "Total"}
    ]
    df = ine.parse_payload(_payload({"2024": rows}))
    assert {"dim_3", "dim_3_t"} <= set(df.columns)


def test_decode_raises_api_error_message():
    body = json.dumps([{"Sucesso": {"Falso": [{"Msg": "indicator does not exist"}]}}]).encode()
    with pytest.raises(ValueError, match="does not exist"):
        ine._decode(body)


def test_decode_falls_back_to_cp1252():
    body = json.dumps(_payload({"2024": [{"geocod": "x", "geodsg": "São"}]}), ensure_ascii=False)
    assert ine._decode(body.encode("cp1252"))[0]["Dados"]["2024"][0]["geodsg"] == "São"


def test_fetch_falls_back_to_per_period_and_reads_back(tmp_path, monkeypatch):
    monkeypatch.setattr(ine, "RAW", tmp_path)
    calls = []

    def fake_get(endpoint, params, **_):
        calls.append((endpoint, params.get("Dim1")))
        if endpoint == "pindicaMeta.jsp":
            cats = {
                "Dim_Num1_S7A2023": [{"cat_id": "S7A2023"}],
                "Dim_Num1_S7A2024": [{"cat_id": "S7A2024"}],
            }
            return json.dumps([{"Dimensoes": {"Categoria_Dim": [cats]}}]).encode()
        if params["Dim1"] == "T":
            raise RuntimeError("503")
        year = params["Dim1"][-4:]
        return json.dumps(_payload({year: ROWS_2024})).encode()

    monkeypatch.setattr(ine, "_get", fake_get)
    paths = ine.fetch_indicator("0000001")
    assert [p.name for p in paths] == ["S7A2023.json", "S7A2024.json"]

    df = ine.read_indicator("0000001")
    assert sorted(df["year"].unique()) == [2023, 2024]

    calls.clear()
    ine.fetch_indicator("0000001", periods=["S7A2023"])  # cached: no new request
    assert calls == []
