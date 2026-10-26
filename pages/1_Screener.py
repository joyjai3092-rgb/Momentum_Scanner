import io
import math

import numpy as np
import pandas as pd
import streamlit as st

from momentum import formulas as fml
from momentum import ui
from momentum.config import WARMUP_CALENDAR_DAYS
from momentum.data import DataError
from momentum.indicators import Indicators
from momentum.scoring import make_scorer, rank_table, snapshot

st.set_page_config(page_title="Screener - Momentum Scanner", page_icon="🔎", layout="wide")
ui.sidebar()
st.title("🔎 Momentum Screener")
st.caption("Rank the stocks in your list with a momentum formula, as on a chosen date.")

# ------------------------------------------------------------------ step 1: list
st.subheader("Step 1 - Your stock list")
universe = ui.universe_section()

# ------------------------------------------------------------------ step 2: formula
st.subheader("Step 2 - Choose a formula")
fid, custom_text = ui.formula_picker("scr")

# ------------------------------------------------------------------ step 3: settings
st.subheader("Step 3 - Settings")
c1, c2, c3, c4 = st.columns(4)
asof = c1.date_input("Rank as on (working day)", value=pd.Timestamp.today().normalize(), max_value=pd.Timestamp.today().normalize(),
                     help="The ranking uses closing prices up to this date. If it is a holiday the previous trading day is used.")
n_hold = c2.number_input("Stocks to hold", min_value=1, max_value=200, value=20, step=1,
                         help="How many top-ranked stocks you want in the portfolio.")
capital = c3.number_input("Investment amount (Rs.)", min_value=1000, value=100000, step=10000,
                          help="Split equally across the stocks to hold - same as Sigma's Quantity Calculator.")
sector_options = []
price_min, price_max = 0.0, 0.0
if universe is not None:
    sector_options = sorted({s for s in universe["Sector"].astype(str) if s and s.lower() != "nan"})
sectors = c4.multiselect("Sectors (empty = all)", sector_options)
p1, p2 = st.columns(2)
price_min = p1.number_input("Minimum price (Rs., 0 = no limit)", min_value=0.0, value=0.0, step=10.0)
price_max = p2.number_input("Maximum price (Rs., 0 = no limit)", min_value=0.0, value=0.0, step=100.0)

go = st.button("Run screener", type="primary", disabled=(universe is None or (fid == fml.CUSTOM_ID and custom_text is None)))
if universe is None:
    st.info("Load a stock list in Step 1 to enable the button.")

