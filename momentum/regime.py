"""Market-regime filters (Sigma Backtest Guide): EMA, MACD, SUPERTREND, EQUITY.

Each function returns a True/False series indexed by trading day:
    True  = market looks healthy ("risk-on")
    False = market looks weak   ("risk-off")
Only data up to each day is used (no peeking into the future).

ASSUMPTIONS (the Sigma guide does not spell these out - please review):
  * EMA:        weak when the index closes BELOW its EMA.
  * MACD:       weak when the MACD line is BELOW its signal line.
  * SUPERTREND: computed on WEEKLY candles; weak when the trend is DOWN. A weekly candle
                is only used from its last trading day onwards (no partial weeks).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema_signal(close: pd.Series, length: int) -> pd.Series:
    ema = close.ewm(span=length, adjust=False).mean()
    on = close >= ema
    on.iloc[: max(length - 1, 0)] = True       # warm-up: assume healthy
    return on


def macd_signal(close: pd.Series, fast: int, slow: int, signal: int) -> pd.Series:
    macd = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = macd.ewm(span=signal, adjust=False).mean()
    on = macd >= sig
    on.iloc[: max(slow - 1, 0)] = True
    return on


def supertrend_trend(high: pd.Series, low: pd.Series, close: pd.Series, period: int, mult: float) -> pd.Series:
    """Classic SuperTrend. Returns True where the trend is UP."""
    n = len(close)
    if n == 0:
        return pd.Series(dtype=bool)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    tr.iloc[0] = (high - low).iloc[0]
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()          # Wilder smoothing
    hl2 = (high + low) / 2.0
    ub = (hl2 + mult * atr).to_numpy()
    lb = (hl2 - mult * atr).to_numpy()
    c = close.to_numpy()

    fub = ub.copy()
    flb = lb.copy()
    up = np.ones(n, dtype=bool)
    for i in range(1, n):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        if up[i - 1]:
            up[i] = not (c[i] < flb[i])
        else:
            up[i] = c[i] > fub[i]
    return pd.Series(up, index=close.index)


def supertrend_signal(ohlc: pd.DataFrame, period: int, mult: float) -> pd.Series:
    """Weekly SuperTrend, mapped back to daily dates without look-ahead."""
    d = ohlc.dropna(subset=["High", "Low", "Close"]).copy()
    weeks = d.index.to_period("W-FRI")
    g = d.groupby(weeks)
    weekly = pd.DataFrame({
        "High": g["High"].max(), "Low": g["Low"].min(), "Close": g["Close"].last(),
    })
    last_day = pd.Series(d.index, index=d.index).groupby(weeks).last()
    trend = supertrend_trend(weekly["High"], weekly["Low"], weekly["Close"], period, mult)
    by_last_day = pd.Series(trend.to_numpy(), index=pd.DatetimeIndex(last_day.to_numpy()))
    out = by_last_day.reindex(d.index.union(by_last_day.index)).ffill()
    out = out.reindex(d.index)
    return out.fillna(True).astype(bool)


def build_signal(ohlc: pd.DataFrame, kind: str, params: tuple) -> pd.Series | None:
    """kind: 'EMA' (length,), 'MACD' (fast, slow, signal), 'SUPERTREND' (period, mult)."""
    kind = kind.upper()
    if kind == "EMA":
        return ema_signal(ohlc["Close"].dropna(), int(params[0]))
    if kind == "MACD":
        return macd_signal(ohlc["Close"].dropna(), int(params[0]), int(params[1]), int(params[2]))
    if kind == "SUPERTREND":
        return supertrend_signal(ohlc, int(params[0]), float(params[1]))
    return None
