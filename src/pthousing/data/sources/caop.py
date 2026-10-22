"""DGT CAOP: official administrative boundaries (municipality geometries).

Downloads the CAOP GeoPackage zips listed in ``config/sources.yaml`` into ``data/raw/caop/`` (each zip is
extracted into its own folder) and reads the municipality layer of every territory. Mainland, Madeira and
the two Azores groups each use their own CRS; geometries are reprojected to ``CRS_METRIC``.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import requests
import yaml

from pthousing.config import CRS_METRIC, INTERIM, MUNI_KEY, RAW, SOURCES_YAML

SOURCE_ID = "caop"
DATASET_ID = "caop_boundaries"
N_MUNICIPALITIES = 308

_TERRITORY = {"Continente": "continente", "ArqMadeira": "madeira", "ArqAcores": "azores"}
_COLUMNS = {
    "dtmn": MUNI_KEY,
    "municipio": "muni_name",
    "distrito_ilha": "district",
    "nuts3": "nuts3_name_2024",
    "nuts2": "nuts2_name_2024",
    "area_ha": "area_ha",
    "n_freguesias": "parishes_n",
}


def source_urls() -> dict[str, str]:
    entry = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))[SOURCE_ID][DATASET_ID]
    return entry["urls"]


def download(refresh: bool = False) -> list[Path]:
    """Download and unpack the CAOP zips; return the GeoPackage files."""
    raw_dir = RAW / SOURCE_ID
    raw_dir.mkdir(parents=True, exist_ok=True)
    for url in source_urls().values():
        zip_path = raw_dir / url.rsplit("/", 1)[-1]
        folder = raw_dir / zip_path.stem
        if folder.exists() and any(folder.glob("*.gpkg")) and not refresh:
            continue
        tmp = zip_path.with_suffix(".part")
        with requests.get(url, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        tmp.replace(zip_path)
        _extract_gpkg(zip_path, folder)
    return sorted(raw_dir.glob("*/*.gpkg"))


def _extract_gpkg(zip_path: Path, folder: Path) -> None:
    folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.lower().endswith(".gpkg"):
                zf.extract(member, folder)


def _municipality_layer(gpkg: Path) -> str:
    layers = [name for name, _ in pyogrio.list_layers(gpkg) if name.endswith("_municipios")]
    if len(layers) != 1:
        raise ValueError(f"Expected one municipality layer in {gpkg.name}, found {layers}")
    return layers[0]


def read_municipalities(geometry: bool = True) -> gpd.GeoDataFrame | pd.DataFrame:
    """All 308 municipalities with names, district, NUTS 2024 names, area and (optionally) geometry."""
    gpkgs = sorted((RAW / SOURCE_ID).glob("*/*.gpkg"))
    if not gpkgs:
        raise FileNotFoundError("No CAOP GeoPackages in data/raw/caop; run caop.download() first")
    frames = []
    for gpkg in gpkgs:
        df = pyogrio.read_dataframe(gpkg, layer=_municipality_layer(gpkg), read_geometry=geometry)
        if geometry:
            df = df.to_crs(CRS_METRIC)
        df["territory"] = next(v for k, v in _TERRITORY.items() if gpkg.name.startswith(k))
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns=_COLUMNS)
    keep = [*_COLUMNS.values(), "territory"] + (["geometry"] if geometry else [])
    out = out[keep].sort_values(MUNI_KEY, ignore_index=True)
    if out[MUNI_KEY].duplicated().any() or len(out) != N_MUNICIPALITIES:
        raise ValueError(
            f"CAOP municipality list is not {N_MUNICIPALITIES} unique codes ({len(out)} rows)"
        )
    return gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_METRIC) if geometry else out


def build_interim() -> Path:
    """Write the municipality layer (with geometry) to data/interim/caop_municipalities.parquet."""
    path = INTERIM / "caop_municipalities.parquet"
    INTERIM.mkdir(parents=True, exist_ok=True)
    read_municipalities().to_parquet(path)
    return path


_COAST = "linha de costa"
_WATER = "limite na água"


def coast_class() -> pd.Series:
    """How each of the 308 municipalities meets the water: ``coast``, ``estuary`` or ``inland``.

    Read from the boundary segments (``*_trocos`` layers): a municipality is ``coast`` if any parish of it lies on
    a segment typed 'Limite e Linha de Costa'; ``estuary`` if it has only 'Limite na Água' segments (the tidal
    Tejo and Sado, where CAOP draws the boundary in the water, e.g. Lisboa); otherwise ``inland``. Indexed by
    ``muni_code``. The sea boundary of a parish carries the code '99' on its outer side, which is ignored.
    """
    gpkgs = sorted((RAW / SOURCE_ID).glob("*/*.gpkg"))
    if not gpkgs:
        raise FileNotFoundError("No CAOP GeoPackages in data/raw/caop; run caop.download() first")
    coast, water = set(), set()
    for gpkg in gpkgs:
        layers = [name for name, _ in pyogrio.list_layers(gpkg) if name.endswith("_trocos")]
        if len(layers) != 1:
            raise ValueError(f"Expected one boundary-segment layer in {gpkg.name}, found {layers}")
        segments = pyogrio.read_dataframe(gpkg, layer=layers[0], read_geometry=False)
        kind = segments["significado_linha"].str.lower()
        for mask, found in ((kind.str.contains(_COAST), coast), (kind.str.contains(_WATER), water)):
            parishes = pd.concat(
                [segments.loc[mask, "ea_direita"], segments.loc[mask, "ea_esquerda"]]
            )
            parishes = parishes.astype(str)
            found.update(parishes[parishes.str.len() == 6].str[:4])
    municipalities = read_municipalities(geometry=False)[MUNI_KEY]
    return pd.Series(
        [
            "coast" if code in coast else "estuary" if code in water else "inland"
            for code in municipalities
        ],
        index=pd.Index(municipalities, name=MUNI_KEY),
        name="coast_class",
    )
