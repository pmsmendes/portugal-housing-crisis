"""Spatial autocorrelation: contiguity / k-nearest weights, global Moran's I, LISA clusters and Gi* hotspots.

Weights are built per territory (mainland, Azores, Madeira), so no neighbour link crosses the sea. Within a
territory the main specification is queen contiguity; a municipality with no land neighbour (an island with one
municipality) is linked to its nearest neighbours in the same territory. Weights are row-standardised, and a
missing value drops the municipality from the weights rather than counting as zero.
"""

import warnings
from contextlib import contextmanager

import geopandas as gpd
import numpy as np
import pandas as pd
from esda import G_Local, Moran, Moran_Local
from libpysal import weights

from pthousing.config import CRS_METRIC, MUNI_KEY

# LISA quadrant labels: High-High, Low-High (low value among high neighbours), Low-Low, High-Low
QUADRANTS = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
ISLAND_NEIGHBOURS = 2  # nearest same-territory municipalities for one with no land neighbour


@contextmanager
def _disconnected_ok():
    """Silence libpysal's 'not fully connected' warning: islands are separate components by design."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*not fully connected.*")
        yield


def _territory_neighbours(geo: gpd.GeoDataFrame, kind: str, k: int) -> dict[str, list[str]]:
    """Neighbour lists (by ``muni_code``) inside one territory."""
    ids = geo[MUNI_KEY].to_list()
    if len(ids) < 2:
        return {i: [] for i in ids}
    if kind == "queen":
        w = weights.Queen.from_dataframe(geo, ids=ids, silence_warnings=True)
    elif kind == "knn":
        w = weights.KNN.from_dataframe(geo, k=min(k, len(ids) - 1), ids=ids, silence_warnings=True)
    else:
        raise ValueError(f"kind must be 'queen' or 'knn', not {kind!r}")
    neighbours = {i: list(w.neighbors[i]) for i in ids}
    isolated = [i for i, n in neighbours.items() if not n]
    if isolated:
        nearest = weights.KNN.from_dataframe(
            geo, k=min(ISLAND_NEIGHBOURS, len(ids) - 1), ids=ids, silence_warnings=True
        )
        for i in isolated:
            neighbours[i] = list(nearest.neighbors[i])
    return neighbours


def build_weights(geo: gpd.GeoDataFrame, kind: str = "queen", k: int = 6) -> weights.W:
    """Row-standardised weights over ``geo`` (needs ``muni_code``, ``territory`` and geometry in metres).

    ``kind='queen'`` links municipalities sharing a border point; ``kind='knn'`` links the ``k`` nearest
    centroids. Links never cross territories. Asymmetric k-nearest links are kept as they are.
    """
    if geo.crs is None or geo.crs.to_epsg() != int(CRS_METRIC.split(":")[1]):
        raise ValueError(f"geometry must be in {CRS_METRIC} (metres)")
    neighbours: dict[str, list[str]] = {}
    for _, part in geo.groupby("territory"):
        neighbours |= _territory_neighbours(part.reset_index(drop=True), kind, k)
    w = weights.W(neighbours, silence_warnings=True)
    w.transform = "R"
    return w


def subset_weights(w: weights.W, ids: list[str]) -> weights.W:
    """Weights restricted to ``ids`` and re-standardised; a municipality left without neighbours is dropped."""
    with _disconnected_ok():
        sub = weights.w_subset(w, ids, silence_warnings=True)
        connected = [i for i in sub.id_order if sub.cardinalities[i] > 0]
        if len(connected) < len(sub.id_order):
            sub = weights.w_subset(sub, connected, silence_warnings=True)
    sub.transform = "R"
    return sub


def _aligned(values: pd.Series, w: weights.W) -> tuple[pd.Series, weights.W]:
    """Values with a value and weights restricted to them, in the weights' order."""
    valid = values.dropna()
    ids = [i for i in w.id_order if i in valid.index]
    sub = subset_weights(w, ids)
    return valid.loc[sub.id_order], sub


