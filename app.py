"""Home page.  Run with:  streamlit run app.py"""
import streamlit as st

from momentum import ui

st.set_page_config(page_title="Momentum Scanner", page_icon="📈", layout="wide")
ui.sidebar()

st.title("📈 Momentum Investing Scanner")
st.write(
    "Rank NSE stocks by **momentum** (stocks that have been rising tend to keep rising for a while) "
    "and **test the idea on past data** - modelled on Sigma Scanner's way of scoring and back-testing."
)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### 1. Screener")
    st.write("Upload your stock list, pick a formula, and get today's ranking plus a buy list with quantities.")
    st.page_link("pages/1_Screener.py", label="Open the Screener", icon="🔎")
with c2:
    st.markdown("### 2. Backtest")
    st.write("Pick a date range and rules (number of stocks, exit rank, market filter) and see how the strategy would have done.")
    st.page_link("pages/2_Backtest.py", label="Open the Backtest", icon="🧪")
with c3:
    st.markdown("### 3. Learn momentum")
    st.write("A plain-English guide built from the research papers, the NSE method and the Sigma guides.")
    st.page_link("pages/3_Learn_Momentum.py", label="Open the guide", icon="📚")

st.divider()
st.markdown("#### Quick start (2 minutes)")
st.markdown(
    "1. Open **Screener** and tick *Use the sample list* - or upload your own Excel (needs a **Symbol** column).\n"
    "2. Switch on **Demo data** in the left bar if you only want to look around (prices are made up).\n"
    "3. Choose a formula from the dropdown. Click **❓ About this formula** to read what it means.\n"
    "4. Press **Run screener**."
)
st.info(
    "**Important limits:** prices come free from Yahoo Finance and can have gaps. Back-tests use the stock list you "
    "upload *today*, so they ignore stocks that were dropped or delisted in the past (survivorship bias) - "
    "real results would usually be lower."
)
st.caption(ui.DISCLAIMER)
