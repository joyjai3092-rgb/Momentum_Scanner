# 📈 Momentum Scanner

Rank NSE stocks by **momentum** (stocks that have been rising tend to keep rising for a while) and **backtest** the idea on past prices - modelled on Sigma Scanner's scoring and backtest screens.

> Educational tool - **not investment advice**. Back-tests use free Yahoo Finance prices and *today's* stock list, so real results would usually be lower.

## What you get

| Page | What it does |
|---|---|
| **Screener** | Upload your Excel list, pick a formula (dropdown, each with a ❓ explanation), get a ranked list, a buy list with quantities and a download. |
| **Backtest** | Pick a start and end date + rules (number of stocks, exit rank, weekly/monthly, market filter). See growth, worst fall, trades, yearly/monthly returns. Includes 5 ready-made strategies and a "compare all formulas" table. |
| **Learn Momentum** | Plain-English guide built from your project papers, the NSE method, the Sigma guides, plus outside sources. |

19 ready-made formulas + a "type your own" box that understands Sigma-style text, e.g. `((70% * 6 Month Performance) + (30% * 1 Month Performance)) / 1 Month Volatility`. Formulas you write can be **saved** and then appear in every dropdown (rules: [docs/FORMULA_RULES.md](docs/FORMULA_RULES.md)).

The Screener also tells you **whether the market is healthy enough to buy** (regime filter) and, if you enter your holdings, gives a **monthly rebalance plan** (EXIT / TRIM / BUY / TOPUP / HOLD).
Full formula list: [docs/FORMULAS.md](docs/FORMULAS.md). Things I had to assume: [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

## Is it free?

- The code and all libraries are free.
- **Streamlit Community Cloud** hosts Streamlit apps for free ([docs](https://docs.streamlit.io/deploy/streamlit-community-cloud)).
- **GitHub Codespaces** gives a GitHub Free personal account 120 compute hours and 15 GB-month storage per month ([GitHub docs](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)). Limits can change - check the page.
- Prices come free from Yahoo Finance.

## Run it - pick ONE way

### A. In your browser with GitHub Codespaces (no installing)
1. Create a free account at github.com, then **New repository** (name e.g. `momentum-scanner`).
2. Click **uploading an existing file**, drag in **everything inside this folder** (including the folders `momentum`, `pages`, `tests`, `sample_data`, `docs` and the dot-folders `.github`, `.devcontainer`, `.streamlit`), then **Commit changes**.
   *Mac tip: dot-folders are hidden in Finder - press `Cmd + Shift + .` to show them.*
3. On the repository page click the green **Code** button → **Codespaces** → **Create codespace on main**.
4. Wait a few minutes. The app opens by itself in a preview tab. If it does not, open the **Terminal** at the bottom and type:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
   then click **Open in Browser** when the pop-up appears.
5. When you finish, stop the codespace (Codespaces menu → Stop) so it does not use your free hours.

### B. A web link anyone can open (Streamlit Community Cloud)
1. Put the files in a GitHub repository (steps 1-2 above).
2. Go to share.streamlit.io, sign in with GitHub, **Create app**, choose your repository, branch `main`, main file `app.py`, **Deploy**.

### C. On your own computer
Install Python 3.11 or newer, open a terminal in this folder, then:
```
pip install -r requirements.txt
streamlit run app.py
```

## Test it

- **On GitHub (automatic):** every upload runs the checks. Open the **Actions** tab → latest run → a green tick means all tests passed. Press **Run workflow** to run them again.
- **By hand:** in a terminal run `python -m pytest -q`.
- **Without internet / to look around:** switch on **Demo data** in the app's left bar (prices are made up - results mean nothing).

The tests check the maths against independent hand calculations, the backtest rules (exit rank, half portfolio, go cash, costs, date range) and click through every page.
*Not covered by the tests:* the live Yahoo Finance download (it could not be reached from where this was built) - see "First run checklist".

## Using the app

1. **Your list:** an Excel (.xlsx) or CSV with a column called **Symbol** (e.g. `RELIANCE`). `Company Name` and `Industry` columns are optional. `sample_data/sample_universe.xlsx` shows the layout. You can upload a different index list each time (Nifty 500, Nifty500 Momentum 50, Nifty500 Multicap, ...).
2. **Screener:** choose a formula → set the market check (Step 4) → optionally enter your holdings (Step 5) → press *Run screener*.
3. **Backtest:** choose a ready-made strategy or set your own rules → pick dates → *Run backtest*.

## First run checklist (live data)
1. Switch Demo data **off**, load the sample list, run the Screener - you should see real prices.
2. In Backtest, check that the index line appears. The index codes `^NSEI` (Nifty 50) and `^CRSLDX` (Nifty 500) are Yahoo Finance codes I could not test live. If one returns no data, pick the other or type another code - the app tells you.
3. Symbols that were renamed or delisted show up in the "skipped" list.

## Folder map
```
app.py                  home page
pages/                  Screener, Backtest, Learn Momentum
momentum/               the maths (formulas.py = formula library + help text)
tests/                  automatic checks
sample_data/            example stock list
my_formulas.json        created when you save your own formulas (keep a backup: use the download button)
docs/                   formula reference, formula-writing rules, assumptions
.github/workflows/      automatic tests on GitHub
.devcontainer/          one-click Codespaces set-up
```
