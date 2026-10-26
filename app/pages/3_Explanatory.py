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

tab_where, tab_drivers, tab_reg, tab_macro, tab_policy = st.tabs(
    ["Where", "Drivers", "Regressions", "Wages, rates and credit", "A policy test"]
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

# ---- wages, rates and credit ---------------------------------------------------------------------
with tab_macro:
    st.markdown(
        "**Nationally, wages and falling rates explain the 2013-2021 rise in prices, but not 2021-2025, and "
        "credit did not drive the recovery.** The gap below is everything wages and mortgage rates do not account "
        "for (credit rationing, richer, cash or foreign buyers, supply, expectations): it is not a measure of a bubble."
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

    st.divider()
    st.subheader("What is at stake: the money")
    st.markdown(
        "IMI and IMT are **municipal** revenue, so a cut costs councils, not the central budget. These are national "
        "figures (`p3_04`, `p3_05`); by council, IMI and IMT are about a sixth of the median council's receipts and 30% in cities (2021-2023, `p3_12`)."
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

    path = table("p3", "rent_update_path").set_index("year")
    gap = table("p3", "rent_update_gap_by_third").set_index("pti_third")
    coef = table("p3", "rent_update_coefficients").set_index("year")
    ceiling = coef[coef["legal_coefficient"] < coef["formula_coefficient"]].iloc[-1]
    ceiling_year = int(ceiling.name)
    base = int(path.index[0])
    st.subheader("Rents: sitting tenants and new tenants")
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
        f"Homes let: {gap.loc['most affordable', 'rented_share_pct']:.0f}% in the most affordable third, "
        f"{gap.loc['least affordable', 'rented_share_pct']:.0f}% in the least. New leases of 2021 per 100 homes let in the census: "
        f"{gap['median_new_leases_per_100_rented'].min():.0f} to {gap['median_new_leases_per_100_rented'].max():.0f} by third, so "
        "roughly nine in ten tenants keep a bounded rent, movers meet the market. New-lease medians are not like-for-like (`p3_11`)."
    )
