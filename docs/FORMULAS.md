# Formula reference (for review)

Generated from `momentum/formulas.py`. Review each formula and tell me: keep / change / remove.

| ID | Name | Works in Sigma Scanner? | Category |
|---|---|---|---|
| F01 | 3-Month Return | Yes | Classic returns (Jegadeesh-Titman) |
| F02 | 6-Month Return | Yes | Classic returns (Jegadeesh-Titman) |
| F03 | 9-Month Return | Yes | Classic returns (Jegadeesh-Titman) |
| F04 | 12-Month Return | Yes | Classic returns (Jegadeesh-Titman) |
| F05 | 6-1 Return (skip latest month) | No (app only) | Skip-month returns |
| F06 | 12-1 Return (Gray-Vogel 'generic momentum') | No (app only) | Skip-month returns |
| F07 | 6M Return / 6M Volatility ('Sharpe returns') | Yes | Risk-adjusted (return per unit of ups and downs) |
| F08 | 12M Return / 12M Volatility | Yes | Risk-adjusted (return per unit of ups and downs) |
| F09 | 6M Return / 3M Volatility | Yes | Risk-adjusted (return per unit of ups and downs) |
| F10 | 12-1 Return / 12M Volatility | No (app only) | Risk-adjusted (return per unit of ups and downs) |
| F11 | (6M + 3M + 1M Returns) / 3M Volatility | Yes | Multi-timeframe blends (Sigma examples) |
| F12 | (50% 9M + 30% 6M + 20% 3M) / 1M Volatility | Yes | Multi-timeframe blends (Sigma examples) |
| F13 | (12M + 6M Returns) / 6M Volatility | Yes | Multi-timeframe blends (Sigma examples) |
| F14 | (70% 6M + 30% 1M) / 1M Volatility | Yes | Multi-timeframe blends (Sigma examples) |
| F15 | 70% 6M + 20% 3M + 10% 1M Returns | Yes | Multi-timeframe blends (Sigma examples) |
| F16 | (80% 9M + 20% 6M) / 1M Volatility | Yes | Multi-timeframe blends (Sigma examples) |
| F17 | NSE Normalized Momentum Score | No (app only) | Index-methodology & research methods |
| F18 | 52-Week-High Proximity | No (app only) | Index-methodology & research methods |
| F19 | Quantitative Momentum (12-1 + Frog-in-the-Pan) | No (app only) | Index-methodology & research methods |

## F01 - 3-Month Return
**In one line:** How much the price rose in the last 3 months.

**How it works:** Compares today's closing price with the close 90 trading days ago. The bigger the % rise, the higher the rank.

**Purpose:** Finds stocks that have only recently started to trend.

**How to read it:** Rank 1 = the biggest 3-month gainer in your list.

**Strengths:** Reacts quickly to new trends. Sigma's table lists it as 'Initial Stage 2, High CAGR'.

**Watch out for:** Noisy: a few lucky weeks can put a stock on top. Sigma's table lists 'Medium risk, Noise'.

**What the documents say:**
- Sigma guide table: 3M Performance = Initial Stage 2 / High CAGR; Medium risk / Noise.
- 1993 paper (US stocks 1965-89, Table I): 3-month ranking earned about 0.3%-0.8% per month (buy minus sell) vs 0.7%-1.5% for 12-month ranking.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`3 Month Performance`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]

_Educational tool - not investment advice._

---

## F02 - 6-Month Return
**In one line:** How much the price rose in the last 6 months.

**How it works:** Compares today's close with the close 180 trading days ago. This is the 'textbook' momentum measure: buy what has risen most over the past half-year.

**Purpose:** A middle-of-the-road momentum signal - not too slow, not too noisy.

**How to read it:** Rank 1 = the biggest 6-month gainer.

**Strengths:** The most studied case in the 1993 paper. Sigma's table lists 'Medium CAGR, Stable returns'.

**Watch out for:** Ignores how bumpy the ride was; Sigma's table lists 'Medium to High risk'.

**What the documents say:**
- Sigma guide table: 6M Performance = Medium CAGR, Stable returns; Medium to High risk.
- 1993 paper: the 6-month ranking / 6-month holding strategy earned a compounded excess return of 12.01% per year (US, 1965-89).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`6 Month Performance`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]

_Educational tool - not investment advice._

