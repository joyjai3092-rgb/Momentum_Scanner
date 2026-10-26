import numpy as np
import pandas as pd
import pytest

from momentum.backtest import BacktestConfig, rebalance_dates, run_backtest
from momentum.indicators import Indicators
from momentum.regime import ema_signal, supertrend_signal, supertrend_trend
from momentum.scoring import make_scorer
from tests.conftest import trending_prices

FORMULA = ("CUSTOM", "1 Month Performance")          # 30-day return: needs only 30 days of history


def _cfg(close, **kw):
    base = dict(start=close.index[40], end=close.index[-1], capital=100000, n_stocks=2, exit_rank=3,
                frequency="Monthly", rebalance_day=15, cost_pct=0.0)
    base.update(kw)
    return BacktestConfig(**base)


# ------------------------------------------------------------ calendar
def test_monthly_dates_holiday_rules():
    days = pd.bdate_range("2024-01-01", "2024-12-31")
    prev = rebalance_dates(days, "2024-01-01", "2024-12-31", "Monthly", 15, "Previous")
    nxt = rebalance_dates(days, "2024-01-01", "2024-12-31", "Monthly", 15, "Next")
    assert len(prev) == len(nxt) == 12
    # 15 Jun 2024 is a Saturday
    assert pd.Timestamp("2024-06-14") in prev and pd.Timestamp("2024-06-17") in nxt
    assert pd.Timestamp("2024-03-15") in prev            # a Friday: exact


def test_day_30_in_february_uses_month_end():
    days = pd.bdate_range("2024-01-01", "2024-04-30")
    d = rebalance_dates(days, "2024-02-01", "2024-02-29", "Monthly", 30, "Previous")
    assert d == [pd.Timestamp("2024-02-29")]


def test_weekly_friday():
    days = pd.bdate_range("2024-01-01", "2024-03-31")
    d = rebalance_dates(days, "2024-01-01", "2024-03-31", "Weekly", 4, "Previous")
    assert all(x.weekday() == 4 for x in d) and len(d) >= 12
    assert d == sorted(set(d))


