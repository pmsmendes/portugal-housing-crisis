"""Forecast and policy simulator: forecast ranges and alternative assumptions with policy costs."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pthousing.config import TABLES
from pthousing.simulation import engine as E
from pthousing.viz import style

st.set_page_config(page_title="Simulator · Portugal's Housing Crisis", layout="wide")

COLORS = {
    "no policy": style.MUTED,
    "policy": style.BLUE,
}  # readable on the light and the dark theme
TRANSPARENT = "rgba(0,0,0,0)"
GRID = "rgba(137,135,129,0.25)"
N_DRAWS = 500


@st.cache_resource
def inputs():
    a, anc = E.load_inputs()
    p = E.draw(a, N_DRAWS, seed=2026)
    return a, anc, p, E.calibrate(a, anc, p)


a, anc, draws, drift = inputs()

st.title("Scenario simulator")
st.markdown(
    f"National paths of housing affordability to **{a.end_year}** for the median municipality. The first three years are the "
    f"validated ETS forecast (p4_01); later years are **scenarios, not forecasts**. Direct effects (homes, euros) are accounting; "
    f"every price response is a behavioural parameter shown with its range and status under *Assumptions*."
)

# ---- inputs --------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Scenario")
    name = st.selectbox(
        "Starting point",
        list(a.scenarios),
        index=1,
        help="Optimistic = low pressure on affordability.",
    )
    sc = a.scenarios[name]
    migration = st.slider(
        "Net migration (people a year)",
        0,
        200_000,
        int(sc["net_migration_per_year"]),
        5_000,
        key=f"{name}-mig",
    )
    income = st.slider(
        "Real income growth (% a year)",
        -1.0,
        4.0,
        float(sc["household_income_growth_real_pct"]),
        0.25,
        key=f"{name}-inc",
    )
    rate = st.slider(
        "Mortgage rate in 3 years (%)",
        1.0,
        6.5,
        float(sc["mortgage_rate_pct"]),
        0.25,
        key=f"{name}-rate",
    )
    completions = st.slider(
        "Completions a year (in 3 years)",
        15_000,
        80_000,
        int(sc["completions_per_year"]),
        1_000,
        key=f"{name}-comp",
    )
    half_life = st.slider(
        "Years for the other-demand boom to halve",
        1.0,
        10.0,
        float(sc["other_demand_half_life_years"]),
        0.5,
        key=f"{name}-fade",
        help="Tourism, foreign buyers, credit, expectations. The single least certain input.",
    )

    st.header(f"Policy (from {a.policy_start_year})")
    construction = st.slider("Extra completions a year", 0, 30_000, 0, 1_000)
    renovation = st.slider("Vacant homes renovated a year", 0, 30_000, 0, 1_000)
    public = st.slider("Public homes built a year", 0, 15_000, 0, 500)
    imi = st.slider("Change in the average IMI rate (pp)", -0.15, 0.15, 0.0, 0.01)
    imt = st.slider("Change in the average IMT rate on homes (pp of price)", -2.0, 2.0, 0.0, 0.25)
    cap = st.radio(
        "Do tax changes show up in prices?",
        ["Unknown (0 to full)", "Not at all", "Fully"],
        help="Phase 3 could not tell: every interval contains both zero and full capitalisation.",
    )

scenario = {
    "net_migration_per_year": float(migration),
    "household_income_growth_real_pct": income,
    "mortgage_rate_pct": rate,
    "completions_per_year": float(completions),
    "other_demand_half_life_years": half_life,
}
policy = E.Policy(construction, renovation, public, imi, imt)
p = {k: v.copy() for k, v in draws.items()}
if cap != "Unknown (0 to full)":
    for key in ("imi_reform.capitalisation_share", "imt_reform.capitalisation_share"):
        p[key][:] = 0.0 if cap == "Not at all" else 1.0

without = E.run(a, anc, scenario, None, p, drift)
with_ = E.run(a, anc, scenario, None if policy.is_empty else policy, p, drift)
effect = E.compare(a, anc, scenario, policy, p) if not policy.is_empty else None


# ---- headline numbers ----------------------------------------------------------------------------
def pct(run: E.Run, metric: str) -> tuple[float, float, float]:
    return tuple(np.quantile(run.end(metric), E.QUANTILES))


pti = pct(with_, "pti_years")
burden = pct(with_, "burden_pct")
cols = st.columns(4)
cols[0].metric(
    f"Price-to-income, {a.end_year}",
    f"{pti[1]:.1f} years",
    f"{pti[1] - anc.pti_years:+.1f} vs {a.start_year} ({anc.pti_years:.1f})",
    delta_color="inverse",
)
cols[0].caption(f"80% range {pti[0]:.1f} to {pti[2]:.1f}")
cols[1].metric(
    f"Mortgage burden, {a.end_year} (% of income)",
    f"{burden[1]:.0f}%",
    f"{burden[1] - anc.burden_pct:+.0f} pp",
    delta_color="inverse",
)
cols[1].caption(f"80% range {burden[0]:.0f} to {burden[2]:.0f}%")
if effect is not None:
    s = E.summarise(effect)
    cols[2].metric(
        "Policy effect on price-to-income", f"{-s['pti_gain_p50']:+.2f} years", delta_color="off"
    )
    cols[2].caption(
        f"80% range {-s['pti_gain_p90']:+.2f} to {-s['pti_gain_p10']:+.2f}; improves in {100 * s['share_improving']:.0f}% of draws"
    )
    cols[3].metric(
        "Budget cost to " + str(a.end_year),
        f"{s['cost_eur_p50'] / 1e9:.1f} bn EUR",
        help="Public spending plus lost IMI/IMT revenue, 2024 euros, no discounting.",
    )
    cols[3].caption(f"Homes added: {s['homes_added_n_p50']:,.0f}")
else:
    cols[2].metric("Policy effect", "none selected", delta_color="off")
    cols[3].metric("Budget cost", "0 bn EUR", delta_color="off")


# ---- charts --------------------------------------------------------------------------------------
def band_chart(metric: str, title: str, ytitle: str, ref: dict | None = None) -> go.Figure:
    fig = go.Figure()
    for label, run in (("no policy", without), ("policy", with_)):
        if label == "policy" and policy.is_empty:
            continue
        b = run.summary(metric)
        color = COLORS[label]
        fig.add_trace(
            go.Scatter(
                mode="lines",
                x=b["year"],
                y=b["p90"],
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                mode="lines",
                x=b["year"],
                y=b["p10"],
                fill="tonexty",
                line=dict(width=0),
                fillcolor=_alpha(color),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                mode="lines",
                x=b["year"],
                y=b["p50"],
                name=label if not policy.is_empty else "median",
                line=dict(color=color, width=2.5),
                hovertemplate="%{x}: %{y:.2f}<extra></extra>",
            )
        )
    if ref:
        fig.add_trace(
            go.Scatter(
                x=ref["years"],
                y=ref["mean"],
                mode="markers",
                name="ETS forecast",
                marker=dict(color=style.MUTED, symbol="diamond", size=8),
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=ref["hi80"] - ref["mean"],
                    arrayminus=ref["mean"] - ref["lo80"],
                    color=style.MUTED,
                ),
            )
        )
    fig.update_layout(
        title=title,
        yaxis_title=ytitle,
        margin=dict(l=10, r=10, t=50, b=10),
        height=380,
        legend=dict(orientation="h", y=-0.15),
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
    )
    fig.update_xaxes(dtick=2, showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def _alpha(hex_color: str, alpha: float = 0.14) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


forecast = pd.read_csv(TABLES / "p4" / "national_forecast.csv")
real = forecast[forecast["series"] == E.FORECAST_SERIES]
ref_years = real["period"].str[:4].astype(float) + 0.5
scale = (
    100
    * np.exp(anc.near_term_log_growth)
    / real.loc[real["period"].str.endswith(f"{a.near_term_year}Q2"), "mean"].iloc[0]
)
reference = {
    "years": ref_years.to_numpy(),
    "mean": (real["mean"] * scale).to_numpy(),
    "lo80": (real["lo80"] * scale).to_numpy(),
    "hi80": (real["hi80"] * scale).to_numpy(),
}

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Affordability", "Housing balance and cost", "Assumptions", "Sensitivity", "Regional outlook"]
)
with tab1:
    left, right = st.columns(2)
    left.plotly_chart(
        band_chart("pti_years", "Price-to-income (years of income)", "years"),
        width="stretch",
    )
    right.plotly_chart(
        band_chart("burden_pct", "Mortgage burden (% of income)", "% of income"),
        width="stretch",
    )
    st.plotly_chart(
        band_chart(
            "price_index", f"Real house price index ({a.start_year} = 100)", "index", reference
        ),
        width="stretch",
    )
    st.caption(
        "Median municipality; the national price, income and mortgage-rate paths move it proportionally, so regional differences "
        "(coastal and urban places rose most, see phase 2) are not modelled. Bands are parameter uncertainty only. "
        "A mortgage burden above 100% means ownership is out of reach, not that anyone pays that."
    )

with tab2:
    bal = with_.summary("cumulative_shortfall_n").assign(label="shortfall")
    fig = go.Figure(
        go.Scatter(
            mode="lines",
            x=bal["year"],
            y=bal["p50"],
            line=dict(color=style.BLUE, width=2.5),
            name="households without a usable dwelling (median)",
        )
    )
    fig.update_layout(
        title="Cumulative households formed beyond the dwellings that can house them",
        margin=dict(l=10, r=10, t=50, b=10),
        height=330,
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        yaxis_title="households (negative: spare capacity)",
    )
    fig.update_yaxes(gridcolor=GRID)
    st.plotly_chart(fig, width="stretch")
    if effect is not None:
        spend = pd.DataFrame(
            {
                "Lever": [
                    "Extra construction",
                    "Vacant renovation",
                    "Public housing",
                    "IMI change",
                    "IMT change",
                ],
                "Cost to the budget, bn EUR (median)": [
                    float(np.median(with_.series[f"cost_{k}_eur"].sum(axis=1))) / 1e9
                    for k in (
                        "construction_boost",
                        "vacant_renovation",
                        "public_housing",
                        "imi_reform",
                        "imt_reform",
                    )
                ],
            }
        )
        st.dataframe(spend.round(2), hide_index=True)
        st.caption(
            "Costs are public spending or lost revenue, in 2024 euros, summed from the policy start year, without discounting; a negative figure is revenue gained. Behavioural revenue effects (changes in transactions or assessed values) are not included."
        )
    else:
        st.info("Choose a policy lever in the sidebar to see its cost.")

with tab3:
    reg = pd.DataFrame(
        [
            {
                "parameter": k,
                "low": r.low,
                "mid": r.mid,
                "high": r.high,
                "status": a.notes[k.split(".")[0]]["status"],
            }
            for k, r in a.ranges.items()
        ]
    )
    st.markdown(
        "**Behavioural parameters.** Uncertainty runs draw each one from a triangular distribution over its range. *literature*: a published estimate; *project*: from earlier phases; *assumption*: no estimate exists, the range is a bound."
    )
    st.dataframe(reg, hide_index=True)
    st.markdown("**Sources and reasoning**")
    for key, note in a.notes.items():
        st.markdown(f"- `{key}` ({note['status']}): {note['source']}")
    st.markdown(
        f"**Starting point ({a.start_year}).** Population {anc.population / 1e6:.2f} million, {anc.households / 1e6:.2f} million households, price-to-income {anc.pti_years:.1f}, mortgage burden {anc.burden_pct:.0f}%, mortgage rate {anc.mortgage_rate_pct:.2f}%."
    )

with tab4:
    sens = E.sensitivity(
        a, anc, scenario, policy if not policy.is_empty else E.Policy.package(a, "supply_mix")
    )
    st.markdown(
        f"Price-to-income in {a.end_year} when one input at a time moves between its low and high value (all others as chosen)."
    )
    st.dataframe(
        sens[["parameter", "kind", "low_pti_end", "high_pti_end", "swing_pti_end"]].round(2),
        hide_index=True,
    )

with tab5:
    st.markdown(
        "**Where will affordability worsen more than elsewhere?** A validated trend extrapolation (phase 4, "
        "`p4_03`), stated *relative to the median municipality*: it ranks places, it does not give their level, "
        "which is the scenario above. Coloured: the 80% interval (from past errors) excludes zero."
    )
    unit = st.radio("Group by", ["Coast x density class", "NUTS 3 region"], horizontal=True)
    name, col = ("classes", "segment") if unit.startswith("Coast") else ("regions", "region")
    out = pd.read_csv(TABLES / "p4" / f"regional_outlook_{name}.csv").sort_values("relative")
    sure = (out["relative_lo80"] > 0) | (out["relative_hi80"] < 0)
    colors = [
        (style.ORANGE if r > 0 else style.BLUE) if k else style.MUTED
        for r, k in zip(out["relative"], sure, strict=True)
    ]
    fig = go.Figure(
        go.Scatter(
            x=out["relative"],
            y=out[col],
            mode="markers",
            marker=dict(size=10, color=colors),
            error_x=dict(
                type="data",
                symmetric=False,
                array=out["relative_hi80"] - out["relative"],
                arrayminus=out["relative"] - out["relative_lo80"],
                color=style.MUTED,
            ),
            customdata=out[["change_pct", "municipalities_n"]],
            hovertemplate="%{y}<br>%{x:+.1f} points vs median (own change %{customdata[0]:+.0f}%, "
            "%{customdata[1]} municipalities)<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color=style.INK_2, line_width=1)
    fig.update_layout(
        title=f"Expected change in price-to-income to 2026 relative to the median municipality ({unit.lower()})",
        height=max(320, 22 * len(out) + 120),
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        xaxis_title="percentage points",
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Class or region trend of 2016 to 2024 (a boom), validated on rolling origins 2019 to 2023: municipal rank "
        "correlation 0.43 two years ahead, region-level skill weak, class-level strong. Mainland only. Adjusted "
        "associations, not causal; single municipalities are noisy (see `reports/p4_forecast.md`)."
    )
