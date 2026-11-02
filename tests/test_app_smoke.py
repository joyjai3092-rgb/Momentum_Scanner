"""Clicks through the real pages (in Demo mode - no internet needed) and checks nothing crashes."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

TIMEOUT = 180
ROOT = Path(__file__).resolve().parents[1]


def _app(page: str) -> AppTest:
    at = AppTest.from_file(str(ROOT / page), default_timeout=TIMEOUT)
    at.session_state["demo"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


@pytest.mark.parametrize("page", ["app.py", "pages/3_Learn_Momentum.py"])
def test_static_pages_open(page):
    _app(page)


def test_screener_runs_on_sample_list():
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    assert not at.exception
    _button(at, "Run screener").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert any("Ranked" in s.value for s in at.success)
    assert len(at.dataframe) >= 2                      # buy list + full ranking


def test_screener_every_formula_runs():
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    ids = at.selectbox(key="scr_formula").options
    assert len(ids) == 20                              # 19 formulas + custom
    for fid in ids:
        if fid == "CUSTOM":
            continue
        at.selectbox(key="scr_formula").select(fid).run()
        _button(at, "Run screener").click().run()
        assert not at.exception, (fid, [e.value for e in at.exception])
        assert not at.error, (fid, [e.value for e in at.error])


def test_backtest_preset_runs_and_shows_results():
    at = _app("pages/2_Backtest.py")
    at.checkbox(key="use_sample").check().run()
    at.selectbox(key="bt_preset").select("1. Beginner Stable").run()
    at.session_state["bt_n"] = 10                      # sample list has only 30 stocks
    at.session_state["bt_exit"] = 20
    at.run()
    _button(at, "Run backtest").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    labels = [m.label for m in at.metric]
    assert "CAGR (yearly growth)" in labels and "Worst fall (max drawdown)" in labels


def test_backtest_uses_the_chosen_date_range():
    at = _app("pages/2_Backtest.py")
    at.checkbox(key="use_sample").check().run()
    at.session_state["bt_n"] = 8
    at.session_state["bt_exit"] = 16
    at.session_state["bt_start"] = pd.Timestamp("2023-01-02").date()
    at.session_state["bt_end"] = pd.Timestamp("2024-06-28").date()
    at.run()
    _button(at, "Run backtest").click().run()
    assert not at.exception, [e.value for e in at.exception]
    res = at.session_state["bt"]["res"]
    assert res.equity.index[0] >= pd.Timestamp("2023-01-02")
    assert res.equity.index[-1] <= pd.Timestamp("2024-06-28")
    assert (res.trades["Date"] >= pd.Timestamp("2023-01-02")).all()
    assert (res.trades["Date"] <= pd.Timestamp("2024-06-28")).all()


def test_backtest_blocks_short_date_range():
    at = _app("pages/2_Backtest.py")
    at.checkbox(key="use_sample").check().run()
    at.session_state["bt_start"] = pd.Timestamp("2024-01-02").date()
    at.session_state["bt_end"] = pd.Timestamp("2024-02-01").date()
    at.run()
    assert any("3 months" in e.value for e in at.error)
    assert _button(at, "Run backtest").disabled


def test_screener_shows_market_banner_and_advice(tmp_path):
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    _button(at, "Run screener").click().run()
    assert not at.exception, [e.value for e in at.exception]
    texts = [x.value for x in at.success] + [x.value for x in at.warning]
    assert any("Market looks" in t for t in texts), texts


def test_screener_rebalance_advice_for_typed_holdings():
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    at.session_state["scr_hold_tbl"] = pd.DataFrame({"Symbol": ["RELIANCE", "NOSUCH"], "Qty": [10, 5]})
    at.run()
    _button(at, "Run screener").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Monthly rebalance advice" in s.value for s in at.subheader)


def test_save_custom_formula_then_it_is_in_dropdown(tmp_path, monkeypatch):
    from momentum import myformulas
    monkeypatch.setattr(myformulas, "STORE_PATH", tmp_path / "f.json")
    at = _app("pages/2_Backtest.py")
    at.selectbox(key="bt_formula").select("CUSTOM").run()
    at.text_input(key="bt_custom").set_value("6 Month Performance / 6 Month Volatility").run()
    at.text_input(key="bt_save_name").set_value("Test mine").run()
    _button(at, "Save this formula").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(o.startswith("U01 - Test mine") for o in at.selectbox(key="bt_formula").options)
    assert at.selectbox(key="bt_formula").value.startswith("U01")
    from momentum import formulas
    formulas.register_user_formulas([])


def test_backtest_with_sigma_supertrend():
    at = _app("pages/2_Backtest.py")
    at.checkbox(key="use_sample").check().run()
    at.selectbox(key="bt_regime").select("SIGMA SUPERTREND").run()
    assert not at.exception, [e.value for e in at.exception]
    at.session_state["bt_n"] = 10
    at.session_state["bt_exit"] = 20
    at.run()
    _button(at, "Run backtest").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert "CAGR (yearly growth)" in [m.label for m in at.metric]


def test_screener_with_sigma_supertrend():
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    at.selectbox(key="scr_regime").select("SIGMA SUPERTREND").run()
    _button(at, "Run screener").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Sigma SuperTrend" in x.value for x in list(at.success) + list(at.warning))


@pytest.mark.parametrize("tf", ["Daily", "Weekly", "Monthly"])
def test_screener_supertrend_custom_atr_and_timeframe(tf):
    at = _app("pages/1_Screener.py")
    at.checkbox(key="use_sample").check().run()
    at.number_input(key="scr_st_p").set_value(7).run()
    at.number_input(key="scr_st_m").set_value(3.5).run()
    at.selectbox(key="scr_tf_SUPERTREND").select(tf).run()
    _button(at, "Run screener").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Market looks" in x.value for x in list(at.success) + list(at.warning))


@pytest.mark.parametrize("regime", ["EMA", "MACD", "SUPERTREND", "SIGMA SUPERTREND"])
def test_backtest_each_regime_on_monthly_candles(regime):
    at = _app("pages/2_Backtest.py")
    at.checkbox(key="use_sample").check().run()
    at.selectbox(key="bt_regime").select(regime).run()
    at.selectbox(key=f"bt_tf_{regime}").select("Monthly").run()
    at.session_state["bt_n"] = 10
    at.session_state["bt_exit"] = 20
    at.run()
    _button(at, "Run backtest").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
