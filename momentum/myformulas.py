"""Formulas saved by the user (kept in a small file `my_formulas.json` next to the app).

Rules are in formulas.RULES_MARKDOWN. A saved formula is checked with the same parser the
Screener and Backtest use, so it can never run code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import formulas as fml
from .sigma_parser import FormulaError, describe, is_sigma_compatible, longest_lookback_months, parse_formula

MAX_SAVED = 50
MAX_NAME = 60
STORE_PATH = Path(os.environ.get("MOMENTUM_MY_FORMULAS", Path(__file__).resolve().parents[1] / "my_formulas.json"))


class SaveError(ValueError):
    """Plain-English reason a formula could not be saved."""


def _next_id(existing: list) -> str:
    used = {r["id"] for r in existing}
    i = 1
    while f"U{i:02d}" in used:
        i += 1
    return f"U{i:02d}"


def build_formula(rec: dict) -> fml.Formula:
    """Turn a saved record {id, name, expr, note} into a Formula with generated help text."""
    parsed = parse_formula(rec["expr"])
    items = describe(parsed)
    months = longest_lookback_months(parsed)
    ok_sigma = is_sigma_compatible(parsed)
    note = (rec.get("note") or "").strip()
    return fml.Formula(
        id=rec["id"], name=rec["name"], category=fml.USER_CATEGORY, kind="sigma", expr=rec["expr"],
        native_key=None,
        one_liner=note or f"Your own formula: {rec['expr']}",
        explanation=f"Score = `{rec['expr']}`. Higher score = better rank. Items used:\n\n" + "\n".join(f"- {x}" for x in items),
        purpose=note or "Written by you.",
        how_to_read="Rank 1 = highest score. Only the order matters, not the size of the number.",
        strengths="Fully under your control.",
        limits=f"Not from a published paper - test it over several date ranges first. Needs about {months:g} months of price history.",
        evidence=("None - this formula was written by you, not taken from the project documents.",),
        sources=(), month_note=fml.SIGMA_MONTH_NOTE,
        sigma_text=rec["expr"] if ok_sigma else None,
        sigma_note="" if ok_sigma else "Uses items that Sigma Scanner does not have (FIP, 52 Week High or Skip), so it only runs in this app.",
        origin="user",
    )


def load_records(path: Path | None = None) -> list:
    p = Path(path or STORE_PATH)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in data if isinstance(data, list) else []:
        if isinstance(r, dict) and {"id", "name", "expr"} <= set(r):
            out.append({"id": str(r["id"]), "name": str(r["name"]), "expr": str(r["expr"]), "note": str(r.get("note", ""))})
    return out


def _write(records: list, path: Path | None = None) -> None:
    p = Path(path or STORE_PATH)
    try:
        p.write_text(json.dumps(records, indent=2), encoding="utf-8")
    except OSError:
        pass          # read-only host: the formulas still live in this browser session


def load_into_registry(records: list) -> None:
    good = []
    for r in records:
        try:
            good.append(build_formula(r))
        except FormulaError:
            continue
    fml.register_user_formulas(good)


def validate(name: str, expr: str, records: list) -> str:
    """Return the cleaned name or raise SaveError."""
    name = (name or "").strip()
    if not name:
        raise SaveError("Please give the formula a name.")
    if len(name) > MAX_NAME:
        raise SaveError(f"The name is too long (maximum {MAX_NAME} characters).")
    if any(r["name"].lower() == name.lower() for r in records):
        raise SaveError("You already have a formula with this name. Choose another name or delete the old one.")
    if any(f.name.lower() == name.lower() for f in fml.LIBRARY):
        raise SaveError("This name is used by a built-in formula. Choose another name.")
    if len(records) >= MAX_SAVED:
        raise SaveError(f"You can save up to {MAX_SAVED} formulas. Delete one first.")
    try:
        parse_formula(expr)
    except FormulaError as exc:
        raise SaveError(str(exc)) from exc
    return name


def save(name: str, expr: str, note: str = "", records: list | None = None, path: Path | None = None) -> list:
    """Add a formula; returns the new full list (also written to disk and the registry)."""
    records = list(records if records is not None else load_records(path))
    name = validate(name, expr, records)
    records.append({"id": _next_id(records), "name": name, "expr": expr.strip(), "note": (note or "").strip()})
    _write(records, path)
    load_into_registry(records)
    return records


def delete(formula_id: str, records: list | None = None, path: Path | None = None) -> list:
    records = [r for r in (records if records is not None else load_records(path)) if r["id"] != formula_id]
    _write(records, path)
    load_into_registry(records)
    return records


def to_json(records: list) -> str:
    return json.dumps(records, indent=2)


def from_json(text: str, records: list) -> tuple:
    """Merge an uploaded backup. Returns (new_records, added_count, skipped_messages)."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SaveError("That file is not a formulas backup (could not read it).") from exc
    if not isinstance(data, list):
        raise SaveError("That file is not a formulas backup.")
    out, added, skipped = list(records), 0, []
    for r in data:
        try:
            name = validate(str(r.get("name", "")), str(r.get("expr", "")), out)
        except (SaveError, AttributeError) as exc:
            skipped.append(f"{r.get('name', '?') if isinstance(r, dict) else '?'}: {exc}")
            continue
        out.append({"id": _next_id(out), "name": name, "expr": str(r["expr"]).strip(), "note": str(r.get("note", "")).strip()})
        added += 1
    return out, added, skipped
