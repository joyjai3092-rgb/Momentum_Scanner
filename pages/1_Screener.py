import io
import math

import numpy as np
import pandas as pd
import streamlit as st

from momentum import formulas as fml
from momentum import ui
from momentum.config import WARMUP_CALENDAR_DAYS
from momentum.data import DataError
from momentum import advisor
from momentum.indicators import Indicators
from momentum.regime import build_signal, equal_weight_index, regime_status
from momentum.scoring import make_scorer, rank_table, snapshot

EMA_CHOICES = [34, 68, 100, 150, 200]
MACD_CHOICES = ["35 70 12", "50 100 15", "75 150 12"]
ST_CHOICES = ["1 1", "1 2", "1 2.5"]

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

# ------------------------------------------------------------------ step 4: market check
st.subheader("Step 4 - Is the market healthy enough to buy? (regime filter)")
g1, g2, g3 = st.columns(3)
regime = g1.selectbox("Filter", ["SUPERTREND", "EMA", "MACD", "None"], key="scr_regime",
                      help="Checks the market index with a simple trend rule. Default = the Sigma guide's example (SuperTrend 1 2.5 on weekly candles).")
params: tuple = ()
if regime == "SUPERTREND":
    a, b = g2.selectbox("SuperTrend (period multiplier, weekly)", ST_CHOICES, index=2, key="scr_st").split()
    params = (int(a), float(b))
elif regime == "EMA":
    params = (g2.selectbox("EMA length (days)", EMA_CHOICES, index=2, key="scr_ema"),)
elif regime == "MACD":
    params = tuple(int(x) for x in g2.selectbox("MACD (fast slow signal, daily)", MACD_CHOICES, key="scr_macd").split())
action = g3.radio("If the market is weak", ["Half Portfolio", "Go Cash"], key="scr_action", horizontal=True,
                  help="Half Portfolio: sell half of each holding and keep at most 50% invested. Go Cash: sell everything.")
index_ticker = ui.index_picker("scr")
use_avg = st.checkbox("Use the average of MY uploaded stocks as the 'market' instead of an index", key="scr_use_avg",
                      help="Fallback when the index download fails. Less reliable than a real index.")

# ------------------------------------------------------------------ step 5: holdings
st.subheader("Step 5 - Monthly rebalance advisor (optional)")
st.caption("Enter what you hold today. The app tells you what to sell, trim, keep and buy using the same rules as the Backtest.")
h_up = st.file_uploader("Upload holdings (Excel / CSV with columns Symbol and Qty) - or type them in the table below",
                        type=["xlsx", "xls", "csv"], key="scr_hold_up")
if h_up is not None:
    try:
        raw_h = pd.read_csv(h_up) if h_up.name.lower().endswith(".csv") else pd.read_excel(h_up)
        st.session_state["scr_hold_tbl"] = advisor.read_holdings(raw_h)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read the holdings file: {exc}")
hold_start = st.session_state.get("scr_hold_tbl", pd.DataFrame({"Symbol": pd.Series(dtype=str), "Qty": pd.Series(dtype=int)}))
holdings_in = st.data_editor(hold_start, num_rows="dynamic", key="scr_hold_editor", hide_index=True,
                             column_config={"Symbol": st.column_config.TextColumn(help="e.g. RELIANCE"),
                                            "Qty": st.column_config.NumberColumn(min_value=0, step=1, help="Number of shares you hold.")})
a1, a2, a3, a4 = st.columns(4)
exit_rank = a1.number_input("Exit rank", min_value=1, max_value=1000, value=2 * 20, step=1, key="scr_exit",
                            help="Sell a holding only when its rank is worse than this. Must be at least 'Stocks to hold'.")
extra_cash = a2.number_input("Extra cash to add (Rs.)", min_value=0, value=0, step=10000, key="scr_cash",
                             help="New money (or cash already lying idle) that should also be invested.")
