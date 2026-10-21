import geopandas as gpd
import matplotlib
import pandas as pd
import pytest
from shapely.geometry import box

matplotlib.use("Agg")

from pthousing.viz import maps, style  # noqa: E402


def test_classify_uses_half_open_classes_and_flags_missing():
    values = pd.Series([1.0, 6.0, 7.9, 8.0, 25.0, None], index=list("abcdef"))
    assert maps.classify(values, [6, 8, 10, 15, 20]).tolist() == [0, 1, 1, 2, 5, -1]


def test_class_labels_cover_every_class():
    assert maps.class_labels([6, 8, 10]) == ["< 6", "6 to 8", "8 to 10", "≥ 10"]
    assert maps.class_labels([40, 60], suffix="%") == ["< 40%", "40% to 60%", "≥ 60%"]


def _geometry():
    return gpd.GeoDataFrame(
        {
            "muni_code": ["0101", "3101", "4201", "0102"],
            "muni_name": list("ABCD"),
            "territory": ["continente", "madeira", "azores", "continente"],
        },
        geometry=[box(-8, 40, -7.5, 40.5), box(-17, 32.7, -16.8, 32.9), box(-28, 38, -27.5, 38.5), box(-8, 39, -7.5, 39.5)],
        crs="EPSG:4326",
    )  # fmt: skip


def test_choropleth_counts_classes_and_marks_missing_in_the_legend():
    values = pd.Series({"0101": 3.0, "3101": 12.0, "4201": 30.0, "0102": None})
    fig = maps.choropleth(
        values, _geometry(), [6, 10, 20], style.SEQUENTIAL_6[:4], "t", "s", "src", "Years"
    )
    legend = fig.legends[0]
    labels = [t.get_text() for t in legend.get_texts()]
    assert labels[0].startswith("< 6") and labels[0].endswith("(1)")
    assert labels[-1] == "Not published   (1)"
    assert sum(int(lab.rsplit("(", 1)[1].rstrip(")")) for lab in labels) == 4
    assert len(fig.axes) == 3  # mainland and two island insets


def test_choropleth_needs_one_color_per_class():
    with pytest.raises(ValueError, match="one color per class"):
        maps.choropleth(
            pd.Series({"0101": 1.0}), _geometry(), [6, 10], ["#000000"], "t", "s", "src", "Years"
        )
