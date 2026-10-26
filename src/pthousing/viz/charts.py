"""Time-series, scatter, coefficient, correlation and forecast-fan charts.

Every figure function takes prepared tables (see ``analysis/descriptive.py``) and returns a finished
``Figure``: takeaway title computed from the plotted data, unit subtitle, source note. Style rules:
one axis per panel, thin marks, a legend whenever there are two or more series, direct labels only on
the story lines, text in ink tokens.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from pthousing.viz import style
from pthousing.viz.style import (
    BLUE,
    CONTEXT_WIDTH,
    GRID,
    INK,
    INK_2,
    LINE_WIDTH,
    MUTED,
    ORANGE,
    SURFACE,
)

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


# ---- spatial autocorrelation ----------------------------------------------------------------------


def moran_trends(table: pd.DataFrame, weights_note: str) -> Figure:
    """Global Moran's I by year for price-to-income (story), median income (contrast) and price per m2.

    ``table`` has columns ``year``, ``series`` ('pti', 'income', 'price'), ``I`` and ``p_sim``.
    """
    wide = table.pivot(index="year", columns="series", values="I")
    years = wide.index
    fig, ax = plt.subplots(figsize=(8, 4.4))
    _line(ax, years, wide["price"], MUTED, width=CONTEXT_WIDTH, z=2)
    _line(ax, years, wide["income"], ORANGE)
    _line(ax, years, wide["pti"], BLUE)
    for name, color in (("pti", BLUE), ("income", ORANGE)):
        _end_dot(ax, years[-1], wide[name].iloc[-1], color)
    _label(ax, years[-1], wide["pti"].iloc[-1], "Price-to-income")
    _label(ax, years[-1], wide["income"].iloc[-1], "Median income")
    ax.annotate(  # nearly on top of the price-to-income end: set it below
        "Price per m2", (years[-1], wide["price"].iloc[-1]), xytext=(8, -12),
        textcoords="offset points", va="center", ha="left", fontsize=9.5, color=INK_2,
        annotation_clip=False,
    )  # fmt: skip
    _years(ax, years)
    ax.set_ylim(0.4, 0.9)
    ax.set_ylabel("Moran's I", color=INK_2)
    first, last = years[0], years[-1]
    rose = wide["pti"].iloc[-1] > wide["pti"].iloc[0]
    p_max = table["p_sim"].max()
    return style.finish(
        fig,
        f"Neighbouring municipalities {'resemble' if rose else 'differ from'} each other "
        f"{'more' if rose else 'less'} on affordability: Moran's I of price-to-income "
        f"{'rose' if rose else 'fell'} from {wide['pti'].iloc[0]:.2f} to {wide['pti'].iloc[-1]:.2f}",
        f"Global Moran's I of price-to-income, median income and price per m2, {first} to {last}; "
        f"0 = no spatial pattern, 1 = neighbours alike. {weights_note}",
        f"Source: INE, CAOP 2024; own calculations. Largest permutation p-value across points: {p_max:.3f}.",
    )


# ---- supply and demand ----------------------------------------------------------------------------


def construction_flows(flows: pd.DataFrame) -> Figure:
    """New family dwellings licensed and completed per year in Portugal (thousands).

    ``flows`` is indexed by year with columns ``licensed_n`` and ``completed_n``.
    """
    years = flows.index
    done = flows["completed_n"] / 1000
    peak_year = done.idxmax()
    low_year = done.loc[peak_year:].idxmin()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _line(ax, years, flows["licensed_n"] / 1000, MUTED)
    _line(ax, years, done, BLUE, z=4)
    for series, color in ((flows["licensed_n"] / 1000, MUTED), (done, BLUE)):
        _end_dot(ax, years[-1], series.iloc[-1], color)
    _label(ax, years[-1], done.iloc[-1], f"{done.iloc[-1]:.0f}k completed")
    _label(
        ax,
        years[-1],
        flows["licensed_n"].iloc[-1] / 1000,
        f"{flows['licensed_n'].iloc[-1] / 1000:.0f}k licensed",
    )
    ax.set_xticks(range(years[0] + (-years[0] % 5), years[-1] + 1, 5))
    ax.set_xlim(years[0] - 0.5, years[-1] + 6.5)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.01)
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Dwellings completed"),
                 Line2D([], [], color=MUTED, lw=LINE_WIDTH, label="Dwellings licensed")], loc="upper right")  # fmt: skip
    return style.finish(
        fig,
        f"Completions fell from {done.loc[peak_year]:.0f}k in {peak_year} to {done.loc[low_year]:.0f}k in {low_year} "
        f"and are back to {done.iloc[-1]:.0f}k",
        "New family dwellings licensed and completed per year, thousands, all municipalities",
        "Source: INE (building licences and completions). New construction only: renovation, demolition and conversion are not counted.",
    )


def housing_balance_by_area(
    census: pd.Series, after: pd.Series, headline: dict[str, float]
) -> Figure:
    """Dwellings added minus households added, per 1,000 households, by area: census decade and since 2021.

    ``census`` (2011 to 2021, observed) and ``after`` (2021 to 2023, implied from population) are indexed by
    area name; the areas are sorted by ``census``. Negative bars (orange) are areas where construction fell
    short of new households. ``headline`` has the national ``census`` and ``after`` values for the title.
    """
    order = census.sort_values().index
    census, after = census.reindex(order), after.reindex(order)
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.28 * len(order) + 2.0), sharey=True)
    for ax, series, title in (
        (axes[0], census, "2011 to 2021 (census: dwellings and households counted)"),
        (axes[1], after, "2021 to 2023 (implied: population / persons per household)"),
    ):
        colors = [ORANGE if v < 0 else BLUE for v in series]
        ax.barh(range(len(series)), series.to_numpy(), color=colors, height=0.68, zorder=3)
        ax.axvline(0, color=INK_2, lw=1, zorder=4)
        ax.set_yticks(range(len(series)), series.index)
        ax.set_ylim(len(series) - 0.4, -0.6)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", visible=False)
        lo, hi = series.min(), series.max()
        pad = 0.08 * (hi - lo)
        ax.set_xlim(min(lo, 0) - pad, max(hi, 0) + pad)
        _panel_title(ax, title)
    n_short, n_short_after = int((census < 0).sum()), int((after < 0).sum())
    return style.finish(
        fig,
        f"Construction fell short of new households in {n_short_after} of {len(after)} areas since 2021, "
        f"against {n_short} of {len(census)} between the censuses",
        "Dwellings added minus households added, per 1,000 households at the start. Orange: fewer new dwellings than new households",
        f"Source: INE (census, population estimates, completions); own calculations. National values: {headline['census']:+.0f} (2011 to 2021), "
        f"{headline['after']:+.0f} (2021 to 2023, implied).",
        head_in=1.15,
        foot_in=0.55,
    )


def r2_ladder(table: pd.DataFrame, outcome: str) -> Figure:
    """Cumulative share of variance explained as blocks of explanations are added (``descriptive.block_r2``).

    The first block is the story: geography. Bars are the cumulative R2 (adjusted R2 as a dot); labels give the
    share each block adds. The title is computed from the table.
    """
    n = len(table)
    fig, ax = plt.subplots(figsize=(9, 0.62 * n + 1.9))
    for i, row in table.reset_index(drop=True).iterrows():
        color = BLUE if i == 0 else MUTED
        ax.barh(i, 100 * row["r2"], color=color, height=0.62, zorder=3)
        ax.plot([100 * row["r2_adj"]], [i], "o", ms=7, mfc=ORANGE, mec=SURFACE, mew=1.5, zorder=5)
        label = (
            f"{100 * row['r2']:.0f}%"
            if i == 0
            else f"{100 * row['r2']:.0f}%  (+{100 * row['r2_added']:.1f} points)"
        )
        ax.annotate(label, (100 * row["r2"], i), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=INK, fontweight="bold")  # fmt: skip
    ax.set_yticks(range(n), table["block"])
    ax.set_ylim(n - 0.4, -0.6)
    ax.set_xlim(0, 100 * table["r2"].max() * 1.6)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    _legend(ax, [Patch(facecolor=MUTED, label="Cumulative R2"),
                 Line2D([], [], marker="o", ls="", ms=7, mfc=ORANGE, mec=SURFACE, label="Adjusted R2")], loc="upper right")  # fmt: skip
    first, last = table.iloc[0], table.iloc[-1]
    rest = 100 * (last["r2"] - first["r2"])
    fig = style.finish(
        fig,
        f"{first['block']} explains {100 * first['r2']:.0f}% of where {outcome} rose; all other drivers add {rest:.0f} points",
        f"Cumulative R2 of the change in {outcome} across mainland municipalities (n = {int(last['n_obs'])}) as blocks are added in this order",
        "Source: INE, AIMA, RNAL, CAOP 2024; own calculations. Order matters when blocks overlap; associations, not causal effects.",
        head_in=1.15,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.38, right=0.97)
    return fig


# ---- regression coefficients ----------------------------------------------------------------------


def coef_ladder(
    table: pd.DataFrame,
    labels: dict[str, str],
    main: str,
    compare: str,
    outcome: str,
    lower_label: bool = True,
) -> Figure:
    """Effect of one within-standard-deviation of each driver on ``outcome`` (in %), across specifications.

    ``table`` is the concatenated output of ``panel.coef_table`` for log outcomes (``coef`` x 100 is then a
    percentage). One panel per driver, one row per specification; ``main`` is blue, ``compare`` orange and the
    other specifications grey. The 95% interval is drawn around the point. ``lower_label`` lowercases the
    driver's name in the title (turn it off for proper nouns).
    """
    terms = [t for t in labels if t in set(table["term"])]
    specs = list(dict.fromkeys(table["spec"]))
    colors = {s: BLUE if s == main else ORANGE if s == compare else MUTED for s in specs}
    fig, axes = plt.subplots(1, len(terms), figsize=(11, 0.5 * len(specs) + 1.9), sharey=True)
    for ax, term in zip(axes, terms, strict=True):
        d = table[table["term"] == term].set_index("spec")
        for i, spec in enumerate(specs):
            if spec not in d.index:
                continue
            row = d.loc[spec]
            lo, hi, mid = (100 * row["sd_within"] * row[k] for k in ("ci_low", "ci_high", "coef"))
            ax.plot([lo, hi], [i, i], color=colors[spec], lw=1.6, solid_capstyle="round", zorder=3)
            ax.plot([mid], [i], "o", ms=7, mfc=colors[spec], mec=SURFACE, mew=1.5, zorder=4)
        ax.axvline(0, color=INK_2, lw=1, zorder=2)
        ax.set_yticks(range(len(specs)), specs)
        ax.set_ylim(len(specs) - 0.4, -0.6)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", visible=False)
        _panel_title(ax, labels[term].replace(" (", "\n("))
        lo_all = (100 * d["sd_within"] * d["ci_low"]).min()
        hi_all = (100 * d["sd_within"] * d["ci_high"]).max()
        pad = 0.12 * (max(hi_all, 0) - min(lo_all, 0))
        ax.set_xlim(min(lo_all, 0) - pad, max(hi_all, 0) + pad)
        narrow = max(hi_all, 0) - min(lo_all, 0) < 3
        ax.xaxis.set_major_locator(mticker.MaxNLocator(3 if narrow else 4, integer=not narrow))
        digits = 1 if narrow else 0
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _, d=digits: "0" if abs(v) < 1e-9 else f"{v:+.{d}f}%")
        )
    main_rows = table[(table["spec"] == main) & table["term"].isin(terms)]
    top = main_rows.loc[main_rows["coef_per_sd"].abs().idxmax()]
    fig = style.finish(
        fig,
        f"One standard deviation of the strongest driver "
        f"({labels[top['term']].split(' (')[0].lower() if lower_label else labels[top['term']].split(' (')[0]}) "
        f"changes {outcome} by {100 * top['coef_per_sd']:+.1f}%",
        f"Per one within-municipality standard deviation of each driver, 95% intervals; "
        f"{main} (blue), {compare} (orange)",
        "Source: INE, Banco de Portugal, RNAL (short-term rentals, mainland); own calculations. "
        "Adjusted associations, not causal effects.",
        head_in=1.5,
        foot_in=0.5,
    )
    fig.subplots_adjust(left=0.19, right=0.985, wspace=0.14)
    return fig


def neighbour_placebo(table: pd.DataFrame, rows: dict[str, str], main: str, compare: str) -> Figure:
    """Coefficient of the neighbours' price-to-income, last year against next year (placebo), by fixed effects.

    ``table`` is the concatenated ``panel.coef_table`` output with a ``spec`` column of the form
    ``'<effects>|<row key>'``; ``rows`` maps row keys to the labels shown (top to bottom); ``main`` and
    ``compare`` are the effects prefixes drawn in blue and orange.
    """
    fig, ax = plt.subplots(figsize=(9, 0.9 * len(rows) + 1.6))
    colors = {main: BLUE, compare: ORANGE}
    offsets = {main: -0.14, compare: 0.14}
    values = {}
    for i, key in enumerate(rows):
        for effects in (main, compare):
            hit = table[(table["spec"] == f"{effects}|{key}") & table["term"].str.startswith("w_")]
            if hit.empty:
                continue
            row = hit.iloc[0]
            values[(effects, key)] = row["coef"]
            y = i + offsets[effects]
            ax.plot(
                [row["ci_low"], row["ci_high"]], [y, y], color=colors[effects], lw=1.8, zorder=3
            )
            ax.plot(
                [row["coef"]], [y], "o", ms=7, mfc=colors[effects], mec=SURFACE, mew=1.5, zorder=4
            )
    ax.axvline(0, color=INK_2, lw=1, zorder=2)
    ax.set_yticks(range(len(rows)), list(rows.values()))
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Coefficient on the neighbours' log price-to-income", color=INK_2)
    low, high = ax.get_xlim()
    ax.set_xlim(low, high + 0.45 * (high - low))  # room on the right for the legend
    _legend(ax, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label=main),
                 Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label=compare)], loc="center right")  # fmt: skip
    first, second = list(rows)[:2]
    lag, lead = values.get((compare, first)), values.get((compare, second))
    if lag is None or lead is None:
        head = "Neighbours' price-to-income and a municipality's own"
    else:
        closeness = "almost as well" if lead > 0.5 * lag else "much less"
        head = (
            f"Within a region, neighbours' price-to-income last year goes with a municipality's ({lag:.2f}); "
            f"next year's does {closeness} ({lead:.2f})"
        )
    fig = style.finish(
        fig,
        head,
        "Fixed-effects regressions of log price-to-income, 2017 to 2022, 95% intervals; the 'next year' row is a "
        "placebo: it cannot be a cause",
        "Source: INE, AIMA, CAOP 2024; own calculations. Adjusted associations, not causal effects.",
        head_in=1.0,
        foot_in=0.9,
    )
    fig.subplots_adjust(left=0.37, right=0.97)
    return fig


# ---- segmentation ---------------------------------------------------------------------------------


def segment_trends(
    panels: list[dict], changes: dict[str, dict[str, float]], start: int, end: int
) -> Figure:
    """Median price-to-income by year for groups of municipalities, one panel per typology dimension.

    ``panels`` holds ``title`` and ``series`` (group label -> Series indexed by year, in drawing order: the
    first is blue, the second orange, any other grey). ``changes`` maps a dimension key ('coast', 'density',
    'tourist') to {group label: % change of the median municipality's price-to-income}; the title is
    computed from them.
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(12, 4.6), sharey=True)
    palette = [BLUE, ORANGE, MUTED]
    top = max(s.max() for p in panels for s in p["series"].values())
    for ax, panel in zip(axes, panels, strict=True):
        for i, (label, s) in enumerate(panel["series"].items()):
            color = palette[min(i, 2)]
            _line(ax, s.index, s, color, width=LINE_WIDTH if i < 2 else CONTEXT_WIDTH)
            _end_dot(ax, s.index[-1], s.iloc[-1], color)
            _label(
                ax,
                s.index[-1],
                s.iloc[-1],
                f"{label} {s.iloc[-1]:.1f}",
                dx=9,
                weight="bold" if i < 2 else "normal",
            )
        _panel_title(ax, panel["title"])
        ax.set_xticks([start, (start + end) // 2, end])
        ax.set_xlim(start - 0.2, end + 0.2)
        ax.set_ylim(0, top * 1.08)
        ax.margins(x=0.02)
    axes[0].set_ylabel("Years of income", color=INK_2)
    urban, rural = changes["density"]["urban"], changes["density"]["rural"]
    coast, inland = changes["coast"]["coast"], changes["coast"]["inland"]
    fig = style.finish(
        fig,
        f"Since {start} price-to-income rose {urban:.0f}% in urban and {rural:.0f}% in rural municipalities, "
        f"{coast:.0f}% on the coast and {inland:.0f}% inland",
        f"Median price-to-income of each group of mainland municipalities, {start} to {end}; "
        "lines use the same municipalities every year; the % change is the median of each municipality's own change",
        "Source: INE, CAOP 2024, RNAL; own calculations. Density, coast and tourism classes: data/external/muni_typology.csv.",
        head_in=1.15,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.06, right=0.9, wspace=0.55)
    return fig


def imi_rate_changes(table: pd.DataFrame) -> Figure:
    """Municipal urban IMI rate changes per tax year (mainland): cuts up, increases down, share at the floor.

    ``table`` has one row per year with ``cuts``, ``increases`` and ``at_floor_pct`` (share of municipalities
    at the 0.30% legal minimum, which cannot cut any further).
    """
    years = table["year"]
    fig, (bars, floor) = plt.subplots(
        1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [2, 1]}
    )
    bars.bar(years, table["cuts"], color=BLUE, width=0.7, zorder=3)
    bars.bar(years, -table["increases"], color=ORANGE, width=0.7, zorder=3)
    bars.axhline(0, color=INK_2, lw=1, zorder=4)
    _years(bars, years)
    bars.set_xlim(years.min() - 0.7, years.max() + 0.7)
    bars.legend(
        handles=[Patch(color=BLUE, label="Cuts"), Patch(color=ORANGE, label="Increases")],
        loc="upper right",
        frameon=False,
    )
    bars.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{abs(v):.0f}"))
    for year, cuts in zip(years, table["cuts"], strict=True):
        if cuts >= 80:
            bars.text(year, cuts + 2, f"{cuts:.0f}", ha="center", va="bottom", color=INK_2)
    _panel_title(bars, "Municipalities that changed the urban rate")
    _line(floor, years, table["at_floor_pct"], BLUE)
    _end_dot(floor, years.iloc[-1], table["at_floor_pct"].iloc[-1], BLUE)
    _label(
        floor,
        years.iloc[-1],
        table["at_floor_pct"].iloc[-1],
        f"{table['at_floor_pct'].iloc[-1]:.0f}%",
        dx=6,
    )
    floor.set_ylim(0, 100)
    floor.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    _years(floor, years[::4])
    floor.set_xlim(years.min() - 0.4, years.max() + 2)
    _panel_title(floor, "At the 0.30% legal floor")
    peak = table.loc[table["cuts"].idxmax()]
    fig = style.finish(
        fig,
        f"{table['cuts'].sum():.0f} rate cuts and {table['increases'].sum():.0f} increases in "
        f"{years.min()} to {years.max()}; {table['at_floor_pct'].iloc[-1]:.0f}% of municipalities now sit at the floor",
        f"Mainland municipalities, urban IMI rate by tax year; cuts peak at {peak['cuts']:.0f} in {peak['year']:.0f}",
        "Source: Autoridade Tributária (Portal das Finanças); own calculations. Parish-rate municipality-years are missing.",
        head_in=1.15,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.06, right=0.97, wspace=0.18)
    return fig


def event_study_plot(
    panels: list[dict], unit: str = "% per 0.01 pp cut", scale: float = 100.0
) -> Figure:
    """Event-study coefficients by event time, one panel per estimate (log outcome x ``scale`` = %).

    Each dict has ``title``, ``table`` (columns k, coef, ci_low, ci_high; the reference k = -1 is added at 0)
    and optionally ``pretrend_p``, ``compare`` (a second table, drawn in orange, e.g. the cohort check) and
    ``benchmark`` (full-capitalisation effect in the same unit, drawn as a dashed line for k >= 0).
    """
    fig, axes = plt.subplots(
        1, len(panels), figsize=(4.4 * len(panels), 4.3), sharey=True, squeeze=False
    )
    for ax, spec in zip(axes[0], panels, strict=True):
        for key, color, shift in (("table", BLUE, -0.07), ("compare", ORANGE, 0.07)):
            if key not in spec:
                continue
            t = pd.concat(
                [
                    spec[key][["k", "coef", "ci_low", "ci_high"]],
                    pd.DataFrame({"k": [-1], "coef": [0.0], "ci_low": [0.0], "ci_high": [0.0]}),
                ]
            ).sort_values("k")
            x = t["k"] + (shift if "compare" in spec else 0)
            ax.vlines(x, scale * t["ci_low"], scale * t["ci_high"], color=color, lw=1.6, zorder=3)
            ax.plot(x, scale * t["coef"], "o", ms=6, mfc=color, mec=SURFACE, mew=1.2, zorder=4)
        if "benchmark" in spec:
            ax.hlines(
                spec["benchmark"], -0.4, spec["table"]["k"].max() + 0.4,
                color=INK_2, lw=1, ls=(0, (4, 3)), zorder=2,
            )  # fmt: skip
            ax.text(
                spec["table"]["k"].max() + 0.45, spec["benchmark"], "full\ncapitalisation",
                va="center", fontsize=8, color=INK_2,
            )  # fmt: skip
        ax.axhline(0, color=INK_2, lw=1, zorder=2)
        ax.axvline(-0.5, color=GRID, lw=1, zorder=1)
        ks = sorted(set(spec["table"]["k"]) | {-1})
        ax.set_xticks(ks, [f"{k:+d}" if k else "0" for k in ks])
        ax.set_xlim(min(ks) - 0.5, max(ks) + 1.9)
        p = spec.get("pretrend_p")
        title = spec["title"] + (
            f"\nPre-trend test p = {p:.2f}" if p is not None and p == p else ""
        )
        _panel_title(ax, title)
        ax.set_xlabel("Years since the cut (reference: year before)", color=INK_2)
    axes[0][0].set_ylabel(unit, color=INK_2)
    if "compare" in panels[0]:
        axes[0][0].legend(
            handles=[
                Line2D([], [], marker="o", color=BLUE, lw=1.6, label="Stacked regression"),
                Line2D([], [], marker="o", color=ORANGE, lw=1.6, label="Cohort-by-cohort 2x2"),
            ],
            loc="lower right",
            frameon=False,
        )
    first = panels[0]
    fig = style.finish(
        fig,
        first.get("headline", "Prices around municipal IMI rate cuts"),
        "Effect on the real price per m² relative to the year before the cut, 95% intervals clustered by municipality",
        "Source: INE, Autoridade Tributária; own calculations. Rates are chosen by councils: read as adjusted associations unless the pre-trend is flat.",
        head_in=1.3,
        foot_in=0.85,
    )
    fig.subplots_adjust(left=0.08, right=0.98, wspace=0.12)
    return fig


def robustness_ladder(
    table: pd.DataFrame,
    main: str,
    benchmark: tuple[float, float, float],
    ks: tuple[int, ...] = (1, 2),
) -> Figure:
    """Event-study coefficient at each event time in ``ks`` across specifications (% per 0.01 pp of cut).

    ``table`` has ``spec``, ``k``, ``coef``, ``ci_low``, ``ci_high`` (in %), ``n_treated`` and ``pretrend_p``;
    a hollow marker means the pre-trend test is rejected at 10%. The shaded band is the (low, mid, high)
    full-capitalisation benchmark.
    """
    specs = list(dict.fromkeys(table["spec"]))
    fig, axes = plt.subplots(
        1,
        len(ks),
        figsize=(5.2 * len(ks) + 2.8, 0.42 * len(specs) + 2.2),
        sharey=True,
        squeeze=False,
    )
    for ax, k in zip(axes[0], ks, strict=True):
        d = table[table["k"] == k].set_index("spec")
        ax.axvspan(benchmark[0], benchmark[2], color=GRID, zorder=1)
        ax.axvline(benchmark[1], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
        for i, spec in enumerate(specs):
            if spec not in d.index:
                continue
            row = d.loc[spec]
            color = BLUE if spec == main else MUTED
            hollow = row["pretrend_p"] < 0.10
            ax.plot([row["ci_low"], row["ci_high"]], [i, i], color=color, lw=1.6, zorder=3)
            ax.plot(
                [row["coef"]],
                [i],
                "o",
                ms=7,
                mfc=SURFACE if hollow else color,
                mec=color,
                mew=1.6,
                zorder=4,
            )
        ax.axvline(0, color=INK_2, lw=1, zorder=2)
        ax.set_yticks(range(len(specs)), [f"{s}" for s in specs])
        ax.set_ylim(len(specs) - 0.4, -0.6)
        ax.grid(axis="y", visible=False)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0"))
        _panel_title(
            ax, f"{'One' if k == 1 else 'Two'} year{'s' if k > 1 else ''} after the cut (k = +{k})"
        )
    last = table[table["k"] == ks[0]].drop_duplicates("spec")
    rejected = int((last["pretrend_p"] < 0.10).sum())
    both = (
        table[table["k"].isin(ks)]
        .groupby("spec")
        .apply(
            lambda g: bool(((g["ci_low"] <= 0) & (g["ci_high"] >= benchmark[1])).all()),
            include_groups=False,
        )
    )
    fig = style.finish(
        fig,
        f"{int(both.sum())} of {len(specs)} specifications cannot tell zero from full capitalisation; {rejected} fail the pre-trend test",
        f"Effect on the real price per m², % per 0.01 pp of cut, 95% intervals; hollow marker = pre-trend rejected at 10%; "
        f"shaded = full capitalisation ({benchmark[0]:.2f}% to {benchmark[2]:.2f}%)",
        "Source: INE, Autoridade Tributária; own calculations. Main specification in blue.",
        head_in=1.3,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.27, right=0.98, wspace=0.08)
    return fig


FORECAST_COLORS = {
    "ETS": BLUE,
    "ARIMA": ORANGE,
    "drift": MUTED,
    "seasonal naive": GRID,
    "naive": INK_2,
}


def forecast_accuracy(
    panels: list[dict],
    baseline: str = "naive",
    unit: str = "quarters",
    note: str = "Origins from 2017Q4: one boom period, no downturn to test against.",
    headline: str | None = None,
    source: str = "INE, Banco de Portugal",
) -> Figure:
    """Rolling-origin accuracy by horizon: RMSE relative to the baseline (top) and 80% interval coverage (bottom).

    Each dict has ``title``, ``rel`` (rows h, columns methods: RMSE divided by the baseline's) and ``acc`` (the
    ``forecasting.accuracy`` table with ``method``, ``h``, ``coverage80``). Lines below 1 beat the baseline; the
    coverage lines should sit on the dashed 80% line. ``unit`` names the horizon step in the labels, ``note``
    ends the source line and ``headline`` replaces the computed title (which describes the best method of the first
    panel and is only right when one method wins in every panel).
    """
    fig, axes = plt.subplots(
        2, len(panels), figsize=(5.2 * len(panels), 6.4), sharex=True, squeeze=False
    )
    for col, spec in enumerate(panels):
        top, bottom = axes[0][col], axes[1][col]
        rel, acc = spec["rel"], spec["acc"]
        for method in rel.columns:
            if method == baseline:
                continue
            color = FORECAST_COLORS.get(method, MUTED)
            _line(
                top,
                rel.index,
                rel[method],
                color,
                method,
                width=2 if method in ("ETS", "ARIMA") else 1.2,
            )
        top.axhline(1, color=INK_2, lw=1, zorder=2)
        top.set_ylim(0, min(max(rel.drop(columns=baseline).max().max() * 1.1, 1.3), 2.5))
        _panel_title(top, spec["title"])
        for method in ("ETS", "ARIMA", baseline):
            d = acc[acc["method"] == method].sort_values("h")
            _line(
                bottom,
                d["h"],
                d["coverage80"],
                FORECAST_COLORS[method],
                method,
                width=2 if method != baseline else 1.2,
            )
        bottom.axhline(0.8, color=INK_2, lw=1, ls=(0, (4, 3)), zorder=2)
        bottom.set_ylim(0, 1.02)
        bottom.yaxis.set_major_formatter(mticker.PercentFormatter(1, decimals=0))
        bottom.set_xticks(sorted(acc["h"].unique()))
        bottom.set_xlabel(f"{unit.capitalize()} ahead", color=INK_2)
    axes[0][0].set_ylabel(f"RMSE relative to {baseline}", color=INK_2)
    axes[1][0].set_ylabel("80% interval coverage", color=INK_2)
    axes[0][0].legend(loc="lower left", frameon=False, ncols=2, fontsize=8.5)
    first = panels[0]["rel"].drop(columns=baseline)
    best = first.mean().idxmin()
    cover = float(np.mean([p["acc"].query("method == @best")["coverage80"].mean() for p in panels]))
    fig = style.finish(
        fig,
        headline
        or f"{best} cuts the error of a naive forecast by {100 * (1 - first[best].mean()):.0f}% on average; its 80% intervals hold {100 * cover:.0f}% of outcomes",
        f"Rolling-origin validation, 1 to {int(max(p['acc']['h'].max() for p in panels))} {unit} ahead (top: RMSE relative to the naive forecast; bottom: share of outcomes inside the 80% interval, dashed = 80%)",
        f"Source: {source}; own calculations. {note}",
        head_in=1.25,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.08, right=0.98, hspace=0.12, wspace=0.18)
    return fig


def forecast_fans(
    panels: list[dict],
    step: int = 4,
    footer: str = "Source: INE, Banco de Portugal; own calculations. Eight quarters is the validated range; 5 to 10 year paths come from the scenarios.",
) -> Figure:
    """History and forecast with 80% and 95% intervals, one panel per series.

    Each dict has ``title``, ``history`` (a Series indexed by year as a float, e.g. 2024.25), ``forecast`` (a frame
    with ``mean``, ``lo80``, ``hi80``, ``lo95``, ``hi95``, same index type) and ``unit_fmt`` for the end label. ``step`` is the spacing of the x ticks and ``footer`` the
    source line.
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(5.4 * len(panels), 4.4), squeeze=False)
    for ax, spec in zip(axes[0], panels, strict=True):
        h, f = spec["history"], spec["forecast"]
        ax.fill_between(f.index, f["lo95"], f["hi95"], color=BLUE, alpha=0.12, lw=0, zorder=2)
        ax.fill_between(f.index, f["lo80"], f["hi80"], color=BLUE, alpha=0.25, lw=0, zorder=2)
        _line(ax, h.index, h, INK_2)
        _line(ax, f.index, f["mean"], BLUE)
        _end_dot(ax, f.index[-1], f["mean"].iloc[-1], BLUE)
        _label(
            ax, f.index[-1], f["mean"].iloc[-1], spec["unit_fmt"].format(f["mean"].iloc[-1]), dx=6
        )
        _end_dot(ax, h.index[-1], h.iloc[-1], INK_2)
        ax.axvline(h.index[-1], color=GRID, lw=1, zorder=1)
        ax.set_xlim(h.index[0] - 0.3, f.index[-1] + 1.6)
        ax.margins(y=0.05)
        _panel_title(ax, spec["title"])
        ax.xaxis.set_major_locator(mticker.MultipleLocator(step))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    first = panels[0]
    f = first["forecast"]
    fig = style.finish(
        fig,
        first.get("headline", "Forecast"),
        "History (grey) and forecast (blue) with 80% and 95% intervals; the model extends the recent trend and knows nothing of policy or rate shocks",
        footer,
        head_in=1.25,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.06, right=0.95, wspace=0.28)
    return fig


# ---- scenarios and the simulator ------------------------------------------------------------------

SCENARIO_COLORS = {"optimistic": BLUE, "baseline": INK_2, "pessimistic": ORANGE}
PARAMETER_LABELS = {
    "other_demand_half_life_years": "Fade of the other-demand boom",
    "net_migration_per_year": "Net migration",
    "mortgage_rate_pct": "Mortgage rate",
    "household_income_growth_real_pct": "Real income growth",
    "completions_per_year": "Completions",
    "income_elasticity_of_price": "Price response to income",
    "usable_share_of_additions": "Share of new homes that house households",
    "price_flexibility_balance": "Price response to the housing balance",
    "mortgage_rate_semi_elasticity": "Price response to the mortgage rate",
}


def scenario_fans(
    panels: list[dict], reference: dict | None = None, headline: str | None = None
) -> Figure:
    """Median and 80% range of each scenario over time, one panel per indicator.

    Each dict has ``title``, ``unit_fmt`` (end label, e.g. "{:.1f}") and ``bands``: scenario name ->
    frame with ``year``, ``p10``, ``p50``, ``p90``. ``reference`` (optional, for the first panel) is the
    forecast the baseline was pinned to: a dict with ``years``, ``mean``, ``lo80``, ``hi80``.
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(5.4 * len(panels), 4.6), squeeze=False)
    for i, (ax, spec) in enumerate(zip(axes[0], panels, strict=True)):
        for name, band in spec["bands"].items():
            color = SCENARIO_COLORS[name]
            ax.fill_between(
                band["year"], band["p10"], band["p90"], color=color, alpha=0.12, lw=0, zorder=1
            )
            _line(ax, band["year"], band["p50"], color, name)
            _end_dot(ax, band["year"].iloc[-1], band["p50"].iloc[-1], color)
            _label(
                ax,
                band["year"].iloc[-1],
                band["p50"].iloc[-1],
                spec["unit_fmt"].format(band["p50"].iloc[-1]),
                dx=7,
            )
        if reference is not None and i == 0:
            ax.errorbar(
                reference["years"], reference["mean"],
                yerr=[reference["mean"] - reference["lo80"], reference["hi80"] - reference["mean"]],
                fmt="D", ms=5, color=INK, ecolor=INK, elinewidth=1.2, capsize=3, zorder=5,
                label="ETS forecast (80% range)",
            )  # fmt: skip
        ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
        first = next(iter(spec["bands"].values()))
        ax.set_xlim(first["year"].iloc[0] - 0.2, first["year"].iloc[-1] + 1.8)
        ax.margins(y=0.06)
        _panel_title(ax, spec["title"])
    axes[0][0].legend(loc="upper left", fontsize=9, labelcolor=INK_2)
    if headline is None:
        end = {k: v["p50"].iloc[-1] for k, v in panels[0]["bands"].items()}
        headline = "Scenarios, median in the last year: " + ", ".join(
            f"{k} {v:.1f}" for k, v in end.items()
        )
    fig = style.finish(
        fig,
        headline,
        "Median (line) and 80% range over parameter uncertainty (band); the first years are pinned to the ETS forecast of p4_01, later years are scenarios",
        "Source: INE, Banco de Portugal; own simulation (config/scenarios.yaml). Median municipality with national price, income and rate paths; conditional paths, not forecasts.",
        head_in=1.25,
        foot_in=0.6,
    )
    fig.subplots_adjust(left=0.06, right=0.95, wspace=0.3)
    return fig


def policy_effects(table: pd.DataFrame, year: int, unit: str = "years of income") -> Figure:
    """Effect of each policy package on price-to-income in the last year, with its cost.

    ``table`` has ``label``, ``pti_gain_p10``, ``pti_gain_p50``, ``pti_gain_p90`` (positive: more affordable)
    and ``cost_bn`` (median cumulative budget cost in billions).
    """
    d = table.sort_values("pti_gain_p50")
    fig, ax = plt.subplots(figsize=(9.2, 0.55 * len(d) + 1.6))
    y = np.arange(len(d))
    colors = [BLUE if g > 0 else ORANGE for g in d["pti_gain_p50"]]
    ax.hlines(y, d["pti_gain_p10"], d["pti_gain_p90"], color=colors, lw=2.2, zorder=3)
    ax.scatter(d["pti_gain_p50"], y, s=64, c=colors, edgecolors=SURFACE, linewidths=1.5, zorder=4)
    ax.axvline(0, color=INK_2, lw=1, zorder=2)
    ax.set_yticks(y, d["label"], color=INK_2)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    span = float(d["pti_gain_p90"].max() - d["pti_gain_p10"].min())
    for yi, (_, row) in zip(y, d.iterrows(), strict=True):
        text = (
            f"{row['pti_gain_p50']:+.2f}   cost {row['cost_bn']:.1f} bn"
            if row["cost_bn"] > 0
            else f"{row['pti_gain_p50']:+.2f}   no cost"
        )
        ax.annotate(
            text, (max(row["pti_gain_p90"], 0), yi), xytext=(8, 0), textcoords="offset points",
            va="center", fontsize=9, color=INK,
        )  # fmt: skip
    ax.set_xlim(min(d["pti_gain_p10"].min(), 0) - 0.05 * span, d["pti_gain_p90"].max() + 0.5 * span)
    ax.set_xlabel(
        f"Fall in price-to-income in {year}, {unit} (right = more affordable)", color=INK_2
    )
    best = d.iloc[-1]
    worse = int((d["pti_gain_p50"] < 0).sum())
    ending = f"{worse} of {len(d)} packages raise the ratio" if worse else "all lower the ratio"
    fig = style.finish(
        fig,
        f"{best['label']} helps most ({best['pti_gain_p50']:+.2f} {unit}); {ending}",
        f"Change in price-to-income against no policy, baseline scenario, {year} (dot: median, line: 80% range over parameter uncertainty)",
        "Source: own simulation. Packages are illustrative sizes from 2027; a tax cut is judged by its price effect only, not by the saving to owners.",
        head_in=1.2,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.27, right=0.97)
    return fig


def sensitivity_tornado(table: pd.DataFrame, base: float, year: int, n: int = 9) -> Figure:
    """Price-to-income in the last year when each input moves from its low to its high value (others at mid).

    ``table`` is ``engine.sensitivity`` output (``parameter``, ``kind``, ``low_pti_end``, ``high_pti_end``,
    ``swing_pti_end``); ``base`` is the central value.
    """
    d = table.sort_values("swing_pti_end", ascending=False).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.2, 0.5 * len(d) + 1.7))
    y = np.arange(len(d))
    for yi, (_, row) in zip(y, d.iterrows(), strict=True):
        lo, hi = sorted((row["low_pti_end"], row["high_pti_end"]))
        color = BLUE if row["kind"] == "scenario" else ORANGE
        ax.barh(yi, hi - lo, left=lo, height=0.55, color=color, alpha=0.85, zorder=3)
        for value, dx, ha in ((lo, -5, "right"), (hi, 5, "left")):
            ax.annotate(
                f"{value:.1f}", (value, yi), xytext=(dx, 0), textcoords="offset points",
                ha=ha, va="center", fontsize=9, color=INK,
            )  # fmt: skip
    ax.axvline(base, color=INK_2, lw=1, zorder=4)
    low = float(d[["low_pti_end", "high_pti_end"]].min().min())
    high = float(d[["low_pti_end", "high_pti_end"]].max().max())
    ax.set_xlim(low - 0.08 * (high - low), high + 0.08 * (high - low))
    ax.set_yticks(y, [PARAMETER_LABELS.get(p, p) for p in d["parameter"]], color=INK_2)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(
        f"Price-to-income in {year} (years of income); line: central value {base:.1f}", color=INK_2
    )
    ax.legend(
        handles=[
            Patch(color=BLUE, label="scenario input (range across the three scenarios)"),
            Patch(color=ORANGE, label="behavioural parameter (low to high)"),
        ],
        loc="lower right", fontsize=9, labelcolor=INK_2,
    )  # fmt: skip
    top = d.iloc[-1]
    label = PARAMETER_LABELS.get(top["parameter"], top["parameter"])
    fig = style.finish(
        fig,
        f"{label} moves price-to-income in {year} by {top['swing_pti_end']:.1f} years, the most of any input",
        "One input at a time between its low and high value, baseline scenario, all others at their central value",
        "Source: own simulation. Behavioural parameters are recalibrated to the forecast, so they move the long run only through the scenarios.",
        head_in=1.2,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.36, right=0.96)
    return fig


