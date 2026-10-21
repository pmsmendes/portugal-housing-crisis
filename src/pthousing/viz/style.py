"""Shared plot style and the one function used to save figures."""

from pathlib import Path

from matplotlib.figure import Figure

from pthousing.config import FIGURES, PHASES


def save_fig(fig: Figure, phase: str, name: str) -> Path:
    """Save a figure to reports/figures/<phase>/<name>.png and return the path."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    path = FIGURES / phase / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    return path