cost_pct = a3.number_input("Cost per trade (%)", min_value=0.0, max_value=5.0, value=0.2, step=0.05, key="scr_cost")
halved = a4.checkbox("I already halved my portfolio last time", key="scr_halved",
                     help="Tick this if the market was weak at your last rebalance and you sold half. "
                          "If the market is healthy now, the advisor will suggest re-investing the idle cash.")

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

    # ---- market check
    status = {"known": False, "healthy": True}
    if regime != "None":
        ohlc, src = None, ""
        if not use_avg:
            ohlc = ui.cached_index(index_ticker, start, end, bool(st.session_state.get("demo")))
            src = f"index {index_ticker}"
        if ohlc is None or ohlc.empty:
            if not use_avg:
                st.warning(f"No data for index '{index_ticker}' - using the average of your uploaded stocks as the 'market' instead.")
            ohlc, src = equal_weight_index(close), "the average of your uploaded stocks"
        sig = build_signal(ohlc, regime, params) if ohlc is not None else None
        status = regime_status(sig, date)
        rtxt = {"SUPERTREND": f"SuperTrend {params[0] if params else ''} {params[1] if params else ''} (weekly)",
                "EMA": f"EMA {params[0] if params else ''}", "MACD": "MACD " + " ".join(map(str, params))}[regime]
        if not status["known"]:
            st.info("Not enough market history to judge the regime.")
        elif status["healthy"]:
            st.success(f"✅ **Market looks HEALTHY - new entries are OK.** ({rtxt} on {src}; healthy since {status['since'].date()}, "
                       f"{status['days']} trading days.)")
        else:
            todo = ("sell half of each holding and keep at most 50% invested" if action == "Half Portfolio"
                    else "sell everything and wait in cash")
            st.warning(f"⛔ **Market looks WEAK - avoid new entries.** ({rtxt} on {src}; weak since {status['since'].date()}, "
                     f"{status['days']} trading days.) Rule you chose: {todo}.")
        st.caption("A rule-based trend signal, not a forecast. It can lag and give false alarms.")

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

    # ---- monthly rebalance advisor
    try:
        hold = advisor.read_holdings(holdings_in) if len(holdings_in) else pd.DataFrame(columns=["Symbol", "Qty"])
    except ValueError as exc:
        st.error(str(exc))
        hold = pd.DataFrame(columns=["Symbol", "Qty"])
    if len(hold):
        st.subheader("Monthly rebalance advice")
        if exit_rank < n_hold:
            st.error("Exit rank must be equal to or bigger than 'Stocks to hold'.")
        else:
            ranked_all = meta.join(rt.join(snap[["Price"]]), how="inner").reset_index(drop=True)
            plan_df, info = advisor.plan(ranked_all, hold, int(n_hold), int(exit_rank), bool(status.get("healthy", True)),
                                         action, bool(halved), float(extra_cash), float(cost_pct))
            st.write(f"Portfolio value about **Rs. {info['portfolio_value']:,.0f}** · one slot = Rs. {info['slot']:,.0f} · "
                     f"**{info['n_exit']} exit, {info['n_trim']} trim, {info['n_buy']} buy, {info['n_topup']} top-up, {info['n_hold']} keep**")
            st.dataframe(plan_df, hide_index=True, column_config={
                "Price": st.column_config.NumberColumn(format="%.2f"),
                "Trade value (Rs.)": st.column_config.NumberColumn(format="%.0f"),
                "Rank": st.column_config.NumberColumn(format="%d")})
            if info["unpriced"]:
                st.warning("No price or score for: " + ", ".join(info["unpriced"]) +
                           ". Check the spelling, or add them to your stock list in Step 1 (holdings outside the list cannot be ranked).")
            if info["free_slots"] > 0:
                st.caption(f"{info['free_slots']} slot(s) stay empty (market rule, or no affordable stock). Cash left about Rs. {info['cash_left']:,.0f}.")
            st.download_button("Download advice (CSV)", plan_df.to_csv(index=False).encode("utf-8"),
                               file_name=f"rebalance_advice_{date.date()}.csv", mime="text/csv")
            st.caption("Prices are the last close in the data; real trades will differ a little. Whole shares only.")

    st.download_button("Download ranking (CSV)", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"momentum_ranking_{date.date()}.csv", mime="text/csv")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        out.to_excel(xw, sheet_name="Full ranking", index=False)
        out[out["Buy list"] == "BUY"].to_excel(xw, sheet_name="Buy list", index=False)
    st.download_button("Download ranking (Excel)", buf.getvalue(), file_name=f"momentum_ranking_{date.date()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption(ui.DISCLAIMER)
