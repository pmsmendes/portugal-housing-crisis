"""Streamlit entry point: uv run streamlit run app/Home.py"""

import streamlit as st

from pthousing.viz import dashboard as D

st.set_page_config(page_title="Portugal's Housing Crisis", layout="wide")


@st.cache_data
def panel():
    return D.load_panel()


p = panel()
years = D.years_with_data(p, "pti_years")
first, last = years[0], years[-1]
now = p[p["year"] == last]
then = p[p["year"] == first]
pti_now, pti_then = now["pti_years"].median(), then["pti_years"].median()

st.title("Portugal's Housing Crisis")
st.markdown(
    "**Why has housing become so hard to afford in Portugal, where did it get worse, and what could be "
    "done about it?** This dashboard answers that with public data on all 308 municipalities: what "
    "happened, what explains it, what a policy tried so far achieved, and what the next ten years could "
    "look like under different assumptions."
)

# ---- the answer in short ---------------------------------------------------------------------------
st.subheader("The short answer")
st.markdown(
    f"- **Homes became much harder to afford.** In {first} the middle municipality needed "
    f"**{pti_then:.1f} years** of a household's income to buy a home; in {last} it needs "
    f"**{pti_now:.1f} years**.\n"
    "- **Prices left incomes behind.** Since 2013, after inflation, house prices rose 129% while "
    "wages rose 27%.\n"
    "- **Where you live matters most.** Region, coast and density explain about half of where "
    "affordability got worse. Immigration, tourism, second homes and supply add little on top of "
    "that, and none can be called a proven cause.\n"
    "- **Higher interest rates hit the monthly payment, not just the price.** The payment burden on "
    "a mortgage went from "
    f"{then['mortgage_burden_pct'].median():.0f}% to {now['mortgage_burden_pct'].median():.0f}% "
    "of income.\n"
    "- **Little is being built.** About 93,000 new homes a year were completed in 1995-2004, against "
    "16,000 in 2015-2025.\n"
    "- **The one policy tested is inconclusive.** Cutting the municipal property tax (IMI) cannot be "
    "told apart from having no effect on prices; the check that would make the result credible fails."
)

cols = st.columns(3)
cols[0].metric(
    f"Price-to-income, {last}",
    f"{pti_now:.1f} years",
    f"{pti_now - pti_then:+.1f} years since {first}",
    delta_color="inverse",
    help="Median municipality: years of median household income needed to buy a home of the municipality's average size.",
)
cols[0].caption(
    "How many years of income a home costs. Higher means harder to afford; red is the worse direction."
)
cols[1].metric(
    f"Mortgage burden, {last}",
    f"{now['mortgage_burden_pct'].median():.0f}% of income",
    f"{now['mortgage_burden_pct'].median() - then['mortgage_burden_pct'].median():+.0f} points since {first}",
    delta_color="inverse",
    help="Yearly payments on an 80% loan over 30 years at the new-loan rate, over median income.",
)
cols[1].caption("Share of income the yearly loan payments would take for a typical home.")
cols[2].metric(
    f"Price per m², {last}",
    f"{now['price_sqm_eur_real'].median():,.0f} EUR",
    f"{100 * (now['price_sqm_eur_real'].median() / then['price_sqm_eur_real'].median() - 1):+.0f}% since {first}",
    delta_color="inverse",
    help="Median municipality, constant 2024 euros.",
)
cols[2].caption(
    "Median sale price per square metre, in 2024 euros: the change is real, with inflation removed."
)
st.caption(
    f"The figures above are for the median municipality (half of the municipalities are above, half "
    f"below), {first} to {last}."
)

st.divider()

# ---- the pages -------------------------------------------------------------------------------------
st.subheader("What is on each page")
st.markdown("Use the sidebar to move between pages. They follow the four phases of the project.")
a, b = st.columns(2)
with a.container(border=True):
    st.markdown(
        "#### 1. Evidence: Geographic and Trends\n"
        "*What happened?* **Geographic** maps every municipality for one measure at a time (price against "
        "income, rents, payment burden, new building, foreign residents and more) and ranks the highest "
        "and lowest. **Trends** shows the same measures over time: the whole country, one municipality "
        "against all the others, and kinds of places (coastal or inland, urban or rural, tourist or not)."
    )
with b.container(border=True):
    st.markdown(
        "#### 2. Explanation: Explanatory\n"
        "*Why did it happen, and where?* Tests which factors go with the rise in unaffordability: where "
        "it happened, supply, population and immigration, tourism and second homes, wages, interest "
        "rates and credit. Every result is an **adjusted association**, not a proven cause, and the page "
        "says how far each association survives extra checks."
    )
a, b = st.columns(2)
with a.container(border=True):
    st.markdown(
        "#### 3. Policy: last tab of Explanatory\n"
        "*Did a policy work?* The one policy that could be tested, cuts in the municipal property tax "
        "(IMI), plus what IMI and the transfer tax (IMT) bring in, what the State spends on housing, "
        "how Portugal compares with other countries, and who would gain from tax cuts."
    )
with b.container(border=True):
    st.markdown(
        "#### 4. Forecast and simulate: Simulator\n"
        "*What next?* Scenario paths to 2035 for the median municipality. Move the sliders for "
        "migration, income growth, interest rates and building, add policy levers (more homes, "
        "renovation, public housing, tax changes) and see the effect on affordability, with its cost and "
        "its uncertainty. These are **scenarios, not predictions**."
    )

st.divider()

# ---- how to read -----------------------------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Terms used throughout")
    st.markdown(
        "- **Price-to-income**: years of a typical household's income needed to buy a typical home. "
        "The yardstick for affordability.\n"
        "- **Mortgage burden**: the yearly loan payments as a share of income, for a loan covering 80% "
        "of the price over 30 years at the going interest rate.\n"
        "- **Real vs nominal**: *nominal* is in the euros of the day; *real* removes inflation (here in "
        "2024 euros), so it shows what something costs compared with everything else.\n"
        "- **Median**: the middle value. Half of the municipalities are above it, half below.\n"
        "- **Municipality** (concelho): Portugal has 308; they are the unit of the maps and tables.\n"
        "- **IMI and IMT**: the yearly property tax and the tax paid when a property changes hands. "
        "Both are income of the local councils."
    )
with right:
    st.subheader("What to keep in mind")
    st.markdown(
        f"- **Different data, different years.** National series go back as far as 1988. Municipal "
        f"prices and incomes start in {first}, rents of new leases in 2020, foreign residents end in "
        "2023. Each page says which years it covers.\n"
        "- **Associations, not proof.** Where something goes with the rise in prices, that does not "
        "show it caused it. The project uses causal language only where a design passes its own test.\n"
        "- **Levels are indicative.** Affordability figures depend on how income and home size are "
        "measured. Rankings and changes are more reliable than any single level.\n"
        "- **Some places have no data.** Small municipalities often have too few sales or leases to "
        "publish a price or rent; they show in grey on the maps."
    )

st.caption(
    "Source: INE, Banco de Portugal, Autoridade Tributária, AIMA, RNAL, CAOP; own calculations. "
    "Code, methodology and full write-ups: see the project README."
)
