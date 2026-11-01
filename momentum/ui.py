"""Shared Streamlit pieces used by every page (kept out of the pages to avoid repetition)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from . import formulas as fml
from . import myformulas as myf
from .config import INDEX_CHOICES
from .data import DataError, download_index, download_prices
from .demo_data import make_demo_prices
from .sigma_parser import FormulaError, describe, parse_formula
from .universe import UniverseError, read_universe

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "sample_universe.xlsx"

DISCLAIMER = (
    "Educational tool - **not investment advice**. Past performance does not guarantee future results. "
    "Momentum strategies can have sharp losses (the 2011 review reports a -36.5% year for one momentum strategy in 2009)."
)


# ------------------------------------------------------------------ sidebar
def load_my_formulas() -> list:
    """Make the formulas the user saved available to every page (cheap: the list is tiny)."""
    if "my_records" not in st.session_state:
        st.session_state["my_records"] = myf.load_records()
    myf.load_into_registry(st.session_state["my_records"])
    return st.session_state["my_records"]


def sidebar() -> None:
    load_my_formulas()
    with st.sidebar:
        st.markdown("### Momentum Scanner")
        st.toggle(
            "Demo data (fake prices - works offline)", key="demo",
            help="Switch on to try the app with made-up prices. Results are NOT real. Switch off to use real prices from Yahoo Finance.",
        )
        if st.session_state.get("demo"):
            st.warning("DEMO DATA is on: all prices are made up.")
        u = st.session_state.get("universe")
        if u is not None:
            st.success(f"{len(u)} stocks loaded")
        st.caption(DISCLAIMER)


# ------------------------------------------------------------------ data (cached)
@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cached_prices(tickers: tuple, start: str, end: str, demo: bool):
    if demo:
        close, _ = make_demo_prices(list(tickers), start, end)
        return close, []
    return download_prices(list(tickers), start, end)


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cached_index(ticker: str, start: str, end: str, demo: bool):
    if demo:
        _, idx = make_demo_prices(["X"], start, end)
        return idx
    return download_index(ticker, start, end)


# ------------------------------------------------------------------ universe upload
def universe_section() -> pd.DataFrame | None:
    """Upload box (or sample list). Stores the result in st.session_state['universe']."""
    st.markdown("**Your stock list** (Excel or CSV with a column called *Symbol*)")
    col1, col2 = st.columns([3, 2])
    with col1:
        up = st.file_uploader("Upload Excel / CSV", type=["xlsx", "xls", "csv"], key="uploader",
                              label_visibility="collapsed")
    with col2:
        use_sample = st.checkbox("Use the sample list (30 large NSE stocks)", key="use_sample",
                                 help="Just to try the app. For real use, download an index list from niftyindices.com and upload it here.")
    data, name = None, None
    if up is not None:
        data, name = up.getvalue(), up.name
    elif use_sample and SAMPLE_PATH.exists():
        data, name = SAMPLE_PATH.read_bytes(), SAMPLE_PATH.name

    if data is not None:
        chosen = st.session_state.get("symbol_col_choice")
        try:
            table, _ = read_universe(data, name, symbol_column=chosen)
            st.session_state["universe"] = table
            st.session_state["universe_name"] = name
        except UniverseError as exc:
            msg = str(exc)
            if msg.startswith("SYMBOL_COLUMN_NOT_FOUND:"):
                cols = msg.split(":", 1)[1].split("|")
                st.warning("I could not find a 'Symbol' column. Which column holds the stock symbols?")
                st.selectbox("Symbol column", cols, key="symbol_col_choice")
                st.session_state.pop("universe", None)
            else:
                st.error(msg)
                st.session_state.pop("universe", None)
    u = st.session_state.get("universe")
    if u is not None:
        st.caption(f"Loaded **{len(u)}** stocks from *{st.session_state.get('universe_name', '')}*.")
        with st.expander("Preview the list"):
            st.dataframe(u, hide_index=True)
    return u


# ------------------------------------------------------------------ formula picker
def _my_formulas_manager(key: str) -> None:
    """Delete saved formulas, download / restore a backup."""
    records = st.session_state.get("my_records", [])
    if not records:
        st.caption("You have not saved any formula yet. Choose 'Custom', type a formula and press 'Save this formula'.")
    for r in records:
        a, b = st.columns([8, 1])
        a.markdown(f"`{r['id']}` **{r['name']}** - `{r['expr']}`")
        if b.button("Delete", key=f"{key}_del_{r['id']}"):
            st.session_state["my_records"] = myf.delete(r["id"], records)
            st.rerun()
    st.download_button("Download backup of my formulas (.json)", myf.to_json(records), file_name="my_formulas.json",
                       mime="application/json", key=f"{key}_dl_formulas", disabled=not records,
                       help="Keep this file. On a free web host saved formulas can disappear when the app restarts - upload the backup to restore them.")
    up = st.file_uploader("Restore from a backup (.json)", type=["json"], key=f"{key}_up_formulas")
    if up is not None and st.button("Add the formulas from this file", key=f"{key}_add_formulas"):
        try:
            new, added, skipped = myf.from_json(up.getvalue().decode("utf-8", errors="replace"), records)
        except myf.SaveError as exc:
            st.error(str(exc))
        else:
            myf._write(new)
            st.session_state["my_records"] = new
            myf.load_into_registry(new)
            st.success(f"Added {added} formula(s)." + (f" Skipped {len(skipped)}: " + "; ".join(skipped) if skipped else ""))
            if added:
                st.rerun()


def _save_box(key: str, text: str) -> None:
    with st.expander("💾 Save this formula to my list"):
        st.caption("Saved formulas appear in the dropdown here and on the Backtest / Screener pages, and in 'Compare all formulas'. "
                   "Tip: run it in the Backtest first.")
        name = st.text_input("Name", key=f"{key}_save_name", max_chars=myf.MAX_NAME, placeholder="e.g. My 6M momentum per risk")
        note = st.text_input("One-line note (optional)", key=f"{key}_save_note")
        if st.button("Save this formula", key=f"{key}_save_btn"):
            records = st.session_state.get("my_records", [])
            try:
                new = myf.save(name, text, note, records)
            except myf.SaveError as exc:
                st.error(str(exc))
            else:
                st.session_state["my_records"] = new
                st.session_state["_select_after_save"] = new[-1]["id"]
                st.rerun()


def formula_picker(key: str) -> tuple:
    """Dropdown + (?) help. Returns (formula_id, custom_text_or_None)."""
    load_my_formulas()
    pending = st.session_state.pop("_select_after_save", None)
    if pending:
        for k in ("scr", "bt"):                                  # the new formula is selected on both pages
            st.session_state[f"{k}_formula"] = pending
    options = [f.id for f in fml.all_formulas()] + [fml.CUSTOM_ID]
    if st.session_state.get(f"{key}_formula") not in options:
        st.session_state[f"{key}_formula"] = options[0]

    def fmt(fid):
        return "Custom - type my own formula" if fid == fml.CUSTOM_ID else fml.label(fml.get_formula(fid))

    c1, c2 = st.columns([5, 2])
    with c1:
        fid = st.selectbox("Ranking formula", options, format_func=fmt, key=f"{key}_formula",
                           help="Higher score = better rank. Click 'About this formula' to understand the selected one.")
    custom = None
    with c2:
        st.write("")
        with st.popover("❓ About this formula"):
            if fid == fml.CUSTOM_ID:
                st.markdown(fml.CUSTOM_HELP)
            else:
                st.markdown(fml.help_markdown(fml.get_formula(fid)))
    if fid == fml.CUSTOM_ID:
        custom = st.text_input(
            "Your formula", key=f"{key}_custom", value="6 Month Performance / 6 Month Volatility",
            help="Items: N Month/Week Performance, N Month/Week Volatility, N Month Performance Skip M Month, FIP, 52 Week High. "
                 "Plus numbers, %, + - * / and brackets. Open the 'Formula rules' box below for the full rules.",
        )
        try:
            parsed = parse_formula(custom)
        except FormulaError as exc:
            st.error(str(exc))
            custom = None
        else:
            st.caption("I read your formula as:  \n" + "  \n".join(f"- {x}" for x in describe(parsed)))
            _save_box(key, custom)
    else:
        f = fml.get_formula(fid)
        st.caption(f"{f.one_liner}  ·  {f.category[3:]}")

    with st.expander("📏 Formula rules (how to write your own)"):
        st.markdown(fml.RULES_MARKDOWN)
    with st.expander("My saved formulas (delete / backup)"):
        _my_formulas_manager(key)
    with st.expander("Browse all formulas (each has its own ❓)"):
        last_cat = None
        for f in fml.all_formulas():
            if f.category != last_cat:
                st.markdown(f"**{f.category}**")
                last_cat = f.category
            a, b = st.columns([8, 1])
            a.markdown(f"`{f.id}` **{f.name}** - {f.one_liner}")
            with b.popover("❓"):
                st.markdown(fml.help_markdown(f))
    return fid, custom


def index_picker(key: str) -> str:
    label = st.selectbox("Market index (for the regime filter and the benchmark line)", list(INDEX_CHOICES) + ["Other (type a Yahoo ticker)"],
                         key=f"{key}_index",
                         help="Nifty 50 is the safest default. If a ticker returns no data the app will tell you.")
    if label.startswith("Other"):
        return st.text_input("Yahoo Finance ticker", value="^NSEI", key=f"{key}_index_custom").strip()
    return INDEX_CHOICES[label]
