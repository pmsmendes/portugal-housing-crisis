import io
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import box

from pthousing.config import CRS_METRIC, RAW
from pthousing.data.sources import caop


def _write_gpkg(path, layer, rows, epsg):
    gdf = gpd.GeoDataFrame(
        [
            {
                "dtmn": code,
                "municipio": name,
                "distrito_ilha": "Ilha X",
                "nuts3": "Região Autónoma X",
                "nuts2": "Região Autónoma X",
                "nuts1": "Região Autónoma X",
                "area_ha": 100.0,
                "perimetro_km": 5,
                "n_freguesias": 3,
                "geometry": box(0, 0, 1000, 1000),
            }
            for code, name in rows
        ],
        crs=f"EPSG:{epsg}",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, layer=layer, driver="GPKG")


@pytest.fixture
def raw_caop(tmp_path, monkeypatch):
    monkeypatch.setattr(caop, "RAW", tmp_path)
    monkeypatch.setattr(caop, "N_MUNICIPALITIES", 3)
    base = tmp_path / "caop"
    _write_gpkg(
        base / "a" / "Continente_CAOP2024.gpkg", "cont_municipios", [("0102", "Águeda")], 3763
    )
    _write_gpkg(
        base / "b" / "ArqMadeira_CAOP2024.gpkg",
        "ram_municipios",
        [("3101", "Calheta"), ("0101", "Zzz")],
        5016,
    )
    return base


def test_read_municipalities_columns_sorting_territory_and_crs(raw_caop):
    m = caop.read_municipalities()
    assert m["muni_code"].tolist() == ["0101", "0102", "3101"]
    assert m.set_index("muni_code").loc["0102", "muni_name"] == "Águeda"  # accents survive
    assert m.set_index("muni_code").loc["3101", "territory"] == "madeira"
    assert m.crs == CRS_METRIC
    assert {"nuts3_name_2024", "area_ha", "parishes_n", "geometry"} <= set(m.columns)


def test_read_municipalities_without_geometry(raw_caop):
    assert "geometry" not in caop.read_municipalities(geometry=False).columns


def test_wrong_count_or_duplicate_codes_are_rejected(raw_caop, monkeypatch):
    monkeypatch.setattr(caop, "N_MUNICIPALITIES", 4)
    with pytest.raises(ValueError, match="unique codes"):
        caop.read_municipalities()


def test_missing_download_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(caop, "RAW", tmp_path)
    with pytest.raises(FileNotFoundError, match="download"):
        caop.read_municipalities()


def test_download_unpacks_only_gpkg_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(caop, "RAW", tmp_path)
    monkeypatch.setattr(
        caop, "source_urls", lambda: {"x": "https://example.test/CAOP_X_2024-gpkg.zip"}
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("X.gpkg", b"gpkg-bytes")
        zf.writestr("notes.txt", b"ignored")
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield buf.getvalue()

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(caop.requests, "get", fake_get)
    files = caop.download()
    assert [f.name for f in files] == ["X.gpkg"]
    assert not list((tmp_path / "caop").glob("*/notes.txt"))
    caop.download()
    assert len(calls) == 1  # already unpacked: no second request


@pytest.mark.skipif(not list((RAW / "caop").glob("*/*.gpkg")), reason="CAOP not downloaded")
def test_real_caop_has_308_valid_municipalities():
    m = caop.read_municipalities()
    assert len(m) == caop.N_MUNICIPALITIES
    assert m["muni_code"].str.fullmatch(r"\d{4}").all()
    assert m.geometry.is_valid.all()
    assert m.set_index("muni_code").loc["1106", "muni_name"] == "Lisboa"
