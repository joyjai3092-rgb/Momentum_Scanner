"""Monthly rebalance advisor: compares what you hold today with today's ranking.

Uses the same rules as the backtest: sell when rank is worse than the exit rank (or the stock has no score),
fill free slots with the best-ranked stocks you do not hold, equal money per slot, whole shares,
skip stocks too expensive for a slot, and the Half Portfolio / Go Cash market rules.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

COLUMNS = ["Action", "Symbol", "Name", "Rank", "Price", "Held qty", "Trade qty", "Trade value (Rs.)", "Why"]


def read_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a table with columns Symbol and Qty (any case). Returns Symbol, Qty (int > 0)."""
    cols = {str(c).strip().lower(): c for c in df.columns}
    sym = next((cols[k] for k in ("symbol", "ticker", "stock", "scrip") if k in cols), None)
    qty = next((cols[k] for k in ("qty", "quantity", "shares", "units") if k in cols), None)
    if sym is None or qty is None:
        raise ValueError("The holdings need two columns: Symbol and Qty (number of shares).")
    out = pd.DataFrame({
        "Symbol": df[sym].astype(str).str.strip().str.upper().str.replace(r"\.NS$", "", regex=True),
        "Qty": pd.to_numeric(df[qty], errors="coerce"),
    })
    out = out[(out["Symbol"] != "") & (out["Symbol"].str.lower() != "nan")].dropna(subset=["Qty"])
    out = out[out["Qty"] > 0]
    out["Qty"] = np.floor(out["Qty"]).astype(int)
    return out.groupby("Symbol", as_index=False)["Qty"].sum()