---

## F03 - 9-Month Return
**In one line:** How much the price rose in the last 9 months.

**How it works:** Compares today's close with the close 270 trading days ago.

**Purpose:** A slower signal that favours stocks with a sustained climb.

**How to read it:** Rank 1 = the biggest 9-month gainer.

**Strengths:** Less affected by short bursts. Sigma's table lists 'Stable returns'.

**Watch out for:** Slow to notice new leaders; Sigma's table lists 'High risk'.

**What the documents say:**
- Sigma guide table: 9M Performance = Stable returns; High risk.
- 1993 paper Table I: 9-month ranking earned about 0.8%-1.35% per month (buy minus sell).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`9 Month Performance`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]

_Educational tool - not investment advice._

---

## F04 - 12-Month Return
**In one line:** How much the price rose in the last 12 months.

**How it works:** Compares today's close with the close 360 trading days ago (Sigma's 12 months).

**Purpose:** The longest standard look-back: picks long-term leaders.

**How to read it:** Rank 1 = the biggest 12-month gainer.

**Strengths:** Strongest result in the 1993 paper's table (12-month ranking, 3-month hold).

**Watch out for:** Includes the latest month, which research says tends to partly reverse (see F06 for the fix). Sigma's table lists 'High risk'.

**What the documents say:**
- Sigma guide table: 12M Performance = Stable returns; High risk.
- 1993 paper: best strategy ranked on 12 months and held 3 months: 1.31% per month (1.49% when a week is skipped).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`12 Month Performance`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]

_Educational tool - not investment advice._

---

## F05 - 6-1 Return (skip latest month)
**In one line:** 6-month return, ignoring the most recent month.

**How it works:** Measures the price change from 6 months ago to 1 month ago (126 to 21 trading days back). The last month is deliberately left out.

**Purpose:** Avoids the short-term 'bounce-back' effect: stocks that jumped in the last month often give a little back.

**How to read it:** Rank 1 = the biggest gain between 6 months ago and 1 month ago.

**Strengths:** Research found that skipping a short gap between ranking and buying gave higher and more significant returns.

**Watch out for:** Not available as a single Sigma Scanner item. Can lag when a stock has only just started to run.

**What the documents say:**
- 1993 paper: strategies that skip a week earned more (e.g. 12-month ranking: 1.49% vs 1.31% per month).
- 2011 review: uses a 'skip a month' version to avoid the 1-month reversal reported by Jegadeesh (1990).

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document).

**Sigma Scanner:** Sigma has no 'skip' item. An approximation is '6 Month Performance - 1 Month Performance' but it is NOT identical.

**Sources:**
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]
- Jegadeesh & Titman (2011), Momentum, SSRN 1919226 [project doc]

_Educational tool - not investment advice._

---

## F06 - 12-1 Return (Gray-Vogel 'generic momentum')
**In one line:** 12-month return, ignoring the most recent month.

**How it works:** Measures the price change from 12 months ago to 1 month ago (252 to 21 trading days back).

**Purpose:** The standard 'generic momentum' used in academic work and the starting point of the Quantitative Momentum method.

**How to read it:** Rank 1 = strongest 12-1 return.

**Strengths:** Well documented and widely used; avoids the last-month bounce-back.

**Watch out for:** Only looks at the total change, not how smooth the climb was (see F19 for that).

**What the documents say:**
- Gray & Vogel: generic momentum = past 12-month returns, skipping the most recent month.

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document).

**Sigma Scanner:** Approximation for Sigma: '12 Month Performance - 1 Month Performance' (not identical, and Sigma months are 30 days).

**Sources:**
- Gray & Vogel, Quantitative Momentum: A Practitioner's Guide [project doc]
- Jegadeesh & Titman (2011), Momentum, SSRN 1919226 [project doc]

_Educational tool - not investment advice._

---

## F07 - 6M Return / 6M Volatility ('Sharpe returns')
**In one line:** 6-month gain divided by how bumpy the ride was.

**How it works:** Two stocks may both rise 40%. The one with calmer day-to-day swings scores higher.

**Purpose:** Prefers smooth winners over jumpy winners.

**How to read it:** Higher score = more gain for each unit of volatility.

**Strengths:** Sigma's own guide uses this as its example and calls it 'Sharpe returns'.

