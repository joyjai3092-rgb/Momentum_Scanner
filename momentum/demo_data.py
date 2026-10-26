"""Made-up prices so the app can be tried (and tested) without internet.

THESE ARE NOT REAL PRICES. Each stock is a random walk with its own drift and volatility.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd


def make_demo_prices(tickers, start, end, seed: int = 7):
    days = pd.bdate_range(pd.Timestamp(start), pd.Timestamp(end))
    n = len(days)
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0004, 0.009, n)
    data = {}
    for t in tickers:
        r = np.random.default_rng(zlib.crc32(t.encode()) ^ seed)
        beta = r.uniform(0.6, 1.4)
        drift = r.normal(0.0002, 0.0004)
        idio = r.uniform(0.008, 0.022)
        ret = beta * market + drift + r.normal(0, idio, n)
        data[t] = 100 * r.uniform(0.5, 20) * np.exp(np.cumsum(ret) - np.cumsum(ret)[0])
    close = pd.DataFrame(data, index=days)

    idx_close = 10000 * np.exp(np.cumsum(market))
    index = pd.DataFrame({
        "Open": np.r_[idx_close[0], idx_close[:-1]],
        "High": idx_close * 1.004,
        "Low": idx_close * 0.996,
        "Close": idx_close,
    }, index=days)
    return close, index
