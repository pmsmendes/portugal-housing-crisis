"""Time-series, scatter, coefficient, correlation and forecast-fan charts.

Every figure function takes prepared tables (see ``analysis/descriptive.py``) and returns a finished
``Figure``: takeaway title computed from the plotted data, unit subtitle, source note. Style rules:
one axis per panel, thin marks, a legend whenever there are two or more series, direct labels only on
the story lines, text in ink tokens.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from pthousing.viz import style
from pthousing.viz.style import BLUE, GRID, INK, INK_2, LINE_WIDTH, MUTED, ORANGE, SURFACE

PEER_COLUMNS = {
    "hpi_de_b2015": "Germany",
    "hpi_es_b2015": "Spain",
    "hpi_fr_b2015": "France",
    "hpi_ie_b2015": "Ireland",
    "hpi_it_b2015": "Italy",
}


# ---- primitives -----------------------------------------------------------------------------------


def _line(
    ax: Axes, x, y, color: str, label: str | None = None, width: float = LINE_WIDTH, z: int = 3
):
    return ax.plot(x, y, color=color, lw=width, label=label, zorder=z, solid_capstyle="round")[0]


def _end_dot(ax: Axes, x, y, color: str) -> None:
    """Marker of at least 8 px with a 2 px surface ring so it stays legible over the line."""
    ax.plot([x], [y], "o", ms=8, mfc=color, mec=SURFACE, mew=2, zorder=6, clip_on=False)


def _label(
    ax: Axes, x, y, text: str, dx: float = 8, va: str = "center", weight: str = "bold"
) -> None:
    ax.annotate(
        text, (x, y), xytext=(dx, 0), textcoords="offset points", va=va, ha="left",
        fontsize=9.5, color=INK, fontweight=weight, annotation_clip=False,
    )  # fmt: skip


def _panel_title(ax: Axes, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=10.5, color=INK_2, fontweight="bold", pad=10)


def _quarter_axis(ax: Axes, dates: pd.Series, base: int = 3) -> None:
    """Year ticks every ``base`` years (multiples of ``base``), none beyond the last date."""
    first, last = dates.min().year, dates.max().year
    ticks = [pd.Timestamp(y, 1, 1) for y in range(first + (-first % base), last + 1, base)]
    ax.set_xticks(ticks, [str(t.year) for t in ticks])
    ax.margins(x=0.01)


def _thousands(ax: Axes, prefix: str = "") -> None:
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{prefix}{v:,.0f}"))


def _legend(ax: Axes, handles: list, loc: str = "upper left") -> None:
    ax.legend(
        handles=handles, loc=loc, fontsize=9, handlelength=1.8, borderaxespad=0.2, labelcolor=INK_2
    )


def _fan(ax: Axes, years, lo, mid, hi, color: str = BLUE) -> None:
    ax.fill_between(years, lo, hi, color=color, alpha=0.10, lw=0, zorder=1)
    _line(ax, years, mid, color)


def _years(ax: Axes, years) -> None:
    ax.set_xticks(list(years))
    ax.margins(x=0.03)


# ---- national price index -------------------------------------------------------------------------


def hpi_real_vs_nominal(nat: pd.DataFrame) -> Figure:
    """Portugal's house price index, nominal and deflated, from ``national_quarterly``."""
    d = nat.dropna(subset=["hpi_total_b2025"])
    real = d.set_index("period_start")["hpi_total_real_b2025"]
    low_date, low = real.idxmin(), real.min()
    ratio = real.iloc[-1] / low
    fig, ax = plt.subplots(figsize=(8, 4.8))
    _line(ax, d["period_start"], d["hpi_total_b2025"], MUTED, "Nominal")
    _line(ax, d["period_start"], d["hpi_total_real_b2025"], BLUE, "Real (constant 2024 euros)", z=4)
    for col, color in (("hpi_total_b2025", MUTED), ("hpi_total_real_b2025", BLUE)):
        _end_dot(ax, d["period_start"].iloc[-1], d[col].iloc[-1], color)
    _quarter_axis(ax, d["period_start"], base=2)
    ax.set_ylim(bottom=0)
    _legend(ax, [Line2D([], [], color=MUTED, lw=LINE_WIDTH, label="Nominal"),
                 Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Real (constant 2024 euros)")])  # fmt: skip
    return style.finish(
        fig,
        f"After inflation, house prices fell until {low_date.year} and have since risen {ratio:.1f}x",
        "INE house price index, all dwellings (2025 = 100), quarterly; real = deflated with the consumer price index",
        "Source: INE (house price index, CPI); own calculations.",
    )


def hpi_peers(nat: pd.DataFrame) -> Figure:
    """Eurostat house price index (2015 = 100): Portugal against the EU27 and five peers."""
    d = nat.set_index("period_start")
    last = d.index[-1]
    pt, eu = d["hpi_pt_b2015"].dropna(), d["hpi_eu27_b2015"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for col in PEER_COLUMNS:
        _line(ax, d.index, d[col], MUTED, width=1.0, z=2)
    _line(ax, d.index, d["hpi_eu27_b2015"], ORANGE, z=3)
    _line(ax, pt.index, pt, BLUE, z=4)
    _end_dot(ax, last, pt.iloc[-1], BLUE)
    _end_dot(ax, last, eu.iloc[-1], ORANGE)
    _label(ax, last, pt.iloc[-1], f"Portugal {pt.iloc[-1]:.0f}")
    _label(ax, last, eu.iloc[-1], f"EU27 {eu.iloc[-1]:.0f}")
    _quarter_axis(ax, d.index.to_series(), base=3)
    ax.set_xlim(right=last + pd.Timedelta(days=900))
    ax.set_ylim(bottom=0)
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Portugal"),
                 Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="EU27"),
                 Line2D([], [], color=MUTED, lw=1.0, label="Germany, Spain, France, Ireland, Italy")])  # fmt: skip
    return style.finish(
        fig,
        f"Portugal's house prices are {pt.iloc[-1] / 100:.1f}x their 2015 level; the EU's, {eu.iloc[-1] / 100:.1f}x",
        "Eurostat house price index, all dwellings purchased (2015 = 100), nominal, quarterly",
        "Source: Eurostat (prc_hpi_q). Portugal's series starts in 2008.",
    )


