"""Explanatory dashboard: what accounts for where affordability worsened (phase 2) and what the one policy test could say (phase 3)."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from pthousing.analysis.panel import LABELS
from pthousing.viz import dashboard as D
from pthousing.viz import style

st.set_page_config(page_title="Explanatory · Portugal's Housing Crisis", layout="wide")

TRANSPARENT = "rgba(0,0,0,0)"
GRID = "rgba(137,135,129,0.25)"
START, END = 2016, 2024
DIMENSIONS = {by: guide["title"] for by, guide in D.GROUP_GUIDE.items()}


def _short(by: str) -> str:
    """'coast', 'density' or 'tourism' for a chart title."""
    return D.GROUP_GUIDE[by]["title"].split(":")[0].lower()


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
with st.container(border=True):
    st.markdown(
        "**How to read this page**\n"
        f"- **The question.** Price-to-income (years of income needed to buy a home) rose in the typical "
        f"municipality between {START} and {END}, but by very different amounts from place to place. "
        "Which places saw the biggest rises, and which factors go with that?\n"
        "- **Association, not cause.** When a factor *goes with* the rise, places with more of it saw "
        "bigger rises. That does not prove it caused them: coast, jobs or wealth may drive both.\n"
        '- **"Variation explained" (R²).** A percentage from 0% to 100%: how much of the *differences '
        "between municipalities* a set of factors accounts for. 0% means they tell you nothing; "
        "100% means they predict every municipality exactly.\n"
        "- **The five tabs.** *Where*: which kinds of place rose most. *Drivers*: supply, rents and "
        "other factors one by one. *Regressions*: the same factors tested together and followed over "
        "time. *Wages, rates and credit*: the national picture. *A policy test*: whether cutting a "
        "property tax moved prices, and what the money at stake is."
    )

cols = st.columns(3)
cols[0].metric("Explained by geography", f"{100 * first['r2']:.0f}%", help=first["block"])
cols[0].caption(
    f"of the differences between municipalities in how much price-to-income rose {START}-{END}, "
    "knowing only district, coast and density class"
)
cols[1].metric(
    "Added by every driver together",
    f"{100 * (last['r2'] - first['r2']):.1f} points",
    help="Demand, supply, tourism and second homes, entered after geography.",
)
cols[1].caption(
    "percentage points of extra variation explained by demand (immigration, population), supply "
    "(building), tourism and second homes once geography is known: almost nothing"
)
cols[2].metric(
    "Municipalities compared",
    f"{int(last['n_obs'])}",
    help="Mainland municipalities with a value in both years.",
)
cols[2].caption(
    f"mainland municipalities with a price-to-income in both {START} and {END} (the islands and places "
    "without a published price are left out)"
)

tab_where, tab_drivers, tab_reg, tab_macro, tab_policy = st.tabs(
    ["Where", "Drivers", "Regressions", "Wages, rates and credit", "A policy test"]
)

# ---- where ---------------------------------------------------------------------------------------
with tab_where:
    st.markdown(
        "**What this tab answers: where did affordability get worse?** The left chart asks how much of "
        "the differences between municipalities can be accounted for by their location, and how much "
        "more is accounted for when other factors are added. The right chart shows the same rise "
        "split by kind of place, so you can see it for yourself."
    )
    st.markdown(
        f"**Left chart, how to read it.** Each bar is the share of the differences between municipalities "
        f"(in how much price-to-income rose) accounted for by everything listed *up to and including* that "
        f"bar. Geography alone accounts for {100 * first['r2']:.0f}%. Each further bar adds the small "
        f"amount written in parentheses, in percentage points (pts): {', '.join(f'{b.split(" (")[0].lower()} +{100 * a:.1f}' for b, a in zip(ladder['block'][1:], ladder['r2_added'][1:], strict=True))}. "
        "The order matters: factors that mostly describe the same dense coastal places add little once "
        "geography is already in."
    )
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
        group=seg["group"].map(lambda g: D.class_label(dim, g)),
        label=lambda x: x["group"] + " (" + x["municipalities_n"].astype(str) + ")",
    )
    with right.container(border=True):
        st.markdown(f"**{DIMENSIONS[dim]}.** {D.GROUP_GUIDE[dim]['intro']}")
        for label, meaning in D.GROUP_GUIDE[dim]["classes"].values():
            st.markdown(f"- **{label}:** {meaning}")
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
        _style(fig, f"Change {START} to {END}, median municipality, by {_short(dim)}"),
        width="stretch",
    )
    right.markdown(
        "**Right chart, how to read it.** For each kind of place the three bars give the change between "
        f"{START} and {END} of the *middle* municipality of the group, in percent: the real price per m² "
        "(blue, after inflation), real household income (gray) and price-to-income (orange, which is "
        "prices relative to income). Where the blue bar towers over the gray one, homes got more expensive "
        "much faster than incomes."
    )
    right.caption(
        "Number of municipalities in parentheses. Income grew by a similar amount everywhere; prices did not."
    )

    st.markdown(
        "**Neighbors resemble each other, but that is regional, not a spillover.** Nearby municipalities "
        "have similar price-to-income: the statistic that measures this (global Moran's I) is 0.63 to "
        "0.76, where 0 would mean no pattern and 1 a perfect one. But once the region is taken into "
        "account no clustering is left. As a further check, last year's neighbors predict a "
        "municipality about as well as *next* year's (which cannot be a cause), so there is no evidence "
        "that price pressure spreads from one municipality to the next (`p2_01`, `p2_03`)."
    )

# ---- drivers -------------------------------------------------------------------------------------
with tab_drivers:
    st.markdown(
        "**What this tab answers: do the usual suspects go with where prices rose?** Pick a candidate "
        "explanation (density, immigration, building, second homes, empty homes) and see it against the "
        "rise in price-to-income, one dot per municipality. Below, two closer looks: how much of what "
        "is built ends up in the dwelling count (supply), and what goes with the rise in rents."
    )
    st.markdown(
        "**Chart below, how to read it.** Each dot is a mainland municipality. Left to right is the "
        "candidate explanation you picked; bottom to top is how much its price-to-income rose between "
        f"{START} and {END}, in percent. The dotted line is the overall tilt of the cloud: if it rises, "
        "places with more of the factor saw bigger rises. The *correlation* under the chart summarizes "
        "that tilt from -1 (opposite) through 0 (no relation) to +1 (perfect). Colors show the kind of "
        "place, which often explains the pattern better than the factor itself."
    )
    d = drivers()
    c1, c2 = st.columns([2, 1])
    key = c1.selectbox("Candidate explanation", list(D.DRIVERS), format_func=D.DRIVERS.get)
    colour = c2.radio(
        "Color by", list(DIMENSIONS), format_func=DIMENSIONS.get, horizontal=True, key="drv-colour"
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

    st.subheader("Supply: how much of what is built shows up in the dwelling count")
    stock_nat = table("p2", "dwelling_stock_national").set_index("measure")
    stock_ret = table("p2", "dwelling_stock_retention_by_class")
    stock_path = table("p2", "dwelling_stock_path").dropna(subset=["growth_pct"])
    st.markdown(
        "**The question.** Every year builders complete new homes, but the number of homes in the "
        "country does not simply rise by that much: some are demolished, merged, or converted to other "
        "uses. Every ten years the census counts all dwellings, which lets us compare the *net* change of "
        "the count with the new homes completed in between.\n\n"
        "**The measure: dwellings added per completion.** Above 1 means the count grew by more than what "
        "was completed (for example through conversions, split dwellings or a more complete census); below 1 "
        "means part of what was built replaced homes that disappeared, or the count fell. "
        "The gap is a residual, not an estimate of demolitions or conversions. The ratio was not "
        "stable: more than one in the boom, less than one since."
    )
    early, late = stock_nat.loc["retention", "2002-2011"], stock_nat.loc["retention", "2012-2021"]
    a, b, c = st.columns(3)
    a.metric(
        "Count change, 2011-21",
        f"+{stock_nat.loc['net_addition_n', '2012-2021']:,.0f}",
        f"{stock_nat.loc['completions_n', '2012-2021']:,.0f} completed",
        delta_color="off",
        help="Net change of the census count of dwellings against the new family dwellings completed in 2012-2021.",
    )
    b.metric(
        "Added per completion",
        f"{late:.2f}",
        f"{early:.2f} in 2002-2011",
        delta_color="off",
        help="Net change of the census count over the dwellings completed in the decade; 2012-2021 shown, 2002-2011 below it.",
    )
    c.metric(
        "Stock in 2025",
        f"{stock_path['stock_n'].iloc[-1] / 1e6:.2f} million",
        f"up to {stock_path['stock_high_n'].iloc[-1] / 1e6:.2f} million",
        delta_color="off",
        help="The 2021 count rolled along completions at the retention of 2012-2021; the upper figure uses that of 2002-2011.",
    )
    st.markdown(
        "**Charts below, how to read them.** *Left:* for each kind of place, the gray dot is "
        "2002-2011 and the blue dot 2012-2021; the dotted vertical line is 1.0 (every completion adds one "
        "dwelling to the count). A blue dot far left of its gray dot means the count stopped following "
        "building. *Right:* the yearly growth of the national stock of dwellings, in percent, rolled "
        "forward from the censuses; the shaded band shows the range if the earlier or the later "
        "decade's ratio applied."
    )
    left, right = st.columns(2)
    ret = stock_ret.sort_values("retention_2012_2021")
    fig = go.Figure()
    for _, row in ret.iterrows():
        fig.add_shape(
            type="line",
            x0=row["retention_2002_2011"],
            x1=row["retention_2012_2021"],
            y0=row["segment"],
            y1=row["segment"],
            line=dict(color=style.MUTED, width=3),
        )
    for col, name, color, where in (
        ("retention_2002_2011", "2002-2011", style.MUTED, "bottom center"),
        ("retention_2012_2021", "2012-2021", style.BLUE, "top center"),
    ):
        fig.add_trace(
            go.Scatter(
                x=ret[col],
                y=ret["segment"],
                mode="markers+text",
                name=name,
                marker=dict(color=color, size=11),
                text=[f"{v:.2f}" for v in ret[col]],
                textposition=where,
            )
        )
    fig.add_vline(x=1.0, line_color=style.INK_2, line_dash="dot", line_width=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(title="Dwellings added to the census count per completion", range=[0, 1.7])
    left.plotly_chart(_style(fig, "By kind of place and decade"), width="stretch")
    left.caption(
        "Coastal urban municipalities went from 1.41 to 0.25; Lisboa and Porto counted fewer dwellings in 2021 than in 2011. "
        "Classes are proxies (`p2_23`)."
    )
    fig = go.Figure(
        [
            go.Scatter(
                x=stock_path["year"],
                y=stock_path["growth_high_pct"],
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=stock_path["year"],
                y=stock_path["growth_low_pct"],
                fill="tonexty",
                fillcolor="rgba(42,119,214,0.15)",
                line=dict(width=0),
                name="Either decade's retention",
                hoverinfo="skip",
            ),
            go.Scatter(
                x=stock_path["year"],
                y=stock_path["growth_pct"],
                name="Each decade at its own retention",
                line=dict(color=style.BLUE, width=3),
            ),
        ]
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    right.plotly_chart(_style(fig, "Yearly growth of the dwelling stock"), width="stretch")
    right.caption(
        "Rolled along national completions so that it meets all three censuses; before 2001 and after 2021 the retention of "
        "the nearest decade is an extrapolation, so the band shows either decade's. Source: INE; own calculations (`p2_23`)."
    )

    st.subheader("Rents: what goes with the rise in rents of new leases")
    rent_nat = table("p2", "rents_sample_and_change").set_index("measure")["value"]
    rent_class = table("p2", "rents_by_class").sort_values("rent_pct", ascending=False)
    rent_coefs = table("p2", "rents_coefficients_per_sd")
    SHORT_DRIVER = {
        "Foreign residents (points)": "Foreign residents",
        "Short-term rentals per 1,000 dwellings": "Short-term rentals",
        "Population change (%)": "Population change",
        "Completions per 1,000 dwellings": "Completions",
        "Starting level (log)": "Starting level",
    }
    st.markdown(
        "**The question.** Prices get most attention, but what do tenants face? INE publishes the median "
        "rent per m² of *new* leases (what someone signing a contract today pays) only where enough leases "
        f"were signed: **{rent_nat['municipalities_n']:.0f} municipalities** have one in both 2020 and 2024 "
        f"({rent_nat['population_share_2021_pct']:.0f}% of residents, mostly larger and more urban). "
        "Foreign residents and registered short-term rentals go with where rents rose; population change "
        "and completions do not."
    )
    a, b, c = st.columns(3)
    a.metric(
        "Real rent, median municipality",
        f"+{rent_nat['median_rent_change_pct']:.0f}%",
        f"price +{rent_nat['median_price_change_pct']:.0f}%",
        delta_color="off",
        help="Median real change 2020-2024 of the rent per m2 of new leases, and of the price per m2, in the same municipalities.",
    )
    a.caption(
        "Change 2020-2024 after inflation, with the price change in the same places below it."
    )
    b.metric(
        "Rents rose in",
        f"{rent_nat['municipalities_with_rising_rent_pct']:.0f}%",
        "of municipalities",
        delta_color="off",
    )
    b.caption(
        "Share of the municipalities with a published rent where the real rent was higher in 2024."
    )
    c.metric(
        "Rent and price changes",
        f"{rent_nat['rank_correlation_rent_price_change']:.2f}",
        "rank correlation",
        delta_color="off",
        help="Across municipalities, the real rent change against the real price change 2020-2024. "
        "1 means places rank identically on both, 0 means no relation.",
    )
    c.caption(
        "Do places where rents rose most also have the biggest price rises? 1 = identical ranking, "
        "0 = unrelated."
    )
    st.markdown(
        "**Charts below, how to read them.** *Left:* the change in real rent and real price 2020-2024 "
        "(median of each kind of place, in percent, after inflation). *Right:* each dot is the "
        "association of one factor with the rise in rent (orange) or price (blue), per *standard "
        "deviation* of the factor (a typical difference between municipalities, so factors measured in "
        "different units can be compared). A dot to the right of the vertical zero line means places "
        "with more of the factor saw bigger rises; the horizontal bar is a 95% interval, and when it "
        "crosses zero the data cannot tell the association from no association."
    )
    left, right = st.columns(2)
    fig = go.Figure()
    for col, name, color in (
        ("price_pct", "Price per m2", style.BLUE),
        ("rent_pct", "Rent per m2 (new leases)", style.ORANGE),
    ):
        fig.add_bar(
            y=rent_class["segment"],
            x=rent_class[col],
            name=name,
            orientation="h",
            marker_color=color,
            text=[f"{v:.0f}%" for v in rent_class[col]],
            textposition="outside",
        )
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Median real change 2020-2024 (%)", range=[0, 45])
    left.plotly_chart(_style(fig, "Rents rose more evenly than prices"), width="stretch")
    left.caption(
        "Coastal urban places: prices +35%, rents +24%; inland rural: rents +21%, prices +8%. Classes are proxies (`p2_24`)."
    )
    fig = go.Figure()
    for key, name, color in (
        ("price", "Price", style.BLUE),
        ("rent", "Rent", style.ORANGE),
    ):
        fig.add_trace(
            go.Scatter(
                x=rent_coefs[key],
                y=rent_coefs["driver"].map(SHORT_DRIVER),
                mode="markers",
                name=name,
                marker=dict(color=color, size=9),
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=rent_coefs[f"{key}_high"] - rent_coefs[key],
                    arrayminus=rent_coefs[key] - rent_coefs[f"{key}_low"],
                    color=color,
                ),
            )
        )
    fig.add_vline(x=0, line_color=style.MUTED, line_width=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="% per standard deviation")
    right.plotly_chart(_style(fig, "Associations, 95% intervals"), width="stretch")
    right.caption(
        "All drivers together, same district with coast and density. Short-term rentals go with rents but not prices; "
        "a negative starting level means catching up. Four years, places that publish a rent, today's registry of rentals: "
        "adjusted associations, not effects, and a null is not evidence of no effect (`p2_24`)."
    )

# ---- regressions ---------------------------------------------------------------------------------
with tab_reg:
    st.markdown(
        "**What this tab answers: do the factors still go with price-to-income when they are tested "
        "together and followed over time?** The earlier tabs compare municipalities at one moment. Here "
        "the method (a *fixed-effects regression*) compares each municipality **with itself** from year to "
        "year, so that permanent differences between places (beach, big city, history) cannot "
        "produce the result. Drivers are measured so that you can compare them: each result is the "
        "percentage change in price-to-income that goes with a *standard deviation* increase of the "
        "driver, meaning a typical year-to-year change within one municipality.\n\n"
        "**How to read the chart.** Each dot is a driver. Right of the vertical zero line, more of the "
        "driver goes with higher price-to-income; left, with lower. The bar is a 95% interval: the range "
        "the true association probably lies in. A **blue** dot has p < 0.05, meaning the association is "
        "unlikely to be chance; a **gray** dot cannot be told from zero. The *p-value* is the chance of "
        "seeing an association this large if there were really none.\n\n"
        "**The specification menu** changes the controls to test robustness: *region-year effects* "
        "also remove whatever hit a whole region in a given year (the strictest test); *errors clustered by "
        "region* widen the intervals to allow for municipalities in a region moving together; *lagged* "
        "uses last year's driver; the last options leave out Lisboa, Setúbal and Porto, stop in 2022 "
        "(before the 2023 jump in foreign-resident titles), or add short-term rentals (mainland only)."
    )
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

# ---- wages, rates and credit ---------------------------------------------------------------------
with tab_macro:
    st.markdown(
        "**Nationally, wages and falling rates explain the 2013-2021 rise in prices, but not 2021-2025, and "
        "credit did not drive the recovery.** The gap below is everything wages and mortgage rates do not account "
        "for (credit rationing, richer, cash or foreign buyers, supply, expectations): it is not a measure of a bubble."
    )
    st.markdown(
        "**What this tab answers: is the national price rise what wages and borrowing costs would "
        "justify?** It builds a benchmark: if households could always spend the same share of the "
        "average wage on a mortgage payment, what price would wages and the interest rate allow? Then "
        "it compares the benchmark with the actual price, and looks at credit and lending rules. "
        "Everything here is national and yearly or quarterly (not by municipality).\n\n"
        "**Left chart, how to read it.** Blue is the actual house price index and gray the price the "
        "benchmark allows, both nominal with 2015 = 100. Blue above gray means prices ran ahead of what "
        "wages and rates support; blue below gray, behind.\n\n"
        "**Right chart, how to read it.** For each period the bars split the price change into the part "
        "that wage growth accounts for (blue), the part due to the change in the mortgage rate (gray; "
        "positive when rates fell, which allowed higher prices, negative when they rose) and what is "
        "left (orange). The dot is "
        "the actual change. The unit is *log points*: close to percent for small changes (60 log points "
        "is a rise of about 82%), but additive, which is why parts add up to the total."
    )
    fp = table("p2", "financeable_price")
    parts = table("p2", "price_change_parts")
    left, right = st.columns([3, 2])
    fig = go.Figure(
        [
            go.Scatter(
                x=fp["year"],
                y=fp["implied_price_b2015"],
                name="Price a constant payment-to-wage burden finances",
                line=dict(color=style.MUTED, width=2),
            ),
            go.Scatter(
                x=fp["year"],
                y=fp["price_b2015"],
                name="House price index",
                line=dict(color=style.BLUE, width=3),
            ),
        ]
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    left.plotly_chart(
        _style(fig, "Actual price against what wages and rates finance (nominal, 2015 = 100)"),
        width="stretch",
    )
    fig = go.Figure(
        [
            go.Bar(name="Wages", x=parts["span"], y=parts["wages_pct"], marker_color=style.BLUE),
            go.Bar(
                name="Mortgage rate", x=parts["span"], y=parts["rate_pct"], marker_color=style.MUTED
            ),
            go.Bar(
                name="Not accounted for",
                x=parts["span"],
                y=parts["gap_pct"],
                marker_color=style.ORANGE,
            ),
            go.Scatter(
                name="Price change",
                x=parts["span"],
                y=parts["price_change_pct"],
                mode="markers",
                marker=dict(size=11, color=style.INK, line=dict(width=2, color="white")),
            ),
        ]
    )
    fig.update_layout(barmode="relative", legend=dict(orientation="h", y=-0.2))
    right.plotly_chart(_style(fig, "What moved the price (log points)"), width="stretch")
    left.caption(
        "Implied price = average wage / payment per euro borrowed (30-year loan, agreed rate), scaled to equal the price on "
        "average 2003-2025: read changes in the gap, not its level (`p2_13`)."
    )
    right.caption(
        "Parts add up to the price change. Source: BIS, INE, Banco de Portugal, Eurostat; own calculations."
    )

    st.subheader("Credit: did borrowing push prices up?")
    st.markdown(
        "**How to read the chart.** All three lines use 2010 = 100 and real values (inflation removed). "
        "Blue is house prices; orange is the total amount households owe on housing loans; gray is loans "
        "divided by prices, a rough gauge of how much credit there is per euro of house value. If credit "
        "had fueled the price rise, the orange line would climb with or before the blue one."
    )
    cq = table("p2", "credit_quarterly")
    cq["period_start"] = pd.to_datetime(cq["period_start"])
    fig = go.Figure(
        [
            go.Scatter(
                x=cq["period_start"],
                y=cq["hpi_real_b2010"],
                name="Real house price index",
                line=dict(color=style.BLUE, width=3),
            ),
            go.Scatter(
                x=cq["period_start"],
                y=cq["housing_loans_real_b2010"],
                name="Real housing-loan stock",
                line=dict(color=style.ORANGE, width=3),
            ),
            go.Scatter(
                x=cq["period_start"],
                y=cq["loans_per_price_b2010"],
                name="Loans per unit of price",
                line=dict(color=style.MUTED, width=2),
            ),
        ]
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(
        _style(fig, "Real prices against real housing credit (2010 = 100)"), width="stretch"
    )
    st.caption(
        "Credit follows price growth rather than leading it, and credit shrank while prices recovered: the stock does not say who "
        "bought or how strict lenders were (`p2_12`). Source: BIS, INE, Banco de Portugal; own calculations."
    )

    st.subheader("Lending terms: what a longer loan and a guarantee change")
    st.markdown(
        "Banks and the State set the rules for who can borrow how much, so these also shape "
        "affordability. Three charts. **Left, 'What a longer term buys':** if a household keeps the same "
        "monthly payment but repays over a longer term (the average term of new loans or the longest "
        "allowed, 40 years) instead of 30 years, how much more can it borrow, in percent? **Right, "
        "'Cash on the day of purchase':** the deposit and buying costs (taxes, fees) a household needs "
        "at different loan-to-value ratios (the loan as a share of the home's value), in years of "
        "income; the State guarantee for borrowers up to 35 allows a 100% loan. **Bottom:** the share "
        "of new loans that are very large against the home's value (above 90%) or *high-risk* (monthly "
        "debt payments above 60% of income and/or a loan above 90% of the value), 2018-2025."
    )
    mat = table("p2", "lending_maturity_capacity")
    cash = table("p2", "lending_cash_needed").set_index("ltv")
    burden = table("p2", "lending_burden")
    left, right = st.columns([3, 2])
    fig = go.Figure()
    for term, color in zip(
        [
            t
            for t in mat["term"].unique()
            if mat.loc[mat["term"] == t, "capacity_gain_pct"].max() > 0
        ],
        (style.MUTED, style.BLUE),
        strict=False,
    ):
        g = mat[mat["term"] == term]
        fig.add_bar(
            x=[f"{int(y)} (rate {r:.1f}%)" for y, r in zip(g["year"], g["rate_pct"], strict=True)],
            y=g["capacity_gain_pct"],
            name=term,
            marker_color=color,
            text=[f"{v:.0f}%" for v in g["capacity_gain_pct"]],
            textposition="outside",
        )
    fig.update_yaxes(title="Larger loan, same payment, vs 30 years (%)", rangemode="tozero")
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.25))
    left.plotly_chart(_style(fig, "What a longer term buys", 360), width="stretch")
    top = mat["capacity_gain_pct"].max()
    head = table("p2", "lending_headline").iloc[0]
    std = table("p2", "lending_standards")

    def _std(indicator: str, period: str) -> float:
        return float(
            std[(std["indicator"] == indicator) & (std["period"].astype(str) == period)][
                "value"
            ].iloc[0]
        )

    left.caption(
        f"At most {top:.0f}% more loan for the same payment (40 years, allowed to borrowers up to 30), against real prices up "
        f"{head['real_price_rise_pct']:.0f}% in 2013-2024 and {head['real_price_rise_2018_2024_pct']:.0f}% in 2018-2024. That ceiling was "
        f"not reached: the mean term of new loans fell from {_std('maturity_weighted_mean', '2018-07'):.1f} to "
        f"{_std('maturity_weighted_mean', '2024-12'):.1f} years (a {head['term_change_capacity_pct']:.1f}% change in what a payment "
        f"carries), and high-risk loans from about {_std('risk_share_high', '2018-Q3'):.0f}% to {_std('risk_share_high', '2024'):.0f}% "
        f"(then back up in 2025, below). The rate rise of 2021-2024 alone cut what a payment carries by "
        f"{head['rate_rise_capacity_cut_pct']:.0f}%. Nothing before 2018 (Banco de Portugal, March 2025; `p2_22`)."
    )
    fig = go.Figure(
        go.Bar(
            x=cash["median_years"],
            y=list(cash.index),
            orientation="h",
            marker_color=style.ORANGE,
            text=[f"{v:.1f} years" for v in cash["median_years"]],
            textposition="outside",
        )
    )
    fig.update_xaxes(title="Years of income", range=[0, cash["median_years"].max() * 1.35])
    fig.update_yaxes(type="category", autorange="reversed")
    right.plotly_chart(_style(fig, "Cash on the day of purchase, 2024", 360), width="stretch")
    full = burden[(burden["ltv"].str.startswith("100")) & (burden["term"] == "30 years")].iloc[0]
    right.caption(
        f"Median municipality, deposit plus {head['buying_costs_pct']:.0f}% costs, by loan-to-value; the State guarantee (borrowers up to 35) allows 100%. "
        f"The payment then is {full['median_burden_pct']:.0f}% of gross income at 30 years, above 50% of gross income "
        f"in {full['share_above_limit_pct']:.0f}% of municipalities (a rough proxy for the debt-service cap, which is on net income) (`p2_22`)."
    )
    terms = table("p2", "lending_series").set_index("year")
    gar = table("p2", "lending_guarantee_2025").iloc[0]
    fig = go.Figure()
    for col, name, color in (
        ("ltv_above_90_pct", "Loans above 90% of the value", style.ORANGE),
        ("risk_share_high", "High-risk loans", style.BLUE),
    ):
        fig.add_scatter(
            x=terms.index, y=terms[col], mode="lines+markers", name=name, line=dict(color=color)
        )
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(title="% of new housing loans", rangemode="tozero")
    fig.update_layout(legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(_style(fig, "Terms of new housing loans, 2018-2025", 340), width="stretch")
    st.caption(
        f"Standards tightened from 2018 (third quarter only) to 2024 and loosened in 2025: loans above 90% of the value "
        f"{terms.loc[2024, 'ltv_above_90_pct']:.1f}% to {terms.loc[2025, 'ltv_above_90_pct']:.0f}%, high-risk loans "
        f"{terms.loc[2024, 'risk_share_high']:.0f}% to {terms.loc[2025, 'risk_share_high']:.0f}%, as the State guarantee "
        f"({gar['guarantee_share_contracts_pct']:.0f}% of new contracts in 2025, mean LTV {gar['ltv_mean_guarantee_pct']:.0f}%, mean term "
        f"{gar['maturity_mean_guarantee_years']:.0f} years) came in; without it the high-risk share was {gar['risk_high_no_guarantee_pct']:.1f}%. "
        f"Real prices rose {gar['real_price_rise_2024_2025_pct']:.0f}% in 2025: coincident in time, not a test "
        "(Banco de Portugal, March 2026; `p2_22`)."
    )

# ---- policy test ---------------------------------------------------------------------------------
with tab_policy:
    st.markdown(
        "**What this tab answers: what did one housing policy do, and what money is at stake?** The first "
        "half tests whether cutting the municipal property tax moved prices. The second half sets out "
        "who collects property taxes, what the State spends on housing, how Portugal compares abroad, "
        "and what happens to tenants under rent rules."
    )
    st.markdown(
        "**Did cutting the municipal property tax (IMI) raise prices?** In theory a lasting tax cut is capitalized "
        "into prices. The test compares prices around municipal rate cuts with the year before the cut. It is "
        "**inconclusive**: the estimates before the cut already differ (the pre-trend test is rejected), and the "
        "interval after the cut contains both zero and full capitalization."
    )
    st.markdown(
        "**Plain words.** *IMI* (Imposto Municipal sobre Imóveis) is the yearly property tax, set by each "
        "council within a legal range. *Capitalization* means that when owning a home gets cheaper "
        "(a lower tax), buyers are willing to pay more for it, so the saving ends up in the price. "
        "*Full capitalization* is the extreme where the whole tax saving is added to the price. "
        "A *pre-trend test* checks whether prices were already moving differently before the cut: if they "
        "were, the later difference cannot be credited to the cut, which is why the test is inconclusive.\n\n"
        "**Chart below, how to read it.** The horizontal axis counts years since a council cut its rate "
        "(year -1, the year before, is the reference at zero). Each dot is the difference in real price "
        "per m² compared with that year, with a 95% interval, for a cut of 0.01 percentage points. "
        "A credible test needs the dots *before* the cut to sit around zero; the dashed orange line is "
        "what full capitalization would imply."
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
        annotation_text="full capitalization",
        annotation_position="top left",
    )
    fig.update_xaxes(title="Years since the cut (reference: year before)", dtick=1)
    fig.update_yaxes(title="Real price per m², % per 0.01 pp of rate cut", ticksuffix="%")
    st.plotly_chart(_style(fig, "Prices around municipal IMI rate cuts", 400), width="stretch")
    st.caption(
        "Effect on the real price per m² per 0.01 percentage point of cut, 95% intervals clustered by municipality "
        f"(`p3_02`). The dashed line is what full capitalization of the tax saving would imply ({bench:.2f}% per 0.01 pp). "
        f"The data are too noisy to tell: the smallest effect this design could detect is {power['detectable_over_benchmark'].iloc[0]:.0f} "
        "times the benchmark one year after the cut. Phase 4 therefore treats capitalization as unknown, anywhere from none to full."
    )

    st.divider()
    st.subheader("What is at stake: the money")
    st.markdown(
        "IMI and IMT are **municipal** revenue, so a cut costs councils, not the central budget. These are national "
        "figures (`p3_04`, `p3_05`); the receipts of each council, 2021-2023, are further down (`p3_12`).\n\n"
        "**Plain words.** *IMT* (Imposto Municipal sobre as Transmissões) is the tax paid once, when a "
        "property changes hands, so it rises and falls with sales and prices. IMI is paid every year "
        "on the property's assessed value, which is updated slowly, so it does not follow prices. "
        "All amounts are in millions of euros at constant prices (inflation removed).\n\n"
        "**Charts below, how to read them.** *Top left:* yearly revenue from the two taxes. *Top right:* "
        "State spending on housing, split into building and allowances. *Bottom left:* how many "
        "councils charge the lowest rate the law allows (0.30%), and so cannot cut any further. "
        "*Bottom right:* Portugal (blue) against five peer countries on price rise, property tax and "
        "housing support, each in its own panel."
    )
    revenue = table("p3", "property_tax_series").set_index("year")
    spend = table("p3", "housing_spending_series").set_index("year")
    left, right = st.columns(2)
    fig = go.Figure()
    fig.add_scatter(
        x=revenue.index,
        y=revenue["imt_real_eur_m"],
        name="IMT (with stamp duty)",
        line=dict(color=style.BLUE),
    )
    fig.add_scatter(
        x=revenue.index, y=revenue["imi_real_eur_m"], name="IMI", line=dict(color=style.ORANGE)
    )
    fig.update_yaxes(title="Million euros, constant prices", rangemode="tozero")
    left.plotly_chart(_style(fig, "Property-tax revenue", 360), width="stretch")
    left.caption(
        f"IMT follows the market (+{100 * (revenue.loc[2025, 'imt_real_b2015'] / revenue.loc[2013, 'imt_real_b2015'] - 1):.0f}% real since 2013); "
        f"IMI has not followed prices (real {100 * (revenue.loc[2025, 'imi_real_eur_m'] / revenue.loc[2019, 'imi_real_eur_m'] - 1):+.0f}% since 2019 "
        f"while real prices rose {100 * (revenue.loc[2025, 'hpi_real_b2015'] / revenue.loc[2019, 'hpi_real_b2015'] - 1):.0f}%). National accounts, accrual basis."
    )
    fig = go.Figure()
    fig.add_scatter(
        x=spend.index,
        y=spend["housing_development_real_eur_m"],
        name="Housing development",
        stackgroup="s",
        line=dict(color=style.BLUE, width=0.5),
    )
    fig.add_scatter(
        x=spend.index,
        y=spend["housing_benefits_real_eur_m"],
        name="Allowances and rent subsidies",
        stackgroup="s",
        line=dict(color=style.ORANGE, width=0.5),
    )
    fig.update_yaxes(title="Million euros, constant prices")
    right.plotly_chart(_style(fig, "State spending on housing", 360), width="stretch")
    right.caption(
        f"{spend.loc[2024, 'support_gdp_pct']:.2f}% of GDP in 2024 ({spend['support_gdp_pct'].min():.2f}% at the low, "
        f"{spend['support_gdp_pct'].max():.2f}% at the 2001 peak). Spending only: tax expenditures are not included (`p3_06`)."
    )

    room = table("p3", "imi_headroom").set_index("year")
    left, right = st.columns(2)
    fig = go.Figure()
    fig.add_bar(
        x=room.index, y=room["at_floor_n"], marker_color=style.BLUE, name="Councils at the floor"
    )
    fig.update_yaxes(title="Councils at the 0.30% legal floor", range=[0, 310])
    left.plotly_chart(
        _style(fig, "Most councils cannot cut the IMI rate further", 360), width="stretch"
    )
    last_room = room.iloc[-1]
    left.caption(
        f"{int(last_room['at_floor_n'])} of {int(last_room['municipalities_n'])} councils are at the floor in {int(room.index[-1])}. "
        f"Without a change of the law the average rate can fall by {last_room['headroom_pp']:.3f} pp, "
        f"{100 * last_room['headroom_share']:.0f}% of the bill (about {last_room['headroom_eur_m']:.0f} million euros a year; "
        f"{100 * room['headroom_share'].iloc[0]:.0f}% in {int(room.index[0])}). The simulator's 0.05 pp cut assumes a lower floor (`p3_05`)."
    )
    mix = table("p3", "peer_policy_mix").set_index("geo").drop(index="EU27_2020", errors="ignore")
    names = {
        "PT": "Portugal",
        "ES": "Spain",
        "IT": "Italy",
        "FR": "France",
        "DE": "Germany",
        "IE": "Ireland",
    }
    mix = mix.loc[list(names)].sort_values("price_change_pct")
    panels = (
        ("price_change_pct", "Prices, %"),
        ("property_tax_gdp_pct", "Tax, % GDP"),
        ("housing_support_gdp_pct", "Support, % GDP"),
    )
    fig = make_subplots(
        rows=1,
        cols=3,
        shared_yaxes=True,
        subplot_titles=[t for _, t in panels],
        horizontal_spacing=0.04,
    )
    for i, (col, _) in enumerate(panels, start=1):
        fig.add_scatter(
            x=mix[col],
            y=[names[g] for g in mix.index],
            mode="markers",
            marker=dict(
                size=[13 if g == "PT" else 9 for g in mix.index],
                color=[style.BLUE if g == "PT" else style.MUTED for g in mix.index],
            ),
            showlegend=False,
            row=1,
            col=i,
        )
        fig.update_xaxes(rangemode="tozero", row=1, col=i)
    right.plotly_chart(_style(fig, "Portugal against five peers", 360), width="stretch")
    right.caption(
        "Prices: nominal change 2015 to 2024. Tax: recurrent property tax; support: housing development plus allowances, both as the mean share of GDP 2015-2024. Italy has no housing-support value (2022-2023 spending far above trend). "
        "Six countries and three indicators: a comparison, not a test (`p3_07`)."
    )

    st.subheader("By council: who collects the money")
    muni_nat = table("p3", "municipal_tax_national").set_index("year")
    by_place = table("p3", "municipal_tax_by_place")
    room_tab = table("p3", "municipal_floor_room").set_index("rate")
    room_by = table("p3", "municipal_floor_room_by_place")
    windfall = table("p3", "municipal_imt_windfall").set_index("measure")["value"]
    last_year = int(muni_nat.index[-1])
    first_year = int(muni_nat.index[0])
    st.markdown(
        f"Receipts of the 307 municipal councils (DGAL via INE, {first_year}-{last_year}): IMI plus IMT were "
        f"**{muni_nat.loc[last_year, 'imi_imt_share_pct']:.0f}%** of all current receipts in {last_year} "
        f"({muni_nat.loc[first_year, 'imi_imt_share_pct']:.0f}% in {first_year}), and {muni_nat.loc[last_year, 'median_council_share_pct']:.0f}% "
        "for the median council. The cost of a cut falls on the council that collects, and councils differ a lot."
    )
    st.markdown(
        "**Charts below, how to read them.** *Left:* what share of a council's yearly current receipts "
        "comes from IMI (blue) and IMT (orange), for the middle council of each kind of place (the "
        "groups are defined on the Trends page, Groups tab). *Right:* if every council charged only the "
        "lowest legal IMI rate, how the lost revenue would be spread across kinds of place, as a share "
        "of the total cost. The numbers in parentheses count councils for which that cost would pass 1% of everything "
        "they receive, which is a noticeable hole in a budget."
    )
    order = [
        ("density_class", "urban", "Urban"),
        ("density_class", "intermediate", "Intermediate"),
        ("density_class", "rural", "Rural"),
        ("coast_class", "coast", "Coastal"),
        ("coast_class", "inland", "Inland"),
        ("tourist", "tourist", "Tourist-heavy"),
        ("tourist", "other", "Other places"),
    ]
    rows = [
        (label, by_place[(by_place["dimension"] == dim) & (by_place["class"] == cls)].iloc[0])
        for dim, cls, label in order
    ]
    left, right = st.columns(2)
    fig = go.Figure()
    for col, name, color in (
        ("imi_share_pct", "IMI", style.BLUE),
        ("imt_share_pct", "IMT", style.ORANGE),
    ):
        fig.add_bar(
            y=[f"{label} ({int(r['councils_n'])})" for label, r in rows],
            x=[r[col] for _, r in rows],
            name=name,
            orientation="h",
            marker_color=color,
            text=[f"{r[col]:.0f}%" for _, r in rows],
            textposition="inside",
        )
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=-0.2))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title=f"Median share, {last_year} (%)")
    left.plotly_chart(_style(fig, "IMI and IMT in a council's receipts", 380), width="stretch")
    left.caption(
        "Median across the councils of each class (number in parentheses); urban and coastal councils and tourist ones, "
        "where IMT is 22% of receipts, depend most (`p3_12`). Classes are proxies (density, coast, registered short-term rentals)."
    )
    rb = room_by[room_by["dimension"].isin(["density_class", "coast_class"])]
    labels_room = {
        "urban": "Urban",
        "intermediate": "Intermediate",
        "rural": "Rural",
        "coast": "Coastal",
        "estuary": "Estuary",
        "inland": "Inland",
    }
    fig = go.Figure(
        go.Bar(
            y=[
                f"{labels_room[c]} ({int(n)} over 1%)"
                for c, n in zip(rb["class"], rb["over_one_pct_n"], strict=True)
            ],
            x=rb["share_of_room_pct"],
            orientation="h",
            marker_color=style.BLUE,
            text=[f"{x:.0f}%" for x in rb["share_of_room_pct"]],
            textposition="outside",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Share of the cost (%)", range=[0, 80])
    right.plotly_chart(_style(fig, "Who would pay a cut to the floor", 380), width="stretch")
    year_before = room_tab.loc["rate of the year before"]
    right.caption(
        "In parentheses: councils for which the cost passes 1% of their current receipts. "
        f"Cutting every urban IMI rate to 0.30% costs {room_tab['room_eur_m'].min():.0f} to {room_tab['room_eur_m'].max():.0f} million euros "
        f"a year ({room_tab['room_share_of_imi_pct'].min():.1f}% to {room_tab['room_share_of_imi_pct'].max():.1f}% of IMI); "
        f"{int(year_before['at_floor_n'])} of {int(year_before['councils_n'])} councils are at the floor already. "
        f"For {int(year_before['over_one_pct_of_current_n'])} councils the cost passes 1% of their current receipts (up to "
        f"{year_before['max_share_of_current_pct']:.0f}%), and they are spread out, many of them inland. Accounting, base held fixed (`p3_12`)."
    )
    a, b, c = st.columns(3)
    a.metric(
        f"IMT, {first_year} to {last_year}",
        f"+{windfall['change_eur_m']:.0f} million euros",
        f"+{windfall['change_pct']:.0f}%",
        delta_color="off",
    )
    b.metric(
        "That rise against the room to cut IMI",
        f"{windfall['rise_over_floor_room_total']:.1f} times",
        f"more than a council's own room in {windfall['councils_where_rise_exceeds_room_pct']:.0f}% of councils",
        delta_color="off",
    )
    c.metric(
        "Councils whose IMT rose",
        f"{windfall['councils_with_a_rise_pct']:.0f}%",
        f"median council {windfall['median_council_change_pct']:+.0f}%",
        delta_color="off",
    )
    st.caption(
        "IMT rose with prices and sales, not as a response to any cut; three years of receipts (basis not stated), no trend. "
        "Municipal IMI is 90% of the national tax on land and buildings (the rest is the State's AIMI) and IMT 102% of the national IMT (`p3_12`)."
    )

    path = table("p3", "rent_update_path").set_index("year")
    gap = table("p3", "rent_update_gap_by_third").set_index("pti_third")
    coef = table("p3", "rent_update_coefficients").set_index("year")
    ceiling = coef[coef["legal_coefficient"] < coef["formula_coefficient"]].iloc[-1]
    ceiling_year = int(ceiling.name)
    base = int(path.index[0])
    st.subheader("Rents: existing tenants and new tenants")
    st.markdown(
        "**The question.** Portuguese law caps how much a landlord can raise the rent of an *existing* "
        "lease each year (a legal coefficient published each year), but not the rent of a *new* lease. So "
        "someone already renting and someone signing today can pay very different amounts for the same "
        "home. **Left chart:** all lines start at 100 in the first year. Blue is the most a landlord could "
        "have charged on a lease signed then, orange the median rent of new leases, gray consumer prices; "
        "the dashed blue line shows what the law would have allowed without the temporary 2023 ceiling. "
        "**Right chart:** by how many percent a new lease costs more than the legally updated old rent, "
        "for municipalities grouped by affordability. This is arithmetic from the rules, not a measure of "
        "what the rules caused."
    )
    left, right = st.columns(2)
    fig = go.Figure()
    for col, name, color, dash in (
        ("new_lease_rent_index", "Median rent of new leases", style.ORANGE, "solid"),
        ("legal_rent_index", f"Highest rent of a lease signed in {base}", style.BLUE, "solid"),
        ("formula_rent_index", f"Same, without the {ceiling_year} ceiling", style.BLUE, "dash"),
        ("cpi_index", "Consumer prices", style.MUTED, "solid"),
    ):
        fig.add_scatter(x=path.index, y=path[col], name=name, line=dict(color=color, dash=dash))
    fig.update_yaxes(title=f"Index, {base} = 100")
    fig.update_xaxes(dtick=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    left.plotly_chart(_style(fig, "What the law lets a landlord charge", 360), width="stretch")
    end = path.index[-1]
    left.caption(
        f"An existing lease may rise only by the yearly coefficient ({100 * (ceiling['legal_coefficient'] - 1):.0f}% in {ceiling_year} "
        f"instead of {100 * (ceiling['formula_coefficient'] - 1):.2f}%): "
        f"{path.loc[end, 'legal_rent_index'] - 100:.1f}% by {end} against consumer prices {path.loc[end, 'cpi_index'] - 100:.1f}% "
        f"and new leases {path.loc[end, 'new_lease_rent_index'] - 100:.1f}%. The gap is arithmetic from the rules; "
        "it is not an estimate of what the rule caused (`p3_11`)."
    )
    gap = gap.loc[["most affordable", "middle", "least affordable"]]
    fig = go.Figure()
    fig.add_bar(
        x=gap.index,
        y=gap["median_gap_pct"],
        marker_color=style.ORANGE,
        text=[f"{v:.0f}%" for v in gap["median_gap_pct"]],
        textposition="outside",
    )
    fig.update_yaxes(title=f"New lease above the updated {base} rent, %", rangemode="tozero")
    right.plotly_chart(_style(fig, f"Gap in {end}, by price-to-income third", 360), width="stretch")
    right.caption(
        f"Median municipality in each third ({int(gap['municipalities_n'].sum())} with a rent in {base} and {end}). "
        f"Homes rented: {gap.loc['most affordable', 'rented_share_pct']:.0f}% in the most affordable third, "
        f"{gap.loc['least affordable', 'rented_share_pct']:.0f}% in the least. New leases of 2021 per 100 homes rented in the census: "
        f"{gap['median_new_leases_per_100_rented'].min():.0f} to {gap['median_new_leases_per_100_rented'].max():.0f} by third, so "
        "roughly nine in ten tenants keep a bounded rent, movers meet the market. New-lease medians are not like-for-like (`p3_11`)."
    )
