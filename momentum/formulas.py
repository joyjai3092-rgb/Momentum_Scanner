"""The formula library: every ranking formula, with plain-English help text.

Each formula is either
  kind="sigma"  - written in Sigma Scanner syntax (could be pasted into Sigma's console), or
  kind="native" - needs extra maths (skip-month, z-scores, ...) so it only runs inside this app.

Nothing here is investment advice. "evidence" lists ONLY what the project documents say.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- short names for the source documents ---------------------------------
SRC = {
    "JT1993": "Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]",
    "JT2011": "Jegadeesh & Titman (2011), Momentum, SSRN 1919226 [project doc]",
    "GV": "Gray & Vogel, Quantitative Momentum: A Practitioner's Guide [project doc]",
    "NSE": "NSE Indices methodology (Nifty200 Momentum 30 / Nifty500 Momentum 50), June 2026 [project doc]",
    "SIGMA_SCORE": "Sigma Scanner - Stock Scoring Usage Guide [project doc]",
    "SIGMA_BT": "Sigma Scanner - Backtest User Guide [project doc]",
    "SIGMA_BTP": "Backtesting Prompt (formula examples) [project doc]",
    "GH2004": "George & Hwang (2004), The 52-Week High and Momentum Investing, Journal of Finance 59 (cited in JT2011 and Gray & Vogel)",
}

SIGMA_MONTH_NOTE = "Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days."
RESEARCH_MONTH_NOTE = "Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document)."


@dataclass(frozen=True)
class Formula:
    id: str
    name: str
    category: str
    kind: str                       # "sigma" or "native"
    expr: str | None                # Sigma-syntax text (kind="sigma")
    native_key: str | None          # key of scorer in scoring.py (kind="native")
    one_liner: str
    explanation: str
    purpose: str
    how_to_read: str
    strengths: str
    limits: str
    evidence: tuple
    sources: tuple
    month_note: str
    sigma_text: str | None          # what to type into Sigma Scanner (None = not possible)
    sigma_note: str = ""
    origin: str = "documented"      # documented / combination


def _f(**kw) -> Formula:
    return Formula(**kw)


LIBRARY: tuple = (
    # ------------------------------------------------------------------ classic returns
    _f(
        id="F01", name="3-Month Return", category="1. Classic returns (Jegadeesh-Titman)",
        kind="sigma", expr="3 Month Performance", native_key=None,
        one_liner="How much the price rose in the last 3 months.",
        explanation="Compares today's closing price with the close 90 trading days ago. The bigger the % rise, the higher the rank.",
        purpose="Finds stocks that have only recently started to trend.",
        how_to_read="Rank 1 = the biggest 3-month gainer in your list.",
        strengths="Reacts quickly to new trends. Sigma's table lists it as 'Initial Stage 2, High CAGR'.",
        limits="Noisy: a few lucky weeks can put a stock on top. Sigma's table lists 'Medium risk, Noise'.",
        evidence=(
            "Sigma guide table: 3M Performance = Initial Stage 2 / High CAGR; Medium risk / Noise.",
            "1993 paper (US stocks 1965-89, Table I): 3-month ranking earned about 0.3%-0.8% per month (buy minus sell) vs 0.7%-1.5% for 12-month ranking.",
        ),
        sources=(SRC["SIGMA_SCORE"], SRC["JT1993"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="3 Month Performance",
    ),
    _f(
        id="F02", name="6-Month Return", category="1. Classic returns (Jegadeesh-Titman)",
        kind="sigma", expr="6 Month Performance", native_key=None,
        one_liner="How much the price rose in the last 6 months.",
        explanation="Compares today's close with the close 180 trading days ago. This is the 'textbook' momentum measure: buy what has risen most over the past half-year.",
        purpose="A middle-of-the-road momentum signal - not too slow, not too noisy.",
        how_to_read="Rank 1 = the biggest 6-month gainer.",
        strengths="The most studied case in the 1993 paper. Sigma's table lists 'Medium CAGR, Stable returns'.",
        limits="Ignores how bumpy the ride was; Sigma's table lists 'Medium to High risk'.",
        evidence=(
            "Sigma guide table: 6M Performance = Medium CAGR, Stable returns; Medium to High risk.",
            "1993 paper: the 6-month ranking / 6-month holding strategy earned a compounded excess return of 12.01% per year (US, 1965-89).",
        ),
        sources=(SRC["SIGMA_SCORE"], SRC["JT1993"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="6 Month Performance",
    ),
    _f(
        id="F03", name="9-Month Return", category="1. Classic returns (Jegadeesh-Titman)",
        kind="sigma", expr="9 Month Performance", native_key=None,
        one_liner="How much the price rose in the last 9 months.",
        explanation="Compares today's close with the close 270 trading days ago.",
        purpose="A slower signal that favours stocks with a sustained climb.",
        how_to_read="Rank 1 = the biggest 9-month gainer.",
        strengths="Less affected by short bursts. Sigma's table lists 'Stable returns'.",
        limits="Slow to notice new leaders; Sigma's table lists 'High risk'.",
        evidence=(
            "Sigma guide table: 9M Performance = Stable returns; High risk.",
            "1993 paper Table I: 9-month ranking earned about 0.8%-1.35% per month (buy minus sell).",
        ),
        sources=(SRC["SIGMA_SCORE"], SRC["JT1993"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="9 Month Performance",
    ),
    _f(
        id="F04", name="12-Month Return", category="1. Classic returns (Jegadeesh-Titman)",
        kind="sigma", expr="12 Month Performance", native_key=None,
        one_liner="How much the price rose in the last 12 months.",
        explanation="Compares today's close with the close 360 trading days ago (Sigma's 12 months).",
        purpose="The longest standard look-back: picks long-term leaders.",
        how_to_read="Rank 1 = the biggest 12-month gainer.",
        strengths="Strongest result in the 1993 paper's table (12-month ranking, 3-month hold).",
        limits="Includes the latest month, which research says tends to partly reverse (see F06 for the fix). Sigma's table lists 'High risk'.",
        evidence=(
            "Sigma guide table: 12M Performance = Stable returns; High risk.",
            "1993 paper: best strategy ranked on 12 months and held 3 months: 1.31% per month (1.49% when a week is skipped).",
        ),
        sources=(SRC["SIGMA_SCORE"], SRC["JT1993"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="12 Month Performance",
    ),
    # ------------------------------------------------------------------ skip-month
    _f(
        id="F05", name="6-1 Return (skip latest month)", category="2. Skip-month returns",
        kind="native", expr=None, native_key="skip_6_1",
        one_liner="6-month return, ignoring the most recent month.",
        explanation="Measures the price change from 6 months ago to 1 month ago (126 to 21 trading days back). The last month is deliberately left out.",
        purpose="Avoids the short-term 'bounce-back' effect: stocks that jumped in the last month often give a little back.",
        how_to_read="Rank 1 = the biggest gain between 6 months ago and 1 month ago.",
        strengths="Research found that skipping a short gap between ranking and buying gave higher and more significant returns.",
        limits="Not available as a single Sigma Scanner item. Can lag when a stock has only just started to run.",
        evidence=(
            "1993 paper: strategies that skip a week earned more (e.g. 12-month ranking: 1.49% vs 1.31% per month).",
            "2011 review: uses a 'skip a month' version to avoid the 1-month reversal reported by Jegadeesh (1990).",
        ),
        sources=(SRC["JT1993"], SRC["JT2011"]), month_note=RESEARCH_MONTH_NOTE,
        sigma_text=None,
        sigma_note="Sigma has no 'skip' item. An approximation is '6 Month Performance - 1 Month Performance' but it is NOT identical.",
    ),
    _f(
        id="F06", name="12-1 Return (Gray-Vogel 'generic momentum')", category="2. Skip-month returns",
        kind="native", expr=None, native_key="skip_12_1",
        one_liner="12-month return, ignoring the most recent month.",
        explanation="Measures the price change from 12 months ago to 1 month ago (252 to 21 trading days back).",
        purpose="The standard 'generic momentum' used in academic work and the starting point of the Quantitative Momentum method.",
        how_to_read="Rank 1 = strongest 12-1 return.",
        strengths="Well documented and widely used; avoids the last-month bounce-back.",
        limits="Only looks at the total change, not how smooth the climb was (see F19 for that).",
        evidence=(
            "Gray & Vogel: generic momentum = past 12-month returns, skipping the most recent month.",
        ),
        sources=(SRC["GV"], SRC["JT2011"]), month_note=RESEARCH_MONTH_NOTE,
        sigma_text=None,
        sigma_note="Approximation for Sigma: '12 Month Performance - 1 Month Performance' (not identical, and Sigma months are 30 days).",
    ),
    # ------------------------------------------------------------------ risk-adjusted
    _f(
        id="F07", name="6M Return / 6M Volatility ('Sharpe returns')", category="3. Risk-adjusted (return per unit of ups and downs)",
        kind="sigma", expr="6 Month Performance / 6 Month Volatility", native_key=None,
        one_liner="6-month gain divided by how bumpy the ride was.",
        explanation="Two stocks may both rise 40%. The one with calmer day-to-day swings scores higher.",
        purpose="Prefers smooth winners over jumpy winners.",
        how_to_read="Higher score = more gain for each unit of volatility.",
        strengths="Sigma's own guide uses this as its example and calls it 'Sharpe returns'.",
        limits="Very calm stocks with small gains can score well; volatility is measured from the same price history, not predicted.",
        evidence=("Sigma Backtest Guide: '6 Month Performance / 6 Month Volatility - we call it Sharpe returns'.",),
        sources=(SRC["SIGMA_BT"], SRC["SIGMA_SCORE"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="6 Month Performance / 6 Month Volatility",
    ),
    _f(
        id="F08", name="12M Return / 12M Volatility", category="3. Risk-adjusted (return per unit of ups and downs)",
        kind="sigma", expr="12 Month Performance / 12 Month Volatility", native_key=None,
        one_liner="12-month gain divided by 12-month bumpiness.",
        explanation="Same idea as F07 over a longer window. Close in spirit to NSE's 'Momentum Ratio' (return divided by 1-year volatility), but without the later z-score step.",
        purpose="Long-term leaders that got there smoothly.",
        how_to_read="Higher score = better return per unit of risk.",
        strengths="Mirrors the building block NSE uses for its Momentum indices.",
        limits="Slow to react; includes the latest month.",
        evidence=("NSE: Momentum Ratio = price return / annualised standard deviation of 1-year daily returns.",),
        sources=(SRC["NSE"], SRC["SIGMA_SCORE"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="12 Month Performance / 12 Month Volatility",
    ),
    _f(
        id="F09", name="6M Return / 3M Volatility", category="3. Risk-adjusted (return per unit of ups and downs)",
        kind="sigma", expr="6 Month Performance / 3 Month Volatility", native_key=None,
        one_liner="6-month gain divided by the last 3 months' bumpiness.",
        explanation="Rewards a 6-month winner whose RECENT behaviour is calm.",
        purpose="Avoid winners that are currently turning wild.",
        how_to_read="Higher score = strong 6-month gain with recent calm.",
        strengths="Named as a try-it example in Sigma's Backtest Guide.",
        limits="Mixing two window lengths makes it a little harder to interpret.",
        evidence=("Sigma Backtest Guide: 'Also, you can try 6 Month Performance / 3 Month Volatility'.",),
        sources=(SRC["SIGMA_BT"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="6 Month Performance / 3 Month Volatility",
    ),
    _f(
        id="F10", name="12-1 Return / 12M Volatility", category="3. Risk-adjusted (return per unit of ups and downs)",
        kind="native", expr=None, native_key="skip_12_1_over_vol",
        one_liner="Skip-month 12-1 return divided by 1-year volatility.",
        explanation="Combines two documented ideas: ignore the latest month (Gray-Vogel / Jegadeesh-Titman) and divide by volatility (NSE / Sigma).",
        purpose="Smooth long-term leaders without the last-month bounce-back.",
        how_to_read="Higher score = better skip-month return per unit of risk.",
        strengths="Joins two well-known ideas in one number.",
        limits="This exact combination is NOT in the project documents - it is my construction, so treat it as an experiment.",
        evidence=("Components are documented; the combination itself is not.",),
        sources=(SRC["GV"], SRC["NSE"]), month_note=RESEARCH_MONTH_NOTE,
        sigma_text=None, sigma_note="Not possible in Sigma Scanner.", origin="combination",
    ),
    # ------------------------------------------------------------------ Sigma blends
    _f(
        id="F11", name="(6M + 3M + 1M Returns) / 3M Volatility", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="(6 Month Performance + 3 Month Performance + 1 Month Performance) / 3 Month Volatility", native_key=None,
        one_liner="Adds the 6-, 3- and 1-month gains, then divides by 3-month bumpiness.",
        explanation="A stock must be doing well over the long, medium AND short window to score high; calm recent trading helps.",
        purpose="Balanced momentum with volatility control - this is the formula in Sigma's own 'Beginner Stable' example.",
        how_to_read="Higher score = broad strength across three windows with low recent volatility.",
        strengths="Easy to explain; uses three time frames so no single window decides.",
        limits="Includes the latest month (noisy). Whether it works in India must be checked with the backtest.",
        evidence=("Sigma Backtesting Prompt: used in the Beginner Stable Strategy example (formula only - no performance claim).",),
        sources=(SRC["SIGMA_BTP"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="(6 Month Performance + 3 Month Performance + 1 Month Performance) / 3 Month Volatility",
    ),
    _f(
        id="F12", name="(50% 9M + 30% 6M + 20% 3M) / 1M Volatility", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="((50% * 9 Month Performance) + (30% * 6 Month Performance) + (20% * 3 Month Performance)) / 1 Month Volatility", native_key=None,
        one_liner="Weighted blend of 9/6/3-month gains, divided by the last month's bumpiness.",
        explanation="Gives most weight to the 9-month gain, less to 6 and 3 months. Dividing by 1-month volatility favours stocks that are calm right now.",
        purpose="Long-term strength with a recent-calm filter.",
        how_to_read="Higher score = strong multi-month climb and quiet last month.",
        strengths="Weights make the priorities explicit.",
        limits="One month of volatility is a short, noisy measurement.",
        evidence=("Sigma Backtesting Prompt: formula example (no performance claim).",),
        sources=(SRC["SIGMA_BTP"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="((50% * 9 Month Performance) + (30% * 6 Month Performance) + (20% * 3 Month Performance)) / 1 Month Volatility",
    ),
    _f(
        id="F13", name="(12M + 6M Returns) / 6M Volatility", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="(12 Month Performance + 6 Month Performance) / 6 Month Volatility", native_key=None,
        one_liner="Adds the 12- and 6-month gains, divided by 6-month bumpiness.",
        explanation="Long-term leaders that are also strong lately, with a smoothness check.",
        purpose="Lower-turnover, steadier selection.",
        how_to_read="Higher score = strong long and medium gains with controlled volatility.",
        strengths="Slow-moving, so the list changes less from one rebalance to the next.",
        limits="Slow to pick up new leaders.",
        evidence=("Sigma Backtesting Prompt: formula example (no performance claim).",),
        sources=(SRC["SIGMA_BTP"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="(12 Month Performance + 6 Month Performance) / 6 Month Volatility",
    ),
    _f(
        id="F14", name="(70% 6M + 30% 1M) / 1M Volatility", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility", native_key=None,
        one_liner="6-month strength plus a boost for the latest month, divided by last-month bumpiness.",
        explanation="Leans on recent behaviour: 30% weight on the last month.",
        purpose="Faster rotation into stocks that are accelerating.",
        how_to_read="Higher score = strong 6 months plus recent acceleration, with a calm last month.",
        strengths="Captures trend acceleration early.",
        limits="Heavy use of the latest month - the research warns the latest month can reverse. Likely more trading.",
        evidence=("Sigma Backtesting Prompt: formula example (no performance claim).",),
        sources=(SRC["SIGMA_BTP"], SRC["JT1993"]), month_note=SIGMA_MONTH_NOTE,
        sigma_text="((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility",
    ),
    _f(
        id="F15", name="70% 6M + 20% 3M + 10% 1M Returns", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="(70% * 6 Month Performance) + (20% * 3 Month Performance) + (10% * 1 Month Performance)", native_key=None,
        one_liner="Weighted blend of 6/3/1-month gains (no volatility step).",
        explanation="Priority to the 6-month gain (70%), then 3 months (20%), then 1 month (10%).",
        purpose="Pure return blend where older performance matters most.",
        how_to_read="Higher score = better weighted gain.",
        strengths="Simple; straight from Sigma's usage guide.",
        limits="Ignores volatility entirely.",
        evidence=("Sigma Scoring Usage Guide: weightage example.",),
        sources=(SRC["SIGMA_SCORE"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="(70% * 6 Month Performance) + (20% * 3 Month Performance) + (10% * 1 Month Performance)",
    ),
    _f(
        id="F16", name="(80% 9M + 20% 6M) / 1M Volatility", category="4. Multi-timeframe blends (Sigma examples)",
        kind="sigma", expr="((80% * 9 Month Performance) + (20% * 6 Month Performance)) / 1 Month Volatility", native_key=None,
        one_liner="Mostly 9-month gain, a bit of 6-month, divided by last-month bumpiness.",
        explanation="Long-term emphasis (80% on 9 months) with a recent-calm filter.",
        purpose="Long-term leaders that are currently quiet.",
        how_to_read="Higher score = strong long climb and low volatility in the last month.",
        strengths="Straight from Sigma's usage guide.",
        limits="One month of volatility is short and noisy.",
        evidence=("Sigma Scoring Usage Guide: weightage example.",),
        sources=(SRC["SIGMA_SCORE"],), month_note=SIGMA_MONTH_NOTE,
        sigma_text="((80% * 9 Month Performance) + (20% * 6 Month Performance)) / 1 Month Volatility",
    ),
    # ------------------------------------------------------------------ research methods
    _f(
        id="F17", name="NSE Normalized Momentum Score", category="5. Index-methodology & research methods",
        kind="native", expr=None, native_key="nse_normalized",
        one_liner="The score NSE uses to build its Nifty Momentum indices.",
        explanation=(
            "Step 1: for each stock, the 12-month and 6-month price returns (measured to the END of last month, as NSE does) are each divided by the 1-year volatility. "
            "Step 2: each result is converted to a z-score (how far above or below the average of your list). "
            "Step 3: the two z-scores are averaged 50/50. "
            "Step 4: converted to a positive score: 1 + z if z >= 0, otherwise 1 / (1 - z)."
        ),
        purpose="A professional, widely followed way of ranking momentum that rewards risk-adjusted strength over both 6 and 12 months.",
        how_to_read="Higher score = stronger risk-adjusted momentum relative to the other stocks in your list. A score above 1 means better than average.",
        strengths="Used by NSE for Nifty200 Momentum 30, Nifty Midcap150 Momentum 50 and Nifty500 Momentum 50.",
        limits=(
            "Because z-scores compare stocks WITHIN your list, results depend on which stocks are uploaded. "
            "NSE also applies filters this app cannot (F&O availability, circuit-hit history, promoter pledge, turnover) and rebalances only in June and December."
        ),
        evidence=("NSE methodology: Momentum Ratio, Z-scores, 50%/50% weighting and the Normalized Momentum Score formula.",),
        sources=(SRC["NSE"],), month_note=RESEARCH_MONTH_NOTE + " Volatility = 1-year annualised std-dev of daily log returns.",
        sigma_text=None, sigma_note="Not possible in Sigma Scanner (needs z-scores across the universe).",
    ),
    _f(
        id="F18", name="52-Week-High Proximity", category="5. Index-methodology & research methods",
        kind="native", expr=None, native_key="high52",
        one_liner="How close the price is to its highest close of the last year.",
        explanation="Score = today's close / highest close in the last 252 trading days. 100% means the stock is at its 52-week high.",
        purpose="Finds stocks near their yearly peak. Research says these tend to keep outperforming.",
        how_to_read="Rank 1 = closest to (or at) its 52-week high.",
        strengths="Very simple. Gray & Vogel: 52-week-high stocks greatly outperform 52-week-low stocks.",
        limits="Uses closing prices only. Says nothing about how fast the stock climbed.",
        evidence=(
            "Gray & Vogel: '52-week-high stocks greatly outperform 52-week-low stocks'.",
            "2011 review: George & Hwang (2004) show stocks perform well after hitting 52-week highs.",
        ),
        sources=(SRC["GV"], SRC["JT2011"], SRC["GH2004"]), month_note=RESEARCH_MONTH_NOTE,
        sigma_text=None, sigma_note="Not available in Sigma Scanner.",
    ),
    _f(
        id="F19", name="Quantitative Momentum (12-1 + Frog-in-the-Pan)", category="5. Index-methodology & research methods",
        kind="native", expr=None, native_key="quant_momentum",
        one_liner="Pick the strongest 12-1 stocks, then prefer the SMOOTHEST climbers.",
        explanation=(
            "Step 1: rank all stocks by 12-1 return and keep the top 10%. "
            "Step 2: among those, count the share of down days and up days over the last 252 days "
            "(FIP = sign of past return x [% down days - % up days]). "
            "Step 3: the more negative the FIP, the smoother the climb, the better the rank. "
            "Stocks outside the top 10% are ranked after them by 12-1 return."
        ),
        purpose="Avoid 'lottery-like' stocks whose gains came from a few big jumps; prefer steady, gradual winners.",
        how_to_read="Rank 1 = a top-decile momentum stock with the smoothest path.",
        strengths="Directly follows the 5-step process of the Quantitative Momentum book (step 4, seasonal timing, is not applied).",
        limits="With a short list (e.g. 30 stocks) the top 10% is only 3 stocks, so the smoothness step has little to choose from. Works best on large universes (Nifty 500).",
        evidence=(
            "Gray & Vogel: top 10% generic momentum, then FIP (lower is better), then ~50 stocks equal weight.",
            "Gray & Vogel: 'Momentum strategies that focus on the path-dependency of momentum generate a much stronger momentum effect' (frog-in-the-pan evidence).",
        ),
        sources=(SRC["GV"],), month_note=RESEARCH_MONTH_NOTE,
        sigma_text=None, sigma_note="Not possible in Sigma Scanner.",
    ),
)

_BY_ID = {f.id: f for f in LIBRARY}
CUSTOM_ID = "CUSTOM"
USER_CATEGORY = "6. My formulas (saved by you)"
_USER: dict = {}                      # formulas saved by the user (filled by myformulas.load_into_registry)


def register_user_formulas(items) -> None:
    """Replace the saved-by-you formulas (called every page run; the list is tiny)."""
    _USER.clear()
    for f in items:
        _USER[f.id] = f


def user_formulas() -> tuple:
    return tuple(_USER.values())


def all_formulas() -> tuple:
    """Built-in library followed by the formulas the user saved."""
    return tuple(LIBRARY) + user_formulas()


def get_formula(formula_id: str) -> Formula:
    if formula_id in _BY_ID:
        return _BY_ID[formula_id]
    return _USER[formula_id]


def categories() -> list:
    seen = []
    for f in all_formulas():
        if f.category not in seen:
            seen.append(f.category)
    return seen


def label(f: Formula) -> str:
    return f"{f.id} - {f.name}"


def help_markdown(f: Formula) -> str:
    """The text shown in the (?) help pop-up."""
    lines = [
        f"### {f.id} - {f.name}",
        f"**In one line:** {f.one_liner}",
        "",
        f"**How it works:** {f.explanation}",
        "",
        f"**Purpose:** {f.purpose}",
        "",
        f"**How to read it:** {f.how_to_read}",
        "",
        f"**Strengths:** {f.strengths}",
        "",
        f"**Watch out for:** {f.limits}",
        "",
        "**What the documents say:**",
    ]
    lines += [f"- {e}" for e in f.evidence]
    lines += ["", f"**Month length used:** {f.month_note}", ""]
    if f.sigma_text:
        lines += ["**Type this into Sigma Scanner:**", f"`{f.sigma_text}`"]
    else:
        lines += [f"**Sigma Scanner:** {f.sigma_note}"]
    if f.origin == "combination":
        lines += ["", "_This combination is my own construction from documented parts - not a published formula._"]
    lines += ["", "**Sources:**"] + [f"- {s}" for s in f.sources]
    lines += ["", "_Educational tool - not investment advice._"]
    return "\n".join(lines)


RULES_MARKDOWN = """### Formula rules (how to write your own formula)
A formula is a list of **items** joined by `+ - * /` and brackets `( )`. Every stock gets one number (its **score**). The **highest score = rank 1**. Only the order matters, not the size of the score.

