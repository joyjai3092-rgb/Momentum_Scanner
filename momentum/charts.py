"""Interactive charts (Altair is installed together with Streamlit). Hover for details, drag to pan, scroll to zoom."""
from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd

BLUE, GREY, GREEN, RED, PURPLE = "#1f6feb", "#8b949e", "#1a7f37", "#cf222e", "#8250df"


def _hover(long: pd.DataFrame, x: str, y: str, color: str, tooltip: list):
    """Lines with a vertical hover rule and dots on the nearest date."""
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=[x], empty=False)
    base = alt.Chart(long)
    points = base.mark_point(filled=True, size=60).encode(x=x, y=y, color=color,
                                                           opacity=alt.condition(nearest, alt.value(1), alt.value(0)))
    rule = base.mark_rule(color=GREY, strokeDash=[4, 3]).encode(x=x, tooltip=tooltip).transform_filter(nearest)
    catcher = base.mark_point(opacity=0).encode(x=x).add_params(nearest)
    return points + rule + catcher


def equity_chart(equity: pd.Series, benchmark: pd.Series | None = None, height: int = 340):
    df = pd.DataFrame({"Strategy": equity})
    if benchmark is not None:
        df["Index (buy & hold)"] = benchmark
    long = df.rename_axis("Date").reset_index().melt("Date", var_name="Line", value_name="Value").dropna()
    color = alt.Color("Line:N", scale=alt.Scale(domain=["Strategy", "Index (buy & hold)"], range=[BLUE, GREY]),
                      legend=alt.Legend(orient="top", title=None))
    y = alt.Y("Value:Q", title="Portfolio value (Rs.)", scale=alt.Scale(zero=False), axis=alt.Axis(format=",.0f"))
    line = alt.Chart(long).mark_line(strokeWidth=2.2).encode(x=alt.X("Date:T", title=None), y=y, color=color)
    tip = [alt.Tooltip("Date:T"), alt.Tooltip("Line:N"), alt.Tooltip("Value:Q", format=",.0f")]
    return (line + _hover(long, "Date:T", "Value:Q", color, tip)).properties(height=height).interactive(bind_y=False)


def drawdown_chart(dd: pd.DataFrame, height: int = 200):
    """dd: columns 'Strategy' (and optionally 'Index (buy & hold)') in % (negative numbers)."""
    long = dd.rename_axis("Date").reset_index().melt("Date", var_name="Line", value_name="Drawdown %").dropna()
    color = alt.Color("Line:N", scale=alt.Scale(domain=["Strategy", "Index (buy & hold)"], range=[RED, GREY]),
                      legend=alt.Legend(orient="top", title=None))
    area = alt.Chart(long).mark_area(opacity=0.35, line=True).encode(
        x=alt.X("Date:T", title=None), y=alt.Y("Drawdown %:Q"), color=color)
    tip = [alt.Tooltip("Date:T"), alt.Tooltip("Line:N"), alt.Tooltip("Drawdown %:Q", format=".1f")]
    return (area + _hover(long, "Date:T", "Drawdown %:Q", color, tip)).properties(height=height).interactive(bind_y=False)