def plan(ranked: pd.DataFrame, holdings: pd.DataFrame, n_stocks: int, exit_rank: int, healthy: bool,
         action: str = "Half Portfolio", already_halved: bool = False, extra_cash: float = 0.0,
         cost_pct: float = 0.2) -> tuple:
    """Build the to-do list.

    ranked   : columns Symbol, Name, Rank, Price (every stock the screener could score, Rank 1 = best)
    holdings : columns Symbol, Qty
    Returns (plan_table, summary_dict).
    """
    cost = cost_pct / 100.0
    r = ranked.drop_duplicates("Symbol").set_index("Symbol")
    rows = []
    cash = float(extra_cash)
    held_value = 0.0
    kept = []                                    # (symbol, qty)
    unpriced = []

    for _, h in holdings.iterrows():
        s, q = h["Symbol"], int(h["Qty"])
        if s in r.index and np.isfinite(r.at[s, "Price"]):
            px = float(r.at[s, "Price"])
            held_value += q * px
        else:
            px = np.nan
        rk = r.at[s, "Rank"] if s in r.index else np.nan
        name = r.at[s, "Name"] if s in r.index else ""
        if pd.isna(rk) or rk > exit_rank:
            why = "No score / no price data" if pd.isna(rk) else f"Rank {int(rk)} is worse than exit rank {exit_rank}"
            if not np.isfinite(px):
                unpriced.append(s)
            rows.append(dict(Action="EXIT", Symbol=s, Name=name, Rank=rk, Price=px, **{"Held qty": q}, **{"Trade qty": q},
                             **{"Trade value (Rs.)": q * px if np.isfinite(px) else np.nan}, Why=why))
            if np.isfinite(px):
                cash += q * px * (1 - cost)
        else:
            kept.append((s, q, rk, name, px))

    weak = not healthy
    go_cash = weak and action == "Go Cash"
    half = weak and action != "Go Cash"

    if go_cash:
        for s, q, rk, name, px in kept:
            rows.append(dict(Action="EXIT", Symbol=s, Name=name, Rank=rk, Price=px, **{"Held qty": q}, **{"Trade qty": q},
                             **{"Trade value (Rs.)": q * px if np.isfinite(px) else np.nan}, Why="Market is weak - Go Cash rule"))
            if np.isfinite(px):
                cash += q * px * (1 - cost)
        kept = []

    equity = held_value + float(extra_cash)                  # value before any trade
    slot = equity / n_stocks if n_stocks else 0.0
    kept_after = []
    for s, q, rk, name, px in kept:
        if half and not already_halved and q // 2 > 0:
            t = q // 2
            rows.append(dict(Action="TRIM", Symbol=s, Name=name, Rank=rk, Price=px, **{"Held qty": q}, **{"Trade qty": t},
                             **{"Trade value (Rs.)": t * px if np.isfinite(px) else np.nan},
                             Why="Market is weak - Half Portfolio rule: sell half"))
            if np.isfinite(px):
                cash += t * px * (1 - cost)
            kept_after.append((s, q - t, rk, name, px))
        else:
            kept_after.append((s, q, rk, name, px))
            rows.append(dict(Action="HOLD", Symbol=s, Name=name, Rank=rk, Price=px, **{"Held qty": q}, **{"Trade qty": 0},
                             **{"Trade value (Rs.)": 0.0},
                             Why=f"Rank {int(rk)} is inside exit rank {exit_rank}"))

    held_now = sum(q * px for _, q, _, _, px in kept_after if np.isfinite(px))
    total = held_now + cash
    invest_fraction = 0.0 if go_cash else (0.5 if half else 1.0)
    budget = min(cash, max(0.0, invest_fraction * total - held_now))
    vacancies = n_stocks - len(kept_after)
    n_buy = 0
    if vacancies > 0 and budget > 0:
        alloc = min(budget / vacancies, total / n_stocks)
        held_syms = {s for s, *_ in kept_after}
        for s, row in r.sort_values("Rank").iterrows():
            if n_buy >= vacancies:
                break
            if s in held_syms or not np.isfinite(row["Price"]) or row["Price"] <= 0:
                continue
            qty = int(math.floor(alloc / (row["Price"] * (1 + cost))))
            if qty < 1:
                continue
            rows.append(dict(Action="BUY", Symbol=s, Name=row["Name"], Rank=row["Rank"], Price=row["Price"], **{"Held qty": 0},
                             **{"Trade qty": qty}, **{"Trade value (Rs.)": qty * row["Price"]},
                             Why=f"Free slot - rank {int(row['Rank'])}"))
            n_buy += 1
            cash -= qty * row["Price"] * (1 + cost)

    # market healthy again after a Half-Portfolio spell: top up existing holdings with idle cash
    if healthy and already_halved and kept_after and cash > 0:
        target = total / n_stocks
        for s, q, rk, name, px in sorted(kept_after, key=lambda x: x[2]):
            if not np.isfinite(px):
                continue
            have = q * px
            if have < target:
                qty = int(math.floor(min(target - have, cash) / (px * (1 + cost))))
                if qty >= 1:
                    rows.append(dict(Action="TOPUP", Symbol=s, Name=name, Rank=rk, Price=px, **{"Held qty": q},
                                     **{"Trade qty": qty}, **{"Trade value (Rs.)": qty * px},
                                     Why="Market healthy again - put idle cash back to work"))
                    cash -= qty * px * (1 + cost)

    out = pd.DataFrame(rows, columns=COLUMNS)
    order = {"EXIT": 0, "TRIM": 1, "BUY": 2, "TOPUP": 3, "HOLD": 4}
    out = out.sort_values(by=["Action", "Rank"], key=lambda c: c.map(order) if c.name == "Action" else c, kind="stable").reset_index(drop=True)
    summary = {
        "portfolio_value": total, "slot": slot, "cash_left": max(cash, 0.0),
        "n_exit": int((out["Action"] == "EXIT").sum()), "n_trim": int((out["Action"] == "TRIM").sum()),
        "n_buy": int((out["Action"] == "BUY").sum()), "n_topup": int((out["Action"] == "TOPUP").sum()),
        "n_hold": int((out["Action"] == "HOLD").sum()), "unpriced": unpriced,
        "free_slots": max(vacancies - n_buy, 0) if not go_cash else n_stocks,
    }
    return out, summary