# ---- municipal prices and rents -------------------------------------------------------------------


def price_fan(
    fan: pd.DataFrame, highlight: pd.Series, highlight_name: str, n_range: tuple[int, int]
) -> Figure:
    """Real price per m2 across municipalities (10th-90th percentile band and median) and one municipality."""
    years = fan.index
    growth = 100 * (fan["q50"].iloc[-1] / fan["q50"].iloc[0] - 1)
    multiple = highlight.iloc[-1] / fan["q50"].iloc[-1]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    _fan(ax, years, fan["q10"], fan["q50"], fan["q90"])
    _line(ax, highlight.index, highlight, ORANGE, z=4)
    _end_dot(ax, years[-1], fan["q50"].iloc[-1], BLUE)
    _end_dot(ax, years[-1], highlight.iloc[-1], ORANGE)
    _label(ax, years[-1], highlight.iloc[-1], f"{highlight_name} {highlight.iloc[-1]:,.0f}")
    _label(ax, years[-1], fan["q50"].iloc[-1], f"Median {fan['q50'].iloc[-1]:,.0f}")
    _years(ax, years)
    ax.set_xlim(right=years[-1] + 1.6)
    ax.set_ylim(bottom=0)
    _thousands(ax)
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Median municipality"),
                 Patch(facecolor=BLUE, alpha=0.18, label="10th to 90th percentile of municipalities"),
                 Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label=highlight_name)])  # fmt: skip
    return style.finish(
        fig,
        f"Real prices per m2 rose {growth:.0f}% in the median municipality; {highlight_name} costs {multiple:.1f}x the median",
        "Median sale price per m2 (last 12 months, year end), constant 2024 euros",
        f"Source: INE (house prices at local level, AT data), CPI; own calculations. {n_range[0]}-{n_range[1]} municipalities per year.",
    )


