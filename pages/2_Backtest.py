import io

import numpy as np
import pandas as pd
import streamlit as st

from momentum import formulas as fml
from momentum import ui
from momentum.backtest import BacktestConfig, run_backtest
from momentum.config import MIN_BACKTEST_DAYS, WARMUP_CALENDAR_DAYS
from momentum.data import DataError
from momentum.indicators import Indicators
from momentum.metrics import drawdown_series, monthly_returns, yearly_returns
from momentum.presets import PRESETS
from momentum.regime import build_signal

st.set_page_config(page_title="Backtest - Momentum Scanner", page_icon="🧪", layout="wide")
ui.sidebar()
st.title("🧪 Momentum Backtest")
st.caption("See how a rule-set would have performed on past prices between two dates.")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
EMA_CHOICES = [34, 68, 100, 150, 200]
MACD_CHOICES = ["35 70 12", "50 100 15", "75 150 12"]
ST_CHOICES = ["1 1", "1 2", "1 2.5"]
PRESET_NAMES = ["Custom (set everything myself)"] + [p.name for p in PRESETS]
today = pd.Timestamp.today().normalize()

DEFAULTS = {
    "bt_preset": PRESET_NAMES[0], "bt_capital": 100000, "bt_n": 20, "bt_exit": 40, "bt_freq": "Monthly",
    "bt_mday": 15, "bt_wday": "Friday", "bt_alt": "Previous", "bt_exec": "Same-day close", "bt_cost": 0.2,
    "bt_regime": "SUPERTREND", "bt_ema": 100, "bt_macd": MACD_CHOICES[0], "bt_st": "1 2.5",
    "bt_action": "Half Portfolio", "bt_sl": 10.0,
    "bt_start": (today - pd.DateOffset(years=3)).date(), "bt_end": today.date(), "bt_formula": "F11",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def apply_preset():
    name = st.session_state["bt_preset"]
    p = next((x for x in PRESETS if x.name == name), None)
    if p is None:
        return
    st.session_state.update({
        "bt_n": p.n_stocks, "bt_exit": p.exit_rank, "bt_freq": p.frequency, "bt_formula": p.formula_id,
        "bt_regime": p.regime, "bt_action": p.regime_action,
    })
    if p.frequency == "Monthly":
        st.session_state["bt_mday"] = p.rebalance_day
    else:
        st.session_state["bt_wday"] = WEEKDAYS[p.rebalance_day]
    if p.regime == "SUPERTREND":
        st.session_state["bt_st"] = " ".join(str(x) for x in p.regime_params)


# ------------------------------------------------------------------ 1. universe
st.subheader("1. Your stock list")
universe = ui.universe_section()

# ------------------------------------------------------------------ 2. strategy
st.subheader("2. Strategy")
st.selectbox("Start from a ready-made strategy", PRESET_NAMES, key="bt_preset", on_change=apply_preset,
             help="Picks sensible starting values for everything below. You can still change them.")
preset = next((p for p in PRESETS if p.name == st.session_state["bt_preset"]), None)
if preset:
    st.caption(f"**{preset.investor}** · risk: {preset.risk} · {preset.behaviour}  \n_Basis: {preset.basis}_")

fid, custom_text = ui.formula_picker("bt")

st.markdown("**Portfolio rules**")
r1, r2, r3, r4 = st.columns(4)
capital = r1.number_input("Starting capital (Rs.)", min_value=1000, step=10000, key="bt_capital",
                          help="Enter a plain number, e.g. 100000 for 1 lakh.")
n_stocks = r2.number_input("Number of stocks", min_value=1, max_value=200, step=1, key="bt_n",
                           help="With bigger capital, more stocks (e.g. 20-25) spread the risk.")
exit_rank = r3.number_input("Exit rank", min_value=1, max_value=1000, step=1, key="bt_exit",
                            help="A stock you hold is sold only when its rank falls BELOW this number. "
                                 "Must be at least the number of stocks. A bigger number = fewer trades.")
cost = r4.number_input("Cost per trade (%)", min_value=0.0, max_value=5.0, step=0.05, key="bt_cost",
                       help="Charged on every buy and every sell (brokerage, taxes, price slippage). "
                            "The 0.2 default is MY ASSUMPTION - change it to match your broker.")
if exit_rank < n_stocks:
    st.error("Exit rank must be equal to or bigger than the number of stocks.")

q1, q2, q3, q4 = st.columns(4)
freq = q1.radio("Rebalance", ["Monthly", "Weekly"], key="bt_freq", horizontal=True)
if freq == "Monthly":
    day = q2.number_input("Rebalance date (1-30)", min_value=1, max_value=30, step=1, key="bt_mday",
                          help="E.g. 15 = check the portfolio on the 15th of every month.")
else:
    wd = q2.selectbox("Rebalance day", WEEKDAYS, key="bt_wday")
    day = WEEKDAYS.index(wd)
alt = q3.radio("If that day is a holiday use the", ["Previous", "Next"], key="bt_alt", horizontal=True,
               help="Previous or next working day (same as Sigma's 'Alternative rebalance day').")
exe = q4.radio("Trade at", ["Same-day close", "Next-day close"], key="bt_exec", horizontal=True,
               help="Sigma-style is the same day's close. 'Next-day close' is more realistic because you can only trade after the ranking is known.")

# ------------------------------------------------------------------ 3. regime filter
st.subheader("3. Market regime filter (protects against bear markets)")
g1, g2, g3 = st.columns(3)
regime = g1.selectbox("Filter", ["None", "EMA", "MACD", "SUPERTREND", "EQUITY"], key="bt_regime",
                      help="EMA / MACD / SUPERTREND watch a market index. EQUITY watches your own realised losses. See the Learn page.")
params: tuple = ()
sl = 10.0
if regime == "EMA":
    params = (g2.selectbox("EMA length (days)", EMA_CHOICES, key="bt_ema"),)
elif regime == "MACD":
    params = tuple(int(x) for x in g2.selectbox("MACD (fast slow signal, daily)", MACD_CHOICES, key="bt_macd").split())
elif regime == "SUPERTREND":
    a, b = g2.selectbox("SuperTrend (period multiplier, weekly)", ST_CHOICES, key="bt_st").split()
    params = (int(a), float(b))
elif regime == "EQUITY":
    sl = g2.number_input("Realised loss limit (%)", min_value=0.5, max_value=50.0, step=0.5, key="bt_sl")
if regime in ("EMA", "MACD", "SUPERTREND"):
    action = g3.radio("When the market is weak", ["Half Portfolio", "Go Cash"], key="bt_action", horizontal=True)
elif regime == "EQUITY":
    action = "Half Portfolio"
    g3.info("EQUITY filter allows only Half Portfolio (Sigma rule).")
else:
    action = "Half Portfolio"
index_ticker = ui.index_picker("bt")

# ------------------------------------------------------------------ 4. dates
st.subheader("4. Date range")
d1, d2 = st.columns(2)
start = d1.date_input("Start date", key="bt_start", max_value=today.date())
end = d2.date_input("End date", key="bt_end", max_value=today.date())
date_ok = (pd.Timestamp(end) - pd.Timestamp(start)).days >= MIN_BACKTEST_DAYS
if not date_ok:
    st.error("Start and end date should be at least 3 months apart.")

ready = universe is not None and exit_rank >= n_stocks and date_ok and not (fid == fml.CUSTOM_ID and custom_text is None)
go = st.button("Run backtest", type="primary", disabled=not ready)
if universe is None:
    st.info("Load a stock list in section 1 to enable the button.")

# ------------------------------------------------------------------ run
if go:
    demo = bool(st.session_state.get("demo"))
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_CALENDAR_DAYS)).strftime("%Y-%m-%d")
    fetch_end = pd.Timestamp(end).strftime("%Y-%m-%d")
    try:
        with st.spinner("Downloading prices - this can take a few minutes for 500 stocks..."):
            close, failed = ui.cached_prices(tuple(universe["Ticker"]), fetch_start, fetch_end, demo)
            index_ohlc = ui.cached_index(index_ticker, fetch_start, fetch_end, demo)
    except DataError as exc:
        st.error(str(exc))
        st.stop()
    notes = []
    if index_ohlc is None or index_ohlc.empty:
        notes.append(f"No data for index '{index_ticker}'. The benchmark line and the regime filter are switched off - try another index ticker.")
        index_ohlc = None
    cfg = BacktestConfig(
        start=pd.Timestamp(start), end=pd.Timestamp(end), capital=float(capital), n_stocks=int(n_stocks),
        exit_rank=int(exit_rank), frequency=freq, rebalance_day=int(day), alt_day=alt, execution=exe,
        cost_pct=float(cost), regime=regime if index_ohlc is not None or regime == "EQUITY" else "None",
        regime_params=params, regime_action=action, equity_sl_pct=float(sl),
    )
    ind = Indicators(close)
    sig = build_signal(index_ohlc, regime, params) if (index_ohlc is not None and regime in ("EMA", "MACD", "SUPERTREND")) else None
    try:
        with st.spinner("Running the backtest..."):
            res = run_backtest(close, index_ohlc, cfg, fid, custom_text, ind=ind, regime_signal=sig)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    res.notes = notes + res.notes
    first_price = close.index[0]
    if first_price > pd.Timestamp(start) - pd.Timedelta(days=250):
        res.notes.append("The downloaded history starts late, so the first rebalances may be skipped until 12 months of data exist.")
    st.session_state["bt"] = dict(res=res, close=close, ind=ind, sig=sig, index_ohlc=index_ohlc,
                                  failed=failed, custom=custom_text, demo=demo)
    st.session_state.pop("bt_compare", None)

