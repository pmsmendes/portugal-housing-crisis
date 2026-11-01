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
PARAM_LABELS = {  # plain names for the inputs of the sensitivity table
    "other_demand_half_life_years": "Years for the other-demand boom to halve",
    "net_migration_per_year": "Net migration (people a year)",
    "mortgage_rate_pct": "Mortgage rate in 3 years",
    "household_income_growth_real_pct": "Real income growth (% a year)",
    "completions_per_year": "Completions a year",
    "income_elasticity_of_price": "How closely prices follow incomes",
    "usable_share_of_additions": "Share of new dwellings that become usual homes",
    "price_flexibility_balance": "How strongly prices react to a housing shortfall",
    "mortgage_rate_semi_elasticity": "How much prices fall per point of mortgage rate",
    "construction_boost.additionality": "Extra building: share that would not happen anyway",
    "construction_boost.cost_per_unit_eur": "Extra building: cost per home",
    "vacant_renovation.reoccupation": "Renovation: share that becomes extra homes",
    "vacant_renovation.cost_per_unit_eur": "Renovation: cost per home",
    "public_housing.crowd_out": "Public housing: private building displaced",
    "public_housing.cost_per_unit_eur": "Public housing: cost per home",
    "imi_reform.tax_value_ratio": "IMI cut: assessed value over market price",
    "imi_reform.discount_rate": "IMI cut: discount rate",
    "imi_reform.capitalisation_share": "IMI cut: share that shows up in prices",
    "imt_reform.capitalisation_share": "IMT cut: share that shows up in prices",
}


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
with st.container(border=True):
    st.markdown(
        "**How to use this page**\n"
        "1. **Pick a starting point** in the sidebar: *optimistic*, *baseline* or *pessimistic*. Each "
        "is a bundle of assumptions about migration, incomes, interest rates, building and the "
        "demand boom. The sliders below it let you change any of them.\n"
        f"2. **Optionally add a policy** (sidebar, second block, acting from {a.policy_start_year}): "
        "more building, renovating vacant homes, public housing, or changing the property taxes IMI and IMT.\n"
        "3. **Read the results.** The four numbers and the charts show the median municipality in "
        f"{a.end_year}: how many years of income a home costs, how heavy a mortgage is, and what a policy "
        "would change and cost.\n\n"
        '**What a scenario is.** Nobody knows the future, so the simulator answers *"if these '
        'assumptions hold, then this follows"*. It is not a prediction. Behind the lines are 500 '
        "random draws of the uncertain numbers (for example how strongly prices react to a shortfall of "
        "homes). The solid line is the middle result and the **shaded band the 80% range**: in 8 of 10 "
        "draws the outcome falls inside it. The band covers uncertainty about these parameters only, "
        "not about the assumptions you choose."
    )

