import streamlit as st

from momentum import formulas as fml
from momentum import ui

st.set_page_config(page_title="Learn Momentum - Momentum Scanner", page_icon="📚", layout="wide")
ui.sidebar()
st.title("📚 Learn Momentum Investing")
st.caption("Plain-English guide. Facts marked [doc] come from the documents in your project; "
           "[external] means an outside source I looked up.")

with st.expander("1. What is momentum investing?", expanded=True):
    st.markdown(
        """
- **Idea:** stocks that have risen the most recently tend to keep rising for a while; stocks that have fallen tend to keep falling. Buy the winners.
- **First big evidence** [doc: Jegadeesh & Titman 1993]: US stocks that did best over the past **3 to 12 months** kept outperforming over the next **3 to 12 months**. Their most-studied case (rank on 6 months, hold 6 months) earned a compounded excess return of **12.01% a year** (1965-89).
- **It is a relative ranking.** You do not predict the market. You rank stocks against each other and hold the top ones.
- **Why might it work?** [doc: Jegadeesh & Titman 2011] The evidence points to investors reacting **slowly** to company news (the price keeps adjusting for months), or following winners until prices overshoot. Researchers still disagree on the cause.
        """
    )

with st.expander("2. The risks - please read"):
    st.markdown(
        """
- **Momentum can crash.** [doc: JT 2011] One momentum strategy lost **36.5% in 2009**, after the market bounced sharply from a crash. The 1930s were also bad. Losses tend to come when the market turns suddenly.
- **Gains fade.** [doc: JT 1993] The 6-month winners gained about 9.5% over the next 12 months but gave back more than half of it over the following 24 months.
- **Trading costs are real.** [doc: JT 1993] After assuming 0.5% per trade, the strategy still earned a positive risk-adjusted return (about 9.3% a year, US 1965-89). [doc: Gray & Vogel] argue costs are manageable for normal investors. Your own costs in India may differ - set them on the Backtest page.
- **Long quiet spells of under-performance happen** [doc: Gray & Vogel: "the blessing (and curse) of long periods of relative outperformance (and underperformance)"].
- **January (US only):** [doc: JT 1993] the US strategy lost about 7% on average in January but gained in other months. This was a US finding; this app does not apply any calendar rule to India.
- **This app's back-tests are optimistic** - see section 8.
        """
    )

with st.expander("3. Key building blocks (glossary)"):
    st.markdown(
        """
| Word | Meaning |
|---|---|
| **Performance (return)** | How much the price rose over a period, e.g. 6 months. |
| **Volatility** | How much the price jumps around day to day. Low = smooth, high = bumpy. |
| **Score** | The number a formula gives each stock. Highest score = rank 1. |
| **Rank** | Position after sorting by score (1 = best). |
| **Rebalance** | The day you re-check the ranking and trade (weekly or monthly). |
| **Exit rank** | You sell a stock only when its rank drops *below* this number. Bigger number = fewer trades. |
| **Skip-month** | Ignoring the most recent month, because very recent winners often bounce back a little. |
| **Regime filter** | A market-health check that cuts or removes your stock holdings in weak markets. |
| **Drawdown** | The fall from a previous peak. Max drawdown = the worst such fall. |
| **CAGR** | Average yearly growth rate. |
| **Sharpe** | Return earned per unit of risk (higher is better). |
        """
    )

with st.expander("4. How Sigma Scanner scores stocks [doc: Sigma guides]"):
    st.markdown(
        """
- Uses only **closing prices**. Current-day data is available after 8 p.m. IST.
- **Building blocks:** Performance, Volatility (and Slope - not used in this app yet) for 1 to 12 months.
- **A month = 30 trading days** (so 6 months = 180 trading days).
- **Operators:** + - x ÷ and brackets; weights in %. Stocks are ranked highest score first; the size of the score does not matter.
- **Sigma's own pros and cons of each look-back:**

| Look-back | Pros (Sigma) | Cons (Sigma) |
|---|---|---|
| 12 months | Stable returns | High risk |
| 9 months | Stable returns | High risk |
| 6 months | Medium CAGR, stable returns | Medium to high risk |
| 3 months | Initial "Stage 2", high CAGR | Medium risk, noise |
| 1 month | Initial "Stage 2" | High risk, heavy noise, low CAGR |

- **Sigma backtest settings:** starting capital, universe, number of stocks, weekly/monthly rebalance and day, **exit rank** (e.g. 20 stocks and exit rank 40 = sell a stock only if it falls out of the top 40), previous/next working day for holidays, scoring formula, regime filter.
        """
    )

with st.expander("5. How NSE builds its Momentum indices [doc: NSE methodology]"):
    st.markdown(
        """
Used for Nifty200 Momentum 30, Nifty Midcap150 Momentum 50 and **Nifty500 Momentum 50**.

1. **Momentum Ratio** = price return ÷ one-year volatility (annualised standard deviation of daily returns), for 12 months and for 6 months.
2. Convert each ratio into a **z-score** (how many standard deviations above/below the average of all eligible stocks).
3. **Weighted average** = 50% x 12-month z + 50% x 6-month z.
4. **Normalized Momentum Score** = 1 + z if z is zero or more, otherwise 1 ÷ (1 - z).
5. Pick the top 30 or 50 stocks. Rebalanced **twice a year (June and December)**.
6. **Buffer to cut trading** (Nifty500 Momentum 50): an existing stock stays while it ranks in the top 75; the top 25 non-members are forced in. *(My observation: this is the same idea as Sigma's "exit rank".)*
7. NSE also screens by liquidity, circuit-limit hits and pledged shares. This app **cannot** replicate those filters, so formula F17 is "NSE-style", not an exact copy of the index.
        """
    )

