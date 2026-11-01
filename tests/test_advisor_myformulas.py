import numpy as np
import pandas as pd
import pytest

from momentum import advisor, formulas as fml, myformulas as myf
from momentum.backtest import BacktestConfig, run_backtest
from momentum.indicators import Indicators
from momentum.regime import build_signal, equal_weight_index, regime_status
from momentum.scoring import make_scorer
from tests.conftest import trending_prices


def ranked(n=10, price=100.0):
    return pd.DataFrame({"Symbol": [f"S{i}" for i in range(1, n + 1)], "Name": "", "Rank": range(1, n + 1), "Price": price})


def hold(**kw):
    return pd.DataFrame({"Symbol": list(kw), "Qty": list(kw.values())})


# ---------------------------------------------------------------- advisor
def test_exit_when_rank_beyond_exit_rank_and_buy_replacement():
    plan, info = advisor.plan(ranked(), hold(S1=10, S9=10), n_stocks=2, exit_rank=5, healthy=True)
    act = dict(zip(plan["Symbol"], plan["Action"]))
    assert act["S9"] == "EXIT" and act["S1"] == "HOLD"
    assert act["S2"] == "BUY"                                   # best-ranked stock not held fills the free slot
    assert info["n_exit"] == 1 and info["n_buy"] == 1


def test_unknown_symbol_is_exit_no_score():
    plan, info = advisor.plan(ranked(), hold(S1=5, ZZZ=3), 2, 5, True)
    row = plan[plan["Symbol"] == "ZZZ"].iloc[0]
    assert row["Action"] == "EXIT" and "No score" in row["Why"]
    assert "ZZZ" in info["unpriced"]


def test_go_cash_exits_everything_and_buys_nothing():
    plan, _ = advisor.plan(ranked(), hold(S1=10, S2=10), 2, 5, healthy=False, action="Go Cash")
    assert set(plan["Action"]) == {"EXIT"}


def test_half_portfolio_trims_once_and_does_not_buy():
    plan, _ = advisor.plan(ranked(), hold(S1=10, S2=10), 4, 8, healthy=False, action="Half Portfolio")
    assert (plan[plan["Action"] == "TRIM"]["Trade qty"] == 5).all()
    assert "BUY" not in set(plan["Action"])
    again, _ = advisor.plan(ranked(), hold(S1=5, S2=5), 4, 8, healthy=False, action="Half Portfolio", already_halved=True)
    assert "TRIM" not in set(again["Action"])


def test_healthy_again_after_half_tops_up_with_idle_cash():
    plan, info = advisor.plan(ranked(), hold(S1=5, S2=5), 2, 5, healthy=True, already_halved=True, extra_cash=1000)
    assert "TOPUP" in set(plan["Action"])


def test_too_expensive_stock_is_skipped():
    r = ranked(4)
    r.loc[r["Symbol"] == "S1", "Price"] = 1_000_000.0
    plan, _ = advisor.plan(r, hold(S4=10), 2, 4, healthy=True, extra_cash=10_000)
    assert "S1" not in set(plan[plan["Action"] == "BUY"]["Symbol"])


def test_read_holdings_cleans_names_and_sums_duplicates():
    h = advisor.read_holdings(pd.DataFrame({"ticker": ["reliance.ns", "RELIANCE", "TCS", ""], "Quantity": [5, 5, 0, 3]}))
    assert h.to_dict("records") == [{"Symbol": "RELIANCE", "Qty": 10}]
    with pytest.raises(ValueError):
        advisor.read_holdings(pd.DataFrame({"a": [1]}))


# ---------------------------------------------------------------- regime helpers
def test_equal_weight_index_and_status():
    close = trending_prices(n=400)
    ohlc = equal_weight_index(close)
    assert len(ohlc) == len(close) and ohlc["Close"].iloc[0] == pytest.approx(100.0)
    sig = build_signal(ohlc, "EMA", (50,))
    st = regime_status(sig, close.index[-1])
    assert st["known"] and st["days"] >= 1 and st["since"] <= close.index[-1]


def test_regime_status_detects_weak_streak():
    idx = pd.bdate_range("2024-01-01", periods=6)
    sig = pd.Series([True, True, False, False, False, False], index=idx)
    st = regime_status(sig, idx[-1])
    assert st["healthy"] is False and st["days"] == 4 and st["since"] == idx[2]
    assert regime_status(None, idx[-1])["known"] is False


# ---------------------------------------------------------------- my formulas
@pytest.fixture
def store(tmp_path):
    yield tmp_path / "f.json"
    fml.register_user_formulas([])


def test_save_load_delete_roundtrip(store):
    recs = myf.save("My momentum", "6 Month Performance / 6 Month Volatility", "note", path=store)
    assert recs[0]["id"] == "U01" and "U01" in {f.id for f in fml.all_formulas()}
    assert myf.load_records(store)[0]["name"] == "My momentum"
    recs = myf.delete("U01", path=store)
    assert recs == [] and "U01" not in {f.id for f in fml.all_formulas()}


@pytest.mark.parametrize("name,expr", [("", "6 Month Performance"), ("x", "import os"), ("x", "6 Month Performance +"),
                                       ("F01 - 3-Month Return".split(" - ")[1], "6 Month Performance")])
def test_bad_saves_are_refused(store, name, expr):
    with pytest.raises(myf.SaveError):
        myf.save(name, expr, path=store)


def test_duplicate_name_refused(store):
    myf.save("A", "6 Month Performance", path=store)
    with pytest.raises(myf.SaveError):
        myf.save("a", "3 Month Performance", path=store)


def test_saved_formula_scores_like_typed_and_backtests(store):
    close = trending_prices(n=420)
    ind = Indicators(close)
    d = close.index[-1]
    myf.save("Mine", "3 Month Performance / 3 Month Volatility", path=store)
    a = make_scorer("U01")(ind, d)
    b = make_scorer("CUSTOM", "3 Month Performance / 3 Month Volatility")(ind, d)
    assert a.tolist() == pytest.approx(b.tolist(), nan_ok=True)
    cfg = BacktestConfig(start=close.index[200], end=close.index[-1], capital=100000, n_stocks=3, exit_rank=5)
    res = run_backtest(close, None, cfg, "U01", ind=ind)
    assert len(res.equity) > 50


def test_new_terms_work_as_custom_formulas():
    close = trending_prices(n=420)
    ind = Indicators(close)
    d = close.index[-1]
    for text in ["12 Month Performance Skip 1 Month", "52 Week High * 6 Month Performance", "6 Month Performance - FIP",
                 "2 Week Performance + 1 Week Volatility"]:
        s = make_scorer("CUSTOM", text)(ind, d)
        assert s.notna().any(), text


def test_backup_import_skips_bad_and_duplicate(store):
    base = myf.save("Keep", "6 Month Performance", path=store)
    text = myf.to_json([{"name": "Keep", "expr": "3 Month Performance"}, {"name": "New", "expr": "3 Month Performance"},
                        {"name": "Bad", "expr": "os.system"}])
    new, added, skipped = myf.from_json(text, base)
    assert added == 1 and len(skipped) == 2 and {r["name"] for r in new} == {"Keep", "New"}
    with pytest.raises(myf.SaveError):
        myf.from_json("not json", base)
