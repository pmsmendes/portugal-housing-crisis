"""Streamlit entry point: uv run streamlit run app/Home.py"""

import streamlit as st

from pthousing.viz import dashboard as D

st.set_page_config(page_title="Portugal's Housing Crisis", layout="wide")


@st.cache_data
def panel():
    return D.load_panel()


p = panel()
last = D.years_with_data(p, "pti_years")[-1]
now = p[p["year"] == last]
first = D.years_with_data(p, "pti_years")[0]
then = p[p["year"] == first]

st.title("Portugal's Housing Crisis")
st.markdown(
    "Evidence, explanation, policy evaluation and scenarios for **housing affordability** across Portugal's "
    "308 municipalities. Use the pages in the sidebar to explore."
)

cols = st.columns(3)
cols[0].metric(
    f"Price-to-income, {last}",
    f"{now['pti_years'].median():.1f} years",
    f"{now['pti_years'].median() - then['pti_years'].median():+.1f} since {first}",
    delta_color="inverse",
    help="Median municipality: years of median household income to buy a home of the municipality's average size.",
)
cols[1].metric(
    f"Mortgage burden, {last}",
    f"{now['mortgage_burden_pct'].median():.0f}% of income",
    f"{now['mortgage_burden_pct'].median() - then['mortgage_burden_pct'].median():+.0f} pp since {first}",
    delta_color="inverse",
    help="Yearly payments on an 80% loan over 30 years at the new-loan rate, over median income.",
)
cols[2].metric(
    f"Real price per m², {last}",
    f"{now['price_sqm_eur_real'].median():,.0f} EUR",
    f"{100 * (now['price_sqm_eur_real'].median() / then['price_sqm_eur_real'].median() - 1):+.0f}% since {first}",
    delta_color="inverse",
    help="Median municipality, constant 2024 euros.",
)

st.divider()
st.subheader("The four phases")
st.markdown(
    """
1. **Evidence.** What happened to prices, rents, income and affordability, nationally and by municipality.
   *Pages: Geographic, Trends.*
2. **Explanation.** Where and why affordability worsened: geography accounts for most of it, and the
   usual suspects (immigration, tourism, second homes, supply) add little beyond it. Adjusted
   associations, not causal claims. *Page: Explanatory.*
3. **Policy evaluation.** Did municipal property-tax cuts raise prices? Inconclusive: the design fails
   its pre-trend test. *Page: Explanatory, last tab.*
4. **Forecast and simulate.** A validated two-year forecast, then scenarios to 2035 with supply and tax
   levers, their cost and their uncertainty. *Page: Simulator.*
"""
)
st.caption(
    "Source: INE, Banco de Portugal, Autoridade Tributária, AIMA, RNAL, CAOP; own calculations. "
    "Code and write-ups: see the project README."
)