with st.expander("6. Quantitative Momentum - the Gray & Vogel recipe [doc]"):
    st.markdown(
        """
1. **Universe:** liquid, mid-to-large stocks.
2. **Generic momentum:** past 12-month return **skipping the latest month**; keep the top 10%.
3. **Quality of momentum (FIP, "frog in the pan"):** among those, prefer stocks whose gain came from **many small up-days** instead of a few huge jumps.
   `FIP = sign(past return) x (% down days - % up days)` over 252 days. **More negative = smoother = better.**
   *Example from the book:* 35% down days, 64% up days -> FIP = 0.35 - 0.64 = **-0.29**.
4. **Seasonality:** the book rebalances quarterly, before quarter-end months (end of Feb, May, Aug, Nov). This app does not apply that step.
5. **Invest with conviction:** about 50 stocks, equal weight.

*Why smooth?* The book argues investors under-react to information that arrives gradually ("frog in a slowly heating pan"), and that jumpy, lottery-like stocks tend to disappoint.
        """
    )

with st.expander("7. Regime filters in plain English [doc: Sigma Backtest Guide]"):
    st.markdown(
        """
A regime filter looks at a market index (e.g. Nifty 500) on each rebalance day.

- **EMA 34/68/100/150/200:** market is weak if the index closes **below** that moving average.
- **MACD (35 70 12 / 50 100 15 / 75 150 12):** a trend-following indicator on daily data.
- **SuperTrend (1 1 / 1 2 / 1 2.5):** a trend line built on **weekly** candles (period, multiplier).
- **EQUITY:** looks at your *own* realised profit/loss on the rebalance day; only "Half Portfolio" is allowed.
- **Half Portfolio:** cut every holding by half and keep that money idle until the market looks healthy at a later rebalance.
- **Go Cash:** sell everything; start again at the next rebalance when the market is healthy.

**My assumptions where the guide is silent** (please review): MACD = weak when the MACD line is below its signal line; SuperTrend = weak when its trend is down; EQUITY = weak when this rebalance's realised loss is at least your limit (as % of portfolio value), healthy again when a later rebalance realises a profit.

*Related outside research [external]:* Barroso & Santa-Clara, "Momentum has its moments" (Journal of Financial Economics, 2015) find momentum crashes can be reduced by scaling exposure down when recent volatility is high - the same spirit as a regime filter.
        """
    )

with st.expander("8. What this app cannot do (honest limits)"):
    st.markdown(
        """
- **Survivorship bias:** you upload *today's* list. Stocks that were dropped from the index, merged or delisted in the past are missing - so back-tests look better than a real investor's experience.
- **Free data:** Yahoo Finance can have gaps, wrong adjustments, or renamed tickers. Skipped symbols are listed after each run.
- **Not an exact Sigma clone:** Sigma does not publish its exact volatility formula, trade timing or regime details. Here: volatility = standard deviation of daily returns over the window, scaled to a year; trades at the same day's close (or next day if you choose). Compare a few results with Sigma before relying on this.
- **No taxes, no liquidity or impact modelling** beyond the cost % you enter.
- **Formulas with "Slope" are not included yet** (the Sigma console has them; we agreed to add them later).
- **Weekly (1-4 week) formulas are not included:** the research here is about 3-12 months, and very short horizons tend to reverse (Jegadeesh 1990, cited in the 2011 review).
        """
    )

with st.expander("9. All 19 formulas at a glance"):
    for cat in fml.categories():
        st.markdown(f"**{cat}**")
        for f in [x for x in fml.LIBRARY if x.category == cat]:
            a, b = st.columns([9, 1])
            a.markdown(f"`{f.id}` **{f.name}** - {f.one_liner}")
            with b.popover("❓"):
                st.markdown(fml.help_markdown(f))

with st.expander("10. Sources and further reading", expanded=True):
    st.markdown(
        """
**In your project documents**
- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*, Journal of Finance 48(1), 65-91.
- Jegadeesh & Titman (2011), *Momentum*, SSRN 1919226.
- Gray & Vogel, *Quantitative Momentum: A Practitioner's Guide to Building a Momentum-Based Stock Selection System*.
- NSE Indices, *Methodology document* (Nifty200 Momentum 30, Nifty500 Momentum 50, ...), June 2026.
- GreenSigma Consultancy, *Sigma Scanner Stock Scoring Usage Guide*, *Backtest User Guide*, *Scoring Prompt*, *Backtesting Prompt*.

**External (looked up for this app)**
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*, Journal of Finance - [PDF](https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf)
- Da, Gurun & Warachka (2014), *Frog in the Pan: Continuous Information and Momentum*, Review of Financial Studies - [PDF](https://www3.nd.edu/~zda/Frog.pdf)
- George & Hwang (2004), *The 52-Week High and Momentum Investing*, Journal of Finance 59 - [summary](https://www.cxoadvisory.com/1284/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks/)
- Barroso & Santa-Clara (2015), *Momentum has its moments*, Journal of Financial Economics - [record](https://ciencia.ucp.pt/en/publications/momentum-has-its-moments/)
- Official NSE index lists and factsheets: [niftyindices.com](https://www.niftyindices.com)
        """
    )
st.caption(ui.DISCLAIMER)
