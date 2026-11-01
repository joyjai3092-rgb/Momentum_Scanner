"""Reads Sigma-Scanner-style scoring formulas, e.g.

    ((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility

Only these building blocks are allowed:
    * "N Month Performance" / "N Month Volatility"   (N = 1..12; "N Year ..." also accepted)  [Sigma]
    * "N Week Performance"  / "N Week Volatility"    (N = 1..4)                               [Sigma prompt]
    * "N Month Performance Skip M Month"             (app only, M < N)
    * "FIP"  (frog-in-the-pan smoothness)  and  "52 Week High"  (price / 52-week high)         (app only)
    * numbers and percentages (70%)
    * + - * x / and the symbols x and the divide sign
    * round brackets

Nothing else is evaluated, so a typed formula can never run arbitrary code.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import MAX_SIGMA_MONTHS


class FormulaError(ValueError):
    """Raised with a plain-English message when a typed formula cannot be read."""


_METRIC_RE = re.compile(
    r"(\d{1,2})\s*(month|months|m|year|years|y)\s*(performance|perf|volatility|vol)\b",
    re.IGNORECASE,
)
_SKIP_RE = re.compile(r"(\d{1,2})\s*months?\s*(?:performance|perf)\s*skip(?:ping)?\s*(\d{1,2})\s*months?", re.IGNORECASE)
_WEEK_RE = re.compile(r"(\d{1,2})\s*weeks?\s*(performance|perf|volatility|vol)\b", re.IGNORECASE)
_H52_RE = re.compile(r"\b52\s*weeks?\s*high\b", re.IGNORECASE)
_FIP_RE = re.compile(r"\bFIP\b", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
MAX_WEEKS = 4
_ALLOWED_AFTER = re.compile(r"^[0-9A-Z_\s\.\+\-\*/\(\)]*$")

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd,
)


@dataclass(frozen=True)
class ParsedFormula:
    text: str                       # what the user typed
    tree: ast.Expression            # safe expression tree
    needs: tuple                    # e.g. (("P", 6), ("V", 3))


def _metric_sub(match: re.Match) -> str:
    n = int(match.group(1))
    unit = match.group(2).lower()
    months = n * 12 if unit.startswith("y") else n
    if not 1 <= months <= MAX_SIGMA_MONTHS:
        raise FormulaError(
            f"'{match.group(0)}' is outside the allowed range: use 1 to {MAX_SIGMA_MONTHS} months."
        )
    kind = "P" if match.group(3).lower().startswith("perf") else "V"
    return f" {kind}{months} "


def _skip_sub(match: re.Match) -> str:
    n, m = int(match.group(1)), int(match.group(2))
    if not (1 <= m < n <= MAX_SIGMA_MONTHS):
        raise FormulaError(
            f"'{match.group(0)}': the skipped months must be fewer than the look-back, and both within 1 to {MAX_SIGMA_MONTHS}."
        )
    return f" PS{n}_{m} "


def _week_sub(match: re.Match) -> str:
    n = int(match.group(1))
    if not 1 <= n <= MAX_WEEKS:
        raise FormulaError(f"'{match.group(0)}' is outside the allowed range: use 1 to {MAX_WEEKS} weeks.")
    kind = "P" if match.group(2).lower().startswith("perf") else "V"
    return f" {kind}W{n} "


def need_name(need: tuple) -> str:
    """Variable name used inside the parsed formula for one item, e.g. ('P', 6) -> 'P6'."""
    k = need[0]
    if k in ("P", "V"):
        return f"{k}{need[1]}"
    if k in ("PW", "VW"):
        return f"{k}{need[1]}"
    if k == "PS":
        return f"PS{need[1]}_{need[2]}"
    return k                                  # FIP, H52


def _need_from_name(name: str):
    u = name.upper()
    m = re.fullmatch(r"([PV])(\d{1,2})", u)
    if m:
        months = int(m.group(2))
        if not 1 <= months <= MAX_SIGMA_MONTHS:
            return None
        return (m.group(1), months)
    m = re.fullmatch(r"([PV])W([1-4])", u)
    if m:
        return (m.group(1) + "W", int(m.group(2)))
    m = re.fullmatch(r"PS(\d{1,2})_(\d{1,2})", u)
    if m and 1 <= int(m.group(2)) < int(m.group(1)) <= MAX_SIGMA_MONTHS:
        return ("PS", int(m.group(1)), int(m.group(2)))
    if u in ("FIP", "H52"):
        return (u,)
    return None


def parse_formula(text: str) -> ParsedFormula:
    """Turn a Sigma-style formula string into a safe, evaluable tree."""
    if not text or not text.strip():
        raise FormulaError("The formula is empty.")
    raw = text.strip()
    s = raw.replace("×", "*").replace("÷", "/").replace("−", "-")
    s = re.sub(r"(?<=[\d\)\s])x(?=[\s\(\d])", "*", s)          # "70% x 6 Month ..." -> *
    s = _H52_RE.sub(" H52 ", s)
    s = _SKIP_RE.sub(_skip_sub, s)
    s = _WEEK_RE.sub(_week_sub, s)
    s = _METRIC_RE.sub(_metric_sub, s)
    s = _FIP_RE.sub(" FIP ", s)
    s = _PERCENT_RE.sub(lambda m: f"({m.group(1)}/100)", s)
    s_check = s.upper()
    if not _ALLOWED_AFTER.match(s_check):
        bad = sorted(set(re.sub(r"[0-9A-Z_\s\.\+\-\*/\(\)]", "", s_check)))
        raise FormulaError(
            "Only 'N Month/Week Performance', 'N Month/Week Volatility', 'N Month Performance Skip M Month', "
            "'FIP', '52 Week High', numbers, % and + - * / ( ) are allowed. "
            f"Could not understand: {' '.join(bad) if bad else raw}"
        )
    if s.count("(") != s.count(")"):
        raise FormulaError("Brackets do not match - check every ( has a closing ).")
    try:
        tree = ast.parse(s.strip(), mode="eval")
    except SyntaxError as exc:
        raise FormulaError("The formula is not written correctly (check operators and brackets).") from exc

    needs = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError("The formula uses something that is not allowed.")
        if isinstance(node, ast.Name):
            need = _need_from_name(node.id)
            if need is None:
                raise FormulaError(
                    f"'{node.id}' is not a recognised item. Use e.g. '6 Month Performance'."
                )
            needs.add(need)
    if not needs:
        raise FormulaError("The formula must use at least one item such as '6 Month Performance'.")
    return ParsedFormula(text=raw, tree=tree, needs=tuple(sorted(needs)))


def evaluate(parsed: ParsedFormula, variables: dict) -> pd.Series:
    """Evaluate with variables like {"P6": Series, "V3": Series} (one value per stock)."""

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return np.float64(node.value)
        if isinstance(node, ast.Name):
            return variables[node.id.upper()]
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
        raise FormulaError("Unsupported expression.")

    with np.errstate(divide="ignore", invalid="ignore"):
        out = ev(parsed.tree)
    if not isinstance(out, pd.Series):
        raise FormulaError("The formula must involve at least one stock measure.")
    return out.replace([np.inf, -np.inf], np.nan)


SIGMA_KINDS = ("P", "V", "PW", "VW")


def is_sigma_compatible(parsed: ParsedFormula) -> bool:
    """True when the formula uses only items Sigma Scanner itself offers."""
    return all(n[0] in SIGMA_KINDS for n in parsed.needs)


def longest_lookback_months(parsed: ParsedFormula) -> float:
    out = 0.0
    for n in parsed.needs:
        k = n[0]
        if k in ("P", "V"):
            out = max(out, n[1])
        elif k in ("PW", "VW"):
            out = max(out, n[1] / 4.0)
        elif k == "PS":
            out = max(out, n[1])
        elif k in ("FIP", "H52"):
            out = max(out, 12)
    return out


def describe(parsed: ParsedFormula) -> list:
    """Plain-English bullet list of what a formula uses (for the help pop-up)."""
    lines = []
    for n in parsed.needs:
        k = n[0]
        if k == "P":
            lines.append(f"**{n[1]} Month Performance**: price change over {n[1]} months ({n[1] * 30} trading days). Higher = stronger.")
        elif k == "V":
            lines.append(f"**{n[1]} Month Volatility**: how bumpy the daily price changes were over {n[1]} months. Higher = bumpier.")
        elif k == "PW":
            lines.append(f"**{n[1]} Week Performance**: price change over {n[1]} week(s) ({n[1] * 5} trading days).")
        elif k == "VW":
            lines.append(f"**{n[1]} Week Volatility**: bumpiness over {n[1]} week(s).")
        elif k == "PS":
            lines.append(f"**{n[1]} Month Performance Skip {n[2]} Month**: price change from {n[1]} months ago to {n[2]} month(s) ago; the latest {n[2]} month(s) are ignored.")
        elif k == "FIP":
            lines.append("**FIP**: smoothness of the last 12 months (about -1 to +1). More NEGATIVE = smoother climb.")
        elif k == "H52":
            lines.append("**52 Week High**: today's price divided by the highest close of the last 252 trading days (1.00 = at the high).")
    return lines
