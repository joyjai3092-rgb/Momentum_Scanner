import numpy as np
import pandas as pd
import pytest

from momentum.indicators import Indicators
from tests.conftest import trending_prices


def test_perf_matches_manual():
    close = trending_prices()
    ind = Indicators(close)
    d = close.index[-1]
    manual = close.iloc[-1] / close.iloc[-1 - 180] - 1
    assert ind.perf(180).loc[d].tolist() == pytest.approx(manual.tolist())
    assert ind.sigma_perf(6).loc[d].tolist() == pytest.approx(manual.tolist())


def test_vol_zero_for_constant_growth_and_positive_for_noise():
    close = trending_prices()
    v = Indicators(close).vol(30).iloc[-1]
    assert v.max() < 1e-9                       # constant daily growth => no variation
    rng = np.random.default_rng(1)
    noisy = pd.DataFrame({"X": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 200)))},
                         index=pd.bdate_range("2022-01-03", periods=200))
    v2 = Indicators(noisy).vol(30).iloc[-1, 0]
    manual = (noisy["X"] / noisy["X"].shift(1) - 1).iloc[-30:].std() * np.sqrt(252)
    assert v2 == pytest.approx(manual)


def test_high_proximity():
    days = pd.bdate_range("2022-01-03", periods=300)
    p = np.r_[np.linspace(100, 200, 280), np.linspace(200, 150, 20)]
    ind = Indicators(pd.DataFrame({"X": p}, index=days))
    assert ind.high_proximity(252).iloc[-1, 0] == pytest.approx(150 / 200)


def test_fip_smooth_vs_jumpy():
    n = 300
    days = pd.bdate_range("2022-01-03", periods=n)
    smooth = 100 * 1.001 ** np.arange(n)                      # up every day
    jumpy = np.full(n, 100.0)
    jumpy[1:] = 100.0
    steps = np.ones(n)
    steps[::50] = 1.8                                          # a few big jumps, tiny drift down otherwise
    steps[steps == 1.0] = 0.9995
    jumpy = 100 * np.cumprod(steps)
    ind = Indicators(pd.DataFrame({"smooth": smooth, "jumpy": jumpy}, index=days))
    f = ind.fip(252).iloc[-1]
    assert f["smooth"] == pytest.approx(-1.0)                  # 100% up days, positive past return
    assert f["jumpy"] > f["smooth"]                            # jumpy is worse (higher)
