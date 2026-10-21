import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from pthousing.analysis import spatial
from pthousing.config import CRS_METRIC


def _grid(n: int = 6, island: bool = True) -> gpd.GeoDataFrame:
    """n x n squares of 1 km on the mainland, plus (optionally) two islands far away."""
    rows = [
        {"muni_code": f"{r}{c:02d}", "territory": "continente", "geometry": box(c, r, c + 1, r + 1)}
        for r in range(n)
        for c in range(n)
    ]
    if island:
        rows += [
            {"muni_code": "9001", "territory": "azores", "geometry": box(-500, 0, -499, 1)},
            {"muni_code": "9002", "territory": "azores", "geometry": box(-300, 0, -299, 1)},
            {"muni_code": "9003", "territory": "azores", "geometry": box(-100, 0, -99, 1)},
        ]
    geo = gpd.GeoDataFrame(rows, crs=CRS_METRIC)
    geo["geometry"] = geo.geometry.scale(1000, 1000, origin=(0, 0))
    return geo


def test_queen_weights_are_row_standardised_and_stay_inside_territory():
    w = spatial.build_weights(_grid())
    assert all(sum(v) == pytest.approx(1) for v in w.weights.values())
    assert set(w.neighbors["9001"]) <= {"9002", "9003"}
    assert not any(n.startswith("9") for n in w.neighbors["000"])
    assert len(w.neighbors["202"]) == 8  # interior square: eight queen neighbours


def test_island_without_land_neighbour_is_linked_to_nearest_in_territory():
    w = spatial.build_weights(_grid())
    assert set(w.neighbors["9001"]) == {"9002", "9003"}
    assert w.islands == []


def test_knn_weights_have_k_neighbours():
    w = spatial.build_weights(_grid(), kind="knn", k=4)
    assert len(w.neighbors["202"]) == 4


def test_weights_reject_unprojected_geometry_and_unknown_kind():
    with pytest.raises(ValueError, match="metres"):
        spatial.build_weights(_grid().to_crs(4326))
    with pytest.raises(ValueError, match="kind"):
        spatial.build_weights(_grid(), kind="rook")


def test_global_moran_detects_a_gradient_and_noise():
    geo = _grid(island=False)
    w = spatial.build_weights(geo)
    gradient = pd.Series(geo.geometry.centroid.x.to_numpy(), index=geo["muni_code"])
    clustered = spatial.global_moran(gradient, w, permutations=199)
    assert clustered["I"] > 0.5 and clustered["p_sim"] < 0.01
    noise = pd.Series(np.random.default_rng(1).normal(size=len(geo)), index=geo["muni_code"])
    random = spatial.global_moran(noise, w, permutations=199)
    assert abs(random["I"]) < 0.3 and random["p_sim"] > 0.01
    assert random["expected"] == pytest.approx(-1 / (len(geo) - 1))


def test_missing_values_drop_out_without_counting_as_zero():
    geo = _grid(island=False)
    w = spatial.build_weights(geo)
    values = pd.Series(geo.geometry.centroid.x.to_numpy(), index=geo["muni_code"])
    values.loc[["000", "101"]] = np.nan
    result = spatial.global_moran(values, w, permutations=99)
    assert result["n"] == len(geo) - 2


def test_local_moran_labels_a_high_block_hh():
    geo = _grid(island=False)
    w = spatial.build_weights(geo)
    values = pd.Series(0.0, index=geo["muni_code"])
    values.loc[["000", "001", "100", "101"]] = 10.0
    values += np.random.default_rng(0).normal(0, 0.1, len(values))
    lisa = spatial.local_moran(values, w, permutations=499, alpha=0.1)
    assert lisa.loc["000", "quadrant"] == "HH"
    assert set(lisa["quadrant"]) <= {"HH", "LH", "LL", "HL"}
    assert set(lisa["cluster"]) <= {"HH", "LH", "LL", "HL", "ns"}


def test_gistar_flags_hot_and_cold_in_opposite_corners():
    geo = _grid(island=False)
    w = spatial.build_weights(geo)
    cx, cy = geo.geometry.centroid.x / 1000, geo.geometry.centroid.y / 1000
    values = pd.Series((cx + cy).to_numpy(), index=geo["muni_code"])
    g = spatial.getis_ord_gistar(values, w, permutations=499, alpha=0.1)
    assert g.loc["505", "z"] > 0 and g.loc["000", "z"] < 0
    assert set(g["hotspot"]) <= {"hot", "cold", "ns"}


def test_moran_by_year_has_one_row_per_year():
    geo = _grid(island=False)
    w = spatial.build_weights(geo)
    base = geo.geometry.centroid.x.to_numpy()
    panel = pd.concat(
        [
            pd.DataFrame({"muni_code": geo["muni_code"], "year": y, "v": base * y})
            for y in (2020, 2021)
        ]
    )
    out = spatial.moran_by_year(panel, "v", w, [2020, 2021], permutations=49)
    assert out["year"].tolist() == [2020, 2021]
    assert (out["I"] > 0.5).all()
