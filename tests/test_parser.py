import numpy as np
import pandas as pd
import pytest

from momentum.sigma_parser import FormulaError, evaluate, parse_formula


def test_sigma_example_value():
    p = parse_formula("((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility")
    assert p.needs == (("P", 1), ("P", 6), ("V", 1))
    v = {"P6": pd.Series([0.2]), "P1": pd.Series([0.05]), "V1": pd.Series([0.3])}
    assert evaluate(p, v).iloc[0] == pytest.approx((0.7 * 0.2 + 0.3 * 0.05) / 0.3)


def test_symbols_and_year_alias():
    p = parse_formula("1 Year Performance ÷ 6 Month Volatility × 2")
    assert ("P", 12) in p.needs and ("V", 6) in p.needs


def test_division_by_zero_becomes_nan():
    p = parse_formula("6 Month Performance / 3 Month Volatility")
    out = evaluate(p, {"P6": pd.Series([0.1, 0.2]), "V3": pd.Series([0.0, 0.5])})
    assert np.isnan(out.iloc[0]) and out.iloc[1] == pytest.approx(0.4)


@pytest.mark.parametrize("bad", [
    "", "import os", "__import__('os').system('x')", "6 Month Slope", "(6 Month Performance",
    "13 Month Performance", "0 Month Performance", "5 + 5", "6 Month Performance ** 2",
    "open('f')", "6 Month Performance; 1",
])
def test_rejects_bad_or_unsafe(bad):
    with pytest.raises(FormulaError):
        parse_formula(bad)
