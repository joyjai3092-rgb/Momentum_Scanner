import io
import math

import numpy as np
import pandas as pd
import streamlit as st

from momentum import formulas as fml
from momentum import ui
from momentum.config import INDEX_EXTRA_DAYS, WARMUP_CALENDAR_DAYS
from momentum.data import DataError
from momentum import advisor, charts
from momentum.indicators import Indicators
from momentum.regime import TIMEFRAMES, build_signal, default_timeframe, equal_weight_index, regime_status
from momentum.scoring import entry_max_rank, make_filter, make_scorer, rank_table, snapshot

EMA_CHOICES = [34, 68, 100, 150, 200]
MACD_CHOICES = ["35 70 12", "50 100 15", "75 150 12"]
ST_CHOICES = ["1 1", "1 2", "1 2.5"]

st.set_page_config(page_title="Screener - Momentum Scanner", page_icon="🔎", layout="wide")
ui.sidebar()
ui.hero("🔎 Momentum Screener", "Rank the stocks in your list with a momentum formula, check the market, and get a buy list and a monthly rebalance plan.", pills=("Formulas + your own", "Filter rules", "Regime check", "Rebalance advisor"))

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
regime = g1.selectbox("Filter", ["SUPERTREND", "SIGMA SUPERTREND", "EMA", "MACD", "None"], key="scr_regime",
                      help="Checks the market index with a simple trend rule. Default = the Sigma guide's example (SuperTrend 1 2.5 on weekly candles).")
params: tuple = ()
if regime == "SUPERTREND":
    a = g2.number_input("ATR period", min_value=1, max_value=100, value=1, step=1, key="scr_st_p")
    b = g3.number_input("ATR multiplier", min_value=0.1, max_value=10.0, value=2.5, step=0.1, key="scr_st_m")
    params = (int(a), float(b))
elif regime == "SIGMA SUPERTREND":
    per = g2.number_input("ATR period", min_value=1, max_value=100, value=10, step=1, key="scr_sst_p")
    mul = g2.number_input("ATR multiplier", min_value=0.1, max_value=10.0, value=3.0, step=0.1, key="scr_sst_m")
    wil = st.radio("ATR method", ["Standard (RMA)", "Simple average"], key="scr_sst_atr", horizontal=True) == "Standard (RMA)"
    params = (int(per), float(mul), wil)
elif regime == "EMA":
    params = (int(g2.number_input("EMA length (candles)", min_value=2, max_value=400, value=100, step=1, key="scr_ema")),)
elif regime == "MACD":
    params = tuple(int(x) for x in g2.selectbox("MACD (fast slow signal, candles)", MACD_CHOICES, key="scr_macd").split())
    mc = g3.text_input("...or type your own MACD (fast slow signal)", key="scr_macd_own", placeholder="e.g. 12 26 9")
    if mc.strip():
        try:
            mp = tuple(int(x) for x in mc.split())
            assert len(mp) == 3 and all(x >= 1 for x in mp) and mp[0] < mp[1]
            params = mp
        except (ValueError, AssertionError):
            g3.error("Type three whole numbers: fast slow signal, with fast smaller than slow.")
action = st.radio("If the market is weak", ["Half Portfolio", "Go Cash"], key="scr_action", horizontal=True,
                  help="Half Portfolio: sell half of each holding and keep at most 50% invested. Go Cash: sell everything.")
timeframe = None
if regime != "None":
    timeframe = st.selectbox("Candle timeframe for the filter", TIMEFRAMES, index=TIMEFRAMES.index(default_timeframe(regime)),
                         key=f"scr_tf_{regime}",
                         help="The indicator is calculated on daily, weekly or monthly candles. EMA length / MACD / SuperTrend periods then count candles of that size.")
index_ticker = ui.index_picker("scr")
use_avg = st.checkbox("Use the average of MY uploaded stocks as the 'market' instead of an index", key="scr_use_avg",
                      help="Fallback when the index download fails. Less reliable than a real index.")

# ------------------------------------------------------------------ step 5: filters
st.subheader("Step 5 - Filter rules (optional)")
flt = ui.filter_controls("scr")

# ------------------------------------------------------------------ step 6: holdings
st.subheader("Step 6 - Monthly rebalance advisor (optional)")
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

