"""Portfolio back-test engine, modelled on the Sigma Scanner Backtest User Guide.

How one rebalance works (plain English)
  1. Score and rank every stock in the universe on the rebalance date.
  2. SELL any stock you hold whose rank is worse than the Exit Rank (or that cannot be scored).
  3. Check the market-regime filter. "Half Portfolio": on the first weak day every holding is cut
     by half and the invested part is then capped at 50% of total value. "Go Cash": sell everything.
  4. BUY the best-ranked stocks you do not hold, until you have `n_stocks` positions. Money is split
     equally between the empty slots; whole shares only; a stock too expensive for its slot is skipped
     (same as Sigma's quantity calculator).
  5. When the market turns healthy again, idle cash is put back to work (top-up to equal weight).

Everything uses adjusted closing prices.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import DEFAULT_COST_PCT
from .indicators import Indicators
from .metrics import compute_metrics, trade_stats
from .regime import INDEX_REGIMES, build_signal
from .scoring import make_scorer


# ---------------------------------------------------------------- settings
@dataclass
class BacktestConfig:
    start: pd.Timestamp
    end: pd.Timestamp
    capital: float = 100000.0
    n_stocks: int = 20
    exit_rank: int = 40
    frequency: str = "Monthly"            # "Monthly" | "Weekly"
    rebalance_day: int = 15               # Monthly: 1-30 ; Weekly: 0=Mon ... 4=Fri
    alt_day: str = "Previous"             # holiday rule: "Previous" | "Next"
    execution: str = "Same-day close"     # "Same-day close" | "Next-day close"
    cost_pct: float = DEFAULT_COST_PCT    # per buy and per sell
    regime: str = "None"                  # None | EMA | MACD | SUPERTREND | SIGMA SUPERTREND | EQUITY
    regime_params: tuple = ()
    regime_timeframe: str = ""            # "" = default for the filter; Daily | Weekly | Monthly
    regime_action: str = "Half Portfolio"  # "Half Portfolio" | "Go Cash"
    equity_sl_pct: float = 10.0           # only for EQUITY filter

    def validate(self) -> None:
        if self.n_stocks < 1:
            raise ValueError("Number of stocks must be at least 1.")
        if self.exit_rank < self.n_stocks:
            raise ValueError("Exit rank must be equal to or bigger than the number of stocks.")
        if self.capital <= 0:
            raise ValueError("Starting capital must be positive.")
        if pd.Timestamp(self.end) <= pd.Timestamp(self.start):
            raise ValueError("End date must be after start date.")
        if self.frequency == "Monthly" and not 1 <= self.rebalance_day <= 30:
            raise ValueError("Monthly rebalance date must be between 1 and 30.")
        if self.frequency == "Weekly" and not 0 <= self.rebalance_day <= 4:
            raise ValueError("Weekly rebalance day must be Monday-Friday.")


@dataclass
class BacktestResult:
    config: BacktestConfig
    formula_id: str
    equity: pd.Series
    benchmark: pd.Series | None
    trades: pd.DataFrame
    rebalances: pd.DataFrame
    holdings: pd.DataFrame
    metrics: dict
    benchmark_metrics: dict
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- calendar
def _snap(trading_days: pd.DatetimeIndex, target: pd.Timestamp, alt_day: str):
    if target in trading_days:
        return target
    pos = trading_days.searchsorted(target, side="left")
    if alt_day == "Next":
        return trading_days[pos] if pos < len(trading_days) else None
    return trading_days[pos - 1] if pos > 0 else None


def rebalance_dates(trading_days: pd.DatetimeIndex, start, end, frequency: str, day: int, alt_day: str) -> list:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    targets = []
    if frequency == "Weekly":
        monday = start - pd.Timedelta(days=start.weekday())
        t = monday + pd.Timedelta(days=day)
        while t <= end + pd.Timedelta(days=7):
            targets.append(t)
            t += pd.Timedelta(days=7)
    else:
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            targets.append(pd.Timestamp(y, m, min(day, calendar.monthrange(y, m)[1])))
            m += 1
            if m == 13:
                y, m = y + 1, 1
    out = []
    for t in targets:
        d = _snap(trading_days, t, alt_day)
        if d is not None and start <= d <= end and (not out or d > out[-1]):
            out.append(d)
    return out


# ---------------------------------------------------------------- engine
def run_backtest(
    close: pd.DataFrame,
    index_ohlc: pd.DataFrame | None,
    cfg: BacktestConfig,
    formula_id: str,
    custom_text: str | None = None,
    ind: Indicators | None = None,
    regime_signal: pd.Series | None = None,
    risk_free: float = 0.0,
) -> BacktestResult:
    cfg.validate()
    close = close.sort_index()
    ind = ind or Indicators(close)
    scorer = make_scorer(formula_id, custom_text)
    valuation = close.ffill()
    td = close.index
    start, end = pd.Timestamp(cfg.start), pd.Timestamp(cfg.end)
    days = td[(td >= start) & (td <= end)]
    notes: list = []
    if len(days) < 20:
        raise ValueError("Not enough trading days between the start and end dates.")

    if regime_signal is None and cfg.regime in INDEX_REGIMES:
        if index_ohlc is None or index_ohlc.empty:
            notes.append("Regime filter skipped: no index data was available.")
        else:
            regime_signal = build_signal(index_ohlc, cfg.regime, cfg.regime_params, cfg.regime_timeframe or None)

    reb = rebalance_dates(td, start, end, cfg.frequency, cfg.rebalance_day, cfg.alt_day)
    cost = cfg.cost_pct / 100.0

    cash = float(cfg.capital)
    shares: dict = {}
    avg_cost: dict = {}
    snapshots: list = []          # (exec_date, cash, shares copy)
    trades: list = []
    rlog: list = []
    risk_off = False

    def last_price(sym, upto):
        v = valuation.at[upto, sym] if sym in valuation.columns else np.nan
        return float(v) if pd.notna(v) else np.nan

    def sell(sym, qty, px, date, action, reason):
        nonlocal cash
        qty = int(min(qty, shares.get(sym, 0)))
        if qty <= 0 or not np.isfinite(px):
            return 0.0
        value = qty * px
        fee = value * cost
        cash += value - fee
        basis = avg_cost[sym]                      # per-share cost INCLUDING the buy fee
        pnl = (px * (1 - cost) - basis) * qty      # net of buy and sell fees
        ret_pct = (px * (1 - cost) / basis - 1) * 100
        shares[sym] -= qty
        if shares[sym] == 0:
            del shares[sym]
            avg_cost.pop(sym, None)
        trades.append({"Date": date, "Symbol": sym, "Action": action, "Qty": qty, "Price": px,
                       "Value": value, "Cost": fee, "Reason": reason, "Realised P&L": pnl,
                       "Return %": ret_pct})
        return pnl

    def buy(sym, qty, px, date, action, reason):
        nonlocal cash
        if qty <= 0 or not np.isfinite(px):
            return
        value = qty * px
        fee = value * cost
        cash -= value + fee
        old = shares.get(sym, 0)
        avg_cost[sym] = (avg_cost.get(sym, 0.0) * old + px * (1 + cost) * qty) / (old + qty)
        shares[sym] = old + qty
        trades.append({"Date": date, "Symbol": sym, "Action": action, "Qty": qty, "Price": px,
                       "Value": value, "Cost": fee, "Reason": reason, "Realised P&L": np.nan,
                       "Return %": np.nan})

    for rdate in reb:
        pos = td.get_loc(rdate)
        if cfg.execution.startswith("Next"):
            if pos + 1 >= len(td) or td[pos + 1] > end:
                continue
            edate = td[pos + 1]
        else:
            edate = rdate

        scores = scorer(ind, rdate).dropna()
        ranks = scores.rank(ascending=False, method="first")
        equity_before = cash + sum(q * (last_price(s, edate) if np.isfinite(last_price(s, edate)) else 0.0)
                                   for s, q in shares.items())
        n_exits = n_entries = 0
        realised = 0.0

        if scores.empty:
            rlog.append({"Rebalance date": rdate, "Trade date": edate, "Market": "n/a",
                         "Held": len(shares), "Cash": cash, "Equity": equity_before,
                         "Exits": 0, "Entries": 0, "Note": "Not enough price history to score yet"})
            snapshots.append((edate, cash, dict(shares)))
            continue

        # 1) exits by rank
        for sym in list(shares):
            r = ranks.get(sym, np.nan)
            if pd.isna(r) or r > cfg.exit_rank:
                why = "No score (no data)" if pd.isna(r) else f"Rank {int(r)} > exit rank {cfg.exit_rank}"
                realised += sell(sym, shares[sym], last_price(sym, edate), edate, "SELL", why)
                n_exits += 1

        # 2) market regime
        was_off = risk_off
        if cfg.regime in INDEX_REGIMES and regime_signal is not None:
            on = bool(regime_signal.asof(rdate)) if len(regime_signal) else True
            risk_off = not on
        elif cfg.regime == "EQUITY":
            pnl_pct = realised / equity_before * 100 if equity_before else 0.0
            if pnl_pct <= -abs(cfg.equity_sl_pct):
                risk_off = True
            elif risk_off and pnl_pct > 0:
                risk_off = False
        else:
            risk_off = False

        half_mode = cfg.regime == "EQUITY" or cfg.regime_action == "Half Portfolio"
        market_txt = "Healthy" if not risk_off else ("Weak - half portfolio" if half_mode else "Weak - cash")

        if risk_off and not half_mode:                       # Go Cash
            for sym in list(shares):
                realised += sell(sym, shares[sym], last_price(sym, edate), edate, "SELL", "Regime: go to cash")
                n_exits += 1
        elif risk_off and half_mode and not was_off:         # first weak day: cut each holding in half
            for sym in list(shares):
                q = shares[sym] // 2
                if q > 0:
                    sell(sym, q, last_price(sym, edate), edate, "TRIM", "Regime: half portfolio")

        # 3) entries
        invest_fraction = 0.0 if (risk_off and not half_mode) else (0.5 if risk_off else 1.0)
        held_value = sum(q * last_price(s, edate) for s, q in shares.items() if np.isfinite(last_price(s, edate)))
        equity_now = cash + held_value
        cap_value = invest_fraction * equity_now
        vacancies = cfg.n_stocks - len(shares)
        budget = min(cash, max(0.0, cap_value - held_value))
        if vacancies > 0 and budget > 0:
            # equal money per slot, but never more than one "fair" slot of the whole portfolio
            # (stops idle cash piling into a few new stocks after a weak-market spell)
            alloc = min(budget / vacancies, equity_now / cfg.n_stocks)
            for sym in ranks.sort_values().index:
                if len(shares) >= cfg.n_stocks:
                    break
                if sym in shares:
                    continue
                px = last_price(sym, edate)
                if not np.isfinite(px) or px <= 0:
                    continue
                qty = int(math.floor(alloc / (px * (1 + cost))))
                if qty < 1:
                    continue                                   # too expensive for its slot: skip
                buy(sym, qty, px, edate, "BUY", f"Rank {int(ranks[sym])}")
                n_entries += 1

        # 4) healthy again after a weak spell: put idle cash back to work
        if was_off and not risk_off and shares:
            held_value = sum(q * last_price(s, edate) for s, q in shares.items() if np.isfinite(last_price(s, edate)))
            target = (cash + held_value) / cfg.n_stocks
            for sym in sorted(shares, key=lambda s: ranks.get(s, 1e9)):
                px = last_price(sym, edate)
                have = shares[sym] * px
                if have < target and np.isfinite(px):
                    qty = int(math.floor(min(target - have, cash) / (px * (1 + cost))))
                    if qty >= 1:
                        buy(sym, qty, px, edate, "TOPUP", "Market healthy again: reinvest idle cash")

        eq = cash + sum(q * last_price(s, edate) for s, q in shares.items() if np.isfinite(last_price(s, edate)))
        rlog.append({"Rebalance date": rdate, "Trade date": edate, "Market": market_txt,
                     "Held": len(shares), "Cash": cash, "Equity": eq,
                     "Exits": n_exits, "Entries": n_entries, "Note": ""})
        snapshots.append((edate, cash, dict(shares)))

    # ---- daily equity curve
    equity = pd.Series(float(cfg.capital), index=days)
    for i, (edate, c, sh) in enumerate(snapshots):
        nxt = snapshots[i + 1][0] if i + 1 < len(snapshots) else None
        mask = (days >= edate) & ((days < nxt) if nxt is not None else True)
        seg = days[mask]
        if len(seg) == 0:
            continue
        if sh:
            vals = valuation.loc[seg, list(sh)].mul(pd.Series(sh), axis=1).sum(axis=1) + c
        else:
            vals = pd.Series(c, index=seg)
        equity.loc[seg] = vals

    benchmark = None
    if index_ohlc is not None and not index_ohlc.empty:
        ic = index_ohlc["Close"].dropna().reindex(days.union(index_ohlc.index)).ffill().reindex(days)
        if ic.notna().sum() > 1:
            ic = ic.bfill()
            benchmark = cfg.capital * ic / ic.iloc[0]

    trades_df = pd.DataFrame(trades, columns=[
        "Date", "Symbol", "Action", "Qty", "Price", "Value", "Cost", "Reason", "Realised P&L", "Return %"])
    last_day = days[-1]
    hold_rows = []
    for s, q in shares.items():
        px = last_price(s, last_day)
        hold_rows.append({"Symbol": s, "Qty": q, "Avg cost": avg_cost[s], "Last price": px,
                          "Value": q * px, "P&L %": (px / avg_cost[s] - 1) * 100})
    holdings = pd.DataFrame(hold_rows, columns=["Symbol", "Qty", "Avg cost", "Last price", "Value", "P&L %"])

    m = compute_metrics(equity, risk_free)
    m.update(trade_stats(trades_df))
    if len(snapshots) == 0:
        notes.append("No rebalance happened inside the date range - check the dates and rebalance day.")
    return BacktestResult(
        config=cfg, formula_id=formula_id, equity=equity, benchmark=benchmark,
        trades=trades_df, rebalances=pd.DataFrame(rlog), holdings=holdings,
        metrics=m, benchmark_metrics=compute_metrics(benchmark, risk_free) if benchmark is not None else {},
        notes=notes,
    )
