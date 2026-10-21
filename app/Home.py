"""Streamlit entry point: uv run streamlit run app/Home.py"""

import streamlit as st

st.set_page_config(page_title="Portugal's Housing Crisis", layout="wide")

st.title("Portugal's Housing Crisis")
st.markdown(
    "Evidence, explanation, policy evaluation and scenarios for housing affordability "
    "across Portuguese municipalities. Use the pages in the sidebar to explore."
)
