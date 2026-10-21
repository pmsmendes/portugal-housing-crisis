"""Municipality choropleths and cluster/hotspot maps.

Maps are drawn in lon/lat with the aspect corrected for latitude; the Azores and Madeira are insets.
Classes are fixed breaks (comparable between years and indicators of the same unit), colored with a
one-hue ramp for levels or the blue-red ramp for changes. Municipalities without a published value are
hatched, never colored as zero.
"""

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from pthousing.config import CRS_WEB, MUNI_KEY
from pthousing.data import interim
from pthousing.viz import style
from pthousing.viz.style import BASELINE, INK_2, MUTED, NO_DATA, SURFACE

# (lon_min, lon_max, lat_min, lat_max) of each map frame; Madeira leaves out the remote Selvagens islands
FRAMES = {
    "continente": (-9.7, -6.1, 36.85, 42.2),
    "azores": (-31.4, -24.9, 36.85, 39.85),
    "madeira": (-17.4, -16.15, 32.55, 33.2),
}
# inset positions (left, bottom, width, height) in figure coordinates, below the 1 inch heading
LAYOUT = {
    "continente": (0.36, 0.07, 0.62, 0.79),
    "azores": (0.0, 0.60, 0.36, 0.22),
    "madeira": (0.0, 0.45, 0.25, 0.13),
}


def municipality_geometry(simplify_m: float = 150.0) -> gpd.GeoDataFrame:
    """CAOP municipalities (``muni_code``, ``muni_name``, ``territory``, geometry) in lon/lat, simplified."""
    geo = interim.read("caop_municipalities")[
        [MUNI_KEY, "muni_name", "territory", "geometry"]
    ].copy()
    geo["geometry"] = geo.geometry.simplify(simplify_m)  # metres, while still in the projected CRS
    return geo.to_crs(CRS_WEB)


def classify(values: pd.Series, breaks: list[float]) -> pd.Series:
    """Class index 0..len(breaks) of each value (class i holds breaks[i-1] <= v < breaks[i]); -1 if missing."""
    idx = np.digitize(values.to_numpy(dtype=float), breaks)
    return pd.Series(np.where(values.isna(), -1, idx), index=values.index)


def class_labels(breaks: list[float], fmt: str = "{:g}", suffix: str = "") -> list[str]:
    """Legend labels: '< b0', 'b0 to b1', ..., '≥ b_last'."""
    f = [fmt.format(b) + suffix for b in breaks]
    return [f"< {f[0]}", *[f"{f[i]} to {f[i + 1]}" for i in range(len(f) - 1)], f"≥ {f[-1]}"]


def _draw(
    ax: Axes, geo: gpd.GeoDataFrame, classes: pd.Series, colors: list[str], frame: tuple
) -> None:
    known = geo[classes.loc[geo.index] >= 0]
    for cls, group in known.groupby(classes.loc[known.index]):
        group.plot(ax=ax, color=colors[int(cls)], edgecolor=SURFACE, linewidth=0.3)
    missing = geo[classes.loc[geo.index] < 0]
    if len(missing):
        missing.plot(ax=ax, facecolor=NO_DATA, edgecolor=MUTED, hatch="//////", linewidth=0.2)
    lon0, lon1, lat0, lat1 = frame
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(1 / np.cos(np.deg2rad((lat0 + lat1) / 2)))
    ax.set_axis_off()


def choropleth(
    values: pd.Series,
    geometry: gpd.GeoDataFrame,
    breaks: list[float],
    colors: list[str],
    title: str,
    subtitle: str,
    source: str,
    legend_title: str,
    fmt: str = "{:g}",
    suffix: str = "",
) -> Figure:
    """Map of ``values`` (indexed by muni_code) in classes given by ``breaks`` and ``colors``.

    ``colors`` must have ``len(breaks) + 1`` entries (light to dark, or blue to red for a change).
    The legend shows how many municipalities fall in each class and how many have no published value.
    """
    if len(colors) != len(breaks) + 1:
        raise ValueError("need one color per class: len(colors) == len(breaks) + 1")
    geo = geometry.set_index(MUNI_KEY)
    classes = classify(values.reindex(geo.index), breaks)
    with mpl.rc_context({"hatch.linewidth": 0.4}):
        fig = plt.figure(figsize=(7.2, 8.6))
        for territory, (left, bottom, width, height) in LAYOUT.items():
            ax = fig.add_axes((left, bottom, width, height))
            _draw(ax, geo[geo["territory"] == territory], classes, colors, FRAMES[territory])
            if territory != "continente":
                ax.text(
                    0.02,
                    0.02,
                    territory.capitalize(),
                    transform=ax.transAxes,
                    fontsize=9,
                    color=MUTED,
                )
    counts = classes.value_counts()
    labels = class_labels(breaks, fmt, suffix)
    handles = [
        Patch(facecolor=c, edgecolor=SURFACE, label=f"{lab}   ({counts.get(i, 0)})")
        for i, (c, lab) in enumerate(zip(colors, labels, strict=True))
    ]
    if (classes < 0).any():
        handles.append(
            Patch(
                facecolor=NO_DATA,
                edgecolor=BASELINE,
                hatch="//////",
                label=f"Not published   ({int((classes < 0).sum())})",
            )
        )
    legend = fig.legend(
        handles=handles, title=legend_title, loc="lower left", bbox_to_anchor=(0.0, 0.02), fontsize=9,
        title_fontsize=9.5, handlelength=1.6, handleheight=1.1, labelcolor=INK_2, alignment="left",
    )  # fmt: skip
    legend.get_title().set_color(INK_2)
    legend.get_title().set_fontweight("bold")
    style.finish(fig, title, subtitle, source, head_in=1.0, foot_in=0.45)
    return fig