# ------------------------------------------------------------------ run
if go:
    u = universe.copy()
    if sectors:
        u = u[u["Sector"].isin(sectors)]
    if u.empty:
        st.error("No stocks left after the sector filter.")
        st.stop()
    asof_ts = pd.Timestamp(asof)
    start = (asof_ts - pd.Timedelta(days=WARMUP_CALENDAR_DAYS)).strftime("%Y-%m-%d")
    end = asof_ts.strftime("%Y-%m-%d")
    try:
        with st.spinner("Downloading prices - this can take a minute for big lists..."):
            close, failed = ui.cached_prices(tuple(u["Ticker"]), start, end, bool(st.session_state.get("demo")))
    except DataError as exc:
        st.error(str(exc))
        st.stop()
    avail = close.index[close.index <= asof_ts]
    if len(avail) == 0:
        st.error("No price data on or before that date.")
        st.stop()
    date = avail.max()
    ind = Indicators(close)
    scorer = make_scorer(fid, custom_text)
    rt = rank_table(ind, date, scorer)
    if rt.empty:
        st.error("None of the stocks has enough price history for this formula on that date. "
                 "Try an earlier/later date or a formula with a shorter look-back.")
        st.stop()
    snap = snapshot(ind, date)
    out = rt.join(snap)
    meta = u.set_index("Ticker")[["Symbol", "Name", "Sector"]]
    out = meta.join(out, how="inner").sort_values("Rank")
    out = out.reset_index(drop=True)
    if price_min > 0:
        out = out[out["Price"] >= price_min]
    if price_max > 0:
        out = out[out["Price"] <= price_max]
    out = out.reset_index(drop=True)
    out["Rank"] = np.arange(1, len(out) + 1)

    # Sigma-style quantity calculator: equal money per stock, skip stocks that cost more than one slot
    per_stock = capital / n_hold
    out["Qty"] = np.floor(per_stock / out["Price"]).astype(int)
    pick, picked = [], 0
    for q in out["Qty"]:
        if picked < n_hold and q >= 1:
            pick.append(True)
            picked += 1
        else:
            pick.append(False)
    out["Buy list"] = np.where(pick, "BUY", "")
    out["Amount (Rs.)"] = np.where(out["Buy list"] == "BUY", out["Qty"] * out["Price"], np.nan)

    lbl = custom_text if fid == fml.CUSTOM_ID else fml.label(fml.get_formula(fid))
    st.success(f"Ranked **{len(out)}** stocks using **{lbl}** on **{date.date()}** (latest available trading day on or before your date).")
    if st.session_state.get("demo"):
        st.warning("DEMO DATA - these prices are made up.")
    if failed:
        with st.expander(f"{len(failed)} symbol(s) had no price data and were skipped"):
            st.write(", ".join(failed))
            st.caption("Common reasons: renamed/merged/delisted company, or a Yahoo Finance gap.")
    missing_hist = len(close.columns) - len(rt)
    if missing_hist > 0:
        st.caption(f"{missing_hist} stock(s) lack enough history for this formula and are not ranked.")

    tab1, tab2 = st.tabs(["Buy list", "Full ranking"])
    show_cols = ["Rank", "Symbol", "Name", "Sector", "Price", "Score", "1M %", "3M %", "6M %", "12M %", "6M Vol %", "FIP", "% of 52W high"]
    cfg = {
        "Price": st.column_config.NumberColumn(format="%.2f"),
        "Score": st.column_config.NumberColumn(format="%.4f", help="Higher = better. The size of the score does not matter, only the order."),
        "1M %": st.column_config.NumberColumn(format="%.1f"),
        "3M %": st.column_config.NumberColumn(format="%.1f"),
        "6M %": st.column_config.NumberColumn(format="%.1f"),
        "12M %": st.column_config.NumberColumn(format="%.1f"),
        "6M Vol %": st.column_config.NumberColumn(format="%.1f", help="Yearly-scaled volatility over 180 trading days."),
        "FIP": st.column_config.NumberColumn(format="%.2f", help="Frog-in-the-Pan smoothness: more negative = smoother climb."),
        "% of 52W high": st.column_config.NumberColumn(format="%.1f"),
        "Qty": st.column_config.NumberColumn(help="Whole shares for one slot of your investment amount."),
        "Amount (Rs.)": st.column_config.NumberColumn(format="%.0f"),
    }
    with tab1:
        buy = out[out["Buy list"] == "BUY"][show_cols + ["Qty", "Amount (Rs.)"]]
        st.write(f"Top **{len(buy)}** stocks, about Rs. {per_stock:,.0f} each. "
                 "A stock too expensive for one slot is skipped and the next one is used (as in Sigma).")
        st.dataframe(buy, hide_index=True, column_config=cfg)
        if len(buy) < n_hold:
            st.warning(f"Only {len(buy)} stocks could be bought with these limits - consider a higher amount or fewer stocks.")
    with tab2:
        st.dataframe(out[show_cols + ["Qty", "Buy list"]], hide_index=True, column_config=cfg)

    st.download_button("Download ranking (CSV)", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"momentum_ranking_{date.date()}.csv", mime="text/csv")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        out.to_excel(xw, sheet_name="Full ranking", index=False)
        out[out["Buy list"] == "BUY"].to_excel(xw, sheet_name="Buy list", index=False)
    st.download_button("Download ranking (Excel)", buf.getvalue(), file_name=f"momentum_ranking_{date.date()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption(ui.DISCLAIMER)