**Watch out for:** Very calm stocks with small gains can score well; volatility is measured from the same price history, not predicted.

**What the documents say:**
- Sigma Backtest Guide: '6 Month Performance / 6 Month Volatility - we call it Sharpe returns'.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`6 Month Performance / 6 Month Volatility`

**Sources:**
- Sigma Scanner - Backtest User Guide [project doc]
- Sigma Scanner - Stock Scoring Usage Guide [project doc]

_Educational tool - not investment advice._

---

## F08 - 12M Return / 12M Volatility
**In one line:** 12-month gain divided by 12-month bumpiness.

**How it works:** Same idea as F07 over a longer window. Close in spirit to NSE's 'Momentum Ratio' (return divided by 1-year volatility), but without the later z-score step.

**Purpose:** Long-term leaders that got there smoothly.

**How to read it:** Higher score = better return per unit of risk.

**Strengths:** Mirrors the building block NSE uses for its Momentum indices.

**Watch out for:** Slow to react; includes the latest month.

**What the documents say:**
- NSE: Momentum Ratio = price return / annualised standard deviation of 1-year daily returns.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`12 Month Performance / 12 Month Volatility`

**Sources:**
- NSE Indices methodology (Nifty200 Momentum 30 / Nifty500 Momentum 50), June 2026 [project doc]
- Sigma Scanner - Stock Scoring Usage Guide [project doc]

_Educational tool - not investment advice._

---

## F09 - 6M Return / 3M Volatility
**In one line:** 6-month gain divided by the last 3 months' bumpiness.

**How it works:** Rewards a 6-month winner whose RECENT behaviour is calm.

**Purpose:** Avoid winners that are currently turning wild.

**How to read it:** Higher score = strong 6-month gain with recent calm.

**Strengths:** Named as a try-it example in Sigma's Backtest Guide.

**Watch out for:** Mixing two window lengths makes it a little harder to interpret.

**What the documents say:**
- Sigma Backtest Guide: 'Also, you can try 6 Month Performance / 3 Month Volatility'.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`6 Month Performance / 3 Month Volatility`

**Sources:**
- Sigma Scanner - Backtest User Guide [project doc]

_Educational tool - not investment advice._

---

## F10 - 12-1 Return / 12M Volatility
**In one line:** Skip-month 12-1 return divided by 1-year volatility.

**How it works:** Combines two documented ideas: ignore the latest month (Gray-Vogel / Jegadeesh-Titman) and divide by volatility (NSE / Sigma).

**Purpose:** Smooth long-term leaders without the last-month bounce-back.

**How to read it:** Higher score = better skip-month return per unit of risk.

**Strengths:** Joins two well-known ideas in one number.

**Watch out for:** This exact combination is NOT in the project documents - it is my construction, so treat it as an experiment.

**What the documents say:**
- Components are documented; the combination itself is not.

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document).

**Sigma Scanner:** Not possible in Sigma Scanner.

_This combination is my own construction from documented parts - not a published formula._

**Sources:**
- Gray & Vogel, Quantitative Momentum: A Practitioner's Guide [project doc]
- NSE Indices methodology (Nifty200 Momentum 30 / Nifty500 Momentum 50), June 2026 [project doc]

_Educational tool - not investment advice._

---

## F11 - (6M + 3M + 1M Returns) / 3M Volatility
**In one line:** Adds the 6-, 3- and 1-month gains, then divides by 3-month bumpiness.

**How it works:** A stock must be doing well over the long, medium AND short window to score high; calm recent trading helps.

**Purpose:** Balanced momentum with volatility control - this is the formula in Sigma's own 'Beginner Stable' example.

**How to read it:** Higher score = broad strength across three windows with low recent volatility.

**Strengths:** Easy to explain; uses three time frames so no single window decides.

**Watch out for:** Includes the latest month (noisy). Whether it works in India must be checked with the backtest.

**What the documents say:**
- Sigma Backtesting Prompt: used in the Beginner Stable Strategy example (formula only - no performance claim).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`(6 Month Performance + 3 Month Performance + 1 Month Performance) / 3 Month Volatility`

**Sources:**
- Backtesting Prompt (formula examples) [project doc]

_Educational tool - not investment advice._

---

## F12 - (50% 9M + 30% 6M + 20% 3M) / 1M Volatility
**In one line:** Weighted blend of 9/6/3-month gains, divided by the last month's bumpiness.