# ---- regional outlook -----------------------------------------------------------------------------


def regional_skill(acc: dict[str, pd.DataFrame]) -> Figure:
    """Rank skill (Spearman correlation of predicted and actual change) of each method, one panel per level.

    ``acc`` maps a panel title to a ``regional_forecast`` accuracy table (``method``, ``h``, ``spearman``). The
    naive forecast predicts no change for everyone, so it has no ranking and is left out. One year ahead is
    light blue, two years dark blue; zero is no skill.
    """
    fig, axes = plt.subplots(
        1, len(acc), figsize=(4.1 * len(acc) + 1.2, 4.4), sharey=True, squeeze=False
    )
    first = next(iter(acc.values()))
    methods = [m for m in dict.fromkeys(first["method"]) if m != "naive"]
    light, dark = style.BLUE_RAMP[250], style.BLUE_RAMP[550]
    for ax, (title, table) in zip(axes[0], acc.items(), strict=True):
        for i, method in enumerate(methods):
            for h, color in ((1, light), (2, dark)):
                row = table[(table["method"] == method) & (table["h"] == h)]
                if row.empty:
                    continue
                ax.plot(
                    [row["spearman"].iloc[0]],
                    [i],
                    "o",
                    ms=8,
                    mfc=color,
                    mec=SURFACE,
                    mew=1.5,
                    zorder=4,
                )
        ax.axvline(0, color=INK_2, lw=1, zorder=2)
        ax.set_yticks(range(len(methods)), [m.replace("_", " ") for m in methods])
        ax.set_ylim(len(methods) - 0.4, -0.6)
        ax.set_xlim(-1, 1)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", visible=False)
        _panel_title(ax, title)
        ax.set_xlabel("Rank correlation, predicted vs actual change", color=INK_2)
    axes[0][0].legend(
        handles=[Line2D([], [], marker="o", ls="", ms=8, mfc=c, mec=SURFACE, label=text)
                 for c, text in ((light, "1 year ahead"), (dark, "2 years ahead"))],
        loc="lower left", fontsize=9, labelcolor=INK_2,
    )  # fmt: skip
    muni = next(iter(acc.values()))
    best = muni[muni["method"] != "naive"].groupby("method")["spearman"].mean().idxmax()
    rho = muni[muni["method"] == best]["spearman"].mean()
    fig = style.finish(
        fig,
        f"A {best.replace('_', ' ')} ranks municipalities better than chance (rank correlation {rho:.2f}); regions are harder",
        "Mean over rolling origins 2019 to 2023 of the rank correlation between the predicted and the actual change in price-to-income",
        "Source: INE, own calculations. Naive (no change) has no ranking. Few groups and origins: the region and class panels are indicative.",
        head_in=1.2,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.2, right=0.98, wspace=0.12)
    return fig


