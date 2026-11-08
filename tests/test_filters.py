import numpy as np
import pandas as pd
import pytest

from momentum import advisor
from momentum.backtest import BacktestConfig, run_backtest
from momentum.indicators import Indicators
from momentum.scoring import entry_max_rank, make_filter, make_scorer, snapshot
from momentum.sigma_parser import FormulaError, parse_filters
from tests.conftest import trending_prices


def _prices():
    # A, B rise; C flat; D falls; E rises for a year then slumps 30% in the last 3 months
    n = 420
    days = pd.bdate_range("2022-01-03", periods=n)
    e = 100 * 1.002 ** np.arange(n)
    e[-90:] = e[-91] * np.linspace(1, 0.7, 90)
    return pd.DataFrame({"A": 100 * 1.002 ** np.arange(n), "B": 100 * 1.001 ** np.arange(n), "C": 100.0 + 0 * np.arange(n),
                         "D": 100 * 0.999 ** np.arange(n), "E": e}, index=days)


def test_parse_filters_ok_and_errors():
    pf = parse_filters("12 Month Performance > 0 AND 3 Month Performance > -10%; 52 Week High >= 0.8")
    assert len(pf.conds) == 3
    assert parse_filters("").conds == ()
    for bad in ["12 Month Performance", "1 > 0", "12 Month Performance > > 0", "__import__('os') > 1", "12 Month Performance = 0"]:
        with pytest.raises(FormulaError):
            parse_filters(bad)


def test_filter_matches_hand_calculation():
    close = _prices()
    ind = Indicators(close)
    d = close.index[-1]
    passes, why = make_filter("12 Month Performance > 0 AND 3 Month Performance > -10%")(ind, d)
    p12 = close.iloc[-1] / close.iloc[-361] - 1
    p3 = close.iloc[-1] / close.iloc[-91] - 1
    expected = (p12 > 0) & (p3 > -0.10)
    assert passes.tolist() == expected.tolist()
    assert why["D"] != "" and why["A"] == ""            # D fails the 12M rule; A passes everything
    assert not passes["E"] and "3 Month" in why["E"]    # E fails the recent-weakness rule only


def test_missing_history_fails_the_rule():
    close = _prices().iloc[-100:]                        # too short for 12 months
    passes, _ = make_filter("12 Month Performance > 0")(Indicators(close), close.index[-1])
    assert not passes.any()


def test_new_columns_in_snapshot_and_f20():
    close = _prices()
    ind = Indicators(close)
    d = close.index[-1]
    snap = snapshot(ind, d)
    assert {"9M %", "1M Vol %", "3M Vol %", "9M Vol %", "12M Vol %", "Consistency"} <= set(snap.columns)
    assert snap["Consistency"].tolist() == pytest.approx((-ind.fip(252).loc[d] * 100).tolist(), nan_ok=True)
    s = make_scorer("F20")(ind, d)
    # hand calculation: mean of the percentile ranks of the 3/6/9/12 month (21-day) returns
    ret = pd.DataFrame({m: close.iloc[-1] / close.iloc[-1 - 21 * m] - 1 for m in (3, 6, 9, 12)})
    assert s.tolist() == pytest.approx((ret.rank(pct=True).mean(axis=1) * 100).tolist())
    assert s.idxmax() == "A"


def test_entry_max_rank():
    assert entry_max_rank(50, 20) == 10 and entry_max_rank(7, 20) == 2
    assert entry_max_rank(50, 0) is None and entry_max_rank(0, 20) is None


def _cfg(**kw):
    close = trending_prices(n=500)
    base = dict(start=close.index[300], end=close.index[-1], capital=100000, n_stocks=2, exit_rank=3, frequency="Monthly")
    base.update(kw)
    return close, BacktestConfig(**base)


def test_filter_blocks_entries_in_backtest():
    close, cfg = _cfg(filters="12 Month Performance > 0.9")          # only the strongest stocks can pass
    res = run_backtest(close, None, cfg, "F02")
    bought = set(res.trades[res.trades["Action"] == "BUY"]["Symbol"])
    assert bought and bought <= {"A", "B"}
    close, cfg = _cfg(filters="12 Month Performance > 100")           # nobody passes
    res = run_backtest(close, None, cfg, "F02")
    assert (res.trades["Action"] == "BUY").sum() == 0


def test_filter_force_exit_vs_block_only():
    n = 520
    days = pd.bdate_range("2021-01-04", periods=n)
    up = np.r_[100 * 1.004 ** np.arange(340), np.full(n - 340, 100 * 1.004 ** 339)]      # rises, then goes flat
    close = pd.DataFrame({"A": up, "B": np.full(n, 100.0)}, index=days)
    base = dict(start=days[300], end=days[-1], capital=100000, n_stocks=1, exit_rank=2, frequency="Monthly",
                filters="1 Month Performance > 0.02")
    forced = run_backtest(close, None, BacktestConfig(filters_force_exit=True, **base), "F02")
    kept = run_backtest(close, None, BacktestConfig(filters_force_exit=False, **base), "F02")
    why = forced.trades[forced.trades["Action"] == "SELL"]["Reason"]
    assert why.str.startswith("Filter failed").any()                   # A is sold once the rule stops passing
    assert (kept.trades["Action"] == "SELL").sum() == 0                # rules only block new buys: A is held on
    assert "A" in set(kept.holdings["Symbol"])