**How it works:** Gives most weight to the 9-month gain, less to 6 and 3 months. Dividing by 1-month volatility favours stocks that are calm right now.

**Purpose:** Long-term strength with a recent-calm filter.

**How to read it:** Higher score = strong multi-month climb and quiet last month.

**Strengths:** Weights make the priorities explicit.

**Watch out for:** One month of volatility is a short, noisy measurement.

**What the documents say:**
- Sigma Backtesting Prompt: formula example (no performance claim).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`((50% * 9 Month Performance) + (30% * 6 Month Performance) + (20% * 3 Month Performance)) / 1 Month Volatility`

**Sources:**
- Backtesting Prompt (formula examples) [project doc]

_Educational tool - not investment advice._

---

## F13 - (12M + 6M Returns) / 6M Volatility
**In one line:** Adds the 12- and 6-month gains, divided by 6-month bumpiness.

**How it works:** Long-term leaders that are also strong lately, with a smoothness check.

**Purpose:** Lower-turnover, steadier selection.

**How to read it:** Higher score = strong long and medium gains with controlled volatility.

**Strengths:** Slow-moving, so the list changes less from one rebalance to the next.

**Watch out for:** Slow to pick up new leaders.

**What the documents say:**
- Sigma Backtesting Prompt: formula example (no performance claim).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`(12 Month Performance + 6 Month Performance) / 6 Month Volatility`

**Sources:**
- Backtesting Prompt (formula examples) [project doc]

_Educational tool - not investment advice._

---

## F14 - (70% 6M + 30% 1M) / 1M Volatility
**In one line:** 6-month strength plus a boost for the latest month, divided by last-month bumpiness.

**How it works:** Leans on recent behaviour: 30% weight on the last month.

**Purpose:** Faster rotation into stocks that are accelerating.

**How to read it:** Higher score = strong 6 months plus recent acceleration, with a calm last month.

**Strengths:** Captures trend acceleration early.

**Watch out for:** Heavy use of the latest month - the research warns the latest month can reverse. Likely more trading.

