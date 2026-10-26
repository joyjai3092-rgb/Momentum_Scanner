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
| EQUITY filter | Weak when this rebalance's realised loss (stocks being sold) is at least your limit as % of portfolio value; healthy again when a later rebalance realises a profit | Guide's wording is ambiguous. |
| Half Portfolio | First weak day: every holding is cut by half, at most 50% stays invested; idle cash is re-invested (top-up) when the market is healthy again | Follows the guide's example. |
| Presets 2-5 | Starting points built from the prompt's formula examples and the guide's advice on exit rank | Preset 1 is exactly the prompt's example. Not proven - backtest them. |
| Index codes | `^NSEI`, `^CRSLDX` (Yahoo) | Could not be tested live from the build environment. |

## Known limits
- **Survivorship bias:** only stocks in today's list are tested.
- **Free Yahoo data:** gaps, wrong adjustments and renamed symbols happen.
- **Not built yet:** Slope formulas, weekly (1-4 week) formulas in the library (the custom box accepts them), taxes, liquidity limits.
- **Live download not tested here:** the build environment could not reach Yahoo Finance. Everything else was tested with made-up prices.