def test_entry_limit_in_backtest():
    close, cfg = _cfg(entry_pct=20, n_stocks=1, exit_rank=6)           # 6 stocks -> top 20% = rank 2
    res = run_backtest(close, None, cfg, "F02")
    bought = set(res.trades[res.trades["Action"] == "BUY"]["Symbol"])
    assert bought <= {"A", "B"}


def test_bad_filter_text_raises():
    close, cfg = _cfg(filters="nonsense")
    with pytest.raises(FormulaError):
        run_backtest(close, None, cfg, "F02")


# ---------------------------------------------------------------- advisor with rules
def _ranked(passes):
    return pd.DataFrame({"Symbol": ["S1", "S2", "S3", "S4"], "Name": "", "Rank": [1, 2, 3, 4], "Price": 100.0,
                         "Passes": passes, "FilterWhy": ["", "", "", ""]})


def test_advisor_sells_held_stock_that_fails_rules_and_skips_failed_buys():
    r = _ranked([True, False, True, True])
    r.loc[r.Symbol == "S2", "FilterWhy"] = "12 Month Performance > 0"
    hold = pd.DataFrame({"Symbol": ["S2"], "Qty": [10]})
    plan, _ = advisor.plan(r, hold, n_stocks=2, exit_rank=4, healthy=True, force_exit_on_fail=True)
    act = dict(zip(plan["Symbol"], plan["Action"]))
    assert act["S2"] == "EXIT" and "Fails filter rule" in plan[plan.Symbol == "S2"].iloc[0]["Why"]
    assert "S1" in act and act["S1"] == "BUY"
    plan, _ = advisor.plan(r, hold, n_stocks=2, exit_rank=4, healthy=True, force_exit_on_fail=False)
    assert dict(zip(plan["Symbol"], plan["Action"]))["S2"] == "HOLD"
    assert "S2" not in set(plan[plan.Action == "BUY"]["Symbol"])


def test_advisor_entry_limit():
    plan, _ = advisor.plan(_ranked([True] * 4), pd.DataFrame({"Symbol": [], "Qty": []}), 3, 4, True, extra_cash=100000, entry_max_rank=2)
    assert set(plan[plan.Action == "BUY"]["Symbol"]) == {"S1", "S2"}


# ---------------------------------------------------------------- score penalty (the script's "-25 points")
def test_penalty_matches_the_scripts_logic_on_f20():
    close = _prices()
    ind = Indicators(close)
    d = close.index[-1]
    base = make_scorer("F20")(ind, d)
    pen = make_scorer("F20", None, ("3 Month Performance > -10%", 25))(ind, d)
    p3 = close.iloc[-1] / close.iloc[-91] - 1
    pct = base.rank(pct=True) * 100
    expected = pct - np.where(p3 > -0.10, 0, 25)
    assert pen.tolist() == pytest.approx(expected.tolist())
    assert pen["E"] < pct["E"] - 24                      # the slumping stock is pushed down


def test_penalty_off_changes_nothing_and_works_in_backtest():
    close = _prices()
    ind = Indicators(close)
    d = close.index[-1]
    assert make_scorer("F02", None, ("", 0))(ind, d).tolist() == make_scorer("F02")(ind, d).tolist()
    cfg = BacktestConfig(start=close.index[300], end=close.index[-1], capital=100000, n_stocks=2, exit_rank=3,
                         penalty_rule="3 Month Performance > -10%", penalty_points=25)
    res = run_backtest(close, None, cfg, "F20")
    assert len(res.equity) > 50


# ---------------------------------------------------------------- PDC (previous day close)
def test_pdc_in_snapshot_trades_holdings_and_advisor():
    close = _prices()
    ind = Indicators(close)
    d = close.index[-1]
    snap = snapshot(ind, d)
    assert snap["PDC"].tolist() == pytest.approx(close.iloc[-2].tolist())
    assert snap["Day %"].tolist() == pytest.approx(((close.iloc[-1] / close.iloc[-2] - 1) * 100).tolist())
    cfg = BacktestConfig(start=close.index[300], end=close.index[-1], capital=100000, n_stocks=2, exit_rank=3)
    res = run_backtest(close, None, cfg, "F02")
    t = res.trades.iloc[0]
    pos = close.index.get_loc(t["Date"])
    assert t["PDC"] == pytest.approx(close.loc[close.index[pos - 1], t["Symbol"]])
    assert {"PDC", "Day %"} <= set(res.holdings.columns)
    r = _ranked([True] * 4)
    r["PDC"] = 99.0
    plan, _ = advisor.plan(r, pd.DataFrame({"Symbol": ["S1"], "Qty": [1]}), 2, 4, True, extra_cash=10000)
    assert "PDC" in plan.columns and (plan["PDC"] == 99.0).all()
