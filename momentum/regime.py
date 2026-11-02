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


INDEX_REGIMES = ("EMA", "MACD", "SUPERTREND", "SIGMA SUPERTREND")


def sigma_supertrend_trend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, mult: float = 3.0,
                           wilder_atr: bool = True) -> pd.Series:
    """'Sigma SuperTrend' = a line-by-line port of the user's Pine Script v4 'Supertrend'.

    src = hl2; up = src - mult*ATR, dn = src + mult*ATR; up only rises while the previous close is above it,
    dn only falls while the previous close is below it; trend flips to up when close > previous dn,
    to down when close < previous up. wilder_atr=True is Pine's atr() (RMA); False is sma(tr, period).
    Returns True where trend == 1 (up). Before the ATR exists the trend is up (Pine's default).
    """
    n = len(close)
    if n == 0:
        return pd.Series(dtype=bool)
    h, l, c = high.to_numpy(float), low.to_numpy(float), close.to_numpy(float)
    prev_c = np.r_[np.nan, c[:-1]]
    tr = np.fmax.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
    tr[0] = h[0] - l[0]
    atr = np.full(n, np.nan)
    if n >= period:
        if wilder_atr:
            atr[period - 1] = tr[:period].mean()
            for i in range(period, n):
                atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        else:
            atr[period - 1:] = pd.Series(tr).rolling(period).mean().to_numpy()[period - 1:]
    src = (h + l) / 2.0
    up = np.full(n, np.nan)
    dn = np.full(n, np.nan)
    trend = np.ones(n, dtype=int)
    for i in range(n):
        if np.isnan(atr[i]):
            continue
        up_raw, dn_raw = src[i] - mult * atr[i], src[i] + mult * atr[i]
        up1 = up[i - 1] if i > 0 and not np.isnan(up[i - 1]) else up_raw
        dn1 = dn[i - 1] if i > 0 and not np.isnan(dn[i - 1]) else dn_raw
        up[i] = max(up_raw, up1) if (i > 0 and c[i - 1] > up1) else up_raw
        dn[i] = min(dn_raw, dn1) if (i > 0 and c[i - 1] < dn1) else dn_raw
        t = trend[i - 1] if i > 0 else 1
        if t == -1 and c[i] > dn1:
            t = 1
        elif t == 1 and c[i] < up1:
            t = -1
        trend[i] = t
    return pd.Series(trend == 1, index=close.index)


def sigma_supertrend_signal(ohlc: pd.DataFrame, period: int = 10, mult: float = 3.0, wilder_atr: bool = True,
                            timeframe: str = "Daily") -> pd.Series:
    """Daily-indexed healthy/weak series. Weekly candles are used only from their last trading day on."""
    d = ohlc.dropna(subset=["High", "Low", "Close"]).copy()
    if timeframe == "Daily":
        return sigma_supertrend_trend(d["High"], d["Low"], d["Close"], period, mult, wilder_atr)
    weeks = d.index.to_period("W-FRI")
    g = d.groupby(weeks)
    weekly = pd.DataFrame({"High": g["High"].max(), "Low": g["Low"].min(), "Close": g["Close"].last()})
    last_day = pd.Series(d.index, index=d.index).groupby(weeks).last()
    trend = sigma_supertrend_trend(weekly["High"], weekly["Low"], weekly["Close"], period, mult, wilder_atr)
    by_last_day = pd.Series(trend.to_numpy(), index=pd.DatetimeIndex(last_day.to_numpy()))
    out = by_last_day.reindex(d.index.union(by_last_day.index)).ffill().reindex(d.index)
    return out.fillna(True).astype(bool)


TIMEFRAMES = ("Daily", "Weekly", "Monthly")


def default_timeframe(kind: str) -> str:
    """SuperTrend follows the Sigma guide (weekly); the others default to daily."""
    return "Weekly" if kind.upper() == "SUPERTREND" else "Daily"


