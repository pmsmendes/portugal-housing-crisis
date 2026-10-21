"""Shared plot style and the functions used to save figures and tables.

Colors follow the validated reference palette of the dataviz method: two categorical accents (blue,
orange; worst colorblind separation dE 24.7), gray for context, a one-hue blue ramp for magnitude and a
blue-red ramp with a gray midpoint for change. Text always wears ink tokens, never a series color.
"""

from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from pthousing.config import FIGURES, PHASES, TABLES

# ---- tokens (light surface) -----------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"  # titles, values
INK_2 = "#52514e"  # subtitles, labels, legend text
MUTED = "#898781"  # axis text, context lines
GRID = "#e1e0d9"  # hairline grid
BASELINE = "#c3c2b7"  # baseline / axes
NEUTRAL = "#f0efec"  # diverging midpoint

BLUE = "#2a78d6"  # categorical slot 1: the accent
ORANGE = "#eb6834"  # categorical slot 2
LINE_WIDTH = 2.0
CONTEXT_WIDTH = 1.0

# sequential ramp (blue steps 100-700) and the steps used for six-class maps, light -> dark
BLUE_RAMP = {
    100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef", 300: "#6da7ec", 350: "#5598e7",
    400: "#3987e5", 450: "#2a78d6", 500: "#256abf", 550: "#1c5cab", 600: "#184f95", 650: "#104281",
    700: "#0d366b",
}  # fmt: skip
SEQUENTIAL_6 = [BLUE_RAMP[s] for s in (100, 200, 300, 400, 550, 700)]
RED_REFERENCE = "#e34948"  # categorical red: hue of the warm arm of the diverging ramp
NO_DATA = GRID  # fill of areas without a published value (drawn with a 45 degree hatch)


# ---- OKLab helpers (to build a warm arm with the same lightness as the cool arm) ------------------


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hex_to_oklch(hex_color: str) -> tuple[float, float, float]:
    """OKLCH (lightness 0-1, chroma, hue in degrees) of an sRGB hex color."""
    rgb = _srgb_to_linear(np.array([int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]) / 255)
    l_, m_, s_ = np.cbrt(
        [
            0.4122214708 * rgb[0] + 0.5363325363 * rgb[1] + 0.0514459929 * rgb[2],
            0.2119034982 * rgb[0] + 0.6806995451 * rgb[1] + 0.1073969566 * rgb[2],
            0.0883024619 * rgb[0] + 0.2817188376 * rgb[1] + 0.6299787005 * rgb[2],
        ]
    )
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return float(lightness), float(np.hypot(a, b)), float(np.degrees(np.arctan2(b, a)) % 360)


def oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    """sRGB hex of an OKLCH color; chroma is reduced until the color fits the sRGB gamut."""
    for c in np.linspace(chroma, 0, 200):
        a, b = c * np.cos(np.radians(hue)), c * np.sin(np.radians(hue))
        l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
        m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
        s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
        cone_l, cone_m, cone_s = l_**3, m_**3, s_**3
        rgb = np.array(
            [
                4.0767416621 * cone_l - 3.3077115913 * cone_m + 0.2309699292 * cone_s,
                -1.2684380046 * cone_l + 2.6097574011 * cone_m - 0.3413193965 * cone_s,
                -0.0041960863 * cone_l - 0.7034186147 * cone_m + 1.7076147010 * cone_s,
            ]
        )
        if ((rgb >= -1e-4) & (rgb <= 1 + 1e-4)).all():
            out = np.clip(_linear_to_srgb(np.clip(rgb, 0, 1)), 0, 1)
            return "#" + "".join(f"{round(v * 255):02x}" for v in out)
    raise ValueError("no in-gamut color found")


def diverging_ramp(steps: int = 3) -> list[str]:
    """Blue (negative) -> gray midpoint -> red (positive), ``steps`` classes per arm, ``2 * steps`` colors.

    The cool arm uses blue ramp steps; the warm arm takes the hue of the categorical red at the same
    lightness and chroma as each cool step, so both arms have equal visual weight.
    """
    cool = {3: (150, 350, 550), 2: (250, 500)}[steps]
    cool_hex = [BLUE_RAMP[s] for s in cool]
    warm_hex = []
    hue = hex_to_oklch(RED_REFERENCE)[2]
    for h in cool_hex:
        lightness, chroma, _ = hex_to_oklch(h)
        warm_hex.append(oklch_to_hex(lightness, chroma, hue))
    return (
        cool_hex[::-1] + warm_hex
    )  # darkest blue ... lightest blue | lightest red ... darkest red


# ---- matplotlib style -----------------------------------------------------------------------------


def apply_style() -> None:
    """Set the project's matplotlib defaults (light surface, hairline grid, thin marks)."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": ["Segoe UI", "DejaVu Sans"],
            "font.size": 9.5,
            "text.color": INK_2,
            "axes.edgecolor": BASELINE,
            "axes.labelcolor": MUTED,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "lines.linewidth": LINE_WIDTH,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "legend.frameon": False,
            "legend.labelcolor": INK_2,
            "figure.dpi": 100,
        }
    )


def finish(
    fig: Figure,
    title: str,
    subtitle: str | None = None,
    source: str | None = None,
    head_in: float = 1.0,
    foot_in: float = 0.7,
) -> Figure:
    """Reserve room for the heading and footnote (in inches) and write them.

    The title states the takeaway; the subtitle says what is plotted and in which unit; the source line
    sits at the bottom. Axes are laid out between the two.
    """
    height = fig.get_figheight()
    fig.subplots_adjust(top=1 - head_in / height, bottom=foot_in / height)
    fig.text(
        0.0,
        1 - 0.12 / height,
        title,
        ha="left",
        va="top",
        fontsize=14.5,
        fontweight="bold",
        color=INK,
    )
    if subtitle:
        fig.text(0.0, 1 - 0.50 / height, subtitle, ha="left", va="top", fontsize=10, color=INK_2)
    if source:
        fig.text(0.0, 0.08 / height, source, ha="left", va="bottom", fontsize=8, color=MUTED)
    return fig


# ---- saving ---------------------------------------------------------------------------------------


def save_fig(fig: Figure, phase: str, name: str) -> Path:
    """Save a figure to reports/figures/<phase>/<name>.png and return the path."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    path = FIGURES / phase / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    return path


def save_table(df: pd.DataFrame, phase: str, name: str) -> Path:
    """Save a table to reports/tables/<phase>/<name>.csv (the table twin of a figure) and return the path."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    path = TABLES / phase / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path