def outlook_ranking(
    table: pd.DataFrame, label: str, n_name: str, horizon: int, end_year: int
) -> Figure:
    """Expected change in price-to-income relative to the median municipality, by group, with 80% intervals.

    ``table`` is ``regional_forecast.outlook_summary`` output (columns ``relative``, ``relative_lo80``,
    ``relative_hi80`` in %, ``change_pct``, ``share_rising`` and the group in ``label``); groups whose interval
    excludes zero are drawn in colour, the rest in grey.
    """
    d = table.sort_values("relative").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.6, 0.3 * len(d) + 2.0))
    sure = (d["relative_lo80"] > 0) | (d["relative_hi80"] < 0)
    for i, row in d.iterrows():
        color = (ORANGE if row["relative"] > 0 else BLUE) if sure[i] else MUTED
        ax.plot(
            [row["relative_lo80"], row["relative_hi80"]],
            [i, i],
            color=color,
            lw=2.2,
            zorder=3,
            solid_capstyle="round",
        )
        ax.plot([row["relative"]], [i], "o", ms=8, mfc=color, mec=SURFACE, mew=1.5, zorder=4)
        ax.annotate(f"{row['change_pct']:+.0f}%", (row["relative_hi80"], i), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK_2)  # fmt: skip
    ax.axvline(0, color=INK_2, lw=1, zorder=2)
    ax.set_yticks(range(len(d)), d["label"], color=INK_2)
    ax.set_ylim(-0.7, len(d) - 0.3)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: "0" if v == 0 else f"{v:+.0f}"))
    ax.set_xlabel(
        "Change in price-to-income relative to the median municipality (percentage points)",
        color=INK_2,
    )
    top, bottom = d.iloc[-1], d.iloc[0]
    n_sure = int(sure.sum())
    fig = style.finish(
        fig,
        f"{top['label']} is expected to worsen most ({top['relative']:+.0f} points above the median), {bottom['label']} least; "
        f"{n_sure} of {len(d)} {n_name} differ clearly",
        f"Median municipality of each {label}, {horizon} years to {end_year}; 80% interval from past errors (coloured: excludes zero). "
        "Label: the group's own expected change",
        "Source: INE; own calculations. A trend extrapolation from 2016-2024 (a boom period): it ranks places, it does not forecast their level.",
        head_in=1.25,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.27, right=0.9)
    return fig


# ---- thirty years of national prices --------------------------------------------------------------