def real_growth_index(index: pd.DataFrame, n: int, base_year: int) -> Figure:
    """Real price and rent per m2 indexed to ``base_year`` = 100, median of a fixed set of municipalities.

    The two series end close together, so the lines are identified by the legend, not by end labels.
    """
    years = index.index
    price, rent = index["price"], index["rent"]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    _line(ax, years, price, BLUE)
    _line(ax, years, rent, ORANGE)
    _end_dot(ax, years[-1], price.iloc[-1], BLUE)
    _end_dot(ax, years[-1], rent.iloc[-1], ORANGE)
    _years(ax, years)
    ax.set_ylim(min(price.min(), rent.min(), 100) - 3, max(price.max(), rent.max()) + 4)
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Sale price per m2"),
                 Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Rent per m2 (new leases)")])  # fmt: skip
    total_p, total_r = price.iloc[-1] - 100, rent.iloc[-1] - 100
    recent_p = 100 * (price.iloc[-1] / price.iloc[-3] - 1)
    recent_r = 100 * (rent.iloc[-1] / rent.iloc[-3] - 1)
    if abs(total_p - total_r) < 2:
        head = f"Real prices and rents both rose about {(total_p + total_r) / 2:.0f}% since {base_year}"
    else:
        head = f"Since {base_year}, real rents rose {total_r:.0f}% and real prices {total_p:.0f}%"
    faster = "rents" if recent_r > recent_p else "prices"
    return style.finish(
        fig,
        f"{head}; over the last two years {faster} rose faster ({max(recent_r, recent_p):.0f}% vs {min(recent_r, recent_p):.0f}%)",
        f"Median across {n} municipalities with both series every year; constant 2024 euros, {base_year} = 100",
        "Source: INE (house prices and rents at local level), CPI; own calculations.",
    )


# ---- mortgage rates -------------------------------------------------------------------------------


def mortgage_rates(nat: pd.DataFrame) -> Figure:
    """Rates on housing loans (left) and the monthly payment on a 100,000 EUR loan (right)."""
    d = nat.set_index("period_start")
    rate = d["mortgage_rate_new_lt1y_pct"].dropna()
    trough = rate.idxmin()
    peak = rate.loc[trough:].max()
    pay = d["mortgage_payment_100k_eur"].dropna()
    rise = 100 * (pay.loc[rate.loc[trough:].idxmax()] / pay.loc[trough] - 1)
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    _line(left, d.index, d["mortgage_rate_stock_gt5y_pct"], MUTED, width=1.0, z=2)
    _line(left, d.index, d["mortgage_aprc_new_pct"], ORANGE, z=3)
    _line(left, d.index, d["mortgage_rate_new_lt1y_pct"], BLUE, z=4)
    left.set_ylim(0, 7.6)  # headroom for the legend
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _quarter_axis(left, d.index.to_series(), base=4)
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="New loans, agreed rate"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="New loans, APRC (includes fees)"),
                   Line2D([], [], color=MUTED, lw=1.0, label="Outstanding loans over 5 years")], loc="upper center")  # fmt: skip
    _panel_title(left, "Interest rates on housing loans")
    _line(right, pay.index, pay, BLUE)
    _end_dot(right, pay.index[-1], pay.iloc[-1], BLUE)
    _label(right, pay.index[-1], pay.iloc[-1], f"{pay.iloc[-1]:.0f}")
    right.set_xlim(right=pay.index[-1] + pd.Timedelta(days=500))
    _quarter_axis(right, pay.index.to_series(), base=4)
    right.set_ylim(bottom=0)
    _thousands(right)
    _panel_title(right, "Monthly payment on a 100,000 EUR loan over 30 years (EUR)")
    return style.finish(
        fig,
        f"Rates fell to {rate.min():.1f}% in {trough.year} and rose to {peak:.1f}%: the same loan costs {rise:.0f}% more a month",
        "Quarterly averages. Payment computed at the agreed rate on new loans (floating, initial fixation up to one year)",
        "Source: Banco de Portugal (BPstat); own calculations.",
    )


# ---- affordability indicators ---------------------------------------------------------------------


