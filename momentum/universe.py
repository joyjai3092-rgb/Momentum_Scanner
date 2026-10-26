"""Reads the user's stock-list file (Excel or CSV) - e.g. an NSE index constituents list."""
from __future__ import annotations

import io

import pandas as pd

from .config import YAHOO_SUFFIX

SYMBOL_HINTS = ("symbol", "ticker", "nse symbol", "scrip", "code")
NAME_HINTS = ("company name", "company", "name", "security name")
SECTOR_HINTS = ("industry", "sector")


class UniverseError(ValueError):
    """Plain-English problem with the uploaded file."""


def _norm(x) -> str:
    return str(x).strip().lower()


def _find_col(columns, hints, exact_first=True):
    cols = {c: _norm(c) for c in columns}
    for h in hints:
        for c, n in cols.items():
            if n == h:
                return c
    for h in hints:
        for c, n in cols.items():
            if h in n:
                return c
    return None


def _read_any(data: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    buf = io.BytesIO(data)
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            return pd.read_excel(buf, header=None, dtype=str)
        return pd.read_csv(buf, header=None, dtype=str, sep=None, engine="python")
    except Exception as exc:  # noqa: BLE001
        raise UniverseError(
            "Could not open the file. Please upload an Excel (.xlsx) or CSV file."
        ) from exc


def read_universe(data: bytes, filename: str, symbol_column: str | None = None):
    """Returns (table, columns_found).

    table columns: Symbol, Ticker (Yahoo), Name, Sector. `Name`/`Sector` may be blank.
    If the symbol column cannot be found, UniverseError carries the list of columns so
    the page can ask the user to pick one.
    """
    raw = _read_any(data, filename)
    if raw.empty:
        raise UniverseError("The file is empty.")

    # find the header row: first row (of the top 15) that contains a symbol-like heading
    header_row = None
    for i in range(min(15, len(raw))):
        row = [_norm(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
        if any(any(h == r or h in r for h in SYMBOL_HINTS) for r in row):
            header_row = i
            break
    if header_row is None:
        header_row = 0
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip() if pd.notna(c) else f"col{j}" for j, c in enumerate(raw.iloc[header_row])]
    df = df.dropna(how="all")
    cols = list(df.columns)

    sym_col = symbol_column if symbol_column in cols else _find_col(cols, SYMBOL_HINTS)
    if sym_col is None:
        raise UniverseError("SYMBOL_COLUMN_NOT_FOUND:" + "|".join(cols))
    name_col = _find_col([c for c in cols if c != sym_col], NAME_HINTS)
    sector_col = _find_col([c for c in cols if c != sym_col], SECTOR_HINTS)

    sym = df[sym_col].astype(str).str.strip().str.upper()
    sym = sym[(sym != "") & (sym != "NAN") & (~sym.str.startswith("DUMMY"))]
    out = pd.DataFrame({"Symbol": sym})
    out["Name"] = df.loc[out.index, name_col].astype(str).str.strip() if name_col else ""
    out["Sector"] = df.loc[out.index, sector_col].astype(str).str.strip() if sector_col else ""
    out = out.drop_duplicates(subset="Symbol").reset_index(drop=True)
    if out.empty:
        raise UniverseError("No stock symbols were found in the file.")
    out["Ticker"] = out["Symbol"].map(
        lambda s: s if s.endswith((".NS", ".BO")) or s.startswith("^") else s + YAHOO_SUFFIX
    )
    return out[["Symbol", "Ticker", "Name", "Sector"]], cols