def long_run_prices(long: pd.DataFrame, seam_year: int = 2009) -> Figure:
    """National house prices, rents and price-to-income since 1988 (``build_panel.national_annual_long``).

    Left: real house price index and real rent index (2015 = 100). Right: the OECD price-to-income index
    (2015 = 100) from 1995. The dotted line marks the year the price series changes source (the INE index starts):
    the join cannot be tested because the sources do not overlap.
    """
    d = long.set_index("year")
    real, rent = d["hpi_real_b2015"], d["rent_real_b2015"]
    pti = d["price_to_income_b2015"].dropna()
    peak_year = real.loc[:2012].idxmax()
    low_year = real.loc[peak_year:].idxmin()
    back = real[real.index > low_year]
    beat = int(back[back > real.loc[peak_year]].index.min())
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    _line(left, rent.index, rent, ORANGE)
    _line(left, real.index, real, BLUE, z=4)
    for series, color in ((rent, ORANGE), (real, BLUE)):
        _end_dot(left, series.index[-1], series.iloc[-1], color)
    _label(left, real.index[-1], real.iloc[-1], f"{real.iloc[-1]:.0f}")
    _label(left, rent.index[-1], rent.iloc[-1], f"{rent.iloc[-1]:.0f}")
    _line(right, pti.index, pti, BLUE)
    _end_dot(right, pti.index[-1], pti.iloc[-1], BLUE)
    _label(right, pti.index[-1], pti.iloc[-1], f"{pti.iloc[-1]:.0f}")
    for ax in (left, right):
        ax.axvline(seam_year, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
        ax.set_xlim(ax.get_xlim()[0], 2025 + 4.5)
        ax.set_xticks(range(1990, 2026, 5))
        ax.set_ylim(bottom=0)
    left.text(
        seam_year + 0.3, 6, "series changes\nsource (2009)", fontsize=8, color=MUTED, va="bottom"
    )
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Real house price index"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Real rent index")], loc="upper left")  # fmt: skip
    _panel_title(left, "House prices and rents after inflation (2015 = 100)")
    _panel_title(right, "House price to disposable income per head (2015 = 100)")
    return style.finish(
        fig,
        f"After inflation, prices peaked in {peak_year}, fell {100 * (1 - real.loc[low_year] / real.loc[peak_year]):.0f}% to {low_year} "
        f"and passed that peak again in {beat}; the price-to-income index is {pti.iloc[-1] / pti.iloc[0]:.1f}x its {pti.index[0]} level",
        "Annual, national, 1988 to 2025 (price-to-income from 1995); real = deflated with the consumer price index",
        "Source: BIS, INE (house prices, CPI), OECD (rents, price-to-income); own calculations. Before 2009 the price index is the BIS "
        "compilation: the join with INE's cannot be tested.",
        head_in=1.3,
        foot_in=0.6,
    )


# ---- renting versus buying ------------------------------------------------------------------------


def rent_vs_buy_long_run(
    nat: pd.DataFrame,
    measured_yield: pd.Series,
    forward_growth: pd.Series,
    flat_real_growth: float,
) -> Figure:
    """National cost of owning against the rent yield, and the price growth that makes owning pay.

    ``nat`` is ``rent_vs_buy.national_breakeven`` (indexed by year). Left: yearly cost of owning and rent
    yield, both in % of the price, with the municipal measure of the yield where it exists. Right: the
    break-even price growth against the growth that followed over the next five years (``forward_growth``,
    nominal, per year) and the growth with flat real prices (``flat_real_growth``).
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    own, rent, be = nat["owner_cost_pct"], nat["rent_yield_pct"], nat["breakeven_pct"]
    _line(left, rent.index, rent, BLUE)
    _line(left, own.index, own, ORANGE, z=4)
    left.plot(
        measured_yield.index, measured_yield, "o", ms=5, mfc=SURFACE, mec=BLUE, mew=1.5, zorder=5
    )
    for series, color in ((rent, BLUE), (own, ORANGE)):
        _end_dot(left, series.index[-1], series.iloc[-1], color)
        _label(left, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.1f}%")
    _legend(left, [Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Yearly cost of owning"),
                   Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Rent yield"),
                   Line2D([], [], color=BLUE, marker="o", ls="", mfc=SURFACE, mew=1.5, label="Rent yield, measured")], loc="upper left")  # fmt: skip
    fwd = forward_growth.dropna()
    right.axhline(0, color=style.BASELINE, lw=1, zorder=1)
    right.axhline(flat_real_growth, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
    right.text(
        be.index[0],
        flat_real_growth + 0.25,
        "flat real prices",
        fontsize=8,
        color=MUTED,
        va="bottom",
    )
    _line(right, be.index, be, BLUE)
    _line(right, fwd.index, fwd, ORANGE, z=4)
    for series, color in ((be, BLUE), (fwd, ORANGE)):
        _end_dot(right, series.index[-1], series.iloc[-1], color)
        _label(right, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.1f}%")
    _legend(right, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Break-even price growth"),
                    Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Price growth, next five years")], loc="upper left")  # fmt: skip
    for ax in (left, right):
        ax.set_xlim(ax.get_xlim()[0], 2025 + 4.5)
        ax.set_xticks(range(2005, 2026, 5))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    left.set_ylim(2.5, 11)
    right.set_ylim(-5, 17)
    _panel_title(left, "Owning against renting, % of the price a year")
    _panel_title(right, "Price growth that makes owning pay, % a year")
    low_year = int(be.idxmin())
    title = (
        f"The price growth that makes owning pay rose from {be.min():.1f}% a year in {low_year} "
        f"to {be.iloc[-1]:.1f}% in {be.index[-1]}"
    )
    return style.finish(
        fig,
        title,
        "National, annual; costs in % of the price; break-even = yearly cost of owning minus the rent yield",
        "Source: OECD (price-to-rent), Banco de Portugal, INE (rents of new leases, IMI rates via AT), own calculations. Assumptions: "
        "80% loan, 3% on the deposit, 1% upkeep, 6% buying costs over 10 years, IMI on 60% of the price.",
        head_in=1.3,
        foot_in=0.6,
    )


def owner_cost_stack(table: pd.DataFrame, rent_yield: pd.Series) -> Figure:
    """Yearly cost of owning by component for chosen years, against the rent yield.

    ``table`` has one row per year with the five ``rent_vs_buy.COMPONENTS`` columns (% of the price);
    ``rent_yield`` the yield for the same years. Components are grouped as financing (interest and the
    return forgone on the deposit), running costs (property tax, upkeep) and buying costs.
    """
    groups = {
        "Interest and return forgone on the deposit": ["interest", "deposit_return"],
        "Property tax and upkeep": ["property_tax", "maintenance"],
        "Buying costs (IMT, stamp duty, fees)": ["buying_costs"],
    }
    shades = [style.BLUE_RAMP[s] for s in (600, 350, 150)]
    fig, ax = plt.subplots(figsize=(9, 3.4 + 0.45 * len(table)))
    y = np.arange(len(table))[::-1]
    left = np.zeros(len(table))
    for (label, cols), color in zip(groups.items(), shades, strict=True):
        width = table[cols].sum(axis=1).to_numpy()
        ax.barh(y, width, left=left, height=0.55, color=color, label=label, zorder=3)
        left = left + width
    for yi, total in zip(y, left, strict=True):
        ax.text(
            total + 0.08,
            yi + 0.36,
            f"{total:.1f}%",
            fontsize=9.5,
            color=INK,
            fontweight="bold",
            va="center",
        )
    ax.plot(
        rent_yield.to_numpy(),
        y,
        "D",
        ms=9,
        mfc=ORANGE,
        mec=SURFACE,
        mew=2,
        zorder=6,
        label="Rent yield",
    )
    ax.set_yticks(y, [str(i) for i in table.index])
    ax.set_xlim(0, max(left.max(), rent_yield.max()) * 1.12)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.grid(axis="y", visible=False)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0, -0.08),
        ncol=2,
        fontsize=9,
        labelcolor=INK_2,
        frameon=False,
    )
    low = int(np.argmin(left))
    return style.finish(
        fig,
        f"Owning cost {left[low]:.1f}% of the price a year in {table.index[low]} and {left[-1]:.1f}% in {table.index[-1]}, "
        f"against a rent yield of {rent_yield.iloc[-1]:.1f}%",
        "Yearly cost of owning a home in % of its price, before price gains, against the rent yield (diamonds)",
        "Source: Banco de Portugal, INE, OECD, AT; own calculations. Assumptions as in docs/methodology.md.",
        head_in=1.0,
        foot_in=1.1,
    )


# ---- foreign residents ----------------------------------------------------------------------------


def foreign_residents_trend(
    totals: pd.DataFrame, brazil: pd.Series, share_by_class: pd.DataFrame
) -> Figure:
    """Foreign residents with a residence title, 2014 to 2023.

    ``totals`` is ``demography.national_totals`` (``foreign_residents_n``, ``foreign_share_pct``), ``brazil``
    the Brazilian count by year, ``share_by_class`` the foreign share of the population (%) by year (rows) and
    density class (columns: urban, intermediate, rural). Left: thousands of residents; right: share of the
    population by class.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.4))
    total = totals["foreign_residents_n"] / 1000
    _line(left, total.index, total, BLUE)
    _line(left, brazil.index, brazil / 1000, ORANGE, z=4)
    for series, color in ((total, BLUE), (brazil / 1000, ORANGE)):
        _end_dot(left, series.index[-1], series.iloc[-1], color)
        _label(left, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:,.0f}k")
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="All foreign residents"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="of which Brazil")])  # fmt: skip
    colors = {"urban": BLUE, "intermediate": ORANGE, "rural": MUTED}
    for name, color in colors.items():
        s = share_by_class[name]
        _line(right, s.index, s, color)
        _end_dot(right, s.index[-1], s.iloc[-1], color)
        _label(right, s.index[-1], s.iloc[-1], f"{s.iloc[-1]:.1f}%")
    _legend(right, [Line2D([], [], color=c, lw=LINE_WIDTH, label=n.capitalize()) for n, c in colors.items()])  # fmt: skip
    for ax in (left, right):
        ax.set_xlim(ax.get_xlim()[0], totals.index.max() + 1.8)
        ax.set_xticks(range(int(totals.index.min()), int(totals.index.max()) + 1, 3))
        ax.set_ylim(bottom=0)
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}k"))
    right.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    _panel_title(left, "Foreign residents with a residence title")
    _panel_title(right, "Share of the resident population, by density")
    first, last = totals.index[0], totals.index[-1]
    return style.finish(
        fig,
        f"Foreign residents rose from {totals['foreign_residents_n'].iloc[0] / 1000:,.0f}k in {first} to "
        f"{totals['foreign_residents_n'].iloc[-1] / 1000:,.0f}k in {last}, {totals['foreign_share_pct'].iloc[0]:.1f}% to "
        f"{totals['foreign_share_pct'].iloc[-1]:.1f}% of residents",
        "Foreign nationals with a residence title on 31 December; density class from 2021 residents per km2",
        "Source: INE (AIMA/SEF titles; resident population estimate), own calculations. Titles, not the foreign-born: "
        "part of the 2023 jump may be administrative.",
        head_in=1.3,
        foot_in=0.6,
    )


def nationality_location_bars(
    location: pd.DataFrame, labels: dict[str, str], names: dict[str, str]
) -> Figure:
    """Where each nationality lives: 100% bars over groups of districts.

    ``location`` is ``demography.nationality_location`` (rows nationality, columns the groups plus ``other``,
    rows add to 100); ``labels`` maps a column to its legend text, ``names`` a nationality code to its name.
    Rows are sorted by the share of the first group.
    """
    first = location.columns[0]
    d = location.sort_values(first)
    shades = [style.BLUE_RAMP[s] for s in (700, 450, 250)] + [style.BASELINE]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(d) + 2.6))
    y = np.arange(len(d))
    left = np.zeros(len(d))
    for column, color in zip(d.columns, shades, strict=False):
        ax.barh(
            y,
            d[column],
            left=left,
            height=0.62,
            color=color,
            label=labels.get(column, column),
            zorder=3,
        )
        left = left + d[column].to_numpy()
    ax.set_yticks(y, [names.get(i, i.capitalize()) for i in d.index])
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.grid(axis="y", visible=False)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0, -0.08),
        ncol=len(d.columns),
        fontsize=9,
        labelcolor=INK_2,
        frameon=False,
    )
    top = d[first].idxmax()
    bottom = d[first].idxmin()
    return style.finish(
        fig,
        f"{names.get(top, top)}: {d[first].max():.0f}% live in {labels.get(first, first)}; "
        f"{names.get(bottom, bottom)}: {d[first].min():.0f}%",
        "Share of each nationality's residents by district, 31 December 2023",
        "Source: INE (AIMA/SEF residence titles), own calculations. Districts of mainland and islands as in CAOP 2024.",
        head_in=1.0,
        foot_in=1.3,
    )


# ---- robustness of the affordability indicators ----------------------------------------------------


def indicator_robustness(table: pd.DataFrame, trends: pd.DataFrame, base_label: str) -> Figure:
    """How much the picture depends on how affordability is defined (``descriptive.compare_definitions``).

    Left: rank correlation with the base indicator across municipalities, of the 2024 level (filled dot) and of
    the change over each definition's window (open dot). Right: the median municipality's indicator rebased to
    its first year (rows years, columns definitions; the first column is the base, drawn in blue).
    """
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(11, 0.45 * len(table) + 3.4), gridspec_kw={"width_ratios": [1.15, 1]}
    )
    d = table.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(d))
    left.axvline(1, color=style.BASELINE, lw=1, zorder=1)
    left.axvline(0, color=style.BASELINE, lw=1, zorder=1)
    for yi, lvl, chg in zip(y, d["rank_corr_level"], d["rank_corr_change"], strict=True):
        if not (np.isnan(lvl) or np.isnan(chg)):
            left.plot([lvl, chg], [yi, yi], color=GRID, lw=2, zorder=2)
    left.plot(d["rank_corr_level"], y, "o", ms=8, mfc=BLUE, mec=SURFACE, mew=1.5, zorder=4)
    left.plot(d["rank_corr_change"], y, "o", ms=8, mfc=SURFACE, mec=ORANGE, mew=2, zorder=5)
    left.set_yticks(
        y, [f"{n}\n({w})" for n, w in zip(d["definition"], d["window"], strict=True)], fontsize=8.5
    )
    left.set_xlim(-0.05, 1.08)
    left.set_ylim(-0.6, len(d) - 0.4)
    left.grid(axis="y", visible=False)
    _legend(left, [Line2D([], [], color=BLUE, marker="o", ls="", ms=8, label="Level, 2024"),
                   Line2D([], [], color=ORANGE, marker="o", ls="", mfc=SURFACE, mew=2, ms=8, label="Change over the window")], loc="lower left")  # fmt: skip
    _panel_title(left, "Rank correlation with the base indicator")
    cols = list(trends.columns)
    styles = [
        (BLUE, "-", 3),
        (ORANGE, "-", 3),
        (MUTED, "-", 2),
        (MUTED, (0, (4, 2)), 2),
        (INK_2, (0, (1, 2)), 2),
    ]
    for col, (color, ls, z) in zip(cols, styles, strict=False):
        right.plot(
            trends.index, trends[col], color=color, ls=ls, lw=LINE_WIDTH, zorder=z, label=col
        )
    right.axhline(100, color=style.BASELINE, lw=1, zorder=1)
    right.set_xticks(range(int(trends.index.min()), int(trends.index.max()) + 1, 2))
    _legend(right, [Line2D([], [], color=c, ls=ls, lw=LINE_WIDTH, label=col) for col, (c, ls, _) in zip(cols, styles, strict=False)], loc="upper left")  # fmt: skip
    _panel_title(right, f"Median municipality's change, {int(trends.index.min())} = 100")
    ends = trends.iloc[-1]
    return style.finish(
        fig,
        f"Purchase definitions rank places alike, rents do not; the rise since {int(trends.index.min())} is "
        f"{ends.min() - 100:+.0f}% to {ends.max() - 100:+.0f}% depending on the definition",
        f"Alternative to '{base_label}': rank correlation across municipalities (left) and the median municipality over time (right)",
        "Source: INE, Banco de Portugal; own calculations. Definitions in docs/methodology.md; windows differ because the series have different lengths.",
        head_in=1.3,
        foot_in=0.6,
    )


