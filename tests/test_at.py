import json
from datetime import date

import pandas as pd
import pytest

from pthousing.data import harmonize
from pthousing.data.sources import at


def _page(year, rows, district="LISBOA"):
    body = "".join(
        f"""<tr align="center" class="iTR"><td class="table_space">{code}</td>
        <td class="table_space">{name}</td><td class="table_space"> {urban} </td>
        <td class="table_space"> {rustic} </td><td class="table_space">{parish}</td>
        <td class="table_space">{link}</td></tr>"""
        for code, name, urban, rustic, parish, link in rows
    )
    return (
        f"<html><body><td class='hTD'><b>Lista das taxas IMI por Munic\xedpio do Distrito {district} "
        f"para o ano {year}</b></td><table><tr><th>C\xf3digo</th></tr>{body}</table></body></html>"
    )


ROWS = [
    (
        "1101",
        "ALENQUER",
        "0,3900 %",
        "0,80 %",
        "",
        '<a href="consultaDeducao.action?x=1">+Info</a>',
    ),
    ("1115", "AMADORA", "0,3000 %", "0,80 %", "", ""),
    ("1304", "GONDOMAR", "", "", '<a href="freguesias">+Info</a>', ""),
]


def test_parse_page_reads_rates_flags_and_year_from_the_title():
    df = at.parse_page(_page(2016, ROWS))
    assert df["portal_code"].tolist() == ["1101", "1115", "1304"]
    assert df["year"].unique().tolist() == [2016]
    assert df["urban_pct"].iloc[:2].tolist() == [0.39, 0.30]
    assert df["urban_pct"].isna().tolist() == [
        False,
        False,
        True,
    ]  # parish-specific rates: no single rate
    assert df["parish_rates"].tolist() == [False, False, True]
    assert df["deduction_link"].tolist() == [True, False, False]
    assert df["rustic_pct"].iloc[0] == 0.8


def test_parse_page_rejects_error_pages_and_a_year_that_was_not_asked_for():
    with pytest.raises(ValueError, match="not an IMI rate list"):
        at.parse_page("<html>Servico indisponivel</html>")
    with pytest.raises(ValueError, match="for 2016, asked for 2017"):
        at.parse_page(_page(2016, ROWS), 2017)
    with pytest.raises(ValueError, match="asked for 2018"):
        at.check_page(_page(2017, ROWS), 2018)


def test_island_codes_cover_every_island_municipality_once():
    crosswalk = harmonize.read_crosswalk()
    islands = set(crosswalk.loc[crosswalk["territory"] != "continente", "muni_code"])
    assert len(at.ISLAND_CODES) == 30
    assert set(at.ISLAND_CODES.values()) == islands
    assert len(set(at.ISLAND_CODES.values())) == len(at.ISLAND_CODES)


def test_to_muni_code_keeps_mainland_maps_islands_and_rejects_unknown_island_codes():
    out = at.to_muni_code(pd.Series(["1101", "2203", "1901"]))
    assert out.tolist() == ["1101", "3103", "4301"]
    with pytest.raises(ValueError, match="without a mapping"):
        at.to_muni_code(pd.Series(["1999"]))


@pytest.fixture
def portal(tmp_path, monkeypatch):
    """Two districts and two years served from memory; records the requests."""
    monkeypatch.setattr(at, "RAW", tmp_path)
    monkeypatch.setattr(
        at, "_config", lambda: {"url": "http://x", "districts": ["11LISBOA", "22FUNCHAL"]}
    )
    calls = []

    def fake_get(year, district, retries=3):
        calls.append((year, district))
        if district.startswith("11"):
            rows = ROWS[:2]
        else:
            rows = [("2203", "FUNCHAL", "0,3500 %", "0,80 %", "", "")]
        return _page(year, rows, district).encode(at.ENCODING)

    monkeypatch.setattr(at, "_get", fake_get)
    return tmp_path, calls


def test_fetch_saves_pages_in_a_dated_snapshot_and_reuses_it(portal):
    tmp, calls = portal
    folder = at.fetch(today=date(2026, 10, 22), years=range(2016, 2018), pause=0)
    assert folder == tmp / "at" / "imi_rates_2026-10-22"
    assert sorted(p.name for p in folder.glob("*.html")) == [
        "2016_11.html", "2016_22.html", "2017_11.html", "2017_22.html",
    ]  # fmt: skip
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pages"] == 4 and manifest["years"] == [2016, 2017]
    assert len(calls) == 4
    assert at.fetch(today=date(2026, 10, 23), years=range(2016, 2018), pause=0) == folder
    assert len(calls) == 4  # the complete snapshot is reused, nothing requested
    newer = at.fetch(refresh=True, today=date(2026, 10, 23), years=range(2016, 2017), pause=0)
    assert newer.name == "imi_rates_2026-10-23" and at.latest_snapshot() == newer


def test_fetch_resumes_an_interrupted_snapshot(portal):
    tmp, calls = portal
    folder = tmp / "at" / "imi_rates_2026-10-21"
    folder.mkdir(parents=True)
    (folder / "2016_11.html").write_bytes(_page(2016, ROWS[:2]).encode(at.ENCODING))  # no manifest
    done = at.fetch(today=date(2026, 10, 22), years=range(2016, 2017), pause=0)
    assert done == folder and (folder / "manifest.json").exists()
    assert calls == [(2016, "22FUNCHAL")]  # the saved page is not requested again


def test_fetch_refuses_a_page_for_the_wrong_year(portal, monkeypatch):
    monkeypatch.setattr(
        at, "_get", lambda year, district, retries=3: _page(2099, ROWS).encode(at.ENCODING)
    )
    with pytest.raises(ValueError, match="asked for 2016"):
        at.fetch(today=date(2026, 10, 22), years=range(2016, 2017), pause=0)


def test_read_parses_a_snapshot_into_municipality_codes(portal):
    at.fetch(today=date(2026, 10, 22), years=range(2016, 2018), pause=0)
    df = at.read()
    assert len(df) == 6  # 2 years x (2 Lisbon rows + 1 Funchal row)
    assert set(df["muni_code"]) == {"1101", "1115", "3103"}
    assert "portal_code" not in df.columns
