import numpy as np
import pandas as pd
import pytest

from momentum import formulas
from momentum.indicators import Indicators
from momentum.presets import PRESETS
from momentum.scoring import make_scorer, rank_table, snapshot
from momentum.sigma_parser import parse_formula


def test_library_integrity():
    ids = [f.id for f in formulas.LIBRARY]
    assert len(ids) == len(set(ids)) == 19
    for f in formulas.LIBRARY:
        assert f.one_liner and f.explanation and f.purpose and f.how_to_read and f.evidence and f.sources
        md = formulas.help_markdown(f)
        assert f.name in md and "Sources" in md
        if f.kind == "sigma":
            parse_formula(f.expr)                       # every Sigma formula must be valid
            assert f.sigma_text
        else:
            assert f.native_key


def test_sigma_text_roundtrips_to_same_expression():
    for f in formulas.LIBRARY:
        if f.kind == "sigma":
            assert parse_formula(f.sigma_text).needs == parse_formula(f.expr).needs


def test_presets_use_real_formulas():
    for p in PRESETS:
        formulas.get_formula(p.formula_id)
        assert p.exit_rank >= p.n_stocks


def test_every_formula_scores_on_demo(demo):
    close, _ = demo
    ind = Indicators(close)
    d = close.index[-1]
    for f in formulas.LIBRARY:
        s = make_scorer(f.id)(ind, d)
        assert s.notna().sum() == close.shape[1], f.id


def test_formula_f02_ranks_by_6m_return(demo):
    close, _ = demo
    ind = Indicators(close)
    d = close.index[-1]
    rt = rank_table(ind, d, make_scorer("F02"))
    manual = (close.iloc[-1] / close.iloc[-1 - 180] - 1).sort_values(ascending=False)
    assert rt.index.tolist() == manual.index.tolist()


def test_nse_score_matches_manual(demo):
    """Independent re-calculation of the NSE method: month-end prices M-1, M-7, M-13."""
    close, _ = demo
    ind = Indicators(close)
    d = close.index[-1]
    got = make_scorer("F17")(ind, d)

    def month_end(back):
        per = d.to_period("M") - back
        return close[close.index.to_period("M") == per].iloc[-1]

    lr = np.log(close / close.shift(1))
    sd = lr.iloc[-252:].std() * np.sqrt(252)
    mr12 = (month_end(1) / month_end(13) - 1) / sd
    mr6 = (month_end(1) / month_end(7) - 1) / sd
    z = 0.5 * (mr12 - mr12.mean()) / mr12.std(ddof=0) + 0.5 * (mr6 - mr6.mean()) / mr6.std(ddof=0)
    exp = pd.Series(np.where(z >= 0, 1 + z, 1 / (1 - z)), index=z.index)
    assert got.tolist() == pytest.approx(exp.tolist())
    assert (got > 0).all()


def test_nse_returns_ignore_current_month_moves(demo):
    """NSE measures to the END of the previous month, so moves inside the current month do not enter the returns."""
    from momentum.scoring import _nse_returns
    close, _ = demo
    d = close.index[-1]
    r12, r6 = _nse_returns(Indicators(close), d)
    bumped = close.copy()
    this_month = bumped.index.to_period("M") == d.to_period("M")
    bumped.loc[this_month, "S00.NS"] *= 1.5
    b12, b6 = _nse_returns(Indicators(bumped), d)
    assert b12["S00.NS"] == pytest.approx(r12["S00.NS"]) and b6["S00.NS"] == pytest.approx(r6["S00.NS"])


def test_quant_momentum_top_decile_sorted_by_fip(demo):
    close, _ = demo
    ind = Indicators(close)
    d = close.index[-1]
    s = make_scorer("F19")(ind, d)
    gen = ind.skip_return(252, 21).loc[d]
    fip = ind.fip(252).loc[d]
    k = int(np.ceil(0.10 * len(gen)))
    top = gen.nlargest(k).index
    assert set(s.nlargest(k).index) == set(top)                 # top-decile always ranked first
    order = s.loc[top].sort_values(ascending=False).index
    assert fip.loc[order].is_monotonic_increasing               # lower (more negative) FIP = better


def test_custom_formula(demo):
    close, _ = demo
    ind = Indicators(close)
    d = close.index[-1]
    s = make_scorer("CUSTOM", "6 Month Performance / 6 Month Volatility")(ind, d)
    f7 = make_scorer("F07")(ind, d)
    assert s.tolist() == pytest.approx(f7.tolist())


def test_snapshot_columns(demo):
    close, _ = demo
    snap = snapshot(Indicators(close), close.index[-1])
    assert {"Price", "1M %", "6M %", "FIP", "% of 52W high"} <= set(snap.columns)
