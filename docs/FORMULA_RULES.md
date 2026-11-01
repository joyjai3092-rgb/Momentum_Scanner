# Rules for writing your own formula

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