def new_build_vs_households(
    comparison: pd.DataFrame, small_share: pd.Series, small_households_pct: dict[int, float]
) -> Figure:
    """Net change in households and completions by size (left), the small-dwelling share of completions (right).

    ``comparison`` is ``housing_mix.national_comparison`` (rows 1, 2, 3, 4plus: persons in the household, bedrooms of
    the dwelling), ``small_share`` the yearly share of completions with up to two bedrooms and
    ``small_households_pct`` the share of households with one or two persons in the census years.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [5, 6]})
    x = np.arange(len(comparison))
    width = 0.38
    households = comparison["households_change_n"] / 1000
    done = comparison["completed_n"] / 1000
    left.axhline(0, color=GRID, lw=1, zorder=1)
    left.bar(x - width / 2, households, width, color=BLUE, zorder=3)
    left.bar(x + width / 2, done, width, color=ORANGE, zorder=3)
    for pos, value in zip(x - width / 2, households, strict=True):
        left.annotate(f"{value:+,.0f}k", (pos, value), xytext=(0, 4 if value >= 0 else -4), textcoords="offset points",
                      ha="center", va="bottom" if value >= 0 else "top", fontsize=8.5, color=INK)  # fmt: skip
    for pos, value in zip(x + width / 2, done, strict=True):
        left.annotate(f"{value:,.0f}k", (pos, value), xytext=(0, 4), textcoords="offset points",
                      ha="center", va="bottom", fontsize=8.5, color=INK)  # fmt: skip
    left.set_xticks(x)
    left.set_xticklabels(["1 person\nT0-T1", "2 persons\nT2", "3 persons\nT3", "4+ persons\nT4+"])
    left.set_ylim(min(households.min() * 1.4, -20), max(households.max(), done.max()) * 1.55)
    _legend(left, [Patch(facecolor=BLUE, label="Change in households, 2011-2021"),
                   Patch(facecolor=ORANGE, label="Dwellings completed, 2011-2021")], loc="upper right")  # fmt: skip
    _panel_title(left, "By household size and bedrooms (thousands)")

    d = small_share.loc[1995:]
    _line(right, d.index, d, ORANGE)
    _end_dot(right, d.index[-1], d.iloc[-1], ORANGE)
    _label(right, d.index[-1], d.iloc[-1], f"{d.iloc[-1]:.0f}%")
    years = sorted(small_households_pct)
    values = [small_households_pct[y] for y in years]
    right.plot(
        years, values, color=BLUE, lw=LINE_WIDTH, marker="o", ms=8, mec=SURFACE, mew=2, zorder=4
    )
    for year, value in zip(years, values, strict=True):
        right.annotate(f"{value:.0f}%", (year, value), xytext=(0, 9), textcoords="offset points",
                       ha="center", fontsize=9.5, color=INK, fontweight="bold")  # fmt: skip
    right.set_xlim(1994, d.index.max() + 3.5)
    right.set_xticks(range(1995, 2026, 5))
    right.set_ylim(0, 75)
    right.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    _legend(right, [Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Completions with up to 2 bedrooms (T0-T2)"),
                    Line2D([], [], color=BLUE, lw=LINE_WIDTH, marker="o", label="Households with 1 or 2 persons (census)")], loc="lower left")  # fmt: skip
    _panel_title(right, "The small end of the mix")
    grew = comparison.loc[comparison["households_change_n"] > 0, "households_change_n"].sum()
    big = comparison.loc[["3", "4plus"], "completed_n"].sum() / comparison["completed_n"].sum()
    shrank = -comparison.loc[comparison["households_change_n"] < 0, "households_change_n"].sum()
    return style.finish(
        fig,
        f"Households of one or two persons grew by {grew / 1000:,.0f}k in 2011-2021, larger ones fell by {shrank / 1000:,.0f}k, "
        f"yet {100 * big:.0f}% of the new dwellings had three or more bedrooms",
        "National, census 2011 to 2021; dwellings paired with households by bedrooms and persons (T0-T1 with 1, T2 with 2, T3 with 3, T4+ with 4+)",
        "Source: INE (census 2011 and 2021; licensing and completions of family dwellings), own calculations. A nominal pairing: a couple can live in a T3.",
        head_in=1.3,
        foot_in=0.6,
    )


def population_components(
    balance: pd.DataFrame, rates: dict[str, pd.DataFrame], first_year: int = 1961
) -> Figure:
    """What moved the population: natural change and net migration, nationally and by density class.

    ``balance`` is ``demography.national_balance`` (thousands per year are plotted from ``first_year``; the
    2020-2021 revision is drawn as grey bars so it is not read as migration). ``rates`` maps a period label to
    ``demography.municipal_balance(..., by="density_class")``: bars of natural change and net migration per
    1,000 residents a year for urban, intermediate and rural municipalities in each period.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [6, 5]})
    d = balance.loc[first_year:]
    natural, migration = d["natural_change_n"] / 1000, d["net_migration_n"] / 1000
    revision = d["revision_n"] / 1000
    left.axhline(0, color=GRID, lw=1, zorder=1)
    rev = revision[revision.abs() > 1]
    left.bar(rev.index, rev, color=MUTED, alpha=0.5, width=0.8, zorder=2)
    _line(left, d.index, natural, BLUE)
    _line(left, d.index, migration, ORANGE)
    for s, color in ((natural, BLUE), (migration, ORANGE)):
        _end_dot(left, s.index[-1], s.iloc[-1], color)
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Natural change (births minus deaths)"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Net migration"),
                   Patch(facecolor=MUTED, alpha=0.5, label="Post-census revision")], loc="upper center")  # fmt: skip
    left.get_legend().set_bbox_to_anchor((0.62, 1.0))
    if first_year <= 1975 <= d.index.max():
        left.annotate(
            "1975: return from the colonies", (1975, migration.loc[1975]), xytext=(-6, 0),
            textcoords="offset points", ha="right", va="center", fontsize=8.5, color=INK_2,
        )  # fmt: skip
    left.set_xticks(range(first_year - first_year % 10 + 10, int(d.index.max()) + 1, 10))
    left.set_xlim(first_year - 1, d.index.max() + 1.5)
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}k"))
    _panel_title(left, "Persons a year, national")

    classes = ["urban", "intermediate", "rural"]
    width, step = 0.38, 1.0
    ticks, labels = [], []
    pos = 0.0
    short = {"urban": "Urban", "intermediate": "Interm.", "rural": "Rural"}
    for period, table in rates.items():
        group_start = pos
        for name in classes:
            row = table.loc[name]
            right.bar(pos - width / 2, row["natural_per_1000_year"], width, color=BLUE, zorder=3)
            right.bar(
                pos + width / 2, row["migration_per_1000_year"], width, color=ORANGE, zorder=3
            )
            ticks.append(pos)
            labels.append(short[name])
            pos += step
        right.annotate(
            period, ((group_start + pos - step) / 2, 0), xycoords=("data", "axes fraction"),
            xytext=(0, -22), textcoords="offset points", ha="center", fontsize=9, color=INK_2,
            fontweight="bold",
        )  # fmt: skip
        pos += 0.6
    right.axhline(0, color=INK_2, lw=1, zorder=4)
    right.set_xticks(ticks, labels, fontsize=8.5)
    right.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    _panel_title(right, "Per 1,000 residents a year, municipalities")
    for ax in (left, right):
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    first_p, last_p = list(rates)[0], list(rates)[-1]
    negative = d["natural_change_n"] < 0
    since = int(negative[~negative].index.max()) + 1  # first year of the final run with more deaths
    peak = d["net_migration_n"].idxmax()
    return style.finish(
        fig,
        f"Since {since} deaths outnumber births; net migration decides if the population grows",
        f"Natural change, net migration (incl. statistical adjustment) and the 2020-2021 revision; municipal rates for {first_p} and {last_p}",
        "Source: Eurostat (demo_gind), INE annual estimates, own calculations. Net migration is a residual of the estimate; "
        f"{int(d.index.max())} may be provisional. Peak: {d.loc[peak, 'net_migration_n'] / 1000:,.0f}k in {int(peak)}.",
        head_in=1.3,
        foot_in=0.6,
    )


# ---- rates and the price cycle --------------------------------------------------------------------


def rates_and_cycles(frame: pd.DataFrame, episodes: pd.DataFrame, profile: pd.DataFrame) -> Figure:
    """Real prices and the mortgage rate by episode (left), and how price growth lines up with rate changes (right).

    ``frame`` is ``macro.quarterly_frame``, ``episodes`` ``macro.episodes`` (``start`` and ``end`` as quarter
    labels; alternate episodes are shaded), ``profile`` ``macro.lag_profile``: bars show the correlation of a
    year's real price growth with the rate change that many quarters earlier, the dotted lines the 95% limit for
    no relation.
    """
    fig = plt.figure(figsize=(11, 5.6))
    grid = fig.add_gridspec(2, 2, width_ratios=[6, 5], hspace=0.35, wspace=0.22)
    top, bottom = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[1, 0], sharex=None)
    right = fig.add_subplot(grid[:, 1])
    dates = frame.index
    price, rate = frame["hpi_real_b2010"], frame["mortgage_rate_new_lt1y_pct"]
    _line(top, dates, price, BLUE)
    _line(bottom, dates, rate, ORANGE)
    for ax, series, color, fmt in ((top, price, BLUE, "{:.0f}"), (bottom, rate, ORANGE, "{:.1f}%")):
        _end_dot(ax, dates[-1], series.iloc[-1], color)
        _label(ax, dates[-1], series.iloc[-1], fmt.format(series.iloc[-1]))
        for i, (_, row) in enumerate(episodes.iterrows()):
            if i % 2 == 0:
                ax.axvspan(
                    pd.Period(row["start"], "Q").to_timestamp(),
                    pd.Period(row["end"], "Q").to_timestamp(),
                    color=GRID, alpha=0.55, lw=0, zorder=0,
                )  # fmt: skip
        ax.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=400))
        _quarter_axis(ax, dates.to_series(), base=4)
    top.set_ylim(bottom=0)
    bottom.set_ylim(bottom=0)
    bottom.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    _panel_title(top, "Real house price index (2010 = 100)")
    _panel_title(bottom, "Agreed rate on new housing loans")

    lags = profile["lag_quarters"]
    right.axhline(0, color=INK_2, lw=1, zorder=2)
    right.bar(lags, profile["corr"], width=0.7, color=BLUE, zorder=3)
    band = profile["band"].iloc[0]
    for sign in (-1, 1):
        right.axhline(sign * band, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
    right.set_xticks(list(lags)[::2])
    right.set_ylim(-0.7, 0.7)
    right.set_xlabel(
        "Quarters between the rate change and the price growth", fontsize=9, color=INK_2
    )
    _panel_title(right, "Price growth against an earlier rate change (correlation)")

    shock = episodes.loc[episodes["rate_change_pp"].idxmax()]
    beyond = int((profile["corr"].abs() > band).sum())
    verdict = (
        "No correlation reaches the limit: rate changes alone do not time the price cycle."
        if beyond == 0
        else f"{beyond} of {len(profile)} correlations pass the limit."
    )
    return style.finish(
        fig,
        f"Rates rose {shock['rate_change_pp']:.1f} points and the payment {shock['payment_change_pct']:.0f}% "
        f"in {shock['start']} to {shock['end']}, yet real prices rose {shock['real_price_change_pct']:.0f}%",
        "Quarterly, national, 2003 to 2026; shaded and white bands alternate between episodes; right: four-quarter changes",
        "Source: BIS and INE (house prices), Banco de Portugal (rates), own calculations. Real = deflated with the consumer price "
        f"index. {verdict}",
        head_in=1.3,
        foot_in=0.6,
    )


def peers_policy_mix(table: pd.DataFrame, names: dict[str, str], focus: str = "PT") -> Figure:
    """Price change, recurrent property tax and housing support for Portugal and its peers, one dot plot each.

    ``table`` is ``peers.policy_mix``; ``names`` maps the country codes drawn (and their order of drawing, which is
    by price change) to labels. A missing value is written as n/a. ``focus`` is the country drawn in blue.
    """
    d = table.loc[list(names)].sort_values("price_change_pct")
    panels = (
        ("price_change_pct", "House prices, change 2015-2024", "{:.0f}%"),
        ("property_tax_gdp_pct", "Recurrent property tax, % of GDP", "{:.2f}"),
        ("housing_support_gdp_pct", "Housing support, % of GDP", "{:.2f}"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.0), sharey=True)
    y = np.arange(len(d))
    for ax, (col, title, fmt) in zip(axes, panels, strict=True):
        for pos, (geo, value) in zip(y, d[col].items(), strict=True):
            hit = geo == focus
            if pd.isna(value):
                ax.annotate(
                    "n/a",
                    (0, pos),
                    xytext=(6, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                    color=MUTED,
                )
                continue
            ax.plot([0, value], [pos, pos], color=BLUE if hit else GRID, lw=1.6, zorder=2)
            ax.plot(
                [value],
                [pos],
                "o",
                ms=9 if hit else 7,
                mfc=BLUE if hit else MUTED,
                mec=SURFACE,
                mew=1.5,
                zorder=4,
            )
            ax.annotate(fmt.format(value), (value, pos), xytext=(8, 0), textcoords="offset points", va="center", fontsize=9,
                        color=INK, fontweight="bold" if hit else "normal")  # fmt: skip
        ax.set_xlim(0, d[col].max() * 1.3)
        ax.set_ylim(-0.6, len(d) - 0.4)
        _panel_title(ax, title)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([names[g] for g in d.index])

    def rank(col: str) -> str:
        values = d[col].dropna()
        place = int(values.rank(ascending=False)[focus])
        return f"{place}{('th', 'st', 'nd', 'rd')[place] if place < 4 else 'th'} of {len(values)}"

    return style.finish(
        fig,
        f"Portugal ranks {rank('price_change_pct')} on price growth since 2015 ({d.loc[focus, 'price_change_pct']:.0f}%), "
        f"{rank('property_tax_gdp_pct')} on property tax and {rank('housing_support_gdp_pct')} on housing support",
        "National, mean of 2015 to 2024 for the shares of GDP; house prices nominal, annual mean index",
        "Source: Eurostat (house price index, national accounts D29A, spending by function), own calculations. Italy has no housing-support value: its 2022-2023 spending is far above trend.",
        head_in=1.3,
        foot_in=0.6,
    )


def housing_spending(portugal: pd.DataFrame, shares: pd.DataFrame, peers: dict[str, str]) -> Figure:
    """Portugal's real housing spending by kind (left) and housing support as a share of GDP against peers (right).

    ``portugal`` is ``spending.portugal_frame`` (real columns in constant euros), ``shares`` is
    ``spending.support_shares`` and ``peers`` maps the geo codes drawn to their names.
    """
    d = portugal.loc[1995:]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    dev, ben = d["housing_development_real_eur_m"], d["housing_benefits_real_eur_m"]
    left.stackplot(
        d.index, dev.fillna(0), ben.fillna(0), colors=[BLUE, ORANGE], alpha=0.9, zorder=3
    )
    left.set_ylim(0, (dev.fillna(0) + ben.fillna(0)).max() * 1.3)
    left.set_xlim(1994, d.index.max() + 1)
    left.set_xticks(range(1995, 2026, 5))
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _legend(left, [Patch(facecolor=BLUE, label="Housing development (incl. public housing)"),
                   Patch(facecolor=ORANGE, label="Housing allowances and rent subsidies")], loc="upper left")  # fmt: skip
    _panel_title(left, "Portugal, million euros of the base year")
    s = shares.loc[1995:]
    pt = s["PT"].dropna()
    for geo, name in peers.items():
        line = s[geo].dropna()
        _line(right, line.index, line, MUTED, width=1.4, z=2)
        _label(
            right,
            line.index[-1],
            line.iloc[-1],
            name,
            weight="normal",
            va="bottom" if geo == "DE" else "center",
        )
    _line(right, pt.index, pt, BLUE)
    _end_dot(right, pt.index[-1], pt.iloc[-1], BLUE)
    _label(right, pt.index[-1], pt.iloc[-1], f"Portugal {pt.iloc[-1]:.2f}%", va="top")
    right.set_xlim(1994, pt.index.max() + 9)
    right.set_xticks(range(1995, 2026, 5))
    right.set_ylim(0, None)
    right.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=1))
    _panel_title(right, "Housing development plus allowances, % of GDP")
    low = pt.loc[2010:].idxmin()
    return style.finish(
        fig,
        f"Housing support rose from {pt.loc[low]:.2f}% of GDP in {low} to {pt.iloc[-1]:.2f}% in {pt.index[-1]}, "
        f"still below France ({s['FR'].iloc[-1]:.1f}%) and Ireland ({s['IE'].iloc[-1]:.1f}%)",
        "General government, annual, 1995 to 2024; spending by function (COFOG): housing development plus housing in social protection",
        "Source: Eurostat (government expenditure by function, national accounts), INE, own calculations. Tax expenditures are not included. Italy and the EU27 are left out: their 2022-2023 values are far above trend.",
        head_in=1.3,
        foot_in=0.6,
    )


