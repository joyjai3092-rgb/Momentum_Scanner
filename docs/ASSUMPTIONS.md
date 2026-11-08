# Assumptions and open points (please review)

Where your documents were silent I had to choose. Nothing below is investment advice.

## From the Sigma guides (followed)
- 1 month = 30 trading days for Sigma-style formulas (6 months = 180 trading days); weeks = 5 days.
- Rank from highest score to lowest; the size of the score does not matter.
- Backtest inputs: capital, number of stocks, weekly/monthly rebalance + day/date (1-30), previous/next day for holidays, exit rank, regime filters (EMA, MACD, SUPERTREND, EQUITY), Half Portfolio / Go Cash, start and end at least 3 months apart.

## My choices (change if you disagree)
| Topic | What the app does | Why / note |
|---|---|---|
| Volatility | Standard deviation of daily returns over the window, scaled to a year | Sigma does not publish its exact formula. Compare a few results with Sigma. |
| Research formulas (F05, F06, F10, F17-F19) | 1 month = 21 trading days, 1 year = 252 | Matches the papers and the NSE document. |
| NSE score (F17) | Returns measured between month-end prices (M-1 vs M-13 and M-7); z-scores are across *your uploaded list* | NSE uses its full eligible universe and extra filters (F&O, circuit hits, pledge, turnover) the app cannot copy; NSE rebalances only in June and December. |
| Quantitative Momentum (F19) | Top 10% by 12-1 return, then smoothest FIP first | The book's seasonal rebalance timing (end Feb/May/Aug/Nov) is not applied. With a 50-stock list the top 10% is only 5 stocks. |
| F10 (12-1 return / volatility) | My own combination of two documented ideas | Marked as such in its help text. |
| Trading cost | 0.2% per buy and per sell | Not from the documents. Set your own on the Backtest page. |
| Trade price | Same-day close (default) or next-day close | Next-day close is more realistic because the ranking is only known after the close. |
| Start of the backtest | The portfolio is first built on the first rebalance date on or after the start date | Cash earns nothing before that. |
| Position sizes | Equal money per slot, whole shares only; a stock too expensive for its slot is skipped | Same as Sigma's quantity calculator. |
| MACD filter | Weak when the MACD line is below its signal line | Guide does not say. |
| SuperTrend filter | Weekly candles; weak when the trend is down; a weekly candle is used only from its last trading day | Guide gives only "Period Multiplier, weekly". |
| Filter timeframe | Every market filter (EMA, MACD, SuperTrend, Sigma SuperTrend) can run on Daily, Weekly or Monthly candles. Lengths count candles (EMA 34 on Weekly = 34 weeks). Defaults: SuperTrend Weekly (Sigma guide), others Daily | A weekly/monthly signal is used only from that candle's last trading day, so there is no look-ahead. Monthly filters react slowly. |
| Filter timeframe | Every index filter (EMA, MACD, SuperTrend, Sigma SuperTrend) can run on Daily, Weekly or Monthly candles; lengths and ATR period / multiplier count candles of that size. Defaults: SuperTrend = Weekly (Sigma guide), others = Daily | A weekly / monthly signal is used only after that candle has closed, so a monthly signal can be up to a month old. Monthly indicators need years of index history (the app downloads about 8 extra years of the index). |
| Sigma SuperTrend filter | Port of your Pine Script v4 'Supertrend': source hl2, ATR period 10, multiplier 3.0, standard ATR (RMA); healthy while trend = up | Pine uses the chart's timeframe, so the app lets you choose Daily or Weekly candles (default Daily). Before the ATR exists the trend counts as up, as in Pine. Checked with constructed price paths, not against TradingView numbers - compare a few dates with your chart. |
| EQUITY filter | Weak when this rebalance's realised loss (stocks being sold) is at least your limit as % of portfolio value; healthy again when a later rebalance realises a profit | Guide's wording is ambiguous. |
| Half Portfolio | First weak day: every holding is cut by half, at most 50% stays invested; idle cash is re-invested (top-up) when the market is healthy again | Follows the guide's example. |
| Presets 2-5 | Starting points built from the prompt's formula examples and the guide's advice on exit rank | Preset 1 is exactly the prompt's example. Not proven - backtest them. |
| Screener regime banner | Same filters as the Backtest (default SuperTrend 1 2.5 weekly) on the chosen index, as of the ranking date | A trend signal, not a forecast. If the index download fails the app falls back to the average of your uploaded stocks (High = Low = Close, so SuperTrend is approximate). |
| Rebalance advisor | Same rules as the Backtest: sell if rank > exit rank or no score; fill free slots with best-ranked unheld stocks; equal money per slot; Half = sell half once, then cap 50% invested; healthy again = top up | You tell the app if you already halved last time (it cannot know). Holdings outside your uploaded list cannot be ranked and show as EXIT / no score. Prices are last closes. |
| Custom formula extras | `Skip`, `FIP` and `52 Week High` terms are app-only; weeks 1-4 and months 1-12 are allowed | Not in Sigma Scanner, so such formulas cannot be pasted there. |
| Filter rules | Yes/no tests on the same items as formulas (e.g. `12 Month Performance > 0`); a stock must pass all; a missing value fails. They block new buys; if ticked they also force a held stock out | Two ready-made rules (12M > 0, 3M > -10%) come from a script you shared; the 10% threshold has no published source. Sigma months (30 days) are used in rules. |
| Score penalty (optional, off by default) | Score is turned into a 0-100 percentile, then N points (default 25) are subtracted from every stock failing the penalty rule (default `3 Month Performance > -10%`), and the list is re-ranked | Mirrors your script's 'Final Rank Score'. Works with any formula, not only F20. A stock whose rule value is missing counts as failing. |
| PDC / Day % | PDC = Previous Day Close = the close of the trading day before the ranking date (or before the trade date in the Backtest). Day % = LTP vs PDC | End-of-day Yahoo data, not live ticks. |
| Entry limit | A NEW stock is bought only if its rank is in the top X% of the stocks scored (0 = off) | Held stocks are judged only by the exit rank. |
| F20 Percentile Composite | Average of the percentile ranks of the 3/6/9/12 month returns (21-day months), 25% each | From a script you shared, not a published source. Percentiles depend on your list size. The script's '-25 points' penalty is replaced by the filter rule. |
| Screener columns | Consistency = -FIP x 100 (higher = steadier); return and volatility columns use 21-day months (1M = 21, 3M = 63, 6M = 126, 9M = 189, 12M = 252 trading days), as in your script | Formula scores and filter rules still use the formula's own month length (Sigma formulas: 30 days), so a '12M %' column can differ slightly from a rule `12 Month Performance`. |
| Index codes | `^NSEI`, `^CRSLDX` (Yahoo) | Could not be tested live from the build environment. |

## Known limits
- **Survivorship bias:** only stocks in today's list are tested.
- **Free Yahoo data:** gaps, wrong adjustments and renamed symbols happen.
- **Not built yet:** Slope formulas, weekly (1-4 week) formulas in the ready-made library (the Custom box accepts them), taxes, liquidity limits.
- **Saved formulas:** stored in `my_formulas.json` next to the app. On free web hosts (e.g. Streamlit Community Cloud) the file can vanish when the app restarts - use the *Download backup* button.
- **Live download not tested here:** the build environment could not reach Yahoo Finance. Everything else was tested with made-up prices.
