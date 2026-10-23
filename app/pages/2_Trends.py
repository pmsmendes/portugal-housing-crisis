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
    "How prices, rents, income and affordability have moved: first the national picture, then a "
    "municipality against all the others, then groups of municipalities."
)

tab_nat, tab_muni, tab_group = st.tabs(["National", "Municipality", "Groups"])

# ---- national ------------------------------------------------------------------------------------
with tab_nat:
    d = nat.dropna(subset=["hpi_total_b2025"])
    real = d.set_index("period_start")["hpi_total_real_b2025"]
    low = real.idxmin()
    st.markdown(
        f"After inflation, house prices fell until **{low.year}** and have since risen "
        f"**{real.iloc[-1] / real.min():.1f}x** (INE house price index, 2025 = 100)."
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

    long = longrun()
    lr = long.set_index("year")["hpi_real_b2015"]
    peak = int(lr.loc[:2012].idxmax())
    low = int(lr.loc[peak:].idxmin())
    pti_s = long.dropna(subset=["price_to_income_b2015"])["price_to_income_b2015"]
    top = "the highest" if pti_s.iloc[-1] >= pti_s.max() else "not the highest"
    st.markdown(
        f"**Thirty years.** After inflation, prices peaked in **{peak}**, fell "
        f"**{100 * (1 - lr[low] / lr[peak]):.0f}%** to {low} and are now **{lr.iloc[-1] / lr[low]:.1f}x** that low; "
        f"the OECD price-to-income index is {top} in its series (from 1995)."
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
    st.caption(
        "Source: BIS, INE (house prices, CPI), OECD (rents, price-to-income); own calculations. Before 2009 the price "
        "index is a BIS compilation whose join with INE's cannot be tested; price-to-income uses income per head."
    )

    left, right = st.columns(2)
    rate = nat.dropna(subset=["mortgage_rate_new_lt1y_pct"])
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
    pay = nat.dropna(subset=["mortgage_payment_100k_eur"])
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
    st.caption(
        "Source: INE (house price index, CPI), Banco de Portugal (BPstat); own calculations. Quarterly."
    )

# ---- municipality --------------------------------------------------------------------------------
with tab_muni:
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
    st.caption(
        f"{ind.note} The band covers every municipality with a value that year ({int(band['n'].min())} to "
        f"{int(band['n'].max())}). Source: INE, Banco de Portugal, AT, AIMA; own calculations."
    )
    if chosen:
        first, last = band.index[0], band.index[-1]
        rows = []
        for name in chosen:
            s = p[p["muni_name"] == name].set_index("year")[column].dropna()
            if len(s) > 1:
                rows.append(
                    {
                        "Municipality": name,
                        f"{s.index[0]}": ind.fmt.format(s.iloc[0]),
                        f"{s.index[-1]}": ind.fmt.format(s.iloc[-1]),
                        "Change": f"{100 * (s.iloc[-1] / s.iloc[0] - 1):+.0f}%"
                        if s.iloc[0]
                        else "n/a",
                    }
                )
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True)

# ---- groups --------------------------------------------------------------------------------------
with tab_group:
    st.markdown(
        "Medians of groups of municipalities, using the same municipalities every year. "
        "Mainland only for tourism (the short-term rental registry covers the mainland)."
    )
    c1, c2 = st.columns(2)
    column = c1.selectbox(
        "Indicator",
        [c for c in D.INDICATORS if len(D.years_with_data(p, c)) > 1],
        format_func=lambda c: D.INDICATORS[c].label,
        key="group-indicator",
    )
    by = c2.radio("Group by", list(D.GROUPS), format_func=D.GROUPS.get, horizontal=True)
    ind = D.INDICATORS[column]
    trend = D.group_trend(p, column, by)
    if trend.empty:
        st.info("No municipality has a value in every year for this indicator.")
    else:
        counts = (
            p.drop_duplicates("muni_code")
            .loc[lambda x: x["muni_code"].isin(p.dropna(subset=[column])["muni_code"])]
            .groupby(by)["muni_code"]
            .count()
        )
        fig = go.Figure()
        for color, group in zip(GROUP_COLORS, trend.columns, strict=False):
            fig.add_trace(
                go.Scatter(
                    x=trend.index,
                    y=trend[group],
                    name=f"{group}",
                    line=dict(color=color, width=2.5),
                )
            )
        fig.update_xaxes(dtick=2)
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(
            _layout(
                fig, f"{ind.label} ({ind.unit}), median by {D.GROUPS[by].lower()}", ind.unit, 440
            ),
            width="stretch",
        )
        first, last = trend.index[0], trend.index[-1]
        change = (100 * (trend.loc[last] / trend.loc[first] - 1)).round(0)
        st.dataframe(
            pd.DataFrame(
                {
                    "Group": trend.columns,
                    f"{first}": [ind.fmt.format(v) for v in trend.loc[first]],
                    f"{last}": [ind.fmt.format(v) for v in trend.loc[last]],
                    "Change of the median": [f"{v:+.0f}%" for v in change],
                }
            ),
            hide_index=True,
        )
        st.caption(
            "Coast, density and tourism classes are own proxies (`data/external/muni_typology.csv`), "
            "not the INE parish typology. The tourist flag describes today's registry. Source: INE, AT, RNAL, CAOP; own calculations."
        )