def construction_costs(frame: pd.DataFrame) -> Figure:
    """Nominal house prices against the cost of building (left) and licensed and completed dwellings (right).

    ``frame`` is ``construction.annual_frame`` (indices 2015 = 100; ``licensed_n`` and ``completed_n`` in dwellings).
    Left: nominal house price index, the total cost index and its materials and labour parts. Right: new family
    dwellings licensed and completed, in thousands.
    """
    d = frame
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    parts = [
        (d["cost_materials_b2015"], MUTED, 1.4, 2),
        (d["cost_labour_b2015"], MUTED, 1.4, 2),
        (d["cost_total_b2015"], ORANGE, LINE_WIDTH, 4),
        (d["hpi_nominal_b2015"], BLUE, LINE_WIDTH, 4),
    ]
    for series, color, width, z in parts:
        _line(left, series.index, series, color, width=width, z=z)
    for series, text in (
        (d["cost_labour_b2015"], "Labour"),
        (d["cost_materials_b2015"], "Materials"),
    ):
        _label(left, series.index[-1], series.iloc[-1], text, weight="normal")
    _end_dot(left, d.index[-1], d["cost_total_b2015"].iloc[-1], ORANGE)
    _end_dot(left, d.index[-1], d["hpi_nominal_b2015"].iloc[-1], BLUE)
    left.axhline(100, color=GRID, lw=1, zorder=1)
    left.set_xlim(d.index.min() - 1, d.index.max() + 3.5)
    left.set_xticks(range(2000, 2026, 5))
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="House price index"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Cost of building (total)")], loc="upper left")  # fmt: skip
    _panel_title(left, "Nominal prices and building costs (2015 = 100)")
    for col, color in (("licensed_n", BLUE), ("completed_n", ORANGE)):
        series = d[col].dropna() / 1000
        _line(right, series.index, series, color)
        _end_dot(right, series.index[-1], series.iloc[-1], color)
    right.set_xlim(d.index.min() - 1, d.index.max() + 1.5)
    right.set_xticks(range(2000, 2026, 5))
    right.set_ylim(0, None)
    _legend(right, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Licensed"),
                    Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Completed")], loc="upper right")  # fmt: skip
    _panel_title(right, "New family dwellings (thousands)")
    since = lambda c: f"{100 * (d[c].iloc[-1] / d.loc[2013, c] - 1):+.0f}%"  # noqa: E731
    return style.finish(
        fig,
        f"Since 2013 house prices are {since('hpi_nominal_b2015')} and building costs {since('cost_total_b2015')}, "
        f"and building tracked prices, not costs",
        f"Annual, national, 2000 to {d.index.max()}; nominal indices, 2015 = 100; new family housing",
        "Source: INE (new housing construction cost index, licensed and completed dwellings), BIS, OECD, own calculations. The cost index is input cost: land, margin and financing are not in it.",
        head_in=1.3,
        foot_in=0.6,
    )


def _quarter_label(t: pd.Timestamp) -> str:
    return f"{t.quarter}Q{t.year}"


def foreign_buyers(premium: pd.DataFrame, markets: pd.DataFrame) -> Figure:
    """Median price per m2 by the buyer's tax residence (left) and the foreign premium (right), quarterly from 4Q2019.

    ``premium`` is ``foreign_buyers.national_premium`` (medians by buyer and premiums in %), ``markets`` is
    ``foreign_buyers.foreign_markets`` (yearly; ``median_premium_pct`` is the premium within each municipality that has a
    foreign-buyer price, median over those municipalities). Left: domestic buyers, EU buyers and buyers from other countries.
    Right: the national premium of foreign over domestic buyers, and the within-municipality premium.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    series = (
        ("domestic", BLUE, "Domestic buyers"),
        ("eu", MUTED, "EU buyers"),
        ("other_foreign", ORANGE, "Buyers from other countries"),
    )
    for col, color, _ in series:
        line = premium[col].dropna()
        _line(left, line.index, line, color, width=LINE_WIDTH if color != MUTED else 1.6)
        _end_dot(left, line.index[-1], line.iloc[-1], color)
    _thousands(left)
    left.set_ylim(0, None)
    left.set_xlim(
        premium.index.min() - pd.Timedelta(days=60), premium.index.max() + pd.Timedelta(days=500)
    )
    _quarter_axis(left, premium.index.to_series(), base=1)
    _legend(
        left,
        [Line2D([], [], color=c, lw=LINE_WIDTH, label=n) for _, c, n in series],
        loc="upper left",
    )
    _panel_title(left, "Median price per m2, last 12 months (euros)")
    nat = premium["premium_foreign_pct"].dropna()
    inside = markets["median_premium_pct"].dropna()
    inside_x = pd.to_datetime(inside.index.astype(str) + "-10-01")
    _line(right, nat.index, nat, BLUE)
    _end_dot(right, nat.index[-1], nat.iloc[-1], BLUE)
    _line(right, inside_x, inside, ORANGE)
    _end_dot(right, inside_x[-1], inside.iloc[-1], ORANGE)
    right.set_ylim(0, None)
    right.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    right.set_xlim(
        nat.index.min() - pd.Timedelta(days=60), nat.index.max() + pd.Timedelta(days=500)
    )
    _quarter_axis(right, nat.index.to_series(), base=1)
    _legend(right, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Nationally"),
                    Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Within a municipality (median of those with a foreign price)")], loc="lower left")  # fmt: skip
    _panel_title(right, "Foreign buyers' premium over domestic buyers")
    first, last = nat.iloc[0], nat.iloc[-1]
    return style.finish(
        fig,
        f"Foreign buyers paid {first:.0f}% more per m2 than domestic buyers in {_quarter_label(nat.index[0])} and {last:.0f}% more in {_quarter_label(nat.index[-1])}",
        f"National and municipal medians of sales in the last 12 months, quarterly, {nat.index[0].year} to {nat.index[-1].year}; by tax residence of the buyer",
        "Source: INE (statistics on house prices at local level), own calculations. A price gap, not a measure of investment: it mixes where, what and how much is bought. Municipal premiums only where a foreign-buyer price is published.",
        head_in=1.3,
        foot_in=0.6,
    )


def property_tax_revenue(frame: pd.DataFrame) -> Figure:
    """Real IMI and IMT revenue (left) and both against the real house price index, 2015 = 100 (right).

    ``frame`` is ``revenue.annual_frame``. Left: million euros of the base year. Right: the same two series as
    indices with the real house price index, so the gap between what homes are worth and what they yield shows.
    """
    d = frame.loc[1995:]
    imi, imt = d["imi_real_eur_m"], d["imt_real_eur_m"]
    price, imi_idx, imt_idx = d["hpi_real_b2015"], d["imi_real_b2015"], d["imt_real_b2015"]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, series_list in (
        (left, ((imt, BLUE), (imi, ORANGE))),
        (right, ((price, MUTED), (imt_idx, BLUE), (imi_idx, ORANGE))),
    ):
        for series, color in series_list:
            _line(
                ax,
                series.index,
                series,
                color,
                width=1.4 if color == MUTED else LINE_WIDTH,
                z=2 if color == MUTED else 4,
            )
            _end_dot(ax, series.index[-1], series.iloc[-1], color)
            _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:,.0f}")
        ax.set_xlim(1994, d.index.max() + 4.5)
        ax.set_xticks(range(1995, 2026, 5))
    left.set_ylim(0, None)
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="IMT (with stamp duty)"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="IMI")], loc="upper left")  # fmt: skip
    _legend(right, [Line2D([], [], color=MUTED, lw=1.4, label="Real house price index"),
                    Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="IMT revenue"),
                    Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="IMI revenue")], loc="upper left")  # fmt: skip
    _panel_title(left, "Revenue (million euros, constant prices)")
    _panel_title(right, "Revenue and house prices (2015 = 100, real)")
    since = lambda s: f"{100 * (s.iloc[-1] / s.loc[2015] - 1):+.0f}%"  # noqa: E731
    return style.finish(
        fig,
        f"Since 2015 real house prices are {since(price)}, IMT revenue {since(imt_idx)} and IMI revenue {since(imi_idx)}",
        "Annual, national, general government, 1995 to 2025; constant euros of the base year (consumer price index)",
        "Source: Eurostat (national accounts D29A and D214C, accrual basis), INE, BIS, OECD, own calculations.",
        head_in=1.3,
        foot_in=0.6,
    )


def wages_and_prices(annual: pd.DataFrame) -> Figure:
    """Real house prices against real wages (left) and two price-to-earnings ratios (right), 1995 onward.

    ``annual`` is ``macro.annual_frame`` (2015 = 100). Left: real house price index and real compensation per
    employee. Right: house price over compensation per employee and the OECD's house price over disposable income
    per head, the second only from its first year.
    """
    d = annual.loc[1995:]
    price, wage = d["hpi_real_b2015"], d["wage_real_b2015"]
    p2w, p2i = d["price_to_wage_b2015"], d["price_to_income_b2015"].dropna()
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    _line(left, wage.index, wage, ORANGE)
    _line(left, price.index, price, BLUE, z=4)
    for series, color in ((wage, ORANGE), (price, BLUE)):
        _end_dot(left, series.index[-1], series.iloc[-1], color)
        _label(left, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.0f}")
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Real house price index"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Real compensation per employee")], loc="upper left")  # fmt: skip
    _line(right, p2i.index, p2i, MUTED, width=1.4, z=2)
    _line(right, p2w.index, p2w, BLUE, z=4)
    for series, color, va in (
        (p2w, BLUE, "top"),
        (p2i, MUTED, "bottom"),
    ):  # ends are 2 points apart
        _end_dot(right, series.index[-1], series.iloc[-1], color)
        _label(right, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.0f}", va=va)
    _legend(right, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Price over compensation per employee"),
                    Line2D([], [], color=MUTED, lw=1.4, label="Price over disposable income per head (OECD)")], loc="upper left")  # fmt: skip
    for ax in (left, right):
        ax.set_xlim(1994, d.index.max() + 4.5)
        ax.set_xticks(range(1995, 2026, 5))
        ax.set_ylim(60, 230)
    _panel_title(left, "After inflation (2015 = 100)")
    _panel_title(right, "House price to earnings (2015 = 100)")
    low = p2w.loc[2008:].idxmin()
    return style.finish(
        fig,
        f"Prices rose {100 * (price.iloc[-1] / price.loc[low] - 1):.0f}% after inflation since {low} and wages {100 * (wage.iloc[-1] / wage.loc[low] - 1):.0f}%: "
        f"the price-to-wage ratio is {p2w.iloc[-1] / p2w.loc[low]:.1f} times its {low} low",
        "Annual, national, 1995 to 2025; compensation of employees over employees (whole economy), deflated with the consumer price index",
        "Source: BIS, INE, OECD, Eurostat (national accounts), own calculations. Per employee: hours and the mix of jobs are not held fixed.",
        head_in=1.3,
        foot_in=0.6,
    )


def credit_and_prices(frame: pd.DataFrame, profile: pd.DataFrame) -> Figure:
    """Real prices against real housing credit (left), debt ratios (middle), and which leads, prices or credit (right).

    ``frame`` is ``credit.quarterly_frame`` (indices 2010 = 100), ``profile`` ``macro.lag_profile`` of a year's real
    price growth on housing-loan growth shifted by each lag: a positive lag is credit growth that came earlier, a
    negative lag credit growth that came later. Dotted lines mark the 95% limit for no relation.
    """
    fig, (left, mid, right) = plt.subplots(1, 3, figsize=(13, 4.6), gridspec_kw={"wspace": 0.3})
    dates = frame.index
    series = (
        ("hpi_real_b2010", BLUE, "Real house price index"),
        ("housing_loans_real_b2010", ORANGE, "Real housing-loan stock"),
        ("loans_per_price_b2010", MUTED, "Loans per unit of price"),
    )
    for col, color, _ in series:
        _line(left, dates, frame[col], color, width=1.4 if color == MUTED else LINE_WIDTH)
        _end_dot(left, dates[-1], frame[col].iloc[-1], color)
        _label(left, dates[-1], frame[col].iloc[-1], f"{frame[col].iloc[-1]:.0f}")
    _legend(left, [Line2D([], [], color=c, lw=LINE_WIDTH, label=lab) for _, c, lab in series])
    left.set_ylim(0, 230)
    left.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=500))
    _quarter_axis(left, dates.to_series(), base=4)
    _panel_title(left, "After inflation, 2010 = 100")

    ratios = (
        ("household_debt_income_pct", BLUE, "Household debt, % of disposable income"),
        ("housing_loans_gdp_pct", ORANGE, "Housing loans, % of GDP"),
    )
    for col, color, _ in ratios:
        _line(mid, dates, frame[col], color)
        _end_dot(mid, dates[-1], frame[col].iloc[-1], color)
        _label(mid, dates[-1], frame[col].iloc[-1], f"{frame[col].iloc[-1]:.0f}%")
    _legend(
        mid,
        [Line2D([], [], color=c, lw=LINE_WIDTH, label=lab) for _, c, lab in ratios],
        loc="lower left",
    )
    mid.set_ylim(0, 130)
    mid.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=500))
    mid.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    _quarter_axis(mid, dates.to_series(), base=4)
    _panel_title(mid, "Debt in relation to income and GDP")

    lags = profile["lag_quarters"]
    right.axhline(0, color=INK_2, lw=1, zorder=2)
    right.bar(lags, profile["corr"], width=0.7, color=BLUE, zorder=3)
    band = profile["band"].iloc[0]
    for sign in (-1, 1):
        right.axhline(sign * band, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
    right.set_xticks(list(lags)[::2])
    right.set_ylim(-0.7, 0.7)
    right.set_xlabel(
        "Quarters credit growth came before (+) or after (-) price growth", fontsize=9, color=INK_2
    )
    _panel_title(right, "Price growth against housing-loan growth (correlation)")

    low = frame["hpi_real_b2010"].loc["2008":].idxmin()
    first, last = frame.loc[low], frame.iloc[-1]
    price_gain = 100 * (last["hpi_real_b2010"] / first["hpi_real_b2010"] - 1)
    loan_gain = 100 * (last["housing_loans_real_eur_m"] / first["housing_loans_real_eur_m"] - 1)
    return style.finish(
        fig,
        f"Real prices rose {price_gain:.0f}% since {low.year} Q{low.quarter} while real housing credit "
        f"{'fell' if loan_gain < 0 else 'rose'} {abs(loan_gain):.0f}%: credit did not drive the recovery",
        f"Quarterly, national, {dates[0].year} Q{dates[0].quarter} to {dates[-1].year} Q{dates[-1].quarter}; right: four-quarter changes",
        "Source: BIS and INE (house prices), Banco de Portugal (loans, household debt), own calculations. Loans per unit of price: "
        "nominal loan stock over the nominal price index. Credit growth is transactions-based (no write-offs or loan sales).",
        head_in=1.3,
        foot_in=0.6,
    )


def financeable_prices(frame: pd.DataFrame, parts: pd.DataFrame) -> Figure:
    """Actual price against the price wages and the mortgage rate could finance (left), and what moved the price (right).

    ``frame`` is ``macro.financeable_price`` (2015 = 100 scale, nominal), ``parts`` a table indexed by episode
    with ``span`` (label like ``"2021-2025"``) and the log-point change of the price (``price_change_pct``) split
    into ``wages_pct``, ``rate_pct`` and ``gap_pct`` (``macro.price_change_parts``). Bars are stacked by sign; the
    dot is the total.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [6, 5]})
    years = frame.index
    actual, implied = frame["price_b2015"], frame["implied_price_b2015"]
    _line(left, years, implied, MUTED, width=1.6, z=2)
    _line(left, years, actual, BLUE, z=4)
    for series, color in ((actual, BLUE), (implied, MUTED)):
        _end_dot(left, years[-1], series.iloc[-1], color)
        _label(left, years[-1], series.iloc[-1], f"{series.iloc[-1]:.0f}")
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="House price index"),
                   Line2D([], [], color=MUTED, lw=1.6, label="Price a constant payment-to-wage burden finances")], loc="upper left")  # fmt: skip
    left.set_xlim(years[0] - 0.5, years[-1] + 3)
    left.set_xticks(range(years[0] + (-years[0] % 5), years[-1] + 1, 5))
    left.set_ylim(bottom=0)
    _panel_title(left, "Nominal, 2015 = 100")

    colors = {"wages_pct": BLUE, "rate_pct": MUTED, "gap_pct": ORANGE}
    names = {"wages_pct": "Wages", "rate_pct": "Mortgage rate", "gap_pct": "Not accounted for"}
    x = np.arange(len(parts))
    pos, neg = np.zeros(len(parts)), np.zeros(len(parts))
    for col, color in colors.items():
        v = parts[col].to_numpy(dtype=float)
        base = np.where(v >= 0, pos, neg)
        right.bar(x, v, bottom=base, width=0.62, color=color, zorder=3)
        pos, neg = pos + np.clip(v, 0, None), neg + np.clip(v, None, 0)
    right.plot(
        x, parts["price_change_pct"].astype(float), "o", ms=8, mfc=INK, mec=SURFACE, mew=2, zorder=6
    )
    right.axhline(0, color=INK_2, lw=1, zorder=2)
    labels = [f"{i}\n{s}" for i, s in zip(parts.index, parts["span"], strict=True)]
    right.set_xticks(x, labels, fontsize=8)
    right.set_ylabel("Log points", fontsize=9, color=INK_2)
    _legend(right, [Patch(color=c, label=names[k]) for k, c in colors.items()] +
            [Line2D([], [], marker="o", ls="", color=INK, label="Price change")], loc="upper left")  # fmt: skip
    _panel_title(right, "What moved the price")

    last = parts.iloc[-1]
    return style.finish(
        fig,
        f"Since {last['span'][:4]} prices rose {last['price_change_pct']:.0f} log points: wages {last['wages_pct']:+.0f}, "
        f"the rate {last['rate_pct']:+.0f}, and {last['gap_pct']:+.0f} that neither accounts for",
        "Annual, national, nominal; the burden is a fixed share of the average wage on a 30-year loan at the agreed rate for new housing loans",
        "Source: BIS, INE, Banco de Portugal, Eurostat (compensation per employee), own calculations. The implied price is scaled to equal the actual "
        "on average 2003 to 2025, so the gap's changes, not its level, carry the information.",
        head_in=1.3,
        foot_in=0.6,
    )