def indicator_trends(panels: list[dict]) -> Figure:
    """One panel per indicator: median across municipalities with the 10th-90th percentile band.

    Each dict has ``title``, ``fan`` (columns q10, q50, q90, n), ``unit_fmt`` (format string for the end
    label) and optionally ``ymax`` and ``step`` (spacing of the year ticks).
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 4.4))
    for ax, spec in zip(axes, panels, strict=True):
        fan = spec["fan"]
        _fan(ax, fan.index, fan["q10"], fan["q50"], fan["q90"])
        _end_dot(ax, fan.index[-1], fan["q50"].iloc[-1], BLUE)
        _label(
            ax,
            fan.index[-1],
            fan["q50"].iloc[-1],
            spec["unit_fmt"].format(fan["q50"].iloc[-1]),
            dx=7,
        )
        ax.set_ylim(0, spec.get("ymax", fan["q90"].max() * 1.25))
        _years(ax, fan.index[:: spec.get("step", 2)])
        ax.set_xlim(fan.index[0] - 0.4, fan.index[-1] + 1.8)
        _panel_title(ax, spec["title"])
    pti = panels[0]["fan"]  # the first panel is price-to-income: it carries the headline
    return style.finish(
        fig,
        f"The median municipality needs {pti['q50'].iloc[-1]:.1f} years of income to buy ({pti['q50'].iloc[0]:.1f} in {pti.index[0]}); at the 90th percentile, {pti['q90'].iloc[-1]:.0f}",
        "Median across municipalities (line) and 10th to 90th percentile (band); ratios to median income per tax household",
        "Source: INE, Banco de Portugal; own calculations. Levels depend on the income concept and dwelling size; read changes and rankings.",
        foot_in=0.75,
    )


def burden_rate_effect(
    actual: pd.Series, fixed: pd.Series, rate_year: int, rates: pd.Series
) -> Figure:
    """Median mortgage burden as observed and with the mortgage rate held at its ``rate_year`` level."""
    years = actual.index
    gap = actual.iloc[-1] - fixed.iloc[-1]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _line(ax, years, fixed, MUTED, z=3)
    _line(ax, years, actual, BLUE, z=4)
    for series, color, text in (
        (actual, BLUE, "As observed"),
        (fixed, MUTED, f"Rate fixed at {rate_year} level"),
    ):
        _end_dot(ax, years[-1], series.iloc[-1], color)
        _label(ax, years[-1], series.iloc[-1], f"{series.iloc[-1]:.0f}%  {text}", dx=8)
    _years(ax, years)
    ax.set_xlim(years[0] - 0.4, years[-1] + 4.8)
    ax.set_ylim(0, max(actual.max(), fixed.max()) * 1.18)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Mortgage burden as observed"),
                 Line2D([], [], color=MUTED, lw=LINE_WIDTH, label=f"Same prices and incomes, rate fixed at its {rate_year} level ({rates[rate_year]:.1f}%)")])  # fmt: skip
    return style.finish(
        fig,
        f"Rising rates account for {gap:.0f} of the {actual.iloc[-1] - actual.iloc[0]:.0f}-point rise in the mortgage burden since {years[0]}",
        "Median across municipalities of yearly loan payments (80% loan, 30 years) as a share of median income per tax household",
        "Source: INE, Banco de Portugal; own calculations. Rate: agreed rate on new housing loans (annual mean).",
    )


def pti_dumbbell(rank: pd.DataFrame, start_year: int, end_year: int) -> Figure:
    """Price-to-income in two years for the least affordable municipalities (one hue, two shades)."""
    r = rank.iloc[::-1].reset_index(drop=True)
    light, dark = style.BLUE_RAMP[250], style.BLUE_RAMP[550]
    fig, ax = plt.subplots(figsize=(7.6, 0.34 * len(r) + 2.0))
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    for i, row in r.iterrows():
        ax.plot(
            [row["start"], row["end"]], [i, i], color=GRID, lw=3, zorder=1, solid_capstyle="round"
        )
        ax.plot([row["start"]], [i], "o", ms=8, mfc=light, mec=SURFACE, mew=2, zorder=3)
        ax.plot([row["end"]], [i], "o", ms=8, mfc=dark, mec=SURFACE, mew=2, zorder=4)
        ax.annotate(f"{row['end']:.0f}", (row["end"], i), xytext=(9, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK_2)  # fmt: skip
    ax.set_yticks(range(len(r)), r["muni_name"], color=INK_2, fontsize=9.5)
    ax.set_xlim(0, r[["start", "end"]].to_numpy().max() * 1.1)
    ax.set_ylim(-0.7, len(r) - 0.3)
    ax.spines["bottom"].set_visible(False)
    _legend(ax, [Line2D([], [], marker="o", ls="", ms=8, mfc=light, mec=SURFACE, label=str(start_year)),
                 Line2D([], [], marker="o", ls="", ms=8, mfc=dark, mec=SURFACE, label=str(end_year))], loc="lower right")  # fmt: skip
    top = r.iloc[-1]
    return style.finish(
        fig,
        f"In {top['muni_name']} a typical home now costs {top['end']:.0f} years of income",
        f"Price-to-income in {start_year} and {end_year}: the {len(r)} least affordable municipalities in {end_year} (years of median income)",
        "Source: INE; own calculations. Price of a home of the municipality's average size.",
        foot_in=0.8,
    )