# ---- inputs --------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Scenario")
    st.caption(
        "What the world looks like. Choosing a starting point sets all five sliders; move them to change it."
    )
    name = st.selectbox(
        "Starting point",
        list(a.scenarios),
        index=1,
        help="Optimistic = low pressure on affordability (slower household growth, more building, "
        "cheaper credit, faster incomes, a short-lived demand boom). Pessimistic = high pressure. "
        "The names describe pressure on affordability, not a judgement on migration or anything else.",
    )
    sc = a.scenarios[name]
    migration = st.slider(
        "Net migration (people a year)",
        0,
        200_000,
        int(sc["net_migration_per_year"]),
        5_000,
        key=f"{name}-mig",
        help="People arriving minus people leaving, each year. 143,641 in 2024 (INE estimate). More "
        "people means more households needing homes.",
    )
    income = st.slider(
        "Real income growth (% a year)",
        -1.0,
        4.0,
        float(sc["household_income_growth_real_pct"]),
        0.25,
        key=f"{name}-inc",
        help="Yearly growth of household income after inflation. Faster growth lets households "
        "afford dearer homes, but also pulls prices up.",
    )
    rate = st.slider(
        "Mortgage rate in 3 years (%)",
        1.0,
        6.5,
        float(sc["mortgage_rate_pct"]),
        0.25,
        key=f"{name}-rate",
        help="The interest rate on new housing loans, reached gradually over the next three years "
        "and held after that. 4.36% in 2024, 3.07% in 2025.",
    )
    completions = st.slider(
        "Completions a year (in 3 years)",
        15_000,
        80_000,
        int(sc["completions_per_year"]),
        1_000,
        key=f"{name}-comp",
        help="New homes completed per year, reached gradually over three years. 27,301 in 2025.",
    )
    half_life = st.slider(
        "Years for the other-demand boom to halve",
        1.0,
        10.0,
        float(sc["other_demand_half_life_years"]),
        0.5,
        key=f"{name}-fade",
        help="Tourism, foreign buyers, credit, expectations: demand that is not explained by "
        "wages or households. How many years until it is half as strong. "
        "The single least certain input.",
    )

    st.header(f"Policy (from {a.policy_start_year})")
    st.caption(
        "What the government could do. All at 0 means no policy; any change adds a cost and an effect "
        "to the results."
    )
    construction = st.slider(
        "Extra completions a year",
        0,
        30_000,
        0,
        1_000,
        help="Homes built each year on top of the scenario, through incentives or simpler rules.",
    )
    renovation = st.slider(
        "Vacant homes renovated a year",
        0,
        30_000,
        0,
        1_000,
        help="Empty homes put back into use through renovation grants.",
    )
    public = st.slider(
        "Public homes built a year",
        0,
        15_000,
        0,
        500,
        help="New publicly owned homes to rent.",
    )
    imi = st.slider(
        "Change in the average IMI rate (pp)",
        -0.15,
        0.15,
        0.0,
        0.01,
        help="IMI is the yearly property tax. 'pp' means percentage points of the assessed value: "
        "-0.05 would lower an average rate of, say, 0.33% to 0.28%. The urban rate cannot go below 0.30% and most "
        "councils are already there: "
        "without a change of the law the average rate can fall by about 0.03 pp (reports/p3_policy.md, p3_05). "
        "Larger cuts assume a lower floor.",
    )
    imt = st.slider(
        "Change in the average IMT rate on homes (pp of price)",
        -2.0,
        2.0,
        0.0,
        0.25,
        help="IMT is the tax paid when a home is bought, a percentage of the price. -1 means one "
        "percentage point less (for example 6% instead of 7%).",
    )
    cap = st.radio(
        "Do tax changes show up in prices?",
        ["Unknown (0 to full)", "Not at all", "Fully"],
        help="When buying a home gets cheaper through a lower tax, buyers may bid prices up so the "
        "saving ends up in the price (capitalisation). Phase 3 could not tell: every interval "
        "contains both zero and full capitalisation.",
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
st.markdown(
    f"**The four numbers, for the median municipality in {a.end_year}.** *Price-to-income*: years of "
    "household income a typical home costs (higher is worse). *Mortgage burden*: the share of income "
    "that the yearly payments on an 80% loan over 30 years would take; above 100% means ownership is "
    "out of reach for a typical household. *Policy effect*: how many years of income your policy "
    "takes off (or adds to) price-to-income. *Budget cost*: public spending plus lost tax revenue, "
    f"added up from {a.policy_start_year}."
)
cols = st.columns(4)
cols[0].metric(
    f"Price-to-income, {a.end_year}",
    f"{pti[1]:.1f} years",
    f"{pti[1] - anc.pti_years:+.1f} vs {a.start_year} ({anc.pti_years:.1f})",
    delta_color="inverse",
)
cols[0].caption(f"years of income. 80% range: {pti[0]:.1f} to {pti[2]:.1f} years")
cols[1].metric(
    f"Mortgage burden, {a.end_year} (% of income)",
    f"{burden[1]:.0f}%",
    f"{burden[1] - anc.burden_pct:+.0f} pp",
    delta_color="inverse",
)
cols[1].caption(
    f"of income. 80% range: {burden[0]:.0f}% to {burden[2]:.0f}%. pp = percentage points since {a.start_year}"
)
if effect is not None:
    s = E.summarise(effect)
    cols[2].metric(
        "Policy effect on price-to-income", f"{-s['pti_gain_p50']:+.2f} years", delta_color="off"
    )
    cols[2].caption(
        f"years of income (negative = more affordable). 80% range: {-s['pti_gain_p90']:+.2f} to "
        f"{-s['pti_gain_p10']:+.2f}; improves affordability in {100 * s['share_improving']:.0f}% of draws"
    )
    cols[3].metric(
        "Budget cost to " + str(a.end_year),
        f"{s['cost_eur_p50'] / 1e9:.1f} bn EUR",
        help="Public spending plus lost IMI/IMT revenue, 2024 euros, no discounting.",
    )
    cols[3].caption(
        f"in billions of 2024 euros. Homes added by the policy: {s['homes_added_n_p50']:,.0f}"
    )
else:
    cols[2].metric("Policy effect", "none selected", delta_color="off")
    cols[2].caption("Move a policy slider in the sidebar to see what it would change.")
    cols[3].metric("Budget cost", "0 bn EUR", delta_color="off")
    cols[3].caption("No policy selected, so no cost.")


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
    st.markdown(
        f"**What this tab shows.** The path of affordability from {a.start_year} to {a.end_year} under "
        "the scenario you chose, for the median municipality (half of the municipalities are better off, "
        "half worse). Three charts:\n"
        "- **Price-to-income** (left): years of income needed to buy a typical home. The line going up "
        "means homes are getting harder to afford.\n"
        "- **Mortgage burden** (right): the share of income taken by loan payments, which rises with "
        "prices *and* with the interest rate.\n"
        f"- **Real house price index** (bottom): prices after inflation, with {a.start_year} = 100. The grey "
        "diamonds are the statistical forecast (ETS, tested on past data) for the first years, with "
        "their 80% range; the lines follow it for the first three years.\n\n"
        "**Solid line and shaded band.** The solid line is the median result of the 500 simulations and "
        "the band the 80% range. With a policy selected, the grey line is the same scenario *without* "
        "the policy and the blue line *with* it, so the gap between them is the policy's effect."
    )
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
    st.markdown(
        "**What this tab shows.** Whether there are enough homes for the households that form, and what "
        "your policy would cost.\n\n"
        "**Chart, how to read it.** Each year some new households form (through migration and smaller "
        "households) and some new homes are added. The line is the running total of households that "
        "have no usable home. Rising means the gap is widening; below zero means spare capacity. "
        "It counts how many households, not which municipalities they are in.\n\n"
        "**Cost table.** For each policy lever you moved, the public spending or lost tax revenue summed "
        f"from {a.policy_start_year} to {a.end_year}, in billions of 2024 euros."
    )
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
                "in plain words": PARAM_LABELS.get(k, k),
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
        "**What this tab shows.** The simulator cannot know how strongly prices react to a housing "
        "shortfall or how many renovated homes are really additional, so each of those numbers is "
        "given as a *low*, a *mid* and a *high* value. Every one of the 500 simulations draws each "
        "number from within its range, which is where the shaded bands come from."
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
    used = (
        "your policy"
        if not policy.is_empty
        else "the example mix (5,000 extra completions, 5,000 renovated and 2,500 public homes a year)"
    )
    st.markdown(
        f"**What this tab shows: which assumptions matter most.** Each row moves *one* input from its "
        f"low to its high value while all the others stay as you chose, and records the result in "
        f"{a.end_year}. A large *swing* means the answer depends heavily on that input; a swing of "
        "zero means the input does not affect the baseline path (it only matters for a policy). "
        "The two policy columns show how much the input changes what a policy "
        f"achieves, using {used}.\n\n"
        "**Reading the columns.** *Scenario input*: one of the five sliders. *Behavioural assumption*: "
        "one of the uncertain numbers on the Assumptions tab. Price-to-income is in years of "
        f"income; *policy effect* is the years taken off price-to-income in {a.end_year} "
        "(a larger number means a bigger improvement)."
    )
    table = sens.assign(
        parameter=sens["parameter"].map(PARAM_LABELS).fillna(sens["parameter"]),
        kind=sens["kind"].map(
            {"scenario": "Scenario input", "behaviour": "Behavioural assumption"}
        ),
    )[
        [
            "parameter",
            "kind",
            "low_pti_end",
            "high_pti_end",
            "swing_pti_end",
            "low_pti_gain",
            "high_pti_gain",
        ]
    ].rename(
        columns={
            "parameter": "Input",
            "kind": "Type",
            "low_pti_end": f"Price-to-income {a.end_year}, input low",
            "high_pti_end": f"Price-to-income {a.end_year}, input high",
            "swing_pti_end": "Swing (years)",
            "low_pti_gain": "Policy effect, input low (years)",
            "high_pti_gain": "Policy effect, input high (years)",
        }
    )
    st.dataframe(table.round(2), hide_index=True)

with tab5:
    st.markdown(
        "**Where will affordability worsen more than elsewhere?** A validated trend extrapolation (phase 4, "
        "`p4_03`), stated *relative to the median municipality*: it ranks places, it does not give their level, "
        "which is the scenario above. Coloured: the 80% interval (from past errors) excludes zero."
    )
    st.markdown(
        "**How to read the chart.** Each dot is a group of municipalities. Its position is how many "
        "percentage points *more* (right, orange) or *fewer* (left, blue) its price-to-income is expected "
        "to rise to 2026 than in the median municipality. The bar is an 80% range based on how wrong the "
        "method was in the past. Grey dots have a range that includes zero, so the data cannot say "
        "whether they will do better or worse than the median. The method simply continues the 2016-2024 "
        "trend of each group, and that was one boom period, so treat it as a ranking, not a forecast of "
        "levels. *Coast x density class* combines the groups defined on the Trends page (for example "
        "coastal and urban); *NUTS 3 region* uses the official statistical regions."
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
