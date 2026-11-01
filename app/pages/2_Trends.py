"""Trend dashboard: national price index and mortgage rates, a municipality against the spread, and group medians."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pthousing.viz import dashboard as D
from pthousing.viz import style

st.set_page_config(page_title="Trends · Portugal's Housing Crisis", layout="wide")

TRANSPARENT = "rgba(0,0,0,0)"
GRID = "rgba(137,135,129,0.25)"
GROUP_COLORS = [style.BLUE, style.ORANGE, style.MUTED, style.INK_2]
DEFAULT_MUNIS = ["Lisboa", "Porto", "Bragança"]


@st.cache_data
def panel() -> pd.DataFrame:
    return D.load_panel()


@st.cache_data
def national() -> pd.DataFrame:
    return D.load_national()


@st.cache_data
def longrun() -> pd.DataFrame:
    return D.load_long_run()


def _alpha(hex_color: str, alpha: float = 0.14) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _layout(fig: go.Figure, title: str, ytitle: str, height: int = 400) -> go.Figure:
    fig.update_layout(
        title=title,
        yaxis_title=ytitle,
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.15),
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    return fig


p, nat = panel(), national()

st.title("Trends")
st.markdown(
    "How prices, rents, income and affordability have moved over time. Each tab looks at the same "
    "question from a different distance: **National** shows the whole country, **Municipality** puts "
    "one or more places against all the others, and **Groups** compares kinds of places (coastal and "
    "inland, urban and rural, tourist and not). Under every chart a short note says what it shows."
)

tab_nat, tab_muni, tab_group = st.tabs(["National", "Municipality", "Groups"])

# ---- national ------------------------------------------------------------------------------------
with tab_nat:
    d = nat.dropna(subset=["hpi_total_b2025"])
    real = d.set_index("period_start")["hpi_total_real_b2025"]
    low = real.idxmin()
    st.markdown(
        "#### House prices since 2009\n"
        "**What this is.** The official house price index of Statistics Portugal (INE) follows what "
        "homes sell for across the country. It is an *index*: the value in 2025 is set to 100, so a "
        "reading of 50 means prices were half of what they are in 2025 and 120 would mean 20% above.\n\n"
        "**Two lines.** The grey *nominal* line is in the euros of each year. The blue *real* line removes "
        "general inflation (everything costing more), so it shows what a home costs compared with other "
        "things you could buy. The gap between the two is inflation. When the real line rises, homes "
        "really became dearer, not just money less valuable."
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=d["period_start"],
            y=d["hpi_total_b2025"],
            name="Nominal",
            line=dict(color=style.MUTED, width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["period_start"],
            y=d["hpi_total_real_b2025"],
            name="Real (2024 euros)",
            line=dict(color=style.BLUE, width=2.5),
        )
    )
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(
        _layout(fig, "House price index, all dwellings (2025 = 100)", "index"),
        width="stretch",
    )
    st.markdown(
        f"**What it shows.** After inflation, house prices fell until **{low.year}** (the years of the "
        f"financial crisis and the 2011-2014 bailout) and have since risen "
        f"**{real.iloc[-1] / real.min():.1f} times** from that low. The nominal line rises more, "
        f"because prices climbed on top of general inflation."
    )

    long = longrun()
    lr = long.set_index("year")["hpi_real_b2015"]
    peak = int(lr.loc[:2012].idxmax())
    low = int(lr.loc[peak:].idxmin())
    pti_s = long.dropna(subset=["price_to_income_b2015"])["price_to_income_b2015"]
    top = "the highest" if pti_s.iloc[-1] >= pti_s.max() else "not the highest"
    st.markdown(
        "#### Thirty years: prices, rents and prices against income\n"
        "**What this is.** The same story over a much longer period, with three lines that all use "
        "2015 = 100 so they can be compared:\n"
        "- **Real house price index** (blue): prices after inflation, as above.\n"
        "- **Real rent index** (orange): what tenants pay, after inflation. It is the rent component of "
        "consumer prices and covers *all* leases, including old ones with regulated rents, so it moves "
        "much more slowly than the rent on a new lease.\n"
        "- **Price to income per head** (dotted): how expensive homes are relative to what people earn. "
        "A rising line means homes are getting harder to afford even if incomes are also rising.\n\n"
        "**The dotted vertical line (2009).** Before 2009 the price series is a compilation by the Bank "
        "for International Settlements (BIS) whose source is not stated; from 2009 it is the INE index. "
        "The two cannot be tested against each other where they join, so treat differences across that "
        "line with about a point of caution."
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=long["year"],
            y=long["hpi_real_b2015"],
            name="Real house price index",
            line=dict(color=style.BLUE, width=2.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=long["year"],
            y=long["rent_real_b2015"],
            name="Real rent index",
            line=dict(color=style.ORANGE, width=2.5),
        )
    )
    pti = long.dropna(subset=["price_to_income_b2015"])
    fig.add_trace(
        go.Scatter(
            x=pti["year"],
            y=pti["price_to_income_b2015"],
            name="Price to income per head",
            line=dict(color=style.INK_2, width=2.5, dash="dot"),
        )
    )
    fig.add_vline(
        x=2009, line_dash="dot", line_color=style.MUTED, annotation_text="series changes source"
    )
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(
        _layout(
            fig, "National prices, rents and price-to-income, 1988 to 2025 (2015 = 100)", "index"
        ),
        width="stretch",
    )
    rent = long.dropna(subset=["rent_real_b2015"]).set_index("year")["rent_real_b2015"]
    st.markdown(
        f"**What it shows.** After inflation, prices peaked in **{peak}**, fell "
        f"**{100 * (1 - lr[low] / lr[peak]):.0f}%** to {low} and are now **{lr.iloc[-1] / lr[low]:.1f} "
        f"times** that low. Real rents moved far less: {100 * (rent.iloc[-1] / rent.loc[low] - 1):+.0f}% "
        f"since {low}, against {100 * (lr.iloc[-1] / lr[low] - 1):+.0f}% for real prices. The OECD "
        f"price-to-income index is {top} in its series (which starts in 1995)."
    )
    st.caption(
        "Source: BIS, INE (house prices, CPI), OECD (rents, price-to-income); own calculations. "
        "Price-to-income uses income per head, not per household."
    )

    rate = nat.dropna(subset=["mortgage_rate_new_lt1y_pct"])
    pay = nat.dropna(subset=["mortgage_payment_100k_eur"])
    r_low = rate.loc[rate["mortgage_rate_new_lt1y_pct"].idxmin()]
    r_now = rate.iloc[-1]
    p_low = pay.loc[pay["period_start"] == r_low["period_start"], "mortgage_payment_100k_eur"]
    p_now = pay["mortgage_payment_100k_eur"].iloc[-1]
    st.markdown(
        "#### The cost of borrowing\n"
        "**Why this matters.** Most buyers borrow. The price of the home is only part of the story: what "
        "a household feels each month is the loan payment, and that depends on the interest rate. The "
        "left chart shows the rate banks charged on new housing loans; the right chart turns that rate "
        "into euros, as the monthly payment on a 100,000 EUR loan repaid over 30 years."
    )
    left, right = st.columns(2)
    fig = go.Figure(
        go.Scatter(
            x=rate["period_start"],
            y=rate["mortgage_rate_new_lt1y_pct"],
            name="New loans, agreed rate",
            line=dict(color=style.BLUE, width=2.5),
        )
    )
    left.plotly_chart(
        _layout(fig, "Interest rate on new housing loans (%)", "%", 340), width="stretch"
    )
    fig = go.Figure(
        go.Scatter(
            x=pay["period_start"],
            y=pay["mortgage_payment_100k_eur"],
            name="Monthly payment",
            line=dict(color=style.ORANGE, width=2.5),
        )
    )
    fig.update_yaxes(rangemode="tozero")
    right.plotly_chart(
        _layout(fig, "Monthly payment on a 100,000 EUR loan over 30 years", "EUR", 340),
        width="stretch",
    )
    if len(p_low):
        st.markdown(
            f"**What it shows.** The rate was lowest in **{r_low['period_start'].year}** "
            f"({r_low['mortgage_rate_new_lt1y_pct']:.1f}%), when the payment on 100,000 EUR was about "
            f"**{p_low.iloc[0]:,.0f} EUR a month**. It is now {r_now['mortgage_rate_new_lt1y_pct']:.1f}% "
            f"and the same loan costs about **{p_now:,.0f} EUR a month**, "
            f"{100 * (p_now / p_low.iloc[0] - 1):+.0f}% more for the same amount borrowed. Homes also cost "
            "more, so the loan needed is larger too: higher prices and higher rates squeeze affordability "
            "together."
        )
    st.caption(
        "Source: Banco de Portugal (BPstat, agreed rate on new housing loans, floating or fixed for under a "
        "year); own calculations (standard repayment formula). Quarterly."
    )

# ---- municipality --------------------------------------------------------------------------------
with tab_muni:
    st.markdown(
        "**What this is.** One measure over time for the places you pick, set against all 308 "
        "municipalities. Choose a measure and up to six municipalities below.\n\n"
        "**How to read the chart.** The *dotted line* is the median municipality: half of the "
        "municipalities are above it and half below. The *grey band* is where the middle 80% sit "
        "(from the 10th to the 90th percentile), so a line far above the band belongs to a place that "
        "is unusual. A place's *own* line shows whether it follows the typical path or departs from it."
    )
    names = sorted(p["muni_name"].dropna().unique())
    c1, c2 = st.columns([1, 2])
    column = c1.selectbox(
        "Indicator",
        [c for c in D.INDICATORS if len(D.years_with_data(p, c)) > 1],
        format_func=lambda c: D.INDICATORS[c].label,
        key="muni-indicator",
    )
    chosen = c2.multiselect(
        "Municipalities",
        names,
        default=[m for m in DEFAULT_MUNIS if m in names],
        max_selections=6,
    )
    ind = D.INDICATORS[column]
    band = D.trend_band(p, column)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=band.index,
            y=band["q90"],
            mode="lines",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=band.index,
            y=band["q10"],
            mode="lines",
            fill="tonexty",
            line=dict(width=0),
            fillcolor=_alpha(style.MUTED, 0.25),
            name="10th to 90th percentile",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=band.index,
            y=band["q50"],
            name="Median municipality",
            line=dict(color=style.INK_2, width=2.5, dash="dot"),
        )
    )
    palette = [style.BLUE, style.ORANGE, "#2a9d8f", "#8e5ea2", "#c49a00", "#d6336c"]
    for color, name in zip(palette, chosen, strict=False):
        s = p[p["muni_name"] == name].set_index("year")[column].dropna()
        fig.add_trace(go.Scatter(x=s.index, y=s, name=name, line=dict(color=color, width=2.5)))
    fig.update_xaxes(dtick=2)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(_layout(fig, f"{ind.label} ({ind.unit})", ind.unit, 460), width="stretch")
    st.markdown(f"**What is measured.** {ind.note} Unit: {ind.unit}.")
    st.caption(
        f"The band covers every municipality with a value that year ({int(band['n'].min())} to "
        f"{int(band['n'].max())}). Source: INE, Banco de Portugal, AT, AIMA; own calculations."
    )
    if chosen:
        rows = [
            {
                "Municipality": "Median municipality",
                f"{band.index[0]}": D.value_text(ind, band["q50"].iloc[0]),
                f"{band.index[-1]}": D.value_text(ind, band["q50"].iloc[-1]),
                "Change": f"{100 * (band['q50'].iloc[-1] / band['q50'].iloc[0] - 1):+.0f}%",
            }
        ]
        first, last = band.index[0], band.index[-1]
        for name in chosen:
            s = p[p["muni_name"] == name].set_index("year")[column]
            v0, v1 = s.get(first), s.get(last)
            ok = pd.notna(v0) and pd.notna(v1) and v0 != 0
            rows.append(
                {
                    "Municipality": name,
                    f"{first}": D.value_text(ind, v0) if pd.notna(v0) else "no value",
                    f"{last}": D.value_text(ind, v1) if pd.notna(v1) else "no value",
                    "Change": f"{100 * (v1 / v0 - 1):+.0f}%" if ok else "n/a",
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption(
            f"The table compares {first} with {last} for the chosen measure. Change is the percentage "
            "change of the value; the first row is the median municipality for reference."
        )

# ---- groups --------------------------------------------------------------------------------------
with tab_group:
    st.markdown(
        "**What this is.** Portugal's 308 municipalities are very different, so an average across all of "
        "them hides a lot. Here they are split into *kinds of places*, and for each kind the chart "
        "follows the **median** (the middle municipality of the group: half are above it, half below). "
        "Choose a measure and a way of grouping; the box below explains what each group means and how "
        "many municipalities it holds.\n\n"
        "Every line is built from the *same* municipalities in every year, so a line only moves because "
        "values changed, not because places entered or left the sample."
    )
    c1, c2 = st.columns(2)
    column = c1.selectbox(
        "Measure",
        [c for c in D.INDICATORS if len(D.years_with_data(p, c)) > 1],
        format_func=lambda c: D.INDICATORS[c].label,
        key="group-indicator",
    )
    by = c2.radio(
        "Group municipalities by",
        list(D.GROUP_GUIDE),
        format_func=lambda g: D.GROUP_GUIDE[g]["title"],
    )
    ind = D.INDICATORS[column]
    guide = D.GROUP_GUIDE[by]
    trend = D.group_trend(p, column, by)
    if trend.empty:
        st.info("No municipality has a value in every year for this measure.")
    else:
        counts = D.group_counts(p, column, by)
        with st.container(border=True):
            st.markdown(f"**How the groups are defined.** {guide['intro']}")
            for raw in trend.columns:
                label, meaning = guide["classes"][raw]
                st.markdown(f"- **{label}** ({counts[raw]} municipalities): {meaning}")
            st.caption(
                "The counts are the municipalities with a value in every year of this measure. "
                "Municipalities without a known class (the islands, for tourism) are left out."
            )
        fig = go.Figure()
        for color, group in zip(GROUP_COLORS, trend.columns, strict=False):
            fig.add_trace(
                go.Scatter(
                    x=trend.index,
                    y=trend[group],
                    name=f"{D.class_label(by, group)} ({counts[group]})",
                    line=dict(color=color, width=2.5),
                )
            )
        fig.update_xaxes(dtick=2)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(
            _layout(fig, f"{ind.label} ({ind.unit}): median of each group", ind.unit, 440),
            width="stretch",
        )
        first, last = trend.index[0], trend.index[-1]
        change = 100 * (trend.loc[last] / trend.loc[first] - 1)
        top, bottom = trend.loc[last].idxmax(), trend.loc[last].idxmin()
        most, least = change.idxmax(), change.idxmin()
        st.markdown(
            f"**What it shows.** In {last} the median {ind.label.lower()} was highest in "
            f"**{D.class_label(by, top)}** places ({D.value_text(ind, trend.loc[last, top])}) and lowest in "
            f"**{D.class_label(by, bottom)}** places ({D.value_text(ind, trend.loc[last, bottom])}). "
            f"From {first} to {last} the median of {D.class_label(by, most)} places changed by "
            f"{change[most]:+.0f}%, against {change[least]:+.0f}% for {D.class_label(by, least)} places. "
            "Lines that move apart mean the groups are on different paths; lines that move together "
            "mean the trend is shared."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Group": [D.class_label(by, g) for g in trend.columns],
                    "Municipalities": [int(counts[g]) for g in trend.columns],
                    f"Median in {first}": [D.value_text(ind, v) for v in trend.loc[first]],
                    f"Median in {last}": [D.value_text(ind, v) for v in trend.loc[last]],
                    "Change of the median": [f"{change[g]:+.0f}%" for g in trend.columns],
                }
            ),
            hide_index=True,
        )
        st.caption(
            "These groups are the project's own simple rules (`data/external/muni_typology.csv`), not the "
            "official INE typology of areas. Coast comes from the municipal boundary file; density is "
            "residents per km² in 2021; the tourist flag uses today's registry of short-term rentals, which "
            "lists surviving registrations only and is applied to every year. A group's median says "
            "nothing about the cause of its trend. Source: INE, AT, RNAL, CAOP; own calculations."
        )
