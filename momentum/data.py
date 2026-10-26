"""Price download from Yahoo Finance (free) via the `yfinance` library."""
from __future__ import annotations

import time

import pandas as pd


class DataError(RuntimeError):
    """Plain-English data problem."""


def _extract_field(raw: pd.DataFrame, field: str, single_ticker: str | None = None) -> pd.DataFrame:
    """Pull one price field (e.g. 'Close') out of whatever shape yfinance returned."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    cols = raw.columns
    if isinstance(cols, pd.MultiIndex):
        if field in cols.get_level_values(0):
            df = raw[field]
        elif field in cols.get_level_values(1):
            df = raw.xs(field, axis=1, level=1)
        else:
            return pd.DataFrame()
    else:
        if field not in cols:
            return pd.DataFrame()
        df = raw[[field]].copy()
        df.columns = [single_ticker or "SINGLE"]
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def download_prices(tickers, start, end, batch_size: int = 60, progress=None):
    """Adjusted close prices. Returns (close_table, failed_tickers).

    Missing days are carried forward for up to 5 trading days (trading halts).
    """
    import yfinance as yf

    tickers = list(dict.fromkeys(tickers))
    end_incl = pd.Timestamp(end) + pd.Timedelta(days=1)       # yfinance 'end' is exclusive
    frames = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        raw = pd.DataFrame()
        for attempt in range(2):
            try:
                raw = yf.download(batch, start=pd.Timestamp(start), end=end_incl, auto_adjust=True,
                                  progress=False, group_by="column", threads=True)
                if raw is not None and not raw.empty:
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1.5)
        part = _extract_field(raw, "Close", batch[0] if len(batch) == 1 else None)
        if not part.empty:
            frames.append(part)
        if progress:
            progress(min(i + batch_size, len(tickers)) / len(tickers))
    if not frames:
        raise DataError(
            "No price data could be downloaded. Check your internet connection (Yahoo Finance may be "
            "temporarily busy) - or switch on 'Demo data' to try the app without internet."
        )
    close = pd.concat(frames, axis=1)
    close = close.loc[:, ~close.columns.duplicated()]
    close = close.dropna(axis=1, how="all").sort_index().ffill(limit=5)
    failed = [t for t in tickers if t not in close.columns]
    return close, failed


def download_index(ticker: str, start, end) -> pd.DataFrame:
    """Index OHLC table (columns Open, High, Low, Close). Empty if unavailable."""
    import yfinance as yf

    end_incl = pd.Timestamp(end) + pd.Timedelta(days=1)
    raw = pd.DataFrame()
    for attempt in range(2):
        try:
            raw = yf.download(ticker, start=pd.Timestamp(start), end=end_incl, auto_adjust=True,
                              progress=False, group_by="column")
            if raw is not None and not raw.empty:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5)
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame({f: _extract_field(raw, f, ticker).iloc[:, 0] for f in ("Open", "High", "Low", "Close")})
    return out.dropna(subset=["Close"]).sort_index()
