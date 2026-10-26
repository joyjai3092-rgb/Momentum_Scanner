import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def demo():
    from momentum.demo_data import make_demo_prices
    tickers = [f"S{i:02d}.NS" for i in range(40)]
    close, index = make_demo_prices(tickers, "2020-01-01", "2025-12-31", seed=3)
    return close, index


def trending_prices(n=420, rates=None, start="2022-01-03"):
    """Deterministic prices: each stock grows at a fixed daily rate."""
    rates = rates or {"A": 0.002, "B": 0.0015, "C": 0.001, "D": 0.0005, "E": 0.0, "F": -0.001}
    days = pd.bdate_range(start, periods=n)
    data = {k: 100 * (1 + r) ** np.arange(n) for k, r in rates.items()}
    return pd.DataFrame(data, index=days)
