"""Geographic dashboard: municipality map filtered by year, price, rent, income, affordability, supply."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pthousing.viz import dashboard as D

st.set_page_config(page_title="Geographic · Portugal's Housing Crisis", layout="wide")

TRANSPARENT = "rgba(0,0,0,0)"


@st.cache_data
def panel() -> pd.DataFrame:
    return D.load_panel()


@st.cache_data
def geometry() -> dict:
    return D.load_geometry()


p = panel()

st.title("Where is housing least affordable?")
st.markdown(
    "Each of Portugal's 308 municipalities colored by one measure at a time. Hover over the map for a "
    "municipality's value; use the sidebar to pick another measure, another year, or the change between "
    "two years. The box below always says what is on the map, in which unit and how to read the colors."
)

# ---- inputs --------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Map")
    column = st.selectbox(
        "Indicator",
        list(D.INDICATORS),
        format_func=lambda c: D.INDICATORS[c].label,
        help="Affordability first; the others explain it.",
    )
    ind = D.INDICATORS[column]
    years = D.years_with_data(p, column)
    mode = st.radio("Show", ["Level", "Change between two years"], horizontal=False)
    if mode == "Level":
        year = st.select_slider("Year", years, value=years[-1])
        since, relative = None, False
    else:
        if len(years) < 2:
            st.warning("This indicator has a single year.")
            st.stop()
        since, year = st.select_slider("Years", years, value=(years[0], years[-1]))
        if since == year:
            st.warning("Choose two different years.")
            st.stop()
        relative = st.toggle("As % change", value=ind.unit.startswith(("EUR", "residents")))
    territory = st.radio(
        "Area",
        list(D.TERRITORIES),
        format_func=D.TERRITORIES.get,
        help="Azores and Madeira are shown on their own so the mainland stays readable.",
    )

frame = D.map_frame(p, column, year, since, relative)
unit = "%" if (since is not None and relative) else ind.unit
if since is not None and not relative:
    unit = f"change in {ind.unit}"
shown = frame[frame["territory"] == territory]
n_missing = int(shown["value"].isna().sum())

# ---- what the map shows ---------------------------------------------------------------------------
vals = frame["value"].dropna()
what = f"{ind.label}, {year}" if since is None else f"{ind.label}, {since} to {year}"
fmt = ind.fmt if since is None else ind.fmt.replace("{:", "{:+")  # changes carry a sign
if since is None:
    reading = "Darker blue means a higher value."
    if ind.tone == "worse_high":
        reading += " Higher is worse for affordability."
    elif ind.tone == "better_high":
        reading += " Higher is better for affordability."
elif relative:
    reading = (
        f"Each municipality's value in {year} compared with {since}, as a percentage. "
        "Red marks the direction that is worse for affordability, blue the direction that is better, "
        "and white means little change."
        if ind.tone != "neutral"
        else f"Each municipality's value in {year} compared with {since}, as a percentage (white: little change)."
    )
else:
    reading = (
        f"Each municipality's value in {year} minus its value in {since}, in the unit above. "
        "Red marks the direction that is worse for affordability, blue the direction that is better, "
        "and white means little change."
        if ind.tone != "neutral"
        else f"Each municipality's value in {year} minus its value in {since}, in the unit above (white: little change)."
    )
with st.container(border=True):
    st.markdown(f"**You are looking at: {what}.** {ind.note}")
    st.markdown(
        f"**Unit:** {unit}.  \n**How to read the colors:** {reading}  \n"
        f"**Available years:** {years[0]} to {years[-1]}."
    )
    if ind.group == "Affordability":
        st.caption(
            "Affordability levels depend on the income concept and the assumed dwelling size, so read the "
            "ranking and the change between years more than the exact level."
        )

# ---- headline numbers ----------------------------------------------------------------------------
cols = st.columns(4)
cols[0].metric("Median municipality", fmt.format(vals.median()))
cols[0].caption(f"{unit}. Half of the municipalities are above this, half below.")
hi = frame.loc[frame["value"].idxmax()]
lo = frame.loc[frame["value"].idxmin()]
cols[1].metric("Highest", fmt.format(hi["value"]))
cols[1].caption(f"{unit}: {hi['muni_name']}")
cols[2].metric("Lowest", fmt.format(lo["value"]))
cols[2].caption(f"{unit}: {lo['muni_name']}")
cols[3].metric("Municipalities with data", f"{len(vals)} of {len(frame)}")
cols[3].caption("The rest are not published or not observed that year.")

# ---- map -----------------------------------------------------------------------------------------
scale, mid = D.colour_scale(ind.tone, change=since is not None)
fig = px.choropleth(
    shown,
    geojson=geometry(),
    locations="muni_code",
    featureidkey="properties.muni_code",
    color="value",
    hover_name="muni_name",
    hover_data={"muni_code": False, "district": True, "value": ":,.2f"},
    color_continuous_scale=scale,
    color_continuous_midpoint=mid,
    labels={"value": unit, "district": "District"},
)
missing = shown[shown["value"].isna()]
if len(
    missing
):  # drawn as gray outlines so a municipality without a value reads as "no data", not a hole
    fig.add_trace(
        go.Choropleth(
            geojson=geometry(),
            locations=missing["muni_code"],
            featureidkey="properties.muni_code",
            z=[0] * len(missing),
            colorscale=[[0, "rgba(137,135,129,0.6)"], [1, "rgba(137,135,129,0.6)"]],
            showscale=False,
            text=missing["muni_name"],
            hovertemplate="%{text}: no value<extra></extra>",
            marker_line_color="rgba(137,135,129,0.6)",
            marker_line_width=0.3,
        )
    )
fig.update_geos(
    fitbounds="locations", visible=False, bgcolor=TRANSPARENT, projection_type="mercator"
)
fig.update_traces(marker_line_color="rgba(137,135,129,0.6)", marker_line_width=0.3)
fig.update_layout(
    title=what,
    height=620,
    margin=dict(l=0, r=0, t=50, b=0),
    paper_bgcolor=TRANSPARENT,
    plot_bgcolor=TRANSPARENT,
    coloraxis_colorbar=dict(title=dict(text=unit, side="right"), thickness=14, len=0.7),
)
left, right = st.columns([3, 2])
left.plotly_chart(fig, width="stretch")
if n_missing:
    left.caption(
        f"{n_missing} municipalities in this area have no value for {what.lower()} and show in gray."
    )

# ---- rankings ------------------------------------------------------------------------------------
with right:
    st.subheader("Ranking")
    ranked = (
        shown.dropna(subset=["value"])
        .assign(value=lambda x: x["value"].round(2))
        .sort_values("value", ascending=False)
        .rename(columns={"muni_name": "Municipality", "district": "District", "value": unit})
    )
    top_n = st.slider("Show", 5, 25, 10, 5)
    st.markdown(f"**Highest {top_n}**")
    st.dataframe(ranked[["Municipality", "District", unit]].head(top_n), hide_index=True)
    st.markdown(f"**Lowest {top_n}**")
    st.dataframe(ranked[["Municipality", "District", unit]].tail(top_n).iloc[::-1], hide_index=True)

st.caption(
    "Source: INE, Banco de Portugal, AT, AIMA; own calculations (see `docs/methodology.md`)."
)