**What the documents say:**
- Sigma Backtesting Prompt: formula example (no performance claim).

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility`

**Sources:**
- Backtesting Prompt (formula examples) [project doc]
- Jegadeesh & Titman (1993), Returns to Buying Winners and Selling Losers, Journal of Finance 48(1) [project doc]

_Educational tool - not investment advice._

---

## F15 - 70% 6M + 20% 3M + 10% 1M Returns
**In one line:** Weighted blend of 6/3/1-month gains (no volatility step).

**How it works:** Priority to the 6-month gain (70%), then 3 months (20%), then 1 month (10%).

**Purpose:** Pure return blend where older performance matters most.

**How to read it:** Higher score = better weighted gain.

**Strengths:** Simple; straight from Sigma's usage guide.

**Watch out for:** Ignores volatility entirely.

**What the documents say:**
- Sigma Scoring Usage Guide: weightage example.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`(70% * 6 Month Performance) + (20% * 3 Month Performance) + (10% * 1 Month Performance)`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]

_Educational tool - not investment advice._

---

## F16 - (80% 9M + 20% 6M) / 1M Volatility
**In one line:** Mostly 9-month gain, a bit of 6-month, divided by last-month bumpiness.

**How it works:** Long-term emphasis (80% on 9 months) with a recent-calm filter.

**Purpose:** Long-term leaders that are currently quiet.

**How to read it:** Higher score = strong long climb and low volatility in the last month.

**Strengths:** Straight from Sigma's usage guide.

**Watch out for:** One month of volatility is short and noisy.

**What the documents say:**
- Sigma Scoring Usage Guide: weightage example.

**Month length used:** Month = 30 trading days (Sigma Scanner rule), so 6 months = 180 trading days.

**Type this into Sigma Scanner:**
`((80% * 9 Month Performance) + (20% * 6 Month Performance)) / 1 Month Volatility`

**Sources:**
- Sigma Scanner - Stock Scoring Usage Guide [project doc]

_Educational tool - not investment advice._

---

## F17 - NSE Normalized Momentum Score
**In one line:** The score NSE uses to build its Nifty Momentum indices.

**How it works:** Step 1: for each stock, the 12-month and 6-month price returns (measured to the END of last month, as NSE does) are each divided by the 1-year volatility. Step 2: each result is converted to a z-score (how far above or below the average of your list). Step 3: the two z-scores are averaged 50/50. Step 4: converted to a positive score: 1 + z if z >= 0, otherwise 1 / (1 - z).

**Purpose:** A professional, widely followed way of ranking momentum that rewards risk-adjusted strength over both 6 and 12 months.

**How to read it:** Higher score = stronger risk-adjusted momentum relative to the other stocks in your list. A score above 1 means better than average.

**Strengths:** Used by NSE for Nifty200 Momentum 30, Nifty Midcap150 Momentum 50 and Nifty500 Momentum 50.

**Watch out for:** Because z-scores compare stocks WITHIN your list, results depend on which stocks are uploaded. NSE also applies filters this app cannot (F&O availability, circuit-hit history, promoter pledge, turnover) and rebalances only in June and December.

**What the documents say:**
- NSE methodology: Momentum Ratio, Z-scores, 50%/50% weighting and the Normalized Momentum Score formula.

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document). Volatility = 1-year annualised std-dev of daily log returns.

**Sigma Scanner:** Not possible in Sigma Scanner (needs z-scores across the universe).

**Sources:**
- NSE Indices methodology (Nifty200 Momentum 30 / Nifty500 Momentum 50), June 2026 [project doc]

_Educational tool - not investment advice._

---

## F18 - 52-Week-High Proximity
**In one line:** How close the price is to its highest close of the last year.

**How it works:** Score = today's close / highest close in the last 252 trading days. 100% means the stock is at its 52-week high.

**Purpose:** Finds stocks near their yearly peak. Research says these tend to keep outperforming.

**How to read it:** Rank 1 = closest to (or at) its 52-week high.

**Strengths:** Very simple. Gray & Vogel: 52-week-high stocks greatly outperform 52-week-low stocks.

**Watch out for:** Uses closing prices only. Says nothing about how fast the stock climbed.

**What the documents say:**
- Gray & Vogel: '52-week-high stocks greatly outperform 52-week-low stocks'.
- 2011 review: George & Hwang (2004) show stocks perform well after hitting 52-week highs.

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document).

**Sigma Scanner:** Not available in Sigma Scanner.

**Sources:**
- Gray & Vogel, Quantitative Momentum: A Practitioner's Guide [project doc]
- Jegadeesh & Titman (2011), Momentum, SSRN 1919226 [project doc]
- George & Hwang (2004), The 52-Week High and Momentum Investing, Journal of Finance 59 (cited in JT2011 and Gray & Vogel)

_Educational tool - not investment advice._

---

## F19 - Quantitative Momentum (12-1 + Frog-in-the-Pan)
**In one line:** Pick the strongest 12-1 stocks, then prefer the SMOOTHEST climbers.

**How it works:** Step 1: rank all stocks by 12-1 return and keep the top 10%. Step 2: among those, count the share of down days and up days over the last 252 days (FIP = sign of past return x [% down days - % up days]). Step 3: the more negative the FIP, the smoother the climb, the better the rank. Stocks outside the top 10% are ranked after them by 12-1 return.

**Purpose:** Avoid 'lottery-like' stocks whose gains came from a few big jumps; prefer steady, gradual winners.

**How to read it:** Rank 1 = a top-decile momentum stock with the smoothest path.

**Strengths:** Directly follows the 5-step process of the Quantitative Momentum book (step 4, seasonal timing, is not applied).

**Watch out for:** With a short list (e.g. 30 stocks) the top 10% is only 3 stocks, so the smoothness step has little to choose from. Works best on large universes (Nifty 500).

**What the documents say:**
- Gray & Vogel: top 10% generic momentum, then FIP (lower is better), then ~50 stocks equal weight.
- Gray & Vogel: 'Momentum strategies that focus on the path-dependency of momentum generate a much stronger momentum effect' (frog-in-the-pan evidence).

**Month length used:** Month = 21 trading days, year = 252 trading days (calendar-style, as in the papers / NSE document).

**Sigma Scanner:** Not possible in Sigma Scanner.

**Sources:**
- Gray & Vogel, Quantitative Momentum: A Practitioner's Guide [project doc]

_Educational tool - not investment advice._

---