# ------------------------------------------------------------------ results
bt = st.session_state.get("bt")
if bt:
    res = bt["res"]
    cfg = res.config
    m, bm = res.metrics, res.benchmark_metrics
    st.divider()
    st.subheader("Results")
    if bt["demo"]:
        st.warning("DEMO DATA - these results come from made-up prices and mean nothing.")
    for n in res.notes:
        st.warning(n)
    if bt["failed"]:
        with st.expander(f"{len(bt['failed'])} symbol(s) had no price data and were skipped"):
            st.write(", ".join(bt["failed"]))
    lbl = bt["custom"] if res.formula_id == fml.CUSTOM_ID else fml.label(fml.get_formula(res.formula_id))
    st.caption(f"Formula: **{lbl}** · {cfg.n_stocks} stocks · exit rank {cfg.exit_rank} · {cfg.frequency} "
               f"· regime: {cfg.regime if cfg.regime != 'None' else 'off'} · {cfg.start.date()} to {cfg.end.date()}")

    k = st.columns(5)
    k[0].metric("End value (Rs.)", f"{m['End value']:,.0f}", f"{m['Total return %']:.1f}%")
    k[1].metric("CAGR (yearly growth)", f"{m['CAGR %']:.1f}%", f"index {bm.get('CAGR %', float('nan')):.1f}%" if bm else None, delta_color="off")
    k[2].metric("Worst fall (max drawdown)", f"{m['Max drawdown %']:.1f}%", f"index {bm.get('Max drawdown %', float('nan')):.1f}%" if bm else None, delta_color="off")
    k[3].metric("Sharpe", f"{m['Sharpe (rf as set)']:.2f}", help="Return per unit of risk, with 0% risk-free rate.")
    k[4].metric("Trades", f"{m.get('Trades (buys+sells)', 0)}", f"costs Rs. {m.get('Total costs paid', 0):,.0f}", delta_color="off")

    chart = pd.DataFrame({"Strategy": res.equity})
    if res.benchmark is not None:
        chart["Index (buy & hold)"] = res.benchmark
    st.markdown("**Portfolio value over time**")
    st.line_chart(chart)
    dd = pd.DataFrame({"Strategy": drawdown_series(res.equity) * 100})
    if res.benchmark is not None:
        dd["Index (buy & hold)"] = drawdown_series(res.benchmark) * 100
    st.markdown("**Drawdown % (fall from the previous peak)**")
    st.area_chart(dd)

    t1, t2, t3, t4, t5, t6 = st.tabs(["Summary table", "Yearly & monthly", "Trades", "Rebalances", "Holdings at end", "Compare all formulas"])
    with t1:
        rows = {k_: [m.get(k_), bm.get(k_) if bm else np.nan] for k_ in
                ["Total return %", "CAGR %", "Max drawdown %", "Volatility % (yearly)", "Sharpe (rf as set)", "Calmar"]}
        st.dataframe(pd.DataFrame(rows, index=["Strategy", "Index (buy & hold)"]).T.style.format("{:.2f}"))
        extra = {k_: m.get(k_) for k_ in ["Trades (buys+sells)", "Closed positions", "Win rate % (closed)", "Total costs paid"]}
        st.write(pd.Series(extra, name="Trading").to_frame().T)
    with t2:
        y = yearly_returns(res.equity).rename(columns={"Return %": "Strategy %"})
        if res.benchmark is not None:
            y["Index %"] = yearly_returns(res.benchmark)["Return %"]
        st.dataframe(y.style.format("{:.1f}"))
        st.markdown("Monthly returns of the strategy (%)")
        st.dataframe(monthly_returns(res.equity).style.format("{:.1f}", na_rep="").background_gradient(cmap="RdYlGn", axis=None, vmin=-15, vmax=15))
    with t3:
        st.dataframe(res.trades, hide_index=True)
    with t4:
        st.dataframe(res.rebalances, hide_index=True)
    with t5:
        st.dataframe(res.holdings, hide_index=True)
    with t6:
        st.write("Runs **every formula in the library and your saved formulas** with the same rules and dates, so you can review them side by side.")
        st.caption("Careful: picking the formula with the best PAST result is 'curve fitting' and often disappoints later. "
                   "Prefer formulas that are good AND sensible AND stable across different date ranges.")
        if st.button("Run all formulas (may take a minute)"):
            rows, prog = [], st.progress(0.0)
            for i, f in enumerate(fml.all_formulas()):
                try:
                    r = run_backtest(bt["close"], bt["index_ohlc"], cfg, f.id, ind=bt["ind"], regime_signal=bt["sig"])
                    rows.append({"ID": f.id, "Formula": f.name, "CAGR %": r.metrics["CAGR %"],
                                 "Max drawdown %": r.metrics["Max drawdown %"], "Sharpe": r.metrics["Sharpe (rf as set)"],
                                 "Total return %": r.metrics["Total return %"], "Trades": r.metrics.get("Trades (buys+sells)", 0)})
                except Exception as exc:  # noqa: BLE001
                    rows.append({"ID": f.id, "Formula": f.name, "CAGR %": np.nan, "Max drawdown %": np.nan,
                                 "Sharpe": np.nan, "Total return %": np.nan, "Trades": 0})
                prog.progress((i + 1) / len(fml.all_formulas()))
            st.session_state["bt_compare"] = pd.DataFrame(rows).sort_values("CAGR %", ascending=False)
        if "bt_compare" in st.session_state:
            st.dataframe(st.session_state["bt_compare"].style.format(
                {"CAGR %": "{:.1f}", "Max drawdown %": "{:.1f}", "Sharpe": "{:.2f}", "Total return %": "{:.1f}"}, na_rep="n/a"),
                hide_index=True)

    # downloads
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame([m]).T.rename(columns={0: "Strategy"}).to_excel(xw, sheet_name="Summary")
        chart.to_excel(xw, sheet_name="Equity curve")
        res.trades.to_excel(xw, sheet_name="Trades", index=False)
        res.rebalances.to_excel(xw, sheet_name="Rebalances", index=False)
        res.holdings.to_excel(xw, sheet_name="Holdings", index=False)
        yearly_returns(res.equity).to_excel(xw, sheet_name="Yearly")
    st.download_button("Download full results (Excel)", buf.getvalue(), file_name="momentum_backtest.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with st.expander("How this backtest works / assumptions"):
        st.markdown(
            "- Uses **adjusted closing prices** (splits and dividends included) from Yahoo Finance.\n"
            "- On each rebalance date every stock is scored and ranked. A held stock is sold only if its rank is worse than the **exit rank**.\n"
            "- Empty slots are filled with the best-ranked stocks not held; money is split equally; whole shares only; a stock too expensive for its slot is skipped.\n"
            "- **Half Portfolio**: the first time the filter turns weak every holding is cut by half and at most 50% of the portfolio stays invested; when the market turns healthy again idle cash is re-invested. **Go Cash**: sell everything and wait.\n"
            "- **Survivorship bias:** only the stocks in the list you uploaded *today* are tested. Stocks that were dropped, merged or delisted are missing, which makes results look better than reality.\n"
            "- Regime-filter details (MACD below its signal line = weak, SuperTrend on weekly candles, EQUITY filter wording) are my reading of the Sigma guide - see the Learn page."
        )
    st.caption(ui.DISCLAIMER)