# ---- kinds of home and kinds of price -------------------------------------------------------------


def price_kinds(
    premium: pd.DataFrame, flats_villas: pd.DataFrame, appraisal: pd.DataFrame
) -> Figure:
    """New against existing homes, flats against villas, and appraisal against transaction prices.

    ``premium`` is ``price_types.new_vs_existing``, ``flats_villas`` ``price_types.flats_vs_villas`` and
    ``appraisal`` ``price_types.appraisal_vs_transaction``. Left: median premium of new over existing homes, %.
    Middle: median appraised price of flats over villas (1 = equal). Right: appraised over transaction price,
    balanced municipalities with the quartile band, and the median of all municipalities with both (grey).
    """
    fig, (left, mid, right) = plt.subplots(1, 3, figsize=(13, 4.6))
    prem = premium["median_premium_pct"]
    _line(left, prem.index, prem, BLUE)
    _end_dot(left, prem.index[-1], prem.iloc[-1], BLUE)
    _label(left, prem.index[-1], prem.iloc[-1], f"{prem.iloc[-1]:.0f}%")
    left.set_ylim(0, 32)
    left.set_xlim(prem.index[0] - 0.3, prem.index[-1] + 1.6)
    left.set_xticks(range(prem.index[0], prem.index[-1] + 1, 2))
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    n_new = int(premium["municipalities_n"].iloc[0])
    _panel_title(left, f"New over existing homes ({n_new} municipalities)")

    ratio = flats_villas["flats_to_villas"]
    mid.axhline(1, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
    _line(mid, ratio.index, ratio, BLUE)
    _end_dot(mid, ratio.index[-1], ratio.iloc[-1], BLUE)
    _label(mid, ratio.index[-1], ratio.iloc[-1], f"{ratio.iloc[-1]:.2f}")
    mid.set_ylim(0.8, 1.35)
    mid.set_xlim(ratio.index[0] - 0.5, ratio.index[-1] + 2.2)
    mid.set_xticks(range(ratio.index[0] + (-ratio.index[0] % 5), ratio.index[-1] + 1, 5))
    _panel_title(mid, "Appraised flats over villas, per m2")

    years = appraisal.index
    right.axhline(1, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
    right.fill_between(
        years, appraisal["balanced_q25"], appraisal["balanced_q75"], color=BLUE, alpha=0.10, lw=0
    )
    _line(right, years, appraisal["all_median"], MUTED, width=1.4, z=2)
    _line(right, years, appraisal["balanced_median"], BLUE, z=4)
    last = appraisal["balanced_median"].iloc[-1]
    _end_dot(right, years[-1], last, BLUE)
    _label(right, years[-1], last, f"{last:.2f}")
    right.set_ylim(0.75, 1.35)
    right.set_xlim(years[0] - 0.4, years[-1] + 1.8)
    right.set_xticks(range(years[0], years[-1] + 1, 3))
    n_bal = int(appraisal["balanced_n"].iloc[0])
    _legend(right, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label=f"Same {n_bal} municipalities"),
                    Line2D([], [], color=MUTED, lw=1.4, label="All with both")], loc="upper right")  # fmt: skip
    _panel_title(right, "Appraisal over transaction price")

    first = prem.index[0]
    return style.finish(
        fig,
        f"New homes cost {prem.loc[first]:.0f}% more than existing ones in {first} and {prem.iloc[-1]:.0f}% in {prem.index[-1]}; "
        f"in {n_bal} municipalities appraisals went from {100 * (appraisal['balanced_median'].iloc[0] - 1):.0f}% above to {100 * (1 - last):.0f}% below transactions",
        "Median over municipalities, price per m2; left: real transaction prices; middle: bank appraisals; right: the same municipalities every year",
        "Source: INE (median transaction value, bank appraisals), own calculations. Appraisals are annual, transactions the last twelve months to Q4. "
        "Property types by rooms are not published for prices.",
        head_in=1.3,
        foot_in=0.6,
    )


# ---- big municipalities and their surroundings ----------------------------------------------------