go = st.button("Run screener", type="primary", disabled=(universe is None or not flt["ok"] or (fid == fml.CUSTOM_ID and custom_text is None)))
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
    scorer = make_scorer(fid, custom_text, (flt["pen_rule"], flt["pen_points"]))
    rt = rank_table(ind, date, scorer)
    if rt.empty:
        st.error("None of the stocks has enough price history for this formula on that date. "
                 "Try an earlier/later date or a formula with a shorter look-back.")
        st.stop()
    snap = snapshot(ind, date)
    out = rt.join(snap)
    out["Percentile"] = (1 - (out["Rank"] - 1) / len(out)) * 100          # 100 = best
    stock_filter = make_filter(flt["text"])
    if stock_filter is not None:
        f_pass, f_why = stock_filter(ind, date)
        out["Passes rules"] = f_pass.reindex(out.index, fill_value=False)
        out["Rules failed"] = f_why.reindex(out.index).fillna("")
    else:
        out["Passes rules"] = True
        out["Rules failed"] = ""
    out["Passes rules"] = out["Passes rules"].astype(bool)
    max_entry = entry_max_rank(len(out), flt["entry_pct"])
    out["Entry OK"] = True if max_entry is None else out["Rank"] <= max_entry
    meta = u.set_index("Ticker")[["Symbol", "Name", "Sector"]]
    out = meta.join(out, how="inner").sort_values("Rank")
    tick_map = dict(zip(out["Symbol"], out.index))                                  # Symbol -> Yahoo ticker
    out["Trend 6M"] = pd.Series({t: close[t].ffill().iloc[-126:].tolist() for t in out.index})        # mini price chart
    ranked_all = out[["Symbol", "Name", "Rank", "Price", "PDC"]].copy()          # for the advisor: ranks before any price filter
    ranked_all["Passes"] = out["Passes rules"]
    ranked_all["FilterWhy"] = out["Rules failed"]
    ranked_all = ranked_all.reset_index(drop=True)
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
    for q, ok_rule, ok_entry in zip(out["Qty"], out["Passes rules"], out["Entry OK"]):
        if picked < n_hold and q >= 1 and ok_rule and ok_entry:
            pick.append(True)
            picked += 1
        else:
            pick.append(False)
    out["Buy list"] = np.where(pick, "BUY", "")
    out["Amount (Rs.)"] = np.where(out["Buy list"] == "BUY", out["Qty"] * out["Price"], np.nan)
    out = out.rename(columns={"Price": "LTP"})                                  # LTP = last available price (see caption below)

    # ---- market check (computed once per run; shown below)
    status = {"known": False, "healthy": True}
    mk_msgs = []
    if regime != "None":
        ohlc, src = None, ""
        if not use_avg:
            idx_start = (asof_ts - pd.Timedelta(days=INDEX_EXTRA_DAYS)).strftime("%Y-%m-%d")
            ohlc = ui.cached_index(index_ticker, idx_start, end, bool(st.session_state.get("demo")))
            src = f"index {index_ticker}"
        if ohlc is None or ohlc.empty:
            if not use_avg:
                mk_msgs.append(("warning", f"No data for index '{index_ticker}' - using the average of your uploaded stocks as the 'market' instead."))
            ohlc, src = equal_weight_index(close), "the average of your uploaded stocks"
        sig = build_signal(ohlc, regime, params, timeframe) if ohlc is not None else None
        status = regime_status(sig, date)
        rtxt = {"SUPERTREND": f"SuperTrend {params[0] if params else ''} {params[1] if params else ''}",
                "SIGMA SUPERTREND": "Sigma SuperTrend " + " ".join(map(str, params[:2])),
                "EMA": f"EMA {params[0] if params else ''}", "MACD": "MACD " + " ".join(map(str, params))}[regime] + f", {timeframe} candles"
        if not status["known"]:
            mk_msgs.append(("info", "Not enough market history to judge the regime."))
        elif status["healthy"]:
            mk_msgs.append(("success", f"✅ **Market looks HEALTHY - new entries are OK.** ({rtxt} on {src}; healthy since {status['since'].date()}, "
                                       f"{status['days']} trading days.)"))
        else:
            todo = ("sell half of each holding and keep at most 50% invested" if action == "Half Portfolio"
                    else "sell everything and wait in cash")
            mk_msgs.append(("warning", f"⛔ **Market looks WEAK - avoid new entries.** ({rtxt} on {src}; weak since {status['since'].date()}, "
                                       f"{status['days']} trading days.) Rule you chose: {todo}."))
        mk_msgs.append(("caption", "A rule-based trend signal, not a forecast. It can lag and give false alarms."))
    mk = (("Not checked" if regime == "None" else ("Healthy ✅" if status.get("healthy", True) else "Weak ⛔"))
          if status.get("known") or regime == "None" else "Unknown")
    lbl = custom_text if fid == fml.CUSTOM_ID else fml.label(fml.get_formula(fid))
    st.session_state["scr_res"] = dict(
        out=out, ranked_all=ranked_all, close=close, date=date, failed=failed, status=status, mk=mk, mk_msgs=mk_msgs, lbl=lbl,
        missing_hist=len(close.columns) - len(rt), max_entry=max_entry, per_stock=per_stock, tick_map=tick_map,
        n_target=int(n_hold), demo=bool(st.session_state.get("demo")),
    )
    st.session_state.pop("scr_detail", None)

