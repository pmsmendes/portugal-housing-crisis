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


# ---- regression coefficients ----------------------------------------------------------------------


def coef_ladder(
    table: pd.DataFrame, labels: dict[str, str], main: str, compare: str, outcome: str
) -> Figure:
    """Effect of one within-standard-deviation of each driver on ``outcome`` (in %), across specifications.

    ``table`` is the concatenated output of ``panel.coef_table`` for log outcomes (``coef`` x 100 is then a
    percentage). One panel per driver, one row per specification; ``main`` is blue, ``compare`` orange and the
    other specifications grey. The 95% interval is drawn around the point.
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
        ax.xaxis.set_major_locator(mticker.MaxNLocator(4, integer=True))
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: "0" if abs(v) < 1e-9 else f"{v:+.0f}%")
        )
    main_rows = table[table["spec"] == main]
    top = main_rows.loc[main_rows["coef_per_sd"].abs().idxmax()]
    fig = style.finish(
        fig,
        f"One standard deviation of the strongest driver ({labels[top['term']].split(' (')[0].lower()}) "
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