def yearly_bars(strategy: pd.Series, index: pd.Series | None = None, height: int = 260):
    df = pd.DataFrame({"Strategy": strategy})
    if index is not None:
        df["Index"] = index
    long = df.rename_axis("Year").reset_index().melt("Year", var_name="Line", value_name="Return %")
    long["Year"] = long["Year"].astype(str)
    return alt.Chart(long).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Year:N", title=None, axis=alt.Axis(labelAngle=0)),
        xOffset="Line:N",
        y=alt.Y("Return %:Q"),
        color=alt.Color("Line:N", scale=alt.Scale(domain=["Strategy", "Index"], range=[BLUE, GREY]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Year:N", "Line:N", alt.Tooltip("Return %:Q", format=".1f")],
    ).properties(height=height)


def monthly_heatmap(table: pd.DataFrame, height: int = 220):
    long = table.reset_index().melt("Year", var_name="Month", value_name="Return %").dropna()
    long["Year"] = long["Year"].astype(str)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    base = alt.Chart(long).encode(x=alt.X("Month:N", sort=months, title=None), y=alt.Y("Year:N", title=None))
    rect = base.mark_rect().encode(
        color=alt.Color("Return %:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[-15, 15], clamp=True), legend=None),
        tooltip=["Year:N", "Month:N", alt.Tooltip("Return %:Q", format=".1f")])
    text = base.mark_text(fontSize=11).encode(text=alt.Text("Return %:Q", format=".1f"))
    return (rect + text).properties(height=height)


def contributors_bar(trades: pd.DataFrame, n: int = 10, height: int = 320):
    """Realised P&L by stock (sells only): the n best and n worst."""
    if trades is None or trades.empty:
        return None
    s = trades[trades["Action"].isin(["SELL", "TRIM"])].groupby("Symbol")["Realised P&L"].sum().dropna()
    if s.empty:
        return None
    s = pd.concat([s.nlargest(n), s.nsmallest(n)]).drop_duplicates().sort_values()
    df = s.rename("Realised P&L (Rs.)").rename_axis("Symbol").reset_index()
    df["Result"] = np.where(df["Realised P&L (Rs.)"] >= 0, "Profit", "Loss")
    return alt.Chart(df).mark_bar().encode(
        y=alt.Y("Symbol:N", sort=df["Symbol"].tolist(), title=None),
        x=alt.X("Realised P&L (Rs.):Q"),
        color=alt.Color("Result:N", scale=alt.Scale(domain=["Profit", "Loss"], range=[GREEN, RED]), legend=None),
        tooltip=["Symbol:N", alt.Tooltip("Realised P&L (Rs.):Q", format=",.0f")],
    ).properties(height=height)


def risk_return_scatter(out: pd.DataFrame, x: str = "12M Vol %", y: str = "12M %", height: int = 380):
    """One dot per stock: return vs volatility. Top-left = high return for low risk."""
    d = out.dropna(subset=[x, y]).copy()
    if d.empty:
        return None
    d["Group"] = np.where(d["Buy list"] == "BUY", "In buy list", np.where(d["Passes rules"], "Ranked", "Fails rules"))
    return alt.Chart(d).mark_circle(opacity=0.8, stroke="white", strokeWidth=0.8).encode(
        x=alt.X(f"{x}:Q", title=x.replace(" %", " (% per year)")), y=alt.Y(f"{y}:Q", title=y),
        size=alt.Size("Percentile:Q", scale=alt.Scale(range=[40, 380]), legend=None),
        color=alt.Color("Group:N", scale=alt.Scale(domain=["In buy list", "Ranked", "Fails rules"], range=[GREEN, BLUE, RED]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["Symbol:N", "Name:N", "Rank:Q", alt.Tooltip("LTP:Q", format=".2f"), alt.Tooltip(f"{y}:Q", format=".1f"),
                 alt.Tooltip(f"{x}:Q", format=".1f"), "Group:N"],
    ).properties(height=height).interactive()


def sector_bar(buy: pd.DataFrame, height: int = 260):
    if buy is None or buy.empty or "Sector" not in buy:
        return None
    c = buy["Sector"].astype(str).replace({"": "Unknown", "nan": "Unknown"}).value_counts().rename_axis("Sector").reset_index(name="Stocks")
    return alt.Chart(c).mark_bar(cornerRadiusEnd=3, color=PURPLE).encode(
        y=alt.Y("Sector:N", sort="-x", title=None), x=alt.X("Stocks:Q", axis=alt.Axis(tickMinStep=1)),
        tooltip=["Sector:N", "Stocks:Q"]).properties(height=height)


def price_chart(prices: pd.Series, height: int = 320):
    """One stock: closing price with its 50-day average and the 52-week-high line. Hover for values."""
    d = pd.DataFrame({"Close": prices}).dropna()
    if d.empty:
        return None
    d["50-day average"] = d["Close"].rolling(50, min_periods=20).mean()
    high = float(d["Close"].iloc[-252:].max())
    long = d.rename_axis("Date").reset_index().melt("Date", var_name="Line", value_name="Price").dropna()
    color = alt.Color("Line:N", scale=alt.Scale(domain=["Close", "50-day average"], range=[BLUE, "#d29922"]),
                      legend=alt.Legend(orient="top", title=None))
    line = alt.Chart(long).mark_line(strokeWidth=2).encode(x=alt.X("Date:T", title=None),
                                                           y=alt.Y("Price:Q", scale=alt.Scale(zero=False), title="Price (Rs.)"), color=color)
    rule = alt.Chart(pd.DataFrame({"y": [high], "label": ["52-week high"]})).mark_rule(color=GREEN, strokeDash=[6, 4]).encode(
        y="y:Q", tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("y:Q", title="Rs.", format=",.2f")])
    tip = [alt.Tooltip("Date:T"), alt.Tooltip("Line:N"), alt.Tooltip("Price:Q", format=",.2f")]
    return (line + rule + _hover(long, "Date:T", "Price:Q", color, tip)).properties(height=height).interactive(bind_y=False)
