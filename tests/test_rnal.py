import json
from datetime import date

import pytest

from pthousing.data.sources import rnal

MS_2015 = 1420070400000  # 2015-01-01
MS_1900 = -2208988800000  # 1900-01-01


def _feature(n, dtmnfr, registered_ms, reliability="Fiavel", x=-9.1, y=38.7):
    return {
        "attributes": {
            "NrRNAL": n,
            "DataRegisto": registered_ms,
            "DataAberturaPublico": registered_ms,
            "Modalidade": "Apartamento",
            "NrUtentes": 4,
            "DTMNFR": dtmnfr,
            "Freguesia": "Alvalade",
            "Concelho": "LISBOA",
            "NUTSIII": "Grande Lisboa",
            "FiabilidadeGeo": reliability,
        },
        "geometry": {"x": x, "y": y},
    }


def test_parse_snapshot_codes_dates_flags_and_reliability_labels():
    raw = {
        "snapshot_date": "2026-10-21",
        "features": [
            _feature(1, "110618", MS_2015, "Fiável"),
            _feature(2, "081005", MS_1900, "NaoFiavel"),
            _feature(3, "081005", MS_2015, "PoucoFiavel", x=None, y=None),
        ],
    }
    df = rnal.parse_snapshot(raw)
    assert df["muni_code"].tolist() == ["1106", "0810", "0810"]
    assert df["registered"].dt.strftime("%Y-%m-%d").tolist() == [
        "2015-01-01",
        "1900-01-01",
        "2015-01-01",
    ]
    assert df["registered_before_2008"].tolist() == [False, True, False]
    assert df["geo_reliability"].tolist() == ["reliable", "unreliable", "low"]
    assert "muni_name" not in df.columns  # names and addresses are not kept
    assert df["lon"].isna().tolist() == [False, False, True]


def test_fetch_pages_until_complete_and_keeps_dated_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(rnal, "RAW", tmp_path)
    monkeypatch.setattr(rnal, "_layer_url", lambda: "https://t.test/layer")
    monkeypatch.setattr(rnal, "PAGE_SIZE", 2)
    features = [_feature(i, "110618", MS_2015) for i in range(5)]
    offsets = []

    def fake_query(url, **params):
        if params.get("returnCountOnly"):
            return {"count": 5}
        offsets.append(params["resultOffset"])
        return {"features": features[params["resultOffset"] : params["resultOffset"] + 2]}

    monkeypatch.setattr(rnal, "_query", fake_query)
    path = rnal.fetch(today=date(2026, 10, 21))
    assert path.name == "rnal_2026-10-21.json" and offsets == [0, 2, 4]
    assert json.loads(path.read_text(encoding="utf-8"))["count"] == 5
    rnal.fetch(today=date(2026, 10, 21))
    assert offsets == [0, 2, 4]  # same-day snapshot is reused
    rnal.fetch(today=date(2026, 10, 22))
    assert (tmp_path / "rnal" / "rnal_2026-10-22.json").exists()
    assert rnal.latest_snapshot().name == "rnal_2026-10-22.json"
    assert len(rnal.read()) == 5


def test_fetch_fails_loudly_on_incomplete_download(tmp_path, monkeypatch):
    monkeypatch.setattr(rnal, "RAW", tmp_path)
    monkeypatch.setattr(rnal, "_layer_url", lambda: "https://t.test/layer")

    def fake_query(url, **params):
        return {"count": 10} if params.get("returnCountOnly") else {"features": []}

    monkeypatch.setattr(rnal, "_query", fake_query)
    with pytest.raises(RuntimeError, match="incomplete"):
        rnal.fetch()
    assert not list((tmp_path / "rnal").glob("*.json"))  # no partial snapshot written


def test_latest_snapshot_without_download_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(rnal, "RAW", tmp_path)
    with pytest.raises(FileNotFoundError, match="fetch"):
        rnal.latest_snapshot()