def global_moran(
    values: pd.Series, w: weights.W, permutations: int = 999, seed: int = 0
) -> dict[str, float]:
    """Global Moran's I of ``values`` (indexed by muni_code) with a permutation pseudo p-value.

    Returns ``I``, ``expected`` (-1/(n-1)), ``z_sim``, ``p_sim`` (two-sided) and ``n``.
    """
    y, sub = _aligned(values, w)
    np.random.seed(seed)  # esda draws its permutations from the global generator
    m = Moran(y.to_numpy(float), sub, permutations=permutations, two_tailed=True)
    return {"I": m.I, "expected": m.EI, "z_sim": m.z_sim, "p_sim": m.p_sim, "n": len(y)}


def local_moran(
    values: pd.Series, w: weights.W, permutations: int = 999, alpha: float = 0.05, seed: int = 0
) -> pd.DataFrame:
    """LISA (local Moran's I): ``local_i``, ``p_sim``, ``quadrant`` and ``cluster`` per municipality.

    ``cluster`` is the quadrant (HH, LL, LH, HL) where the pseudo p-value is below ``alpha``, else ``ns``.
    No multiple-testing correction is applied: with 300 tests, read clusters as exploratory.
    """
    y, sub = _aligned(values, w)
    lisa = Moran_Local(
        y.to_numpy(float),
        sub,
        permutations=permutations,
        seed=seed,
        n_jobs=1,
        alternative="two-sided",
    )
    out = pd.DataFrame(
        {
            "local_i": lisa.Is,
            "p_sim": lisa.p_sim,
            "quadrant": [QUADRANTS[q] for q in lisa.q],
        },
        index=pd.Index(sub.id_order, name=MUNI_KEY),
    )
    out["cluster"] = out["quadrant"].where(out["p_sim"] < alpha, "ns")
    return out


def getis_ord_gistar(
    values: pd.Series, w: weights.W, permutations: int = 999, alpha: float = 0.05, seed: int = 0
) -> pd.DataFrame:
    """Getis-Ord Gi* (the municipality counts in its own neighbourhood): ``z``, ``p_sim`` and ``hotspot``.

    ``hotspot`` is 'hot' or 'cold' where the pseudo p-value is below ``alpha`` (by the sign of ``z``), else 'ns'.
    """
    y, sub = _aligned(values, w)
    with _disconnected_ok():
        starred = weights.fill_diagonal(sub, 1.0)  # self counts as a neighbour
    g = G_Local(
        y.to_numpy(float),
        starred,
        transform="R",
        star=None,
        permutations=permutations,
        seed=seed,
        n_jobs=1,  # no worker processes: joblib would write memmaps to the C: temp folder
        alternative="two-sided",
    )
    out = pd.DataFrame({"z": g.Zs, "p_sim": g.p_sim}, index=pd.Index(sub.id_order, name=MUNI_KEY))
    out["hotspot"] = np.where(out["p_sim"] < alpha, np.where(out["z"] > 0, "hot", "cold"), "ns")
    return out


def moran_by_year(
    panel: pd.DataFrame, column: str, w: weights.W, years: list[int], permutations: int = 999
) -> pd.DataFrame:
    """Global Moran's I of ``column`` for each year, one row per year."""
    rows = []
    for year in years:
        values = panel.loc[panel["year"] == year].set_index(MUNI_KEY)[column]
        rows.append({"year": year, **global_moran(values, w, permutations)})
    return pd.DataFrame(rows)


def spatial_lag(values: pd.Series, w: weights.W) -> pd.Series:
    """Average of ``values`` over each municipality's neighbours (the spatial lag Wy), by ``muni_code``.

    Weights are row-standardised, so this is a weighted mean; a neighbour without a value is left out and
    the remaining weights are re-scaled. A municipality with no neighbour holding a value gets NaN.
    """
    ids = list(w.id_order)
    sparse = w.sparse.tocsr()
    y = values.reindex(ids).to_numpy(dtype=float)
    known = ~np.isnan(y)
    numerator = sparse @ np.where(known, y, 0.0)
    weight_sum = sparse @ known.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        lag = np.where(weight_sum > 0, numerator / weight_sum, np.nan)
    return pd.Series(lag, index=pd.Index(ids, name=MUNI_KEY), name=values.name)
