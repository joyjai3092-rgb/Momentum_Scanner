"""Price-based measures for every stock, calculated once for the whole date range.

`close` is a table: one row per trading day, one column per stock (adjusted close).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RESEARCH_DAYS_PER_MONTH, SIGMA_DAYS_PER_MONTH, TRADING_DAYS_PER_YEAR


class Indicators:
    def __init__(self, close: pd.DataFrame):
        self.close = close.sort_index()
        self._cache: dict = {}

    def _memo(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    @property
    def daily_returns(self) -> pd.DataFrame:
        return self._memo(("ret",), lambda: self.close / self.close.shift(1) - 1)

    def perf(self, days: int) -> pd.DataFrame:
        """Price change over the last `days` trading days: price_now / price_then - 1."""
        return self._memo(("perf", days), lambda: self.close / self.close.shift(days) - 1)

    def vol(self, days: int) -> pd.DataFrame:
        """Std-deviation of daily returns over `days` days, annualised."""
        return self._memo(
            ("vol", days),
            lambda: self.daily_returns.rolling(days, min_periods=days).std() * np.sqrt(TRADING_DAYS_PER_YEAR),
        )

    def sigma_perf(self, months: int) -> pd.DataFrame:
        return self.perf(months * SIGMA_DAYS_PER_MONTH)

    def sigma_vol(self, months: int) -> pd.DataFrame:
        return self.vol(months * SIGMA_DAYS_PER_MONTH)

    def skip_return(self, lookback_days: int, skip_days: int) -> pd.DataFrame:
        """Return from `lookback_days` ago to `skip_days` ago (ignores the latest stretch)."""
        return self._memo(
            ("skip", lookback_days, skip_days),
            lambda: self.close.shift(skip_days) / self.close.shift(lookback_days) - 1,
        )

    def log_vol(self, days: int) -> pd.DataFrame:
        """Annualised std-deviation of daily LOG returns (NSE methodology)."""

        def calc():
            lr = np.log(self.close / self.close.shift(1))
            return lr.rolling(days, min_periods=days).std() * np.sqrt(TRADING_DAYS_PER_YEAR)

        return self._memo(("logvol", days), calc)

    def high_proximity(self, days: int) -> pd.DataFrame:
        """Price divided by its highest close of the last `days` days (1.0 = at the high)."""
        return self._memo(
            ("hi", days),
            lambda: self.close / self.close.rolling(days, min_periods=days).max(),
        )

    def fip(self, days: int) -> pd.DataFrame:
        """Frog-in-the-Pan: sign(past return) * (%negative days - %positive days).

        More NEGATIVE = smoother, steadier climb (better). Gray & Vogel, ch. 6/8.
        """

        def calc():
            r = self.daily_returns
            ok = r.notna()
            neg = (r < 0).astype(float).where(ok)
            pos = (r > 0).astype(float).where(ok)
            pct_neg = neg.rolling(days, min_periods=days).mean()
            pct_pos = pos.rolling(days, min_periods=days).mean()
            formation = self.skip_return(days, RESEARCH_DAYS_PER_MONTH)
            return np.sign(formation) * (pct_neg - pct_pos)

        return self._memo(("fip", days), calc)