**Items you can use**

| Item | Meaning | In Sigma Scanner? |
|---|---|---|
| `N Month Performance` (N = 1 to 12) | Price change over N months. 1 month = 30 trading days. | Yes |
| `N Month Volatility` (N = 1 to 12) | How bumpy daily price changes were over N months. | Yes |
| `N Week Performance` / `N Week Volatility` (N = 1 to 4) | Same, for N weeks (5 trading days each). | Yes (Scoring Prompt) |
| `N Month Performance Skip M Month` | Price change from N months ago to M months ago; the latest M months are ignored. M must be smaller than N. | No - app only |
| `FIP` | Frog-in-the-Pan smoothness of the last 12 months, about -1 to +1. **More negative = smoother = better.** | No - app only |
| `52 Week High` | Today's price / highest close of the last 252 days. 1.00 = at the 52-week high. | No - app only |

**Numbers and weights:** `2`, `0.5`, `70%` (= 0.7). `x` and the multiply/divide signs are accepted too.

**The rules**
1. Use at least one item. Nothing else is allowed: no other words, no powers, no functions.
2. Brackets must match.
3. Higher score = better. Performance, `52 Week High` rise when a stock is strong. **Volatility and FIP are better when LOW**, so divide by Volatility (`Performance / Volatility`) or subtract it.
4. If a stock is missing a price, or a division by zero happens, that stock is simply not ranked.
5. A formula needs history as long as its longest item (e.g. 12 months). Younger stocks are skipped.
6. FIP is a small number (about -1 to +1) while performance can be 0.5 or more, so when you mix them choose weights carefully.
7. Names must be unique. You can save up to 50 formulas.

**Examples**
- `6 Month Performance / 6 Month Volatility`
- `((70% * 6 Month Performance) + (30% * 3 Month Performance)) / 1 Month Volatility`
- `(12 Month Performance Skip 1 Month) / 12 Month Volatility`
- `52 Week High * 6 Month Performance`

**Good practice:** test a new formula in the Backtest over more than one period before trusting it. Picking the formula with the best past result alone is "curve fitting".
"""

CUSTOM_HELP = RULES_MARKDOWN