# ------------------------------------------------------------------ show results (kept on screen while you search / sort / pick a stock)
res = st.session_state.get("scr_res")
if res:
    out, ranked_all, close, date = res["out"].copy(), res["ranked_all"], res["close"], res["date"]
    failed, status, mk, max_entry, per_stock, tick_map = res["failed"], res["status"], res["mk"], res["max_entry"], res["per_stock"], res["tick_map"]
    lbl, n_target = res["lbl"], res["n_target"]
    st.success(f"Ranked **{len(out)}** stocks using **{lbl}** on **{date.date()}** (latest available trading day on or before your date).")
    st.caption(f"**LTP** = last available price in the data, i.e. the closing price on {date.date()} (end-of-day from Yahoo Finance, not a live tick).")
    if res["demo"]:
        st.warning("DEMO DATA - these prices are made up.")
    if failed:
        with st.expander(f"{len(failed)} symbol(s) had no price data and were skipped"):
            st.write(", ".join(failed))
            st.caption("Common reasons: renamed/merged/delisted company, or a Yahoo Finance gap.")
    missing_hist = res["missing_hist"]
    if missing_hist > 0:
        st.caption(f"{missing_hist} stock(s) lack enough history for this formula and are not ranked.")

    for _lvl, _txt in res["mk_msgs"]:
        getattr(st, _lvl)(_txt)

    n_buy = int((out["Buy list"] == "BUY").sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Stocks ranked", f"{len(out)}", border=True)
    k2.metric("Pass your rules", f"{int(out['Passes rules'].sum())}", f"{int((~out['Passes rules']).sum())} fail" if flt["text"] else None, delta_color="off", border=True)
    k3.metric("In the buy list", f"{n_buy}", f"target {n_target}", delta_color="off", border=True)
    k4.metric("Market", mk, border=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🟢 Buy list", "📋 Full ranking", "📊 Charts", "🔍 Stock detail"])
    out["Rules"] = np.where(out["Passes rules"], "✅ OK", "❌ " + out["Rules failed"])
    show_cols = ["Rank", "Symbol", "Name", "Sector", "LTP", "PDC", "Day %", "Trend 6M", "Score", "Percentile",
                 "1M %", "3M %", "6M %", "9M %", "12M %",
                 "1M Vol %", "3M Vol %", "6M Vol %", "9M Vol %", "12M Vol %",
                 "FIP", "Consistency", "% of 52W high", "Rules"]
    cfg = {
        "LTP": st.column_config.NumberColumn(format="%.2f", help="Last available price (closing price on the ranking date)."),
        "PDC": st.column_config.NumberColumn(format="%.2f", help="Previous Day Close: the close of the trading day before the ranking date."),
        "Day %": st.column_config.NumberColumn(format="%.2f", help="LTP compared with the previous day's close (PDC)."),
        "Trend 6M": st.column_config.LineChartColumn("Trend (6M)", help="Closing prices over the last 126 trading days."),
        "Score": st.column_config.NumberColumn(format="%.4f", help="Higher = better. The size of the score does not matter, only the order. With the score penalty on, this is a 0-100 percentile minus the penalty."),
        "1M %": st.column_config.NumberColumn(format="%.1f"),
        "3M %": st.column_config.NumberColumn(format="%.1f"),
        "6M %": st.column_config.NumberColumn(format="%.1f"),
        "12M %": st.column_config.NumberColumn(format="%.1f"),
        "9M %": st.column_config.NumberColumn(format="%.1f"),
        "Percentile": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100, help="100 = best score in your list, 0 = worst."),
        "1M Vol %": st.column_config.NumberColumn(format="%.1f", help="Yearly-scaled volatility (std of daily returns) over the window."),
        "3M Vol %": st.column_config.NumberColumn(format="%.1f", help="Yearly-scaled volatility over 63 trading days (3 x 21)."),
        "6M Vol %": st.column_config.NumberColumn(format="%.1f", help="Yearly-scaled volatility over 126 trading days (6 x 21)."),
        "9M Vol %": st.column_config.NumberColumn(format="%.1f"),
        "12M Vol %": st.column_config.NumberColumn(format="%.1f"),
        "FIP": st.column_config.NumberColumn(format="%.2f", help="Frog-in-the-Pan smoothness: more negative = smoother climb."),
        "Consistency": st.column_config.NumberColumn(format="%.1f", help="Same measure as FIP with the sign flipped and x100: (% up days - % down days) over 252 days, HIGHER = steadier."),
        "Rules": st.column_config.TextColumn(help="Result of your filter rules (Step 5)."),
        "% of 52W high": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100, help="100 = at its 52-week high."),
        "Qty": st.column_config.NumberColumn(help="Whole shares for one slot of your investment amount."),
        "Amount (Rs.)": st.column_config.NumberColumn(format="%.0f"),
    }
    with tab1:
        buy = out[out["Buy list"] == "BUY"][show_cols + ["Qty", "Amount (Rs.)"]]
        st.write(f"Top **{len(buy)}** stocks, about Rs. {per_stock:,.0f} each. "
                 "A stock too expensive for one slot is skipped and the next one is used (as in Sigma).")
        st.dataframe(ui.tag_table(buy), hide_index=True, column_config=cfg)
        if len(buy) < n_target:
            st.warning(f"Only {len(buy)} stocks could be bought with these limits - consider a higher amount or fewer stocks.")
    with tab2:
        f1, f2 = st.columns([2, 3])
        q = f1.text_input("🔎 Search symbol / name / sector", key="scr_search")
        view = f2.radio("Show", ["All ranked", "Buy list only", "Passing my rules", "Failing my rules"], horizontal=True, key="scr_view")
        tbl = out
        if q.strip():
            mask = (tbl["Symbol"].str.contains(q, case=False, na=False) | tbl["Name"].astype(str).str.contains(q, case=False, na=False)
                    | tbl["Sector"].astype(str).str.contains(q, case=False, na=False))
            tbl = tbl[mask]
        if view == "Buy list only":
            tbl = tbl[tbl["Buy list"] == "BUY"]
        elif view == "Passing my rules":
            tbl = tbl[tbl["Passes rules"]]
        elif view == "Failing my rules":
            tbl = tbl[~tbl["Passes rules"]]
        st.caption(f"{len(tbl)} of {len(out)} stocks shown. Click a column heading to sort.")
        st.dataframe(ui.tag_table(tbl[show_cols + ["Qty", "Buy list"]]), hide_index=True, column_config=cfg)
        if flt["text"] or max_entry is not None:
            st.caption(f"{int((~out['Passes rules']).sum())} stock(s) fail your rules and {int((~out['Entry OK']).sum())} are outside the entry limit - they are not in the buy list.")

    with tab3:
        ch = charts.risk_return_scatter(out)
        if ch is not None:
            st.markdown("**Return vs risk (12 months).** Each dot is a stock; bigger dot = better score. Top-left = good return for low volatility. Drag to pan, scroll to zoom, hover for details.")
            st.altair_chart(ch, width="stretch")
        sc = charts.sector_bar(out[out["Buy list"] == "BUY"])
        if sc is not None:
            st.markdown("**Buy list by sector**")
            st.altair_chart(sc, width="stretch")

    with tab4:
        pick = st.selectbox("Pick a stock", out["Symbol"].tolist(), key="scr_detail",
                            format_func=lambda x: f"{x} - {out.loc[out['Symbol'] == x, 'Name'].iloc[0]}")
        row = out[out["Symbol"] == pick].iloc[0]
        tkr = tick_map.get(pick)
        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Rank", f"{int(row['Rank'])} of {len(out)}", f"top {100 - row['Percentile'] + 100 / len(out):.0f}%", delta_color="off", border=True)
        a2.metric("LTP (Rs.)", f"{row['LTP']:,.2f}", f"{row['Day %']:+.2f}% vs PDC" if pd.notna(row["Day %"]) else None, border=True)
        a3.metric("PDC (Rs.)", f"{row['PDC']:,.2f}" if pd.notna(row["PDC"]) else "n/a", border=True)
        a4.metric("% of 52W high", f"{row['% of 52W high']:.0f}%" if pd.notna(row["% of 52W high"]) else "n/a", border=True)
        a5.metric("Decision", "BUY" if row["Buy list"] == "BUY" else "Not in buy list",
                  f"{int(row['Qty'])} shares" if row["Buy list"] == "BUY" else None, delta_color="off", border=True)
        pc = charts.price_chart(close[tkr].ffill().iloc[-300:]) if tkr in close.columns else None
        if pc is not None:
            st.markdown("**Price, last ~14 months** (green dashed line = 52-week high; yellow = 50-day average)")
            st.altair_chart(pc, width="stretch")
        st.markdown("**Why it ranked here** - each measure and where the stock stands among your list (100% = best)")
        spec = [("1M %", True), ("3M %", True), ("6M %", True), ("9M %", True), ("12M %", True),
                ("12M Vol %", False), ("Consistency", True), ("% of 52W high", True)]
        why = []
        for col, higher_better in spec:
            v = row[col]
            ser = out[col].dropna()
            pct = np.nan if pd.isna(v) or ser.empty else (ser <= v).mean() * 100 if higher_better else (ser >= v).mean() * 100
            why.append({"Measure": col, "Value": v, "Better than (% of list)": pct,
                        "Note": "lower is better" if not higher_better else ""})
        st.dataframe(pd.DataFrame(why), hide_index=True, column_config={
            "Value": st.column_config.NumberColumn(format="%.2f"),
            "Better than (% of list)": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100)})
        st.markdown("**Your filter rules:** " + (row["Rules"] if flt["text"] else "none set"))
        st.caption(f"Score {row['Score']:.4f} · formula: {lbl}")

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
            plan_df, info = advisor.plan(ranked_all, hold, int(n_hold), int(exit_rank), bool(status.get("healthy", True)),
                                         action, bool(halved), float(extra_cash), float(cost_pct),
                                         entry_max_rank=max_entry, force_exit_on_fail=flt["force_exit"])
            st.write(f"Portfolio value about **Rs. {info['portfolio_value']:,.0f}** · one slot = Rs. {info['slot']:,.0f} · "
                     f"**{info['n_exit']} exit, {info['n_trim']} trim, {info['n_buy']} buy, {info['n_topup']} top-up, {info['n_hold']} keep**")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("🔴 Exit", info["n_exit"], border=True)
            m2.metric("🟠 Trim", info["n_trim"], border=True)
            m3.metric("🟢 Buy", info["n_buy"] + info["n_topup"], border=True)
            m4.metric("⚪ Keep", info["n_hold"], border=True)
            m5.metric("Cash left (Rs.)", f"{info['cash_left']:,.0f}", border=True)
            icons = {"EXIT": "🔴 EXIT", "TRIM": "🟠 TRIM", "BUY": "🟢 BUY", "TOPUP": "🟢 TOPUP", "HOLD": "⚪ HOLD"}
            disp = plan_df.rename(columns={"Price": "LTP"}).assign(Action=lambda d: d["Action"].map(icons))
            st.dataframe(ui.tag_table(disp), hide_index=True, column_config={
                "LTP": st.column_config.NumberColumn(format="%.2f", help="Last available price."),
                "PDC": st.column_config.NumberColumn(format="%.2f", help="Previous Day Close."),
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

    out = out.drop(columns=["Trend 6M"])
    st.download_button("Download ranking (CSV)", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"momentum_ranking_{date.date()}.csv", mime="text/csv")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        out.to_excel(xw, sheet_name="Full ranking", index=False)
        out[out["Buy list"] == "BUY"].to_excel(xw, sheet_name="Buy list", index=False)
    st.download_button("Download ranking (Excel)", buf.getvalue(), file_name=f"momentum_ranking_{date.date()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption(ui.DISCLAIMER)
