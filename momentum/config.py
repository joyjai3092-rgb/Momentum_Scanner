"""Central settings. Change numbers here, not scattered through the code."""

# Sigma Scanner convention (from its Scoring Usage Guide): "6 Month Performance"
# means the last 180 trading days, i.e. 1 month = 30 trading days.
SIGMA_DAYS_PER_MONTH = 30
MAX_SIGMA_MONTHS = 12

# Research-style formulas (12-1, NSE score, 52-week high, Quantitative Momentum)
# follow the calendar convention used in the papers / NSE document:
# 12 months ~ 252 trading days, 1 month ~ 21 trading days.
RESEARCH_DAYS_PER_MONTH = 21
TRADING_DAYS_PER_YEAR = 252

YAHOO_SUFFIX = ".NS"

# Cost per buy or sell, in percent of trade value. This is an ASSUMPTION (not from
# the project documents) - the user can change it on the Backtest page.
DEFAULT_COST_PCT = 0.2

# Index tickers on Yahoo Finance for the market-regime filter.
# NOTE: could not be verified live from the build environment - the app tells the
# user clearly if a ticker returns no data.
INDEX_CHOICES = {
    "Nifty 50 (^NSEI)": "^NSEI",
    "Nifty 500 (^CRSLDX)": "^CRSLDX",
}

# How many calendar days of history to fetch BEFORE the backtest start so that
# the longest look-back (12 Sigma months = 360 trading days) is available.
WARMUP_CALENDAR_DAYS = 800

# Sigma: start and end date should be at least 3 months apart.
MIN_BACKTEST_DAYS = 90
