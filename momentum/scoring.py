"""Turns a formula into a score for every stock on a given date."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .config import RESEARCH_DAYS_PER_MONTH, SIGMA_DAYS_PER_MONTH, TRADING_DAYS_PER_YEAR
from .formulas import CUSTOM_ID, Formula, get_formula
from .indicators import Indicators
from .sigma_parser import ParsedFormula, evaluate, need_name, parse_formula

D12 = 12 * RESEARCH_DAYS_PER_MONTH   # 252
D6 = 6 * RESEARCH_DAYS_PER_MONTH     # 126
D1 = RESEARCH_DAYS_PER_MONTH         # 21

QM_TOP_FRACTION = 0.10               # Gray & Vogel: top 10% by generic momentum


def _row(df: pd.DataFrame, date) -> pd.Series:
    return df.loc[date]


def _need_series(ind: Indicators, date, need: tuple) -> pd.Series:
    k = need[0]
    sm = SIGMA_DAYS_PER_MONTH
    if k == "P":
        return _row(ind.perf(need[1] * sm), date)
    if k == "V":
        return _row(ind.vol(need[1] * sm), date)
    if k == "PW":
        return _row(ind.perf(need[1] * 5), date)
    if k == "VW":
        return _row(ind.vol(need[1] * 5), date)
    if k == "PS":
        return _row(ind.skip_return(need[1] * sm, need[2] * sm), date)
    if k == "FIP":
        return _row(ind.fip(D12), date)
    if k == "H52":
        return _row(ind.high_proximity(TRADING_DAYS_PER_YEAR), date)
    raise KeyError(f"Unknown formula item: {need}")


def _sigma_vars(ind: Indicators, date, needs) -> dict:
    return {need_name(n): _need_series(ind, date, n) for n in needs}


def _normalise_z(z: pd.Series) -> pd.Series:
    """NSE: 1 + z if z >= 0 else 1 / (1 - z)."""
    return pd.Series(np.where(z >= 0, 1 + z, 1 / (1 - z)), index=z.index).where(z.notna())


def _zscore(x: pd.Series) -> pd.Series:
    sd = x.std(ddof=0)
    if not sd or math.isnan(sd):
        return x * np.nan
    return (x - x.mean()) / sd


def _nse_returns(ind: Indicators, date) -> tuple:
    """(12-month, 6-month) price return between month-end closes, as in the NSE method.

    Month M = the month of `date`. 12M = P(end of M-1) / P(end of M-13) - 1,
    6M = P(end of M-1) / P(end of M-7) - 1. Stocks without those prices get NaN.
    """
    month_end = ind._memo(("month_end",), lambda: ind.close.groupby(ind.close.index.to_period("M")).last())
    m = pd.Timestamp(date).to_period("M")

    def at(back: int) -> pd.Series:
        p = m - back
        if p in month_end.index:
            return month_end.loc[p]
        return pd.Series(np.nan, index=ind.close.columns)

    p1, p7, p13 = at(1), at(7), at(13)
    return p1 / p13 - 1, p1 / p7 - 1


def _score_native(key: str, ind: Indicators, date) -> pd.Series:
    if key == "skip_6_1":
        return _row(ind.skip_return(D6, D1), date)
    if key == "skip_12_1":
        return _row(ind.skip_return(D12, D1), date)
    if key == "skip_12_1_over_vol":
        return (_row(ind.skip_return(D12, D1), date) / _row(ind.log_vol(D12), date)).replace([np.inf, -np.inf], np.nan)
    if key == "high52":
        return _row(ind.high_proximity(TRADING_DAYS_PER_YEAR), date)
    if key == "nse_normalized":
        # NSE: returns are measured between MONTH-END prices - price(M-1) / price(M-13) and
        # price(M-1) / price(M-7), where M is the month of the rebalance date. Volatility = 1 year.
        sd = _row(ind.log_vol(D12), date)
        r12, r6 = _nse_returns(ind, date)
        mr12 = (r12 / sd).replace([np.inf, -np.inf], np.nan)
        mr6 = (r6 / sd).replace([np.inf, -np.inf], np.nan)
        both = pd.concat([mr12, mr6], axis=1).dropna()
        z = 0.5 * _zscore(both.iloc[:, 0]) + 0.5 * _zscore(both.iloc[:, 1])
        return _normalise_z(z).reindex(mr12.index)
    if key == "quant_momentum":
        gen = _row(ind.skip_return(D12, D1), date)
        fip = _row(ind.fip(D12), date)
        ok = pd.concat([gen, fip], axis=1).dropna()
        ok.columns = ["gen", "fip"]
        score = pd.Series(np.nan, index=gen.index)
        if ok.empty:
            return score
        k = max(int(math.ceil(QM_TOP_FRACTION * len(ok))), 1)
        top = ok["gen"].nlargest(k).index
        # Everyone else: percentile of generic momentum, always below 1.
        rest = ok.drop(index=top)["gen"]
        if len(rest):
            score.loc[rest.index] = rest.rank(pct=True) * 0.99 - 0.0  # 0..<1
        # Top decile: 10 + (-FIP)  -> always above 9, lower FIP = higher score
        score.loc[top] = 10 - ok.loc[top, "fip"]
        return score
    raise KeyError(f"Unknown native scorer: {key}")


def make_scorer(formula_id: str, custom_text: str | None = None):
    """Return fn(ind, date) -> Series of scores (NaN = cannot be scored)."""
    if formula_id == CUSTOM_ID:
        parsed: ParsedFormula = parse_formula(custom_text or "")

        def custom(ind: Indicators, date) -> pd.Series:
            return _clean(evaluate(parsed, _sigma_vars(ind, date, parsed.needs)), ind, date)

        return custom

    f: Formula = get_formula(formula_id)
    if f.kind == "sigma":
        parsed = parse_formula(f.expr)

        def sigma(ind: Indicators, date) -> pd.Series:
            return _clean(evaluate(parsed, _sigma_vars(ind, date, parsed.needs)), ind, date)

        return sigma

    def native(ind: Indicators, date) -> pd.Series:
        return _clean(_score_native(f.native_key, ind, date), ind, date)

    return native


def _clean(score: pd.Series, ind: Indicators, date) -> pd.Series:
    """A stock with no price on the date cannot be scored."""
    has_price = ind.close.loc[date].notna()
    return score.where(has_price).astype(float)


def rank_table(ind: Indicators, date, scorer) -> pd.DataFrame:
    """Scores + ranks (1 = best) for every scorable stock on `date`."""
    s = scorer(ind, date).dropna().sort_values(ascending=False, kind="stable")
    out = pd.DataFrame({"Score": s})
    out["Rank"] = np.arange(1, len(out) + 1)
    return out[["Rank", "Score"]]


def snapshot(ind: Indicators, date) -> pd.DataFrame:
    """Handy extra columns shown next to the score (all Sigma-month based)."""
    cols = {
        "Price": ind.close.loc[date],
        "1M %": ind.perf(1 * SIGMA_DAYS_PER_MONTH).loc[date] * 100,
        "3M %": ind.perf(3 * SIGMA_DAYS_PER_MONTH).loc[date] * 100,
        "6M %": ind.perf(6 * SIGMA_DAYS_PER_MONTH).loc[date] * 100,
        "12M %": ind.perf(12 * SIGMA_DAYS_PER_MONTH).loc[date] * 100,
        "6M Vol %": ind.vol(6 * SIGMA_DAYS_PER_MONTH).loc[date] * 100,
        "FIP": ind.fip(D12).loc[date],
        "% of 52W high": ind.high_proximity(TRADING_DAYS_PER_YEAR).loc[date] * 100,
    }
    return pd.DataFrame(cols)