def centres_and_surroundings(
    gradient: pd.DataFrame, cores: pd.DataFrame, names: pd.Series
) -> Figure:
    """Real price and income change by distance from a large municipality, and the two metropolitan cores.

    ``gradient`` is ``centres.gradient`` (outcomes ``price`` and ``income``, indexed by steps from the nearest
    municipality of 100,000 residents; the last step pools it and above), ``cores`` ``centres.core_vs_rest`` per
    outcome (rows indexed by outcome and core code), ``names`` the municipality names by code. Left: median
    change in % by distance. Right: each core's price change beside the median of the rest of its area.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [6, 5]})
    price = gradient.xs("price", level="outcome")
    income = gradient.xs("income", level="outcome")
    steps = price.index.to_numpy()
    _line(left, steps, income["median"], ORANGE)
    _line(left, steps, price["median"], BLUE, z=4)
    for series, color in ((income["median"], ORANGE), (price["median"], BLUE)):
        _end_dot(left, steps[-1], series.iloc[-1], color)
        _label(left, steps[-1], series.iloc[-1], f"{series.iloc[-1]:.0f}%")
    _end_dot(left, steps[0], price["median"].iloc[0], BLUE)
    _label(left, steps[0], price["median"].iloc[0], f"{price['median'].iloc[0]:.0f}%", dx=10)
    labels = ["Large\nmunicipality"] + [
        f"{int(s)} step" + ("s" if s > 1 else "") for s in steps[1:-1]
    ]
    labels.append(f"{int(steps[-1])}+ steps")
    left.set_xticks(steps, labels, fontsize=8.5)
    left.set_xlim(steps[0] - 0.5, steps[-1] + 0.9)
    left.set_ylim(0, 125)
    left.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    _legend(left, [Line2D([], [], color=BLUE, lw=LINE_WIDTH, label="Price per m2"),
                   Line2D([], [], color=ORANGE, lw=LINE_WIDTH, label="Median income")], loc="upper right")  # fmt: skip
    _panel_title(left, "Change 2016 to 2024 by distance from a large municipality")

    table = cores.xs("price", level="outcome")
    width = 0.38
    for i, (_code, row) in enumerate(table.iterrows()):
        right.bar(i - width / 2, row["core"], width, color=BLUE, zorder=3)
        right.bar(i + width / 2, row["rest_median"], width, color=MUTED, zorder=3)
        right.annotate(f"{row['core']:.0f}%", (i - width / 2, row["core"]), xytext=(0, 3),
                       textcoords="offset points", ha="center", fontsize=9, color=INK, fontweight="bold")  # fmt: skip
        right.annotate(f"{row['rest_median']:.0f}%", (i + width / 2, row["rest_median"]), xytext=(0, 3),
                       textcoords="offset points", ha="center", fontsize=9, color=INK_2, fontweight="bold")  # fmt: skip
    right.set_xticks(range(len(table)), [names[c] for c in table.index], fontsize=9.5)
    right.set_ylim(0, 175)
    right.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    _legend(right, [Patch(facecolor=BLUE, label="The core"), Patch(facecolor=MUTED, label="Rest of its metropolitan area, median")], loc="upper left")  # fmt: skip
    _panel_title(right, "Price change 2016 to 2024: Lisboa and Porto")

    return style.finish(
        fig,
        f"Real prices rose {price['median'].iloc[0]:.0f}% in large municipalities and {price['median'].iloc[-1]:.0f}% far from them; "
        "Lisboa itself rose less than its suburbs, Porto more",
        "Median over municipalities; distance = border steps to the nearest municipality with 100,000+ residents (2021); real = deflated with the consumer price index",
        "Source: INE (prices, income, population), CAOP boundaries, own calculations. Large municipalities include the metropolitan suburbs (Sintra, Gaia, Amadora).",
        head_in=1.3,
        foot_in=0.6,
    )


VALIDATION_COLORS = {
    "rolling origin": INK_2,
    "random folds": ORANGE,
    "leave one out, purged": BLUE,
    "blocks, purged": MUTED,
}


def validation_schemes(panels: list[dict]) -> Figure:
    """Skill against a no-change forecast by validation scheme and horizon, one panel per series.

    Each dict has ``title`` and ``scores`` (``forecasting.scheme_scores`` rows with ``scheme``, ``h`` and ``skill``).
    Skill is 1 minus the ratio of the model's RMSE to that of no change: above 0 the model beats naive. The rolling
    origin is the real-time answer; any scheme that sits above it is overstating what a forecaster could have done.
    """
    fig, axes = plt.subplots(
        1, len(panels), figsize=(5.4 * len(panels), 4.6), sharey=True, squeeze=False
    )
    schemes = list(VALIDATION_COLORS)
    offsets = np.linspace(-0.27, 0.27, len(schemes))
    for ax, spec in zip(axes[0], panels, strict=True):
        s = spec["scores"]
        horizons = sorted(s["h"].unique())
        for off, scheme in zip(offsets, schemes, strict=True):
            d = s[s["scheme"] == scheme].set_index("h").reindex(horizons)
            real = scheme == "rolling origin"
            ax.plot(
                np.arange(len(horizons)) + off,
                d["skill"],
                "o",
                ms=10 if real else 7,
                mfc=VALIDATION_COLORS[scheme],
                mec=SURFACE,
                mew=1.5,
                zorder=5 if real else 4,
                label=scheme,
            )
        ax.axhline(0, color=INK_2, lw=1, zorder=2)
        for i, h in enumerate(horizons):
            roll = s[(s["scheme"] == "rolling origin") & (s["h"] == h)]["skill"].iloc[0]
            ax.plot([i - 0.4, i + 0.4], [roll, roll], color=INK_2, lw=0.8, ls=(0, (3, 3)), zorder=1)
        ax.set_xticks(np.arange(len(horizons)), [f"{h}" for h in horizons])
        ax.set_xlabel("Quarters ahead", color=INK_2)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1, decimals=0))
        _panel_title(ax, spec["title"])
    axes[0][0].set_ylabel("Skill against a no-change forecast", color=INK_2)
    axes[0][-1].legend(loc="upper right", frameon=False, fontsize=8.5)
    cost = panels[-1]["scores"]
    cost = cost[cost["h"] == cost["h"].max()].set_index("scheme")["skill"]
    fig = style.finish(
        fig,
        f"Random folds give the cost-of-ownership model {100 * cost['random folds']:.0f}% skill at the longest horizon; in real time it has {100 * cost['rolling origin']:.0f}%",
        "Skill of one regression on the last four quarterly changes, scored on the same targets under four ways of splitting the data (dashed = rolling origin)",
        "Source: INE, Banco de Portugal; own calculations. The model is a validation test case, not the project's forecaster.",
        head_in=1.25,
        foot_in=0.55,
    )
    fig.subplots_adjust(left=0.09, right=0.98, wspace=0.08)
    return fig


def age_structure(profile: pd.DataFrame, groups: pd.DataFrame) -> Figure:
    """National age profile in two years (left) and the 65+ share by kind of place in both years (right).

    ``profile``: residents by five-year group (rows, age order) with the two years as columns. ``groups``: one row per
    kind of place with ``label``, ``start`` and ``end`` (median share of residents aged 65+, %), in drawing order.
    """
    first, last = profile.columns[0], profile.columns[-1]
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(11.5, 4.8), gridspec_kw={"width_ratios": [1.25, 1]}
    )
    x = np.arange(len(profile))
    _line(left, x, profile[first] / 1e3, MUTED, width=LINE_WIDTH)
    _line(left, x, profile[last] / 1e3, BLUE, width=LINE_WIDTH)
    _label(left, x[-1], profile[first].iloc[-1] / 1e3, str(first), dx=6, weight="normal")
    _label(left, x[-1], profile[last].iloc[-1] / 1e3, str(last), dx=6)
    left.set_xticks(x[::2], list(profile.index[::2]), color=INK_2, fontsize=8.5)
    left.set_xlim(-0.3, len(profile) + 0.8)
    left.set_ylim(0, None)
    left.set_xlabel("Age group", color=INK_2)
    left.set_ylabel("Residents (thousands)", color=INK_2)
    _panel_title(left, "Who lives in Portugal")
    g = groups.iloc[::-1].reset_index(drop=True)
    light, dark = style.BLUE_RAMP[250], style.BLUE_RAMP[550]
    right.grid(axis="x")
    right.grid(axis="y", visible=False)
    for i, row in g.iterrows():
        right.plot(
            [row["start"], row["end"]], [i, i], color=GRID, lw=3, zorder=1, solid_capstyle="round"
        )
        right.plot([row["start"]], [i], "o", ms=8, mfc=light, mec=SURFACE, mew=2, zorder=3)
        right.plot([row["end"]], [i], "o", ms=8, mfc=dark, mec=SURFACE, mew=2, zorder=4)
        right.annotate(f"{row['end']:.0f}%", (row["end"], i), xytext=(9, 0), textcoords="offset points",
                       va="center", fontsize=9, color=INK_2)  # fmt: skip
    right.set_yticks(range(len(g)), g["label"], color=INK_2, fontsize=9.5)
    right.set_xlim(0, g[["start", "end"]].to_numpy().max() * 1.15)
    right.set_ylim(-0.7, len(g) - 0.3)
    right.spines["bottom"].set_visible(False)
    right.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    _legend(right, [Line2D([], [], marker="o", ls="", ms=8, mfc=light, mec=SURFACE, label=str(first)),
                    Line2D([], [], marker="o", ls="", ms=8, mfc=dark, mec=SURFACE, label=str(last))], loc="lower right")  # fmt: skip
    _panel_title(right, "Share aged 65+, median municipality")
    fig = style.finish(
        fig,
        f"Every kind of place has aged; the rural interior is oldest, at {groups['end'].max():.0f}% aged 65+",
        f"Residents by five-year age group in {first} and {last} (left); share aged 65+ by coast and density class (right)",
        "Source: INE (resident population estimates); own calculations. Classes: own proxies (data/external/muni_typology.csv).",
        head_in=1.25,
        foot_in=0.6,
    )
    fig.subplots_adjust(left=0.07, right=0.97, wspace=0.28)
    return fig


def vacancy_vs_shortfall(groups: pd.DataFrame, top: pd.DataFrame, sens: pd.DataFrame) -> Figure:
    """Excess vacancy against the household shortfall by price pressure (left) and in the largest shortfalls (right).

    ``groups`` is ``vacancy.by_group`` by price-to-income tercile (rows low, mid, high), ``top`` is
    ``vacancy.largest_shortfalls`` (municipalities in rank order) and ``sens`` ``vacancy.sensitivity``; the title
    quotes the coverage at the default frictional level with all and a quarter of the excess usable.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [5, 6]})
    x = np.arange(len(groups))
    width = 0.38
    excess_k, short_k = groups["excess_n"] / 1000, groups["shortfall_n"] / 1000
    left.bar(x - width / 2, excess_k, width, color=ORANGE, zorder=3)
    left.bar(x + width / 2, short_k, width, color=BLUE, zorder=3)
    for pos, value in zip(x - width / 2, excess_k, strict=True):
        left.annotate(f"{value:,.0f}k", (pos, value), xytext=(0, 4), textcoords="offset points",
                      ha="center", va="bottom", fontsize=8.5, color=INK)  # fmt: skip
    for pos, value in zip(x + width / 2, short_k, strict=True):
        left.annotate(f"{value:,.0f}k", (pos, value), xytext=(0, 4), textcoords="offset points",
                      ha="center", va="bottom", fontsize=8.5, color=INK)  # fmt: skip
    left.set_xticks(x)
    labels = [f"{g}\nprice-to-income\ncovered {c:.0f}%" for g, c in zip(groups.index, groups["coverage_pct"], strict=True)]  # fmt: skip
    left.set_xticklabels(labels)
    left.set_ylim(0, max(excess_k.max(), short_k.max()) * 1.3)
    _legend(left, [Patch(facecolor=ORANGE, label="Excess vacant dwellings, 2021"),
                   Patch(facecolor=BLUE, label="Shortfall of homes, 2021-2023")], loc="upper left")  # fmt: skip
    _panel_title(left, "By price pressure, 2024 terciles (thousands)")

    y = np.arange(len(top))[::-1]
    right.barh(y + 0.19, top["excess_n"] / 1000, 0.36, color=ORANGE, zorder=3)
    right.barh(y - 0.19, top["shortfall_n"] / 1000, 0.36, color=BLUE, zorder=3)
    for pos, vacancy_pct, big in zip(
        y, top["vacancy_2021_pct"], top[["excess_n", "shortfall_n"]].max(axis=1), strict=True
    ):
        right.annotate(f"{vacancy_pct:.0f}% vacant", (big / 1000, pos), xytext=(6, 0), textcoords="offset points",
                       va="center", fontsize=8.5, color=INK_2)  # fmt: skip
    right.set_yticks(y, top["name"], color=INK_2, fontsize=9.5)
    right.set_xlim(0, top[["excess_n", "shortfall_n"]].to_numpy().max() / 1000 * 1.3)
    right.set_ylim(-0.7, len(top) - 0.3)
    _panel_title(right, "The ten municipalities with the largest shortfall (thousands)")

    def pick(share: float) -> float:
        row = sens[(sens["frictional_pct"] == 5.0) & (sens["usable_share"] == share)]
        return row["coverage_pct"].iloc[0]

    return style.finish(
        fig,
        f"On paper excess vacancy could house {pick(1.0):.0f}% of the shortfall where it arises; if a quarter is usable, {pick(0.25):.0f}%",
        "Vacant dwellings above a 5% frictional level (census 2021) against implied new households minus completions (2021-2023), municipality by municipality",
        "Source: INE (census 2021, population estimates, completions), own calculations. Vacancy is not condition or availability; the shortfall is a proxy.",
        head_in=1.3,
        foot_in=0.95,
    )


def vacant_surcharge(table: pd.DataFrame, bite: pd.Series, national_imi_eur_m: float) -> Figure:
    """Revenue of a surcharge on excess vacant homes by legal share (left), its size against rent (right).

    ``table`` has one row per share of excess vacancy that can be classified as vacant (index) and the columns
    ``all_eur_m`` (every municipality) and ``pressured_eur_m`` (high price-to-income tercile only); ``bite`` is
    ``revenue.surcharge_bite`` per municipality, shown as a share of the yearly rent.
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [5, 6]})
    x = np.arange(len(table))
    width = 0.38
    left.bar(x - width / 2, table["all_eur_m"], width, color=ORANGE, zorder=3)
    left.bar(x + width / 2, table["pressured_eur_m"], width, color=BLUE, zorder=3)
    for offset, col in ((-width / 2, "all_eur_m"), (width / 2, "pressured_eur_m")):
        for pos, value in zip(x + offset, table[col], strict=True):
            left.annotate(f"{value:,.0f}", (pos, value), xytext=(0, 4), textcoords="offset points",
                          ha="center", va="bottom", fontsize=8.5, color=INK)  # fmt: skip
    left.set_xticks(x)
    left.set_xticklabels([f"{s:.0%} of excess\nclassified vacant" for s in table.index])
    left.set_ylim(0, table["all_eur_m"].max() * 1.2)
    _legend(left, [Patch(facecolor=ORANGE, label="All municipalities"),
                   Patch(facecolor=BLUE, label="Highest price-to-income third only")], loc="upper left")  # fmt: skip
    _panel_title(left, "Extra IMI a year (EUR million)")

    d = (100 * bite.dropna()).clip(upper=100)
    right.hist(d, bins=np.arange(0, d.max() + 1, 1), color=BLUE, zorder=3)
    right.set_ylim(0, right.get_ylim()[1] * 1.15)
    right.axvline(d.median(), color=INK, lw=1.2, zorder=4)
    right.annotate(f"median {d.median():.1f}%", (d.median(), right.get_ylim()[1]), xytext=(6, -12),
                   textcoords="offset points", fontsize=9, color=INK)  # fmt: skip
    right.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    _panel_title(right, f"Extra IMI as a share of a year's rent, {len(d)} municipalities")
    low, high = table["all_eur_m"].iloc[[0, -1]]
    return style.finish(
        fig,
        f"Tripling IMI on excess vacant homes raises {low:,.0f} to {high:,.0f} EUR m ({100 * low / national_imi_eur_m:.0f}% to {100 * high / national_imi_eur_m:.0f}% of IMI) "
        f"and costs the owner {d.median():.0f}% of a year's rent",
        "Excess vacant dwellings (above 5% of the stock, census 2021) x typical IMI of the municipality x 2 extra times the rate; calibrated to national IMI revenue, 2024",
        "Source: INE (census, prices, rents), Autoridade Tributária (rates), Eurostat (IMI revenue), own calculations. Accounting only: no response by owners.",
        head_in=1.3,
        foot_in=0.9,
    )


def funding_gain(result: pd.DataFrame, baseline_rise_years: float) -> Figure:
    """Fall in the end-year price-to-income for each budget and lever, with its 80% range over the draws.

    ``result`` has one row per budget and lever (``funding.gain_for_budget`` plus ``budget``, ``eur_m_a_year`` and
    ``lever``: "extra completions" or "renovated vacant homes"); ``baseline_rise_years`` is the rise of the baseline over
    the horizon, quoted in the title as the yardstick.
    """
    fig, ax = plt.subplots(figsize=(11, 4.8))
    budgets = list(dict.fromkeys(result["budget"]))
    y = np.arange(len(budgets))[::-1]
    for offset, lever, color in (
        (0.19, "extra completions", ORANGE),
        (-0.19, "renovated vacant homes", BLUE),
    ):
        d = result[result["lever"] == lever].set_index("budget").loc[budgets]
        ax.barh(y + offset, d["gain_p50"], 0.36, color=color, zorder=3)
        ax.errorbar(d["gain_p50"], y + offset, xerr=[d["gain_p50"] - d["gain_p10"], d["gain_p90"] - d["gain_p50"]],
                    fmt="none", ecolor=INK_2, elinewidth=1, capsize=3, zorder=4)  # fmt: skip
        for pos, high, value, units in zip(
            y + offset, d["gain_p90"], d["gain_p50"], d["units_a_year"], strict=True
        ):
            ax.annotate(f"{value:.2f} yrs, {units:,.0f} homes a year", (high, pos), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=INK_2)  # fmt: skip
    labels = [
        f"{b}\n{result.loc[result['budget'] == b, 'eur_m_a_year'].iloc[0]:,.0f} EUR m a year"
        for b in budgets
    ]
    ax.set_yticks(y, labels, color=INK_2, fontsize=9.5)
    ax.set_xlim(0, result["gain_p90"].max() * 2.0)
    ax.set_ylim(-0.7, len(budgets) - 0.3)
    ax.set_xlabel(
        "Fall in 2035 price-to-income, years of income (median and 80% range)", color=INK_2
    )
    _legend(ax, [Patch(facecolor=ORANGE, label="Extra completions"),
                 Patch(facecolor=BLUE, label="Renovated vacant homes")], loc="lower right")  # fmt: skip
    best = result[result["budget"].str.startswith("Surcharge, 100%")]["gain_p50"].max()
    return style.finish(
        fig,
        f"Building with the whole vacant-home surcharge cuts 2035 price-to-income by {best:.2f} years of a {baseline_rise_years:.1f}-year rise",
        "Baseline scenario, budgets from 2027 to 2035 at mid unit costs, one lever at a time; behavioural parameters are the simulator's assumptions",
        "Source: simulator (p4_02), surcharge revenue (p3_08), Eurostat (government spending by function), own calculations. Modelled, not estimated.",
        head_in=1.3,
        foot_in=0.9,
    )


def offset_cost(
    offset: pd.DataFrame, labels: dict[str, str], housing_spending_bn: float, rise_years: float
) -> Figure:
    """Yearly cost of cancelling the baseline rise with each supply package, against today's housing spending.

    ``offset`` is ``funding.offset_requirement`` (index: package; ``yearly_cost_bn``, ``yearly_cost_gdp_pct``,
    ``yearly_cost_vs_housing_spending``), ``labels`` maps each package to its axis label, ``housing_spending_bn`` is the
    yearly spending line and ``rise_years`` the rise being cancelled (title).
    """
    fig, ax = plt.subplots(figsize=(11, 4.4))
    d = offset.loc[list(labels)]
    y = np.arange(len(d))[::-1]
    ax.barh(y, d["yearly_cost_bn"], 0.55, color=ORANGE, zorder=3)
    ax.axvline(housing_spending_bn, color=BLUE, lw=1.6, zorder=4)
    ax.annotate(f"housing spending today, {housing_spending_bn:.1f} bn", (housing_spending_bn, len(d) - 0.2), xytext=(6, 0),
                textcoords="offset points", fontsize=8.5, color=BLUE, va="center")  # fmt: skip
    for pos, (_, row) in zip(y, d.iterrows(), strict=True):
        ax.annotate(f"{row['yearly_cost_bn']:.1f} bn a year, {row['yearly_cost_vs_housing_spending']:.1f}x spending, {row['yearly_cost_gdp_pct']:.1f}% of GDP",
                    (row["yearly_cost_bn"], pos), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK_2)  # fmt: skip
    ax.set_yticks(y, list(labels.values()), color=INK_2, fontsize=9.5)
    ax.set_xlim(0, d["yearly_cost_bn"].max() * 1.75)
    ax.set_ylim(-0.6, len(d) + 0.1)
    ax.set_xlabel(
        "Cost a year, 2027-2035, EUR billion (linear extrapolation of the simulator)", color=INK_2
    )
    return style.finish(
        fig,
        f"Cancelling a {rise_years:.1f}-year rise by supply alone would cost at least {d['yearly_cost_bn'].min():.1f} bn a year, "
        f"{d['yearly_cost_vs_housing_spending'].min():.0f} times today's housing spending",
        "Baseline scenario: each package scaled until its fall in 2035 price-to-income equals the baseline rise; arithmetic, not a forecast",
        "Source: simulator (p4_02), Eurostat (GDP, housing spending), own calculations. Far outside the packages tested; unit costs are assumptions.",
        head_in=1.3,
        foot_in=0.9,
    )
