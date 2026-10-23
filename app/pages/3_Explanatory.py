"""Explanatory dashboard: what accounts for where affordability worsened (phase 2) and what the one policy test could say (phase 3)."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pthousing.analysis.panel import LABELS
from pthousing.viz import dashboard as D
from pthousing.viz import style

st.set_page_config(page_title="Explanatory · Portugal's Housing Crisis", layout="wide")

TRANSPARENT = "rgba(0,0,0,0)"
GRID = "rgba(137,135,129,0.25)"
START, END = 2016, 2024
DIMENSIONS = {"coast_class": "Coast", "density_class": "Density", "tourist": "Tourism"}


@st.cache_data
def panel() -> pd.DataFrame:
    return D.load_panel()


@st.cache_data
def drivers() -> pd.DataFrame:
    return D.driver_frame(panel(), START, END)


@st.cache_data
def table(phase: str, name: str) -> pd.DataFrame:
    return D.read_table(phase, name)


def _style(fig: go.Figure, title: str, height: int = 380) -> go.Figure:
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


ladder = table("p2", "synthesis_r2_ladder")
segments = table("p2", "segment_summary")
first, last = ladder.iloc[0], ladder.iloc[-1]

st.title("What explains where affordability worsened?")
st.markdown(
    f"Between {START} and {END} the median municipality's price-to-income rose about 19%, driven by prices, "
    "not incomes. The question here is *where* it rose most and what goes with that. Everything on this page "
    "is an **adjusted association, not a causal effect**; the one design that could identify a cause "
    "(municipal tax cuts) did not pass its checks (last tab)."
)
cols = st.columns(3)
cols[0].metric("Explained by geography", f"{100 * first['r2']:.0f}%", help=first["block"])
cols[0].caption("District, coast and density classes together")
cols[1].metric(
    "Added by every driver together",
    f"{100 * (last['r2'] - first['r2']):.1f} points",
    help="Demand, supply, tourism and second homes, entered after geography.",
)
cols[1].caption("Demand, supply, tourism and second homes")
cols[2].metric(
    "Municipalities compared",
    f"{int(last['n_obs'])}",
    help="Mainland municipalities with a value in both years.",
)
cols[2].caption(f"Change in price-to-income {START} to {END}")

tab_where, tab_drivers, tab_reg, tab_policy = st.tabs(
    ["Where", "Drivers", "Regressions", "A policy test"]
)

# ---- where ---------------------------------------------------------------------------------------
with tab_where:
    left, right = st.columns(2)
    # variance explained ladder
    lad = ladder.copy()
    lad["label"] = lad["block"].str.replace(r" \(.*\)", "", regex=True)
    fig = go.Figure(
        go.Bar(
            y=lad["label"],
            x=100 * lad["r2"],
            orientation="h",
            marker_color=[style.BLUE] + [style.MUTED] * (len(lad) - 1),
            text=[
                f"{100 * r:.0f}%" + ("" if i == 0 else f"  (+{100 * a:.1f} pts)")
                for i, (r, a) in enumerate(zip(lad["r2"], lad["r2_added"], strict=True))
            ],
            textposition="outside",
            hovertemplate="%{y}: %{x:.1f}% explained<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0, 85], ticksuffix="%")
    left.plotly_chart(
        _style(fig, "Share of the variation explained, as blocks are added"),
        width="stretch",
    )
    left.caption(
        "Cumulative R² of the change in price-to-income across mainland municipalities. Order matters when blocks "
        "overlap: the drivers alone explain 35%, but they mostly describe the same dense coastal places."
    )

    dim = right.radio("Compare", list(DIMENSIONS), format_func=DIMENSIONS.get, horizontal=True)
    seg = segments[segments["dimension"].str.startswith(dim.split("_")[0])]
    seg = seg.assign(
        group=seg["group"].str.capitalize(),
        label=lambda x: x["group"] + " (" + x["municipalities_n"].astype(str) + ")",
    )
    fig = go.Figure(
        [
            go.Bar(
                name="Price per m² (real)",
                x=seg["label"],
                y=seg["price_real_change_pct"],
                marker_color=style.BLUE,
            ),
            go.Bar(
                name="Income (real)",
                x=seg["label"],
                y=seg["income_real_change_pct"],
                marker_color=style.MUTED,
            ),
            go.Bar(
                name="Price-to-income",
                x=seg["label"],
                y=seg["pti_change_pct"],
                marker_color=style.ORANGE,
            ),
        ]
    )
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(ticksuffix="%")
    right.plotly_chart(
        _style(fig, f"Change {START} to {END}, median municipality, by {DIMENSIONS[dim].lower()}"),
        width="stretch",
    )
    right.caption(
        "Number of municipalities in brackets. Income grew by a similar amount everywhere; prices did not."
    )

    st.markdown(
        "**Neighbours resemble each other, but that is regional, not a spillover.** Global Moran's I of "
        "price-to-income is 0.63 to 0.76 (strong clustering). Within a region no clustering is left, and "
        "last year's neighbours predict a municipality about as well as next year's (a placebo), so there is "
        "no evidence that price pressure spreads from one municipality to the next (`p2_01`, `p2_03`)."
    )

# ---- drivers -------------------------------------------------------------------------------------
with tab_drivers:
    d = drivers()
    c1, c2 = st.columns([2, 1])
    key = c1.selectbox("Candidate explanation", list(D.DRIVERS), format_func=D.DRIVERS.get)
    colour = c2.radio(
        "Colour by", list(DIMENSIONS), format_func=DIMENSIONS.get, horizontal=True, key="drv-colour"
    )
    log_x = key == "density_per_km2"
    dd = d.dropna(subset=[key, "pti_change_pct"])
    dd = dd[dd[key] > 0] if log_x else dd
    fig = px.scatter(
        dd,
        x=key,
        y="pti_change_pct",
        color=colour,
        hover_name="muni_name",
        hover_data={"district": True, key: ":,.1f", "pti_change_pct": ":.0f", colour: False},
        log_x=log_x,
        color_discrete_sequence=[style.BLUE, style.ORANGE, style.MUTED, style.INK_2],
        labels={
            key: D.DRIVERS[key],
            "pti_change_pct": f"Change in price-to-income {START}-{END} (%)",
            colour: DIMENSIONS[colour],
        },
    )
    line = D.fit_line(dd[key], dd["pti_change_pct"], log_x=log_x)
    fig.add_trace(
        go.Scatter(
            x=line["x"],
            y=line["y"],
            mode="lines",
            name="Fitted line",
            line=dict(color=style.INK_2, dash="dot", width=2),
        )
    )
    fig.update_traces(
        marker=dict(size=8, opacity=0.8, line=dict(width=0.5, color="white")),
        selector=dict(mode="markers"),
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(_style(fig, "Each dot is a mainland municipality", 480), width="stretch")
    st.caption(
        f"Correlation {line['r']:+.2f} across {line['n']} municipalities. A raw correlation across places mixes the "
        "effect of a driver with everything else that differs between places (coast, density, jobs): it "
        "shows what goes with the rise, not what causes it. Source: INE, AIMA, census 2011 and 2021; own calculations."
    )

# ---- regressions ---------------------------------------------------------------------------------
with tab_reg:
    fe = table("p2", "fe_regressions_pti")
    specs = [
        s
        for s in fe["spec"].unique()
        if s.startswith(("Municipality", "Errors", "Drivers", "Without", "Through"))
    ]
    spec = st.selectbox(
        "Specification",
        specs,
        index=specs.index("Municipality + region-year effects")
        if "Municipality + region-year effects" in specs
        else 0,
        help="'Region-year effects' compare municipalities within the same NUTS 3 region and year.",
    )
    t = fe[fe["spec"] == spec].copy()
    t["label"] = t["term"].map(LABELS).fillna(t["term"])
    t["pct"] = 100 * t["coef_per_sd"]
    t["lo"] = 100 * t["sd_within"] * t["ci_low"]
    t["hi"] = 100 * t["sd_within"] * t["ci_high"]
    fig = go.Figure(
        go.Scatter(
            x=t["pct"],
            y=t["label"],
            mode="markers",
            marker=dict(size=10, color=[style.BLUE if p < 0.05 else style.MUTED for p in t["p"]]),
            error_x=dict(
                type="data",
                symmetric=False,
                array=t["hi"] - t["pct"],
                arrayminus=t["pct"] - t["lo"],
                color=style.MUTED,
            ),
            customdata=t["p"],
            hovertemplate="%{y}<br>%{x:+.1f}% (p = %{customdata:.3f})<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color=style.INK_2, line_width=1)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(ticksuffix="%")
    st.plotly_chart(
        _style(
            fig,
            "Effect on price-to-income of one within-municipality standard deviation of each driver",
            360,
        ),
        width="stretch",
    )
    st.caption(
        f"Fixed-effects regression of log price-to-income, {int(t['n_obs'].iloc[0]):,} municipality-years in "
        f"{int(t['n_munis'].iloc[0])} municipalities, 95% intervals, errors clustered. Blue: p < 0.05. "
        "Foreign residents are an association with where residence titles are issued, not an effect of immigrants; "
        "supply responds to prices as well as the reverse. Rental (short-term) controls are in the mainland specifications of `p2_02`."
    )
    st.dataframe(
        t[["label", "pct", "lo", "hi", "p"]]
        .rename(
            columns={
                "label": "Driver",
                "pct": "Effect (%)",
                "lo": "Low (%)",
                "hi": "High (%)",
                "p": "p-value",
            }
        )
        .round(3),
        hide_index=True,
    )

# ---- policy test ---------------------------------------------------------------------------------
with tab_policy:
    st.markdown(
        "**Did cutting the municipal property tax (IMI) raise prices?** In theory a lasting tax cut is capitalised "
        "into prices. The test compares prices around municipal rate cuts with the year before the cut. It is "
        "**inconclusive**: the estimates before the cut already differ (the pre-trend test is rejected), and the "
        "interval after the cut contains both zero and full capitalisation."
    )
    ev = table("p3", "event_study_main")
    ev = ev[(ev["version"] == "dose") & (ev["estimator"] == "stacked regression")].sort_values("k")
    zero = pd.DataFrame({"k": [-1], "coef": [0.0], "ci_low": [0.0], "ci_high": [0.0]})
    ev = pd.concat([ev, zero]).sort_values("k")
    power = table("p3", "power")
    bench = float(power["full_capitalisation_mid_pct"].iloc[0])
    fig = go.Figure(
        go.Scatter(
            x=ev["k"],
            y=100 * ev["coef"],
            mode="markers",
            marker=dict(size=10, color=style.BLUE),
            error_y=dict(
                type="data",
                symmetric=False,
                array=100 * (ev["ci_high"] - ev["coef"]),
                arrayminus=100 * (ev["coef"] - ev["ci_low"]),
                color=style.BLUE,
            ),
            name="Stacked event study",
        )
    )
    fig.add_hline(y=0, line_color=style.INK_2, line_width=1)
    fig.add_hline(
        y=bench,
        line_dash="dash",
        line_color=style.ORANGE,
        annotation_text="full capitalisation",
        annotation_position="top left",
    )
    fig.update_xaxes(title="Years since the cut (reference: year before)", dtick=1)
    fig.update_yaxes(title="Real price per m², % per 0.01 pp of rate cut", ticksuffix="%")
    st.plotly_chart(_style(fig, "Prices around municipal IMI rate cuts", 400), width="stretch")
    st.caption(
        "Effect on the real price per m² per 0.01 percentage point of cut, 95% intervals clustered by municipality "
        f"(`p3_02`). The dashed line is what full capitalisation of the tax saving would imply ({bench:.2f}% per 0.01 pp). "
        f"The data are too noisy to tell: the smallest effect this design could detect is {power['detectable_over_benchmark'].iloc[0]:.0f} "
        "times the benchmark one year after the cut. Phase 4 therefore treats capitalisation as unknown, anywhere from none to full."
    )
