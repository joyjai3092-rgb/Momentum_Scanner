"""Reads Sigma-Scanner-style scoring formulas, e.g.

    ((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility

Only these building blocks are allowed (same as the Sigma guides):
    * "N Month Performance" / "N Month Volatility"   (N = 1..12; "N Year ..." also accepted)
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
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
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


def parse_formula(text: str) -> ParsedFormula:
    """Turn a Sigma-style formula string into a safe, evaluable tree."""
    if not text or not text.strip():
        raise FormulaError("The formula is empty.")
    raw = text.strip()
    s = raw.replace("×", "*").replace("÷", "/").replace("−", "-")
    s = re.sub(r"(?<=[\d\)\s])x(?=[\s\(\d])", "*", s)          # "70% x 6 Month ..." -> *
    s = _METRIC_RE.sub(_metric_sub, s)
    s = _PERCENT_RE.sub(lambda m: f"({m.group(1)}/100)", s)
    s_check = s.upper()
    if not _ALLOWED_AFTER.match(s_check):
        bad = sorted(set(re.sub(r"[0-9A-Z_\s\.\+\-\*/\(\)]", "", s_check)))
        raise FormulaError(
            "Only 'N Month Performance', 'N Month Volatility', numbers, % and + - * / ( ) are "
            f"allowed. Could not understand: {' '.join(bad) if bad else raw}"
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
            m = re.fullmatch(r"([PV])(\d{1,2})", node.id.upper())
            if not m:
                raise FormulaError(
                    f"'{node.id}' is not a recognised item. Use e.g. '6 Month Performance'."
                )
            needs.add((m.group(1), int(m.group(2))))
    if not needs:
        raise FormulaError("The formula must use at least one Performance or Volatility item.")
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
