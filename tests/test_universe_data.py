import io

import pandas as pd
import pytest

from momentum.data import _extract_field
from momentum.universe import UniverseError, read_universe


def _xlsx(rows, header=None):
    buf = io.BytesIO()
    pd.DataFrame(rows, columns=header).to_excel(buf, index=False, header=header is not None)
    return buf.getvalue()


def test_standard_nse_layout():
    data = _xlsx([["Reliance Industries Ltd.", "Oil Gas", "reliance ", "EQ"],
                  ["TCS Ltd.", "IT", "TCS", "EQ"],
                  ["Dup", "IT", "TCS", "EQ"],
                  ["Placeholder", "x", "DUMMYSTOCK1", "EQ"],
                  ["M&M", "Auto", "M&M", "EQ"]],
                 header=["Company Name", "Industry", "Symbol", "Series"])
    u, cols = read_universe(data, "list.xlsx")
    assert u["Symbol"].tolist() == ["RELIANCE", "TCS", "M&M"]
    assert u["Ticker"].tolist() == ["RELIANCE.NS", "TCS.NS", "M&M.NS"]
    assert u.loc[0, "Sector"] == "Oil Gas"


def test_title_rows_above_header_are_skipped():
    rows = [["NIFTY 500 constituents", None], ["as on 2026", None], ["Symbol", "Company"], ["INFY", "Infosys"]]
    u, _ = read_universe(_xlsx(rows), "x.xlsx")
    assert u["Symbol"].tolist() == ["INFY"]


def test_csv_and_existing_suffix():
    csv = b"Ticker,Name\nABC.NS,Abc\nXYZ.BO,Xyz\n"
    u, _ = read_universe(csv, "x.csv")
    assert u["Ticker"].tolist() == ["ABC.NS", "XYZ.BO"]


def test_missing_symbol_column_reports_columns():
    with pytest.raises(UniverseError) as e:
        read_universe(b"foo,bar\n1,2\n", "x.csv")
    assert str(e.value).startswith("SYMBOL_COLUMN_NOT_FOUND:")
    u, _ = read_universe(b"foo,bar\nAAA,2\n", "x.csv", symbol_column="foo")
    assert u["Symbol"].tolist() == ["AAA"]


def test_garbage_file():
    with pytest.raises(UniverseError):
        read_universe(b"\x00\x01\x02", "x.xlsx")


def test_extract_field_both_yfinance_shapes():
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    a = pd.DataFrame({("Close", "AAA.NS"): [1.0, 2.0], ("Close", "BBB.NS"): [3.0, 4.0],
                      ("Volume", "AAA.NS"): [9, 9], ("Volume", "BBB.NS"): [9, 9]}, index=idx)
    a.columns = pd.MultiIndex.from_tuples(a.columns)
    assert _extract_field(a, "Close").columns.tolist() == ["AAA.NS", "BBB.NS"]
    b = pd.DataFrame({("AAA.NS", "Close"): [1.0, 2.0], ("AAA.NS", "Open"): [1.0, 2.0]}, index=idx)
    b.columns = pd.MultiIndex.from_tuples(b.columns)
    assert _extract_field(b, "Close").columns.tolist() == ["AAA.NS"]
    c = pd.DataFrame({"Close": [1.0, 2.0], "Open": [1.0, 2.0]}, index=idx)
    assert _extract_field(c, "Close", "ZZZ.NS").columns.tolist() == ["ZZZ.NS"]
    assert _extract_field(pd.DataFrame(), "Close").empty
