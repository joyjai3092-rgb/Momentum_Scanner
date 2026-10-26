"""Performance numbers from a daily equity curve."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS_PER_YEAR


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def compute_metrics(equity: pd.Series, risk_free: float = 0.0) -> dict:
    equity = equity.dropna()
    if len(equity) < 2:
        return {}
    ret = equity / equity.shift(1) - 1
    ret = ret.dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else np.nan
    vol = ret.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    ann_mean = ret.mean() * TRADING_DAYS_PER_YEAR
    sharpe = (ann_mean - risk_free) / vol if vol and not np.isnan(vol) else np.nan
    dd = drawdown_series(equity)
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd and not np.isnan(cagr) else np.nan
    return {
        "Start value": float(equity.iloc[0]),
        "End value": float(equity.iloc[-1]),
        "Total return %": total * 100,
        "CAGR %": cagr * 100 if not np.isnan(cagr) else np.nan,
        "Max drawdown %": max_dd * 100,
        "Volatility % (yearly)": vol * 100,
        "Sharpe (rf as set)": sharpe,
        "Calmar": calmar,
    }


def yearly_returns(equity: pd.Series) -> pd.DataFrame:
    equity = equity.dropna()
    last = equity.groupby(equity.index.year).last()
    prev = last.shift(1)
    prev.iloc[0] = equity.iloc[0]
    out = (last / prev - 1) * 100
    return out.rename("Return %").to_frame().rename_axis("Year")


def monthly_returns(equity: pd.Series) -> pd.DataFrame:
    equity = equity.dropna()
    key = [equity.index.year, equity.index.month]
    last = equity.groupby(key).last()
    prev = last.shift(1)
    prev.iloc[0] = equity.iloc[0]
    r = (last / prev - 1) * 100
    table = r.unstack(level=1)
    table.index.name = "Year"
    table.columns = [pd.Timestamp(2000, int(m), 1).strftime("%b") for m in table.columns]
    return table


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"Trades (buys+sells)": 0}
    sells = trades[trades["Action"] == "SELL"]
    wins = (sells["Realised P&L"] > 0).sum() if len(sells) else 0
    return {
        "Trades (buys+sells)": int(len(trades)),
        "Closed positions": int(len(sells)),
        "Win rate % (closed)": (wins / len(sells) * 100) if len(sells) else np.nan,
        "Total costs paid": float(trades["Cost"].sum()),
    }
