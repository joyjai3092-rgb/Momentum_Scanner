"""The 5 ready-made backtest strategies, following the structure of the Backtesting Prompt.

Strategy 1 is copied from the prompt's own example. Strategies 2-5 use formula examples and
guidance from the Sigma guides (e.g. 'tight exit rank for high-risk', 'higher exit rank for weekly'),
but the exact numbers are STARTING POINTS chosen by me - to be reviewed and backtested, not advice.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    investor: str
    universe_hint: str
    n_stocks: int
    frequency: str
    rebalance_day: int         # Monthly: date 1-30 ; Weekly: 0=Mon..4=Fri
    exit_rank: int
    formula_id: str
    regime: str = "SUPERTREND"
    regime_params: tuple = (1, 2.5)
    regime_action: str = "Half Portfolio"
    behaviour: str = ""
    risk: str = ""
    basis: str = ""


PRESETS: tuple = (
    Preset("1. Beginner Stable", "Moderate beginner", "NIFTY 500", 15, "Monthly", 15, 45, "F11",
           behaviour="Stable momentum with controlled volatility and lower churn.", risk="Medium",
           basis="Exactly the example given in the Backtesting Prompt."),
    Preset("2. Balanced Momentum", "Moderate", "NIFTY 500", 20, "Monthly", 15, 50, "F12",
           behaviour="Long-term strength with a recent-calm filter.", risk="Medium",
           basis="Formula from the prompt's examples; exit rank 50 follows the guide's 'moderate: 50-60'."),
    Preset("3. Aggressive High CAGR", "Aggressive", "NIFTY 500 (or mid/small cap)", 20, "Monthly", 15, 30, "F14",
           behaviour="High churn aggressive momentum; fast trend capture.", risk="High",
           basis="Formula from the prompt's examples; 20 stocks / exit rank 30 is the guide's own 'high-risk' example."),
    Preset("4. Low Drawdown", "Conservative", "NIFTY 500", 25, "Monthly", 15, 60, "F13",
           behaviour="Slower, steadier selection; lower trading.", risk="Low to Medium",
           basis="Formula from the prompt's examples; more stocks and a wide exit rank (60) to cut trading."),
    Preset("5. Fast Rotation", "Aggressive, active", "NIFTY 500", 20, "Weekly", 4, 60, "F14",
           behaviour="Fast trend capture with weekly checks.", risk="High",
           basis="Weekly on Friday; the guide advises a higher exit rank for weekly so trades stay manageable."),
)