def _on_timeframe(ohlc: pd.DataFrame, timeframe: str, fn) -> pd.Series:
    """Run `fn(candles) -> bool Series` on Daily / Weekly / Monthly candles and map it back to every trading day.

    A weekly or monthly candle's signal is used only from that candle's LAST trading day onwards, so no
    day ever sees a future price. Days before the first signal count as healthy.
    """
    d = ohlc.dropna(subset=["High", "Low", "Close"]).copy()
    if timeframe == "Daily":
        return fn(d).astype(bool)
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    per = d.index.to_period("W-FRI" if timeframe == "Weekly" else "M")
    g = d.groupby(per)
    candles = pd.DataFrame({"Open": g["Open"].first() if "Open" in d else g["Close"].first(),
                            "High": g["High"].max(), "Low": g["Low"].min(), "Close": g["Close"].last()})
    last_day = pd.Series(d.index, index=d.index).groupby(per).last()
    sig = fn(candles)
    by_last_day = pd.Series(sig.to_numpy(), index=pd.DatetimeIndex(last_day.to_numpy()))
    out = by_last_day.reindex(d.index.union(by_last_day.index)).ffill().reindex(d.index)
    return out.fillna(True).astype(bool)


def build_signal(ohlc: pd.DataFrame, kind: str, params: tuple, timeframe: str | None = None) -> pd.Series | None:
    """kind: 'EMA' (length,), 'MACD' (fast, slow, signal), 'SUPERTREND' (period, mult),
    'SIGMA SUPERTREND' (period, mult, wilder_atr[, timeframe]).
    timeframe: 'Daily' | 'Weekly' | 'Monthly' (None = the default for that kind). Lengths count candles of that timeframe.
    """
    kind = kind.upper()
    sigma_tf = params[3] if kind == "SIGMA SUPERTREND" and len(params) > 3 else None
    tf = timeframe or sigma_tf or default_timeframe(kind)
    if kind == "EMA":
        n = int(params[0])
        return _on_timeframe(ohlc, tf, lambda o: ema_signal(o["Close"], n))
    if kind == "MACD":
        f, sl, sg = (int(x) for x in params[:3])
        return _on_timeframe(ohlc, tf, lambda o: macd_signal(o["Close"], f, sl, sg))
    if kind == "SUPERTREND":
        p, m = int(params[0]), float(params[1])
        return _on_timeframe(ohlc, tf, lambda o: supertrend_trend(o["High"], o["Low"], o["Close"], p, m))
    if kind == "SIGMA SUPERTREND":
        p = tuple(params) + (10, 3.0, True)[len(params):]
        per, mult, wil = int(p[0]), float(p[1]), bool(p[2])
        return _on_timeframe(ohlc, tf, lambda o: sigma_supertrend_trend(o["High"], o["Low"], o["Close"], per, mult, wil))
    return None


def equal_weight_index(close: pd.DataFrame) -> pd.DataFrame | None:
    """A stand-in 'market' made from the uploaded stocks: their average daily return, compounded.

    Used only when no real index is available. It has no separate High/Low, so High = Low = Close
    (SuperTrend then uses close-to-close moves only - an approximation).
    """
    if close is None or close.empty:
        return None
    rets = close.pct_change(fill_method=None).mean(axis=1, skipna=True).fillna(0.0)
    level = 100.0 * (1.0 + rets).cumprod()
    return pd.DataFrame({"Open": level, "High": level, "Low": level, "Close": level})


def regime_status(signal: pd.Series | None, asof) -> dict:
    """Today's market state from a build_signal() series.

    Returns {known, healthy, since, days}: `since` = first day of the current streak.
    """
    if signal is None or len(signal) == 0:
        return {"known": False, "healthy": True, "since": None, "days": 0}
    s = signal.loc[: pd.Timestamp(asof)]
    if s.empty:
        return {"known": False, "healthy": True, "since": None, "days": 0}
    now = bool(s.iloc[-1])
    flips = s.ne(s.shift()).to_numpy()
    start_pos = int(np.flatnonzero(flips)[-1])
    return {"known": True, "healthy": now, "since": s.index[start_pos], "days": len(s) - start_pos}
