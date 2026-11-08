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
from .sigma_parser import FormulaError, describe, parse_filters, parse_formula
from .universe import UniverseError, read_universe

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "sample_universe.xlsx"

DISCLAIMER = (
    "Educational tool - **not investment advice**. Past performance does not guarantee future results. "
    "Momentum strategies can have sharp losses (the 2011 review reports a -36.5% year for one momentum strategy in 2009)."
)


# ------------------------------------------------------------------ sidebar
CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1280px;}
.hero {background: linear-gradient(120deg, #0b3d91 0%, #1f6feb 55%, #8250df 100%); color: #fff; padding: 1.6rem 1.8rem;
       border-radius: 16px; margin-bottom: 1.2rem; box-shadow: 0 6px 18px rgba(31,111,235,.25);}
.hero h1 {color: #fff; margin: 0 0 .3rem 0; font-size: 2rem; padding: 0;}
.hero p {color: rgba(255,255,255,.92); margin: 0; font-size: 1.02rem;}
.pill {display:inline-block; background: rgba(255,255,255,.18); border-radius: 999px; padding: .15rem .7rem; margin: .6rem .4rem 0 0; font-size: .82rem;}
.card-title {font-weight: 700; font-size: 1.15rem; margin-bottom: .2rem;}
.small-note {color: #6e7781; font-size: .85rem;}
div[data-testid="stTabs"] button[role="tab"] {font-weight: 600;}
h2, h3 {letter-spacing: -0.01em;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, pills: tuple = ()) -> None:
    chips = "".join(f'<span class="pill">{p}</span>' for p in pills)
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p>{chips}</div>', unsafe_allow_html=True)


def load_my_formulas() -> list:
    """Make the formulas the user saved available to every page (cheap: the list is tiny)."""
    if "my_records" not in st.session_state:
        st.session_state["my_records"] = myf.load_records()
    myf.load_into_registry(st.session_state["my_records"])
    return st.session_state["my_records"]


def sidebar() -> None:
    load_my_formulas()
    inject_css()
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


ABS_RULE = "12 Month Performance > 0"
WEAK_RULE = "3 Month Performance > -10%"


def filter_controls(key: str) -> dict:
    """Optional yes/no rules + entry limit. Returns {text, ok, force_exit, entry_pct}."""
    st.caption("Optional safety rules. A stock must pass **every** rule to be bought. They do not change the ranking.")
    c1, c2 = st.columns(2)
    abs_on = c1.checkbox(f"Absolute momentum: {ABS_RULE}", key=f"{key}_f_abs",
                         help="Only buy a stock that is higher than it was 12 months ago (about 360 trading days). Avoids 'the best of a bad lot'.")
    weak_on = c2.checkbox(f"Skip recent weakness: {WEAK_RULE}", key=f"{key}_f_weak",
                          help="Skip a stock that fell more than 10% in the last 3 months. The 10% is the threshold from the script you shared - change it in the box below if you like.")
    more = st.text_area("More rules (optional, one per line)", key=f"{key}_f_text", height=70,
                        placeholder="e.g. 52 Week High >= 0.8",
                        help="Open 'Formula rules' in the formula section for the full list of items.")
    d1, d2 = st.columns(2)
    force = d1.checkbox("Also sell a held stock that fails the rules", value=True, key=f"{key}_f_force",
                        help="Ticked: a stock you hold that stops passing is sold. Unticked: rules only stop NEW buys.")
    entry = d2.number_input("Buy a new stock only if it is in the top X% (0 = no limit)", min_value=0.0, max_value=99.0, step=5.0,
                            value=0.0, key=f"{key}_entry_pct",
                            help="Example: 20 = a new stock must rank in the top 20% of the stocks scored. Held stocks are judged by the exit rank instead.")
    pen_on = st.checkbox("Also push weak stocks DOWN the ranking (score penalty)", key=f"{key}_pen_on",
                         help="Instead of (or as well as) blocking a stock, lower its score. The score is first turned into a 0-100 percentile "
                              "(100 = best in your list), then the points below are subtracted from every stock that fails the penalty rule, and the list is re-ranked.")
    pen_rule, pen_points = "", 0.0
    if pen_on:
        p1, p2 = st.columns(2)
        pen_rule = p1.text_input("Penalty applies when a stock FAILS this rule", value=WEAK_RULE, key=f"{key}_pen_rule")
        pen_points = float(p2.number_input("Points to subtract (0-100)", min_value=1.0, max_value=100.0, value=25.0, step=5.0, key=f"{key}_pen_pts"))
    rules = ([ABS_RULE] if abs_on else []) + ([WEAK_RULE] if weak_on else []) + [x.strip() for x in more.splitlines() if x.strip()]
    text = " AND ".join(rules)
    ok = True
    if text:
        try:
            pf = parse_filters(text)
            st.caption("Rules read as: " + " · ".join(f"`{c[0]}`" for c in pf.conds))
        except FormulaError as exc:
            st.error(str(exc))
            ok = False
    if pen_on:
        try:
            if not parse_filters(pen_rule).conds:
                raise FormulaError("Type the rule that triggers the penalty.")
        except FormulaError as exc:
            st.error(str(exc))
            ok = False
    return {"text": text if ok else "", "ok": ok, "force_exit": bool(force), "entry_pct": float(entry),
            "pen_rule": pen_rule if (ok and pen_on) else "", "pen_points": pen_points if (ok and pen_on) else 0.0}


# ------------------------------------------------------------------ colour tags for tables (work in light and dark themes)
_GREEN, _RED, _AMBER, _GREY = "rgba(46,160,67,0.28)", "rgba(248,81,73,0.28)", "rgba(210,153,34,0.30)", "rgba(139,148,158,0.20)"
ACTION_TAGS = {"BUY": _GREEN, "TOPUP": _GREEN, "SELL": _RED, "EXIT": _RED, "TRIM": _AMBER, "HOLD": _GREY}


def _tag_action(v):
    parts = str(v).split() if isinstance(v, str) else []
    key = parts[-1].upper() if parts else ""
    return f"background-color: {ACTION_TAGS[key]}; font-weight: 600" if key in ACTION_TAGS else ""


def _tag_signed(v):
    if not isinstance(v, (int, float)) or pd.isna(v) or v == 0:
        return ""
    return "color: #2da44e" if v > 0 else "color: #f85149"


def _tag_rules(v):
    if isinstance(v, str) and v.startswith("❌"):
        return "color: #f85149"
    return "color: #2da44e" if isinstance(v, str) and v.startswith("✅") else ""


def tag_table(df: pd.DataFrame):
    """Return a Styler: green/red for BUY/SELL tags, up/down colours for % columns, red for failed rules."""
    sty = df.style
    for c in df.columns:
        if c in ("Action", "Buy list"):
            sty = sty.map(_tag_action, subset=[c])
        elif c == "Rules":
            sty = sty.map(_tag_rules, subset=[c])
        elif c in ("Day %", "1M %", "3M %", "6M %", "9M %", "12M %", "P&L %", "Return %", "Realised P&L"):
            sty = sty.map(_tag_signed, subset=[c])
    return sty