# ------------------------------------------------------------ engine: exact numbers
def test_first_buys_exact_no_costs():
    close = trending_prices()
    r = run_backtest(close, None, _cfg(close), *FORMULA)
    first = r.trades.iloc[:2]
    assert first["Symbol"].tolist() == ["A", "B"]         # fastest growers
    d = first["Date"].iloc[0]
    for _, t in first.iterrows():
        px = close.loc[d, t["Symbol"]]
        assert t["Qty"] == int((100000 / 2) // px)          # equal money per slot, whole shares
    assert r.equity.iloc[0] == 100000                       # before first trade: all cash
    assert r.rebalances.iloc[0]["Held"] == 2


def test_expensive_stock_is_skipped():
    close = trending_prices()
    close["A"] = close["A"] * 1000                          # one share costs more than a slot
    r = run_backtest(close, None, _cfg(close), *FORMULA)
    assert "A" not in set(r.trades["Symbol"])
    assert r.trades.iloc[0]["Symbol"] == "B"


def test_exit_rank_sells_laggard_and_replaces():
    close = trending_prices(n=420)
    # B collapses after day 200 -> falls below exit rank 3 -> must be sold
    close.loc[close.index[200]:, "B"] = close.loc[close.index[200], "B"] * np.linspace(1, 0.3, len(close) - 200)
    r = run_backtest(close, None, _cfg(close, exit_rank=3), *FORMULA)
    sells = r.trades[(r.trades["Action"] == "SELL") & (r.trades["Symbol"] == "B")]
    assert len(sells) == 1 and "exit rank" in sells.iloc[0]["Reason"]
    assert "B" not in set(r.holdings["Symbol"])


def test_costs_are_charged_both_ways():
    close = trending_prices()
    r0 = run_backtest(close, None, _cfg(close, cost_pct=0.0), *FORMULA)
    r1 = run_backtest(close, None, _cfg(close, cost_pct=0.5), *FORMULA)
    assert r1.trades["Cost"].sum() > 0
    assert r1.equity.iloc[-1] < r0.equity.iloc[-1]
    row = r1.trades.iloc[0]
    assert row["Cost"] == pytest.approx(row["Value"] * 0.005)


# ------------------------------------------------------------ ledger reconciliation (independent check)
def _replay(result, close, capital):
    cash = capital
    pos = {}
    for _, t in result.trades.sort_values("Date", kind="stable").iterrows():
        if t["Action"] in ("BUY", "TOPUP"):
            cash -= t["Value"] + t["Cost"]
            pos[t["Symbol"]] = pos.get(t["Symbol"], 0) + t["Qty"]
        else:
            cash += t["Value"] - t["Cost"]
            pos[t["Symbol"]] = pos.get(t["Symbol"], 0) - t["Qty"]
    last = close.ffill().iloc[-1]
    return cash + sum(q * last[s] for s, q in pos.items()), pos


@pytest.mark.parametrize("kw", [
    dict(frequency="Monthly", regime="None"),
    dict(frequency="Weekly", rebalance_day=4, regime="None", exit_rank=12),
    dict(frequency="Monthly", regime="EMA", regime_params=(50,), regime_action="Half Portfolio"),
    dict(frequency="Monthly", regime="EMA", regime_params=(50,), regime_action="Go Cash"),
    dict(frequency="Monthly", regime="SUPERTREND", regime_params=(1, 2.5), execution="Next-day close"),
    dict(frequency="Monthly", regime="EQUITY", equity_sl_pct=1.0),
])
def test_ledger_matches_equity_and_rules_hold(demo, kw):
    close, index = demo
    params = dict(start=pd.Timestamp("2022-01-03"), end=pd.Timestamp("2025-12-31"), capital=250000,
                  n_stocks=8, exit_rank=14, cost_pct=0.2)
    params.update(kw)
    cfg = BacktestConfig(**params)
    ind = Indicators(close)
    r = run_backtest(close, index, cfg, "F11", ind=ind)
    final, pos = _replay(r, close, 250000)
    assert r.equity.iloc[-1] == pytest.approx(final, rel=1e-9)               # curve == trade ledger
    assert all(q >= 0 for q in pos.values())                                  # never short
    assert max(len(set(s for s, q in pos.items() if q > 0)), 0) <= cfg.n_stocks
    assert (r.rebalances["Held"] <= cfg.n_stocks).all()
    assert r.equity.notna().all() and (r.equity > 0).all()


def test_held_stocks_are_within_exit_rank_after_each_rebalance(demo):
    close, index = demo
    cfg = BacktestConfig(start=pd.Timestamp("2022-01-03"), end=pd.Timestamp("2025-12-31"), n_stocks=6,
                         exit_rank=10, cost_pct=0.0, regime="None")
    ind = Indicators(close)
    r = run_backtest(close, None, cfg, "F02", ind=ind)
    scorer = make_scorer("F02")
    pos = {}
    for rd, grp in r.trades.groupby("Date", sort=True):
        for _, t in grp.iterrows():
            pos[t["Symbol"]] = pos.get(t["Symbol"], 0) + (t["Qty"] if t["Action"] in ("BUY", "TOPUP") else -t["Qty"])
        held = [s for s, q in pos.items() if q > 0]
        ranks = scorer(ind, rd).dropna().rank(ascending=False, method="first")
        assert all(ranks[s] <= cfg.exit_rank for s in held), rd


# ------------------------------------------------------------ regime behaviour
def _market(n=300, up=True):
    days = pd.bdate_range("2022-01-03", periods=n)
    c = 100 * (1.002 ** np.arange(n)) if up else 100 * (0.998 ** np.arange(n))
    return pd.DataFrame({"Open": c, "High": c * 1.003, "Low": c * 0.997, "Close": c}, index=days)


def test_supertrend_up_and_down():
    assert supertrend_signal(_market(up=True), 1, 2.5).iloc[-1]
    assert not supertrend_signal(_market(up=False), 1, 2.5).iloc[-1]


def test_supertrend_flips_after_peak():
    n = 400
    days = pd.bdate_range("2021-01-04", periods=n)
    c = np.r_[100 * 1.003 ** np.arange(250), 100 * 1.003 ** 249 * 0.99 ** np.arange(1, 151)]
    oh = pd.DataFrame({"Open": c, "High": c * 1.004, "Low": c * 0.996, "Close": c}, index=days)
    s = supertrend_signal(oh, 1, 2.5)
    assert s.iloc[240] and not s.iloc[-1]


def test_ema_signal():
    m = _market(up=False)
    assert not ema_signal(m["Close"], 20).iloc[-1]


def _two_phase_world():
    """Stocks rise for 250 days then the market falls hard for 150 days."""
    n = 420
    days = pd.bdate_range("2022-01-03", periods=n)
    rates = {"A": 0.002, "B": 0.0015, "C": 0.001, "D": 0.0005, "E": 0.0003, "F": 0.0002}
    up = {k: 100 * (1 + r) ** np.arange(250) for k, r in rates.items()}
    close = pd.DataFrame({k: np.r_[v, v[-1] * (1 - 0.004 + r) ** np.arange(1, n - 249)[:n - 250]]
                          for (k, v), r in zip(up.items(), rates.values())}, index=days)
    mk = close.mean(axis=1)
    index = pd.DataFrame({"Open": mk, "High": mk * 1.003, "Low": mk * 0.997, "Close": mk}, index=days)
    return close, index


def test_half_portfolio_and_go_cash_behave():
    close, index = _two_phase_world()
    base = dict(start=close.index[40], end=close.index[-1], n_stocks=4, exit_rank=6, cost_pct=0.0,
                regime="EMA", regime_params=(40,))
    half = run_backtest(close, index, BacktestConfig(regime_action="Half Portfolio", **base), *FORMULA)
    cash = run_backtest(close, index, BacktestConfig(regime_action="Go Cash", **base), *FORMULA)
    none = run_backtest(close, index, BacktestConfig(**{**base, "regime": "None"}), *FORMULA)

    assert "Weak - half portfolio" in set(half.rebalances["Market"])
    assert "Regime: half portfolio" in set(half.trades["Reason"])
    assert "Weak - cash" in set(cash.rebalances["Market"])
    assert cash.rebalances[cash.rebalances["Market"] == "Weak - cash"]["Held"].eq(0).all()
    # in a falling market protection should lose less than staying fully invested
    assert cash.equity.iloc[-1] > half.equity.iloc[-1] > none.equity.iloc[-1]
    # half mode never invests more than ~50% once the weak phase is under way (plus drift tolerance)
    weak = half.rebalances[half.rebalances["Market"] == "Weak - half portfolio"]
    assert (((weak["Equity"] - weak["Cash"]) / weak["Equity"]) <= 0.55).all()


def test_reinvests_idle_cash_when_market_recovers():
    close, index = _two_phase_world()
    # then a strong recovery
    n = len(close)
    days = pd.bdate_range(close.index[0], periods=n + 160)
    ext = pd.DataFrame({k: np.r_[close[k].to_numpy(), close[k].iloc[-1] * 1.006 ** np.arange(1, 161)] for k in close}, index=days)
    mk = ext.mean(axis=1)
    idx = pd.DataFrame({"Open": mk, "High": mk * 1.003, "Low": mk * 0.997, "Close": mk}, index=days)
    cfg = BacktestConfig(start=days[40], end=days[-1], n_stocks=4, exit_rank=6, cost_pct=0.0,
                         regime="EMA", regime_params=(40,), regime_action="Half Portfolio")
    r = run_backtest(ext, idx, cfg, *FORMULA)
    assert "TOPUP" in set(r.trades["Action"])
    last = r.rebalances.iloc[-1]
    assert last["Market"] == "Healthy" and (last["Cash"] / last["Equity"]) < 0.15


def test_benchmark_is_index_buy_and_hold(demo):
    close, index = demo
    cfg = BacktestConfig(start=pd.Timestamp("2022-01-03"), end=pd.Timestamp("2025-12-31"), n_stocks=5, exit_rank=10)
    r = run_backtest(close, index, cfg, "F02")
    s, e = r.benchmark.index[0], r.benchmark.index[-1]
    assert r.benchmark.iloc[-1] == pytest.approx(100000 * index.loc[e, "Close"] / index.loc[s, "Close"])


def test_validation_errors():
    close = trending_prices()
    with pytest.raises(ValueError):
        run_backtest(close, None, _cfg(close, exit_rank=1), *FORMULA)
    with pytest.raises(ValueError):
        run_backtest(close, None, _cfg(close, rebalance_day=31), *FORMULA)


def test_new_buys_never_bigger_than_one_fair_slot():
    """After a weak spell idle cash must not pile into a few new stocks (each buy <= equity / n_stocks)."""
    close, index = _two_phase_world()
    n = len(close)
    days = pd.bdate_range(close.index[0], periods=n + 160)
    ext = pd.DataFrame({k: np.r_[close[k].to_numpy(), close[k].iloc[-1] * 1.006 ** np.arange(1, 161)] for k in close}, index=days)
    mk = ext.mean(axis=1)
    idx = pd.DataFrame({"Open": mk, "High": mk * 1.003, "Low": mk * 0.997, "Close": mk}, index=days)
    cfg = BacktestConfig(start=days[40], end=days[-1], n_stocks=4, exit_rank=5, cost_pct=0.0,
                         regime="EMA", regime_params=(40,), regime_action="Half Portfolio")
    r = run_backtest(ext, idx, cfg, *FORMULA)
    buys = r.trades[r.trades["Action"] == "BUY"].merge(r.rebalances[["Trade date", "Equity"]],
                                                       left_on="Date", right_on="Trade date")
    # Equity column is AFTER trading, so allow a small tolerance for price drift on the day
    assert (buys["Value"] <= buys["Equity"] / cfg.n_stocks * 1.02).all()
