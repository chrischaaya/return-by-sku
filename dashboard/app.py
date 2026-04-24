"""
Return Investigation Tool — main Streamlit entry point.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Return Investigation Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import config
from engine.analyzer import load_data
from engine.recommender import size_action, sku_summary
from engine.actions import (
    save_action, save_no_action, resolve_sku, add_new_action,
    revert_action, get_excluded_skus, get_skus_by_status, get_action,
)
from engine.cache import save_cache, load_cache, get_cache_age
from engine.settings import load_settings, save_settings, DEFAULTS
from anthropic import Anthropic
from engine.pipelines import get_sku_review_comments
from engine.tracking import get_tracking_data, get_tracking_summaries
import plotly.graph_objects as go

# --- Authentication ---
ALLOWED_DOMAIN = "hiccup.com"

_is_logged_in = getattr(st.user, "is_logged_in", False)
if not _is_logged_in:
    st.title("Return Investigation Tool")
    st.markdown("Sign in with your @hiccup.com Google account to continue.")
    if hasattr(st, "login"):
        st.login("google")
    else:
        st.error("Authentication requires Streamlit >= 1.42. Please update.")
    st.stop()

# Verify domain
_user_email = getattr(st.user, "email", "") or ""
if not _user_email.endswith(f"@{ALLOWED_DOMAIN}"):
    st.error(f"Access denied. Only @{ALLOWED_DOMAIN} accounts are allowed.")
    if hasattr(st, "logout"):
        st.logout()
    st.stop()

_actor = _user_email.split("@")[0]  # e.g. "chris" from "chris@hiccup.com"

SIZE_ORDER = [
    "XXS", "XS", "S", "S/M", "M", "M/L", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36",
    "37", "38", "39", "40", "42", "44", "46", "48", "50",
    "ONE SIZE", "STD",
]


def size_sort_key(s):
    try:
        return SIZE_ORDER.index(str(s).upper())
    except ValueError:
        return 999


def issue_label(ps, pl, pq, po, has_reasons, reason_count=None):
    if not has_reasons:
        return "Not enough data"
    low_data = reason_count is not None and reason_count < 10
    sizing = ps + pl
    if sizing >= 0.25:
        rs = ps / max(pl, 0.01) if ps > 0 else 0
        rl = pl / max(ps, 0.01) if pl > 0 else 0
        if rs >= 3 or (ps > 0 and pl == 0):
            lbl = "Runs small"
        elif rl >= 3 or (pl > 0 and ps == 0):
            lbl = "Runs large"
        elif rs >= 2:
            lbl = "Likely runs small"
        elif rl >= 2:
            lbl = "Likely runs large"
        else:
            lbl = f"Sizing varies ({ps:.0%} small, {pl:.0%} large)"
        if pq >= 0.25:
            lbl += " + Quality issue"
        if low_data:
            lbl += " (low data)"
        return lbl
    if pq >= 0.25:
        lbl = "Quality issue"
        if low_data:
            lbl += " (low data)"
        return lbl
    lbl = "No dominant pattern — review product"
    if low_data:
        lbl += " (low data)"
    return lbl


# --- CSS ---
st.markdown("""<style>
.sku-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 16px; margin-bottom: 14px; background: #fff; }
.problem-box { padding: 10px 14px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #e74c3c; background: #fef2f2; font-size: 14px; }
.progress-card { padding: 12px 14px; border-radius: 6px; background: #fffbeb; border-left: 4px solid #f59e0b; margin-bottom: 6px; font-size: 14px; }
.new-badge { display: inline-block; background: #22c55e; color: white; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; margin-left: 8px; vertical-align: middle; }
.sizes-affected { font-size: 13px; color: #666; }
/* Action tracking: compact date inputs */
[data-testid="stDateInput"] { max-width: 140px; }
[data-testid="stDateInput"] input { font-size: 13px !important; padding: 6px 10px !important; }
</style>""", unsafe_allow_html=True)

# --- Header ---
h1, h2, h3, h4 = st.columns([5, 1, 0.5, 0.6])
with h1:
    st.title("Return Investigation Tool")
    st.caption(f"Last updated: {get_cache_age()}")
with h2:
    should_update = st.button("Refresh Data", use_container_width=True)
with h3:
    show_settings = st.button("⚙️", use_container_width=True)
with h4:
    st.markdown(f'<div style="font-size:12px; color:#888; text-align:right; padding-top:8px;">{_actor}</div>', unsafe_allow_html=True)
    if st.button("Logout", key="logout_btn", use_container_width=True):
        st.logout()
        st.rerun()

use_turkish = False


# --- Settings dialog ---
@st.dialog("Settings", width="large")
def _show_settings():
    s = load_settings()

    st.caption("Thresholds")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        s["filter_threshold"] = st.number_input("Filter threshold", 0.0, 2.0, float(s.get("filter_threshold", 0.0)), 0.1, help="Which products appear. 0 = all. 1.0 = above median. 1.3 = 30% above median.")
    with c2:
        s["problematic_threshold"] = st.number_input("Problematic threshold", 0.0, 2.0, float(s.get("problematic_threshold", 1.3)), 0.1, help="Sizes above this are highlighted red. 1.3 = 30% above category median.")
    with c3:
        s["min_recent_sales_per_size"] = st.number_input("Min sales/size", 1, 100, int(s["min_recent_sales_per_size"]), help="A size needs this many lifetime sales to be included.")
    with c4:
        s["new_product_max_age_days"] = st.number_input("New product window (days)", 7, 180, int(s.get("new_product_max_age_days", 45)), help="Products first sold within this many days appear in the New Products tab.")
    s["new_product_min_sales_per_size"] = s["min_recent_sales_per_size"]

    st.caption("Data filters")
    c5, c6 = st.columns(2)
    with c5:
        s["fast_delivery_lag_days"] = st.number_input("Grace period — fast channels (days)", 1, 30, int(s["fast_delivery_lag_days"]), help="Exclude recent orders for Trendyol/Hepsiburada (fast delivery).")
    with c6:
        s["slow_delivery_lag_days"] = st.number_input("Grace period — other channels (days)", 1, 30, int(s["slow_delivery_lag_days"]), help="Exclude recent orders for slower channels.")
    all_channels = sorted([
        "trendyol", "trendyolRO", "fashiondays", "fashiondaysBG",
        "emag", "emagBG", "emagHU", "hepsiburada", "hiccup",
        "debenhams", "namshi", "tiktokShop", "amazonUS", "amazonUK",
        "allegro", "ananas", "shein", "noon", "walmart", "aboutYou", "vogaCloset",
    ], key=str.lower)
    st.caption("Excluded channels")
    exc_c1, exc_c2, exc_c3 = st.columns([4, 0.6, 0.6])
    with exc_c2:
        if st.button("All", use_container_width=True, help="Exclude all channels"):
            st.session_state["_exc_ch"] = all_channels
    with exc_c3:
        if st.button("Clear", use_container_width=True, help="Include all channels"):
            st.session_state["_exc_ch"] = []
    with exc_c1:
        if "_exc_ch" not in st.session_state:
            st.session_state["_exc_ch"] = s["excluded_channels"]
        s["excluded_channels"] = st.multiselect("Excluded channels", options=all_channels, default=None, key="_exc_ch", label_visibility="collapsed", help="Completely excluded from all calculations.")

    if st.button("Save & recalculate", type="primary", use_container_width=True):
        save_settings(s)
        config.reload_settings()
        st.cache_data.clear()
        with st.spinner("Recalculating with new settings..."):
            st.session_state["data"] = load_data()
            save_cache(st.session_state["data"])
            st.session_state.pop("computed", None)
        st.toast("Settings saved and data recalculated!")
        st.rerun()


if show_settings:
    _show_settings()

# --- Load data ---
if should_update:
    st.cache_data.clear()
    with st.spinner("Refreshing data... (~30s)"):
        st.session_state["data"] = load_data()
        save_cache(st.session_state["data"])
        st.session_state.pop("computed", None)
    st.toast("Data refreshed!")
elif "data" not in st.session_state:
    cached = load_cache()
    if cached and cached.get("updatedOn"):
        st.session_state["data"] = cached
    else:
        with st.spinner("Loading data... (~30s)"):
            st.session_state["data"] = load_data()
            save_cache(st.session_state["data"])
            st.session_state.pop("computed", None)

data = st.session_state.get("data")
if data is None:
    st.info("Click 'Refresh Data' to load.")
    st.stop()

# --- Compute P75 flagging ---
if "computed" not in st.session_state:
    df_sku = data["df_sku"].copy()
    df_sku_size = data["df_sku_size"].copy()

    if df_sku_size is not None and not df_sku_size.empty:
        import numpy as np

        FILTER_THRESH = config.FILTER_THRESHOLD
        PROB_THRESH = config.PROBLEMATIC_THRESHOLD
        FLOOR_PP = 0.05

        def weighted_median(g):
            sg = g.sort_values("return_rate")
            cw = sg["sold"].cumsum()
            return sg[cw >= sg["sold"].sum() / 2.0].iloc[0]["return_rate"]

        active = df_sku_size[df_sku_size["sold"] > 0]
        cat_stats = {}
        for cat, g in active.groupby("category_l3"):
            wm = weighted_median(g)
            ft = max(wm * FILTER_THRESH, wm + FLOOR_PP) if FILTER_THRESH > 0 else 0
            ht = max(wm * PROB_THRESH, wm + FLOOR_PP) if PROB_THRESH > 0 else 0
            cat_totals_sold = g["sold"].sum()
            cat_totals_ret = g["returned"].sum()
            cat_avg_val = cat_totals_ret / cat_totals_sold if cat_totals_sold > 0 else 0
            cat_stats[cat] = {"weighted_median": wm, "trigger": ft, "highlight_trigger": ht, "category_avg": cat_avg_val}

        cat_df = pd.DataFrame(cat_stats).T
        cat_df.index.name = "category_l3"
        df_sku_size = df_sku_size.merge(cat_df[["trigger", "highlight_trigger", "category_avg"]], on="category_l3", how="left")

        # Global fallback
        if not active.empty:
            g_wm = weighted_median(active)
            g_ft = max(g_wm * FILTER_THRESH, g_wm + FLOOR_PP) if FILTER_THRESH > 0 else 0
            g_ht = max(g_wm * PROB_THRESH, g_wm + FLOOR_PP) if PROB_THRESH > 0 else 0
            g_avg = active["returned"].sum() / active["sold"].sum()
        else:
            g_ft = g_ht = 0
            g_avg = 0
        df_sku_size["trigger"] = df_sku_size["trigger"].fillna(g_ft)
        df_sku_size["highlight_trigger"] = df_sku_size["highlight_trigger"].fillna(g_ht)
        df_sku_size["category_avg"] = df_sku_size["category_avg"].fillna(g_avg)
        df_sku_size["size_p75"] = df_sku_size["highlight_trigger"]

        # Filter flag (which products appear)
        if FILTER_THRESH == 0:
            df_sku_size["is_flagged"] = True
        else:
            df_sku_size["is_flagged"] = df_sku_size["return_rate"] > df_sku_size["trigger"]

        # Highlight flag (which sizes are red)
        if PROB_THRESH == 0:
            df_sku_size["is_highlighted"] = True
        else:
            df_sku_size["is_highlighted"] = df_sku_size["return_rate"] > df_sku_size["highlight_trigger"]

        df_sku_size["qualifies_size"] = df_sku_size["sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        df_sku_size["qualifies_rising"] = df_sku_size["sold"] >= config.MIN_RECENT_SALES_PER_SIZE

        # Product visibility (filter threshold)
        df_sku_size["is_problematic"] = df_sku_size["qualifies_size"] & df_sku_size["is_flagged"]
        df_sku_size["is_problematic_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_flagged"]
        # Red highlighting (problematic threshold)
        df_sku_size["is_red"] = df_sku_size["qualifies_size"] & df_sku_size["is_highlighted"]
        df_sku_size["is_red_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_highlighted"]

        for cn, pc in [("problematic_sizes", "is_problematic"), ("problematic_sizes_rising", "is_problematic_rising")]:
            cts = df_sku_size[df_sku_size[pc]].groupby("sku_prefix")["size"].count().rename(cn)
            df_sku = df_sku.drop(columns=[cn], errors="ignore")
            df_sku = df_sku.merge(cts, on="sku_prefix", how="left")
            df_sku[cn] = df_sku[cn].fillna(0).astype(int)

        for cn, pc in [("highlighted_sizes", "is_red"), ("highlighted_sizes_rising", "is_red_rising")]:
            cts = df_sku_size[df_sku_size[pc]].groupby("sku_prefix")["size"].count().rename(cn)
            df_sku = df_sku.drop(columns=[cn], errors="ignore")
            df_sku = df_sku.merge(cts, on="sku_prefix", how="left")
            df_sku[cn] = df_sku[cn].fillna(0).astype(int)

    # --- Compute priority score ---
    if "deviation_pct" in df_sku.columns and "total_sold" in df_sku.columns:
        df_sku["priority_score"] = (
            df_sku["deviation_pct"].clip(lower=0)
            * df_sku["total_sold"].apply(lambda x: math.sqrt(max(x, 0)))
            * (1 + 0.2 * df_sku.get("highlighted_sizes", 0))
        )
    else:
        df_sku["priority_score"] = 0

    if "parkpalet_stock" not in df_sku_size.columns:
        from engine.pipelines import get_parkpalet_stock
        sr = get_parkpalet_stock()
        if sr:
            df_sku_size = df_sku_size.merge(pd.DataFrame(sr), on=["sku_prefix", "size"], how="left")
            df_sku_size["parkpalet_stock"] = df_sku_size["parkpalet_stock"].fillna(0).astype(int)
        else:
            df_sku_size["parkpalet_stock"] = 0

    excluded = get_excluded_skus()
    rs = df_sku[(df_sku["problematic_sizes_rising"] > 0) & (df_sku["is_rising_star"] == True) & (~df_sku["sku_prefix"].isin(excluded))].copy()
    bs = df_sku[(df_sku["problematic_sizes"] > 0) & (~df_sku["sku_prefix"].isin(rs["sku_prefix"])) & (~df_sku["sku_prefix"].isin(excluded))].copy()
    na = pd.concat([bs, rs]).drop_duplicates(subset="sku_prefix")

    st.session_state["computed"] = {"df_sku": df_sku, "df_sku_size": df_sku_size, "bestsellers": bs, "rising_stars": rs, "needs_attention": na}

c = st.session_state["computed"]
df_sku, df_sku_size = c["df_sku"], c["df_sku_size"]
needs_attention, rising_stars, bestsellers = c["needs_attention"], c["rising_stars"], c["bestsellers"]
tracking_data = get_skus_by_status("tracking")
parked_data = get_skus_by_status("no_action")

# --- Tabs ---
tab_att, tab_track, tab_park = st.tabs([
    f"Needs Attention ({len(needs_attention)})",
    f"Action Tracking ({len(tracking_data)})",
    f"Parked ({len(parked_data)})",
])


# =====================================================================
# HELPERS
# =====================================================================
def render_size_table(sku_prefix, is_rising=False):
    rc_col = "is_red_rising" if is_rising else "is_red"
    ss = df_sku_size[df_sku_size["sku_prefix"] == sku_prefix].copy()
    if ss.empty:
        return
    ss["_s"] = ss["size"].apply(size_sort_key)
    ss = ss.sort_values("_s")
    p75 = ss["size_p75"].iloc[0] if "size_p75" in ss.columns else 0
    for col in ["reason_count", "parkpalet_stock", "review_count", "avg_rating", "fit_true", "fit_small", "fit_large"]:
        if col not in ss.columns:
            ss[col] = 0
        else:
            ss[col] = ss[col].fillna(0)
    ss["issue"] = ss.apply(lambda r: issue_label(r.get("pct_too_small", 0), r.get("pct_too_large", 0), r.get("pct_quality", 0), r.get("pct_other", 0), True, reason_count=r.get("reason_count", 0)), axis=1)
    ss["act"] = ss.apply(lambda r: size_action(r["return_rate"], p75, r.get("pct_too_small", 0), r.get("pct_too_large", 0), r.get("pct_quality", 0), r.get("pct_other", 0), r.get(rc_col, False), r.get("parkpalet_stock", 0), r.get("sold", 0)), axis=1)
    ip = ss[rc_col].values if rc_col in ss.columns else [False] * len(ss)

    ts = ss["sold"].sum()
    tr = ss.get("returned", pd.Series([0])).sum()
    trate = tr / ts if ts > 0 else 0
    tstock = ss["parkpalet_stock"].sum()
    trc = ss["reason_count"].sum()
    if trc > 0:
        rc = ss["reason_count"]
        t_s = (ss["pct_too_small"] * rc).sum() / trc
        t_l = (ss["pct_too_large"] * rc).sum() / trc
        t_q = (ss["pct_quality"] * rc).sum() / trc
        t_o = (ss["pct_other"] * rc).sum() / trc
    else:
        t_s = t_l = t_q = t_o = 0
    ti = issue_label(t_s, t_l, t_q, t_o, True, reason_count=trc)
    ad = ss.apply(lambda r: {"size": r["size"], "is_flagged": r.get(rc_col, False), "pct_small": r.get("pct_too_small", 0), "pct_large": r.get("pct_too_large", 0), "pct_quality": r.get("pct_quality", 0), "stock": r.get("parkpalet_stock", 0)}, axis=1).tolist()
    ta = sku_summary(ad) or ""

    def fp(v):
        return f"{v:.0%}" if v > 0 else "—"

    # Rating totals
    total_reviews = int(ss["review_count"].sum()) if "review_count" in ss.columns else 0
    if total_reviews > 0 and "avg_rating" in ss.columns:
        total_avg_rating = round((ss["avg_rating"] * ss["review_count"]).sum() / total_reviews, 1)
    else:
        total_avg_rating = 0

    def frating(rating, count):
        return f"{rating:.1f} ({count})" if count > 0 else "—"

    # ── Main size table ──
    cols = ["Size", "Sold", "Returns", "Return %", "Rating", "Stock", "Action"]
    rows = []
    for i, (_, r) in enumerate(ss.iterrows()):
        rc = int(r.get("review_count", 0))
        rows.append({"Size": r["size"], "Sold": int(r["sold"]), "Returns": int(r.get("returned", 0)), "Return %": f"{r['return_rate']:.1%}", "Rating": frating(r.get("avg_rating", 0), rc), "Stock": int(r.get("parkpalet_stock", 0)), "Action": r["act"], "_p": ip[i] if i < len(ip) else False})
    rows.append({"Size": "TOTAL", "Sold": int(ts), "Returns": int(tr), "Return %": f"{trate:.1%}", "Rating": frating(total_avg_rating, total_reviews), "Stock": int(tstock), "Action": ta, "_p": False})

    html = _render_html_table(cols, rows)
    st.markdown(html, unsafe_allow_html=True)

    # ── Diagnostic panels side by side ──
    dc1, dc2 = st.columns(2)

    # Left: Return Reasons (from returns data)
    with dc1:
        st.markdown('<p style="font-size:12px; font-weight:600; color:#555; margin:12px 0 4px;">Return Reasons</p>', unsafe_allow_html=True)
        reason_cols = ["Size", "w/ Reason", "Too Small", "Too Large", "Quality", "Other"]
        reason_rows = []
        t_with_reason = 0
        for _, r in ss.iterrows():
            rc = int(r.get("reason_count", 0))
            t_with_reason += rc
            reason_rows.append({"Size": r["size"], "w/ Reason": rc, "Too Small": fp(r.get("pct_too_small", 0)), "Too Large": fp(r.get("pct_too_large", 0)), "Quality": fp(r.get("pct_quality", 0)), "Other": fp(r.get("pct_other", 0)), "_p": False})
        if reason_rows:
            reason_rows.append({"Size": "ALL", "w/ Reason": t_with_reason, "Too Small": fp(t_s), "Too Large": fp(t_l), "Quality": fp(t_q), "Other": fp(t_o), "_p": False})
            st.markdown(_render_html_table(reason_cols, reason_rows, compact=True), unsafe_allow_html=True)
        else:
            st.caption("No return reason data available")

    # Right: Customer Fit (from reviews data)
    with dc2:
        st.markdown('<p style="font-size:12px; font-weight:600; color:#555; margin:12px 0 4px;">Customer Fit (from reviews)</p>', unsafe_allow_html=True)
        fit_cols = ["Size", "w/ Fit", "Runs Small", "True to Size", "Runs Large"]
        fit_rows = []
        t_fit_true = t_fit_small = t_fit_large = 0
        ffit = lambda n, t: f"{n/t:.0%}" if t > 0 else "—"
        for _, r in ss.iterrows():
            ft = int(r.get("fit_true", 0)) + int(r.get("fit_small", 0)) + int(r.get("fit_large", 0))
            t_fit_true += int(r.get("fit_true", 0))
            t_fit_small += int(r.get("fit_small", 0))
            t_fit_large += int(r.get("fit_large", 0))
            fit_rows.append({"Size": r["size"], "w/ Fit": ft, "Runs Small": ffit(int(r.get("fit_small", 0)), ft), "True to Size": ffit(int(r.get("fit_true", 0)), ft), "Runs Large": ffit(int(r.get("fit_large", 0)), ft), "_p": False})
        if fit_rows:
            t_fit_total = t_fit_true + t_fit_small + t_fit_large
            fit_rows.append({"Size": "ALL", "w/ Fit": t_fit_total, "Runs Small": ffit(t_fit_small, t_fit_total), "True to Size": ffit(t_fit_true, t_fit_total), "Runs Large": ffit(t_fit_large, t_fit_total), "_p": False})
            st.markdown(_render_html_table(fit_cols, fit_rows, compact=True), unsafe_allow_html=True)
        else:
            st.caption("No customer fit data available")


def _render_html_table(cols, rows, compact=False):
    """Render a list of column names + row dicts into a styled HTML table."""
    fs = "12px" if compact else "13px"
    html = f'<table style="width:100%; border-collapse:collapse; font-size:{fs};">'
    html += '<tr style="background:#f8f8f8; font-weight:600; border-bottom:2px solid #ddd;">'
    for col in cols:
        html += f'<th style="padding:{"3px 6px" if compact else "5px 8px"}; text-align:left; white-space:nowrap;">{col}</th>'
    html += '</tr>'
    for rd in rows:
        is_total = rd["Size"] in ("TOTAL", "ALL")
        bg = "background:#f0f0f0; font-weight:600;" if is_total else ("background:#ffcccc;" if rd.get("_p") else "")
        html += f'<tr style="{bg} border-bottom:1px solid #eee;">'
        for col in cols:
            sty = f'padding:{"3px 6px" if compact else "4px 8px"}; vertical-align:top;'
            if col == "Action":
                sty += " white-space:pre-wrap; min-width:170px; font-size:12px;"
            html += f'<td style="{sty}">{rd.get(col, "")}</td>'
        html += '</tr>'
    html += '</table>'
    return html


@st.cache_data(ttl=300)
def _fetch_reviews(sku_prefix):
    return get_sku_review_comments(sku_prefix)


def _render_review_html(r, turkish=False):
    """Render a single review as HTML."""
    rating = int(r.get("rating", 0))
    stars = "★" * rating + "☆" * (5 - rating)
    size = r.get("size", "?")
    fit_map = {"TRUE_TO_SIZE": "True to Size", "SMALL": "Runs Small", "LARGE": "Runs Large"}
    fit = fit_map.get(r.get("fit", ""), r.get("fit", ""))
    dt = r.get("createdOn")
    if dt:
        if isinstance(dt, str):
            date_str = dt[:10]
        else:
            date_str = dt.strftime("%d %b %Y")
    else:
        date_str = ""
    comment = r.get("originalComment") or r.get("comments", "") or ""
    name = r.get("name", "")
    title = r.get("reviewTitle", "")
    title_html = f"<b>{title}</b><br>" if title else ""
    return (
        f'<div style="border-left:3px solid #ddd; padding:6px 12px; margin:6px 0; font-size:13px;">'
        f'<div style="color:#666;"><span style="color:#d4a017;">{stars}</span> · Size {size} · {fit} · {date_str}</div>'
        f'<div style="margin-top:3px;">{title_html}{comment}</div>'
        f'<div style="color:#999; font-size:12px; margin-top:2px;">— {name}</div>'
        f'</div>'
    )


def _filter_reviews(reviews, filt_size, filt_rating, filt_fit):
    fit_map_rev = {"True to Size": "TRUE_TO_SIZE", "Runs Small": "SMALL", "Runs Large": "LARGE"}
    filtered = reviews
    if filt_size != "All":
        filtered = [r for r in filtered if r.get("size") == filt_size]
    if filt_rating != "All":
        filtered = [r for r in filtered if r.get("rating") == int(filt_rating)]
    if filt_fit != "All":
        filtered = [r for r in filtered if r.get("fit") == fit_map_rev.get(filt_fit)]
    return filtered


@st.dialog("Customer Reviews", width="large")
def _reviews_dialog(sku_prefix):
    reviews = _fetch_reviews(sku_prefix)
    turkish = st.session_state.get("_dialog_turkish", False)

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        all_sizes = sorted(set(r.get("size", "") for r in reviews if r.get("size")))
        filt_size = st.selectbox("Size", ["All"] + all_sizes, key=f"dlg_size_{sku_prefix}")
    with fc2:
        filt_rating = st.selectbox("Rating", ["All", "5", "4", "3", "2", "1"], key=f"dlg_rating_{sku_prefix}")
    with fc3:
        filt_fit = st.selectbox("Fit", ["All", "True to Size", "Runs Small", "Runs Large"], key=f"dlg_fit_{sku_prefix}")

    filtered = _filter_reviews(reviews, filt_size, filt_rating, filt_fit)

    # Pagination state
    per_page = 50
    total = len(filtered)
    total_pages = max(1, -(-total // per_page))
    pg_key = f"dlg_pg_{sku_prefix}"
    if pg_key not in st.session_state:
        st.session_state[pg_key] = 1
    if st.session_state[pg_key] > total_pages:
        st.session_state[pg_key] = 1

    def _nav_bar(pos):
        pg = st.session_state[pg_key]
        start = (pg - 1) * per_page + 1
        end = min(pg * per_page, total)
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1:
            if st.button("←", key=f"dlg_prev_{pos}_{sku_prefix}", disabled=pg <= 1):
                st.session_state[pg_key] = pg - 1
        with c2:
            st.markdown(
                f'<div style="text-align:center; font-size:13px; color:#888; padding-top:4px;">'
                f'{total} reviews · Page {pg} of {total_pages} · Showing {start}–{end}'
                f'</div>', unsafe_allow_html=True,
            )
        with c3:
            if st.button("→", key=f"dlg_next_{pos}_{sku_prefix}", disabled=pg >= total_pages):
                st.session_state[pg_key] = pg + 1

    _nav_bar("top")

    pg = st.session_state[pg_key]
    start = (pg - 1) * per_page
    page_reviews = filtered[start:start + per_page]
    html = "".join(_render_review_html(r, turkish=turkish) for r in page_reviews)
    st.markdown(html, unsafe_allow_html=True)

    if total_pages > 1:
        _nav_bar("bot")


def render_reviews(sku_prefix):
    """Render customer review comments section with preview + dialog."""
    reviews = _fetch_reviews(sku_prefix)
    if not reviews:
        st.caption("No customer reviews")
        return

    turkish = use_turkish

    st.markdown(
        f'<p style="font-size:12px; font-weight:600; color:#555; margin:12px 0 4px;">'
        f'Customer Reviews ({len(reviews)})</p>',
        unsafe_allow_html=True,
    )

    # Preview: first 5
    preview_html = "".join(_render_review_html(r, turkish=turkish) for r in reviews[:5])
    st.markdown(preview_html, unsafe_allow_html=True)

    if len(reviews) > 5:
        if st.button(f"Show all {len(reviews)} reviews", key=f"rev_all_{sku_prefix}"):
            st.session_state["_dialog_turkish"] = turkish
            _reviews_dialog(sku_prefix)


def render_product_card(row, is_rising=False, cta_mode="action"):
    """Render a single product as a self-contained card."""
    sku = row["sku_prefix"]
    name = row.get("product_name", sku) or sku
    img_url = row.get("image_url")
    has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
    n_prob = int(row.get("highlighted_sizes_rising" if is_rising else "highlighted_sizes", 0))
    baseline = row.get("category_baseline", 0)
    cat_avg = row.get("category_avg", baseline)
    rate = row.get("return_rate", 0)

    with st.container(border=True):
        # Top section: image + info
        if has_img:
            ic, mc = st.columns([1, 5])
        else:
            ic, mc = None, st.container()

        if ic:
            with ic:
                st.image(img_url, width=80)

        with mc:
            title = f"**{name}**"
            if is_rising:
                title += ' <span class="new-badge">NEW</span>'
            st.markdown(title, unsafe_allow_html=True)
            pm = row.get('product_manager', '') or 'N/A'
            st.caption(f"{sku} · {row.get('supplier_name', 'N/A')} · {row.get('category_l3', '')} · PM: {pm}")
            p_rating = row.get('product_avg_rating', 0)
            p_reviews = int(row.get('product_review_count', 0))
            rating_str = f"★ {p_rating}/5 ({p_reviews} reviews)" if p_reviews > 0 else "No reviews"
            st.markdown(
                f'<div class="problem-box">'
                f'Return rate: <b>{rate:.1%}</b> · Category average: {cat_avg:.1%} · '
                f'{rating_str} · '
                f'<span class="sizes-affected">{n_prob} size{"s" if n_prob != 1 else ""} affected</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Expandable size table
        with st.expander("Size breakdown", expanded=False):
            if has_img:
                ic, tc = st.columns([1, 5])
                with ic:
                    st.image(img_url, width=200)
            else:
                tc = st.container()
            with tc:
                render_size_table(sku, is_rising=is_rising)
                render_reviews(sku)

        # CTAs
        if cta_mode == "action":
            c1, c2, c3 = st.columns([1, 1, 4])
            with c1:
                if st.button("✓ Action taken", key=f"act_{sku}", use_container_width=True):
                    st.session_state[f"modal_{sku}"] = True
            with c2:
                if st.button("✗ No action possible", key=f"noact_{sku}", use_container_width=True):
                    save_no_action(sku, _actor)
                    st.session_state.pop("computed", None)
                    st.rerun()
            if st.session_state.get(f"modal_{sku}"):
                st.markdown("---")
                txt = st.text_area("What action was taken?", key=f"sum_{sku}", placeholder="e.g. Revised size chart with supplier")
                if st.button("Submit", key=f"sub_{sku}"):
                    if txt.strip():
                        save_action(sku, txt.strip(), float(rate), _actor)
                        st.session_state.pop(f"modal_{sku}", None)
                        st.session_state.pop("computed", None)
                        st.rerun()




SIZE_COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#a855f7", "#f97316", "#06b6d4", "#ec4899", "#84cc16"]


def _build_tracking_row(sku_prefix, action_doc, preloaded=None):
    """Build one row of tracking data."""
    row = df_sku[df_sku["sku_prefix"] == sku_prefix]
    name = row.iloc[0]["product_name"] if not row.empty else sku_prefix
    img_url = row.iloc[0].get("image_url") if not row.empty else None
    supplier = row.iloc[0].get("supplier_name", "N/A") if not row.empty else "N/A"
    pm = row.iloc[0].get("product_manager", "") if not row.empty else ""

    action_summary = action_doc.get("actionSummary", "N/A")
    created_on = action_doc.get("createdOn")
    days_ago = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(created_on, tz="UTC")).days if created_on else 0

    action_iso = created_on.isoformat() if created_on else datetime.now(timezone.utc).isoformat()
    td = get_tracking_data(sku_prefix, action_iso, _preloaded=preloaded)

    pre_po = td["pre_po_rate"]
    last_14d = td["last_14d_rate"]
    if pre_po is not None and last_14d is not None:
        change_pp = (last_14d - pre_po) * 100
    else:
        change_pp = None

    po_info = ""
    if td["pos"]:
        p = td["pos"][0]
        d = p["received_on"]
        ds = d.strftime("%d %b") if hasattr(d, "strftime") else str(d)[:10]
        u = sum(i.get("received", 0) for i in p.get("items", []))
        po_info = f"{ds} ({u}u)"

    return {
        "sku_prefix": sku_prefix, "name": name, "img_url": img_url,
        "supplier": supplier, "pm": pm, "action_summary": action_summary,
        "created_on": created_on, "days_ago": days_ago,
        "td": td, "pre_po": pre_po, "last_14d": last_14d,
        "lifetime": td["lifetime_rate"], "change_pp": change_pp,
        "po_info": po_info, "badge": td["badge"],
    }


def _render_tracking_table(rows):
    """Render the tracking table as HTML."""
    return rows


def _render_expanded_graph(r):
    """Render the Plotly graph for an expanded tracking row."""
    td = r["td"]
    rolling_df = td["rolling_df"]
    if rolling_df.empty:
        st.caption("Not enough data for graph yet.")
        return

    sku = r["sku_prefix"]
    from datetime import date as date_type, timedelta as td_delta

    # Time range + per-size toggle
    min_date = rolling_df["date"].min().date() if not rolling_df.empty else date_type.today() - td_delta(days=90)
    max_date = rolling_df["date"].max().date() if not rolling_df.empty else date_type.today()
    default_start = max(min_date, date_type.today() - td_delta(days=45))
    # Get metrics from the caller (passed via r dict)
    _last14 = r.get("_last14_str", "—")
    _lifetime = r.get("_lifetime_str", "—")

    tfc = st.columns([0.55, 0.55, 0.7, 2.2, 0.7, 0.5])
    with tfc[0]:
        start_d = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date, key=f"tr_s_{sku}")
    with tfc[1]:
        end_d = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key=f"tr_e_{sku}")
    with tfc[2]:
        st.markdown('<div style="height:29px;"></div>', unsafe_allow_html=True)
        show_sizes = st.checkbox("Per-size", key=f"sizes_{sku}", value=False)
    with tfc[4]:
        st.markdown(f'<div style="text-align:right;"><div style="font-size:10px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">Last 14d</div><div style="font-size:20px; font-weight:700;">{_last14}</div></div>', unsafe_allow_html=True)
    with tfc[5]:
        st.markdown(f'<div style="text-align:right;"><div style="font-size:10px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">Lifetime</div><div style="font-size:20px; font-weight:700;">{_lifetime}</div></div>', unsafe_allow_html=True)

    df = rolling_df.copy()
    df = df[(df["date"].dt.date >= start_d) & (df["date"].dt.date <= end_d)]
    if df.empty:
        st.caption("No data in selected range")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["overall_rate"], mode="lines", name="Overall",
        line=dict(color="#333", width=3), hovertemplate="%{x|%d %b %Y}<br>Overall: %{y:.1%}<extra></extra>", connectgaps=False,
    ))

    if show_sizes:
        for i, size in enumerate(td["sizes"]):
            col = f"rate_{size}"
            if col not in df.columns:
                continue
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[col], mode="lines", name=size,
                line=dict(color=SIZE_COLORS[i % len(SIZE_COLORS)], width=1.5), opacity=0.6,
                hovertemplate=f"{size}: %{{y:.1%}}<extra></extra>", connectgaps=False,
            ))

    action_date = r["created_on"]
    if action_date:
        ad_str = action_date.strftime("%Y-%m-%d") if hasattr(action_date, "strftime") else str(action_date)[:10]
        ad_label = action_date.strftime("%d %b") if hasattr(action_date, "strftime") else ad_str
        fig.add_shape(type="line", x0=ad_str, x1=ad_str, y0=0, y1=1, yref="paper", line=dict(color="#f59e0b", width=2, dash="dash"))
        fig.add_annotation(x=ad_str, y=1, yref="paper", text=f"ACTION ({ad_label})", showarrow=False, font=dict(color="#f59e0b", size=10), yshift=10)

    # Show ALL POs within the visible date range (including older ones)
    from engine.pipelines import get_sku_pos as _get_sku_pos
    all_sku_pos = _get_sku_pos(sku, df["date"].min().to_pydatetime().replace(tzinfo=timezone.utc) - td_delta(days=30))
    for po in (all_sku_pos or []):
        received = po.get("received_on")
        if received:
            rs = received.strftime("%Y-%m-%d") if hasattr(received, "strftime") else str(received)[:10]
            rs_label = received.strftime("%d %b") if hasattr(received, "strftime") else rs
            units = sum(it.get("received", 0) for it in po.get("items", []))
            fig.add_shape(type="line", x0=rs, x1=rs, y0=0, y1=1, yref="paper", line=dict(color="#16a34a", width=2, dash="dash"))
            fig.add_annotation(x=rs, y=1, yref="paper", text=f"PO {rs_label} ({units}u)", showarrow=False, font=dict(color="#16a34a", size=10), yshift=10)

    all_vals = df["overall_rate"].dropna().tolist()
    if show_sizes:
        for size in td["sizes"]:
            col = f"rate_{size}"
            if col in df.columns:
                all_vals.extend(df[col].dropna().tolist())
    if all_vals:
        y_max = max(all_vals) + 0.03
        y_max = max(y_max, 0.10)
    else:
        y_max = 0.5

    # X-axis: fit exactly to filtered data range
    x_min = df["date"].min()
    x_max = df["date"].max()

    fig.update_layout(
        yaxis=dict(tickformat=".0%", title="", gridcolor="#f0f0f0", range=[0, y_max]),
        xaxis=dict(title="", gridcolor="#f0f0f0", range=[x_min, x_max]),
        height=480, margin=dict(t=20, b=40, l=40, r=10),
        plot_bgcolor="white", legend=dict(orientation="h", y=-0.25), hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# =====================================================================
# TAB 1: NEEDS ATTENTION
# =====================================================================
with tab_att:
    # ── Search bar ──
    search = st.text_input("Search", placeholder="Search by product name or SKU...", key="att_search", label_visibility="collapsed")

    # ── Controls row: view toggle, sort, filters ──
    st.markdown(
        '<div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin:-8px 0 8px;">'
        '<span style="font-size:11px; font-weight:600; color:#999; text-transform:uppercase; letter-spacing:0.5px; margin-right:4px;">Filters</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    fc1, fc2, fc3, fc4 = st.columns([1.5, 1.5, 1.5, 1])
    with fc1:
        cats = sorted(needs_attention["category_l3"].dropna().unique().tolist())
        sel_cat = st.selectbox("Category", ["All categories"] + cats, key="att_cat", label_visibility="collapsed")
    with fc2:
        sups = sorted(needs_attention["supplier_name"].dropna().unique().tolist())
        sel_sup = st.selectbox("Supplier", ["All suppliers"] + sups, key="att_sup", label_visibility="collapsed")
    with fc3:
        sort_by = st.selectbox("Sort", ["Returns (most)", "Return %", "Priority (impact)", "Sales (highest)", "Newest first"], index=0, key="att_sort", label_visibility="collapsed")
    with fc4:
        show_new = st.toggle("New only", value=False)

    display = rising_stars.copy() if show_new else needs_attention.copy()
    if sort_by == "Priority (impact)":
        display = display.sort_values("priority_score", ascending=False)
    elif sort_by == "Sales (highest)":
        display = display.sort_values("total_sold", ascending=False)
    elif sort_by == "Returns (most)":
        display = display.sort_values("total_returned", ascending=False)
    elif sort_by == "Return %":
        display = display.sort_values("return_rate", ascending=False)
    else:
        if "first_order" in display.columns:
            display = display.sort_values("first_order", ascending=False, na_position="last")
    if search:
        q = search.lower()
        display = display[display["sku_prefix"].str.lower().str.contains(q, na=False) | display["product_name"].astype(str).str.lower().str.contains(q, na=False)]
    if sel_cat != "All categories":
        display = display[display["category_l3"] == sel_cat]
    if sel_sup != "All suppliers":
        display = display[display["supplier_name"] == sel_sup]

    total_items = len(display)

    # Per-page selector + pagination state
    per_page_options = [30, 50, 100, 200]
    if "att_pp" not in st.session_state:
        st.session_state["att_pp"] = 30
    if "att_page" not in st.session_state:
        st.session_state["att_page"] = 1

    per_page = st.session_state["att_pp"]
    total_pages = max(1, -(-total_items // per_page))
    if st.session_state["att_page"] > total_pages:
        st.session_state["att_page"] = 1
    page = st.session_state["att_page"]

    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_items)
    page_display = display.iloc[start_idx:end_idx]

    # Top bar: count + pagination
    st.markdown(
        f'<div style="display:flex; justify-content:space-between; align-items:center; padding:4px 0 8px;">'
        f'<span style="font-size:13px; color:#888;">{total_items} products</span>'
        f'<span style="font-size:13px; color:#888;">Showing {start_idx+1}–{end_idx} of {total_items}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for _, row in page_display.iterrows():
        render_product_card(row, is_rising=row["sku_prefix"] in rising_stars["sku_prefix"].values, cta_mode="action")

    # Bottom pagination bar
    if total_pages > 1 or per_page != 30:
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns([2, 3, 2])
        with pc1:
            new_pp = st.selectbox("Per page", per_page_options, index=per_page_options.index(per_page), key="_att_pp_sel", label_visibility="collapsed")
            if new_pp != per_page:
                st.session_state["att_pp"] = new_pp
                st.session_state["att_page"] = 1
                st.rerun()
        with pc2:
            # Page number buttons
            pages_to_show = []
            if total_pages <= 7:
                pages_to_show = list(range(1, total_pages + 1))
            else:
                pages_to_show = sorted(set([1, total_pages] + list(range(max(1, page - 2), min(total_pages + 1, page + 3)))))
            btn_cols = st.columns(len(pages_to_show) + 2)
            with btn_cols[0]:
                if st.button("←", disabled=page == 1, key="pg_prev"):
                    st.session_state["att_page"] = page - 1
                    st.rerun()
            for idx, p in enumerate(pages_to_show):
                with btn_cols[idx + 1]:
                    if p == page:
                        st.markdown(f'<div style="text-align:center; background:#1a73e8; color:white; border-radius:4px; padding:4px 0; font-size:13px; font-weight:600;">{p}</div>', unsafe_allow_html=True)
                    else:
                        if st.button(str(p), key=f"pg_{p}"):
                            st.session_state["att_page"] = p
                            st.rerun()
            with btn_cols[-1]:
                if st.button("→", disabled=page == total_pages, key="pg_next"):
                    st.session_state["att_page"] = page + 1
                    st.rerun()
        with pc3:
            st.markdown(f'<div style="text-align:right; font-size:13px; color:#888; padding-top:6px;">Page {page} of {total_pages}</div>', unsafe_allow_html=True)

# =====================================================================
# TAB 2: ACTION TRACKING
# =====================================================================
with tab_track:
    if not tracking_data:
        st.info("No actions taken yet. Mark products as 'Action taken' from the Needs Attention tab.")
    else:
        sorted_tracking = sorted(tracking_data.items(), key=lambda x: x[1].get("createdOn", datetime.min), reverse=True)

        # Batch PO lookup (fast — one query)
        from engine.pipelines import get_pos_for_skus
        po_pairs = [(s, d.get("createdOn", datetime.now(timezone.utc))) for s, d in sorted_tracking]
        all_pos = get_pos_for_skus(po_pairs)

        # Build list items (fast — from df_sku in memory + action docs + PO dates)
        tracking_items = []
        for sku_prefix, action_doc in sorted_tracking:
            row = df_sku[df_sku["sku_prefix"] == sku_prefix]
            in_data = not row.empty
            name = row.iloc[0]["product_name"] if in_data else action_doc.get("actionSummary", sku_prefix)[:40]
            img_url = row.iloc[0].get("image_url") if in_data else None
            supplier = row.iloc[0].get("supplier_name", "—") if in_data else "—"
            pm = row.iloc[0].get("product_manager", "") if in_data else ""
            lifetime = float(row.iloc[0]["return_rate"]) if in_data else 0
            created_on = action_doc.get("createdOn")
            days_ago = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(created_on, tz="UTC")).days if created_on else 0
            date_str = created_on.strftime("%d %b") if created_on and hasattr(created_on, "strftime") else "—"
            pos = all_pos.get(sku_prefix, [])
            po_str = ""
            if pos:
                po_d = pos[0]["received_on"]
                po_str = po_d.strftime("%d %b") if hasattr(po_d, "strftime") else str(po_d)[:10]
            tracking_items.append({
                "sku_prefix": sku_prefix, "name": name, "img_url": img_url,
                "supplier": supplier, "pm": pm, "lifetime": lifetime, "in_data": in_data,
                "action_summary": action_doc.get("actionSummary", "N/A"),
                "created_on": created_on, "days_ago": days_ago, "date_str": date_str,
                "po_str": po_str,
            })

        # ── Split layout: list left, graph right ──
        left_col, right_col = st.columns([1, 2])

        with left_col:
            if tracking_items:
                # Auto-select first if nothing selected
                if "track_selected" not in st.session_state or st.session_state["track_selected"] not in {i["sku_prefix"] for i in tracking_items}:
                    st.session_state["track_selected"] = tracking_items[0]["sku_prefix"]

                track_search = st.text_input("Search", placeholder="Filter by name or SKU...", key="track_search", label_visibility="collapsed")
                display_items = tracking_items
                if track_search:
                    q = track_search.lower()
                    display_items = [i for i in tracking_items if q in i["sku_prefix"].lower() or q in str(i["name"]).lower()]

                st.caption(f"{len(display_items)} tracked")

                # Scrollable list with View buttons
                with st.container(height=500):
                    for item in display_items:
                        sku = item["sku_prefix"]
                        is_sel = st.session_state.get("track_selected") == sku
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([0.4, 3, 0.8])
                            with c1:
                                if item.get("img_url") and isinstance(item["img_url"], str) and item["img_url"].startswith("http"):
                                    st.image(item["img_url"], width=36)
                            with c2:
                                st.markdown(f"**{item['name']}**")
                                po_line = f"PO: {item['po_str']}" if item["po_str"] else "PO: no PO yet"
                                st.caption(f"{sku} · {item['supplier']} · Action: {item['date_str']} · {po_line}")
                            with c3:
                                if is_sel:
                                    st.markdown('<div style="padding:4px 0; text-align:center; font-size:12px; color:#1a73e8; font-weight:600;">Viewing</div>', unsafe_allow_html=True)
                                else:
                                    if st.button("View", key=f"view_{sku}", use_container_width=True):
                                        st.session_state["track_selected"] = sku
                                        st.rerun()

        with right_col:
            selected_sku = st.session_state.get("track_selected")
            selected_item = next((i for i in tracking_items if i["sku_prefix"] == selected_sku), None)

            if selected_item:
                # Load graph data on demand
                action_doc = tracking_data[selected_sku]
                created_on = action_doc.get("createdOn")
                action_iso = created_on.isoformat() if created_on else datetime.now(timezone.utc).isoformat()
                # Fetch from Jan 1 of current year
                from datetime import date as _dt
                _days = (_dt.today() - _dt(_dt.today().year, 1, 1)).days + 14
                td = get_tracking_data(selected_sku, action_iso, days_back=_days, _excluded_channels=",".join(sorted(config.EXCLUDED_CHANNELS)))

                last_14d = td["last_14d_rate"]
                last_14d_str = f"{last_14d:.1%}" if last_14d is not None and last_14d > 0 else ("No data" if last_14d is None or last_14d == 0 else f"{last_14d:.1%}")
                lifetime_str = f"{selected_item['lifetime']:.1%}"
                pm_str = f" · PM: {selected_item['pm']}" if selected_item["pm"] else ""

                # Header + CTAs
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px;">'
                    f'<div>'
                    f'<div style="font-size:20px; font-weight:700; color:#1a1a1a;">{selected_item["name"]}</div>'
                    f'<div style="font-size:12px; color:#888; margin-top:2px;">{selected_item["sku_prefix"]} · {selected_item["supplier"]}{pm_str}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                bc1, bc2, bc3 = st.columns([5, 0.7, 0.8])
                with bc2:
                    if st.button("✓ Resolved", key="resolve_selected", use_container_width=True):
                        resolve_sku(selected_sku, _actor)
                        st.session_state.pop("track_selected", None)
                        st.toast(f"Resolved: {selected_item['name']}")
                        st.rerun()
                with bc3:
                    if st.button("+ New Action", key="new_action_btn", use_container_width=True):
                        st.session_state["new_action_modal"] = selected_sku

                if st.session_state.get("new_action_modal") == selected_sku:
                    new_txt = st.text_area("What action was taken?", key=f"new_act_txt_{selected_sku}", placeholder="e.g. Sent revised measurements to supplier")
                    if st.button("Submit", key="new_act_submit"):
                        if new_txt and new_txt.strip():
                            add_new_action(selected_sku, new_txt.strip(), selected_item["lifetime"], _actor)
                            st.session_state.pop("new_action_modal", None)
                            st.toast("Action added!")
                            st.rerun()

                # Action timeline (collapsed by default, expandable)
                actions_list = action_doc.get("actions", [])
                if not actions_list:
                    actions_list = [{"summary": selected_item["action_summary"], "date": created_on}]

                show_all_actions = st.session_state.get(f"show_all_actions_{selected_sku}", False)
                reversed_actions = list(reversed(actions_list))
                visible_actions = reversed_actions if show_all_actions else reversed_actions[:3]

                timeline_html = '<div style="margin:10px 0 8px; border-left:2px solid #f59e0b; padding-left:12px; max-height:200px; overflow-y:auto;">'
                for i, act in enumerate(visible_actions):
                    a_date = act.get("date")
                    a_str = a_date.strftime("%d %b %Y") if a_date and hasattr(a_date, "strftime") else "—"
                    a_days = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(a_date, tz="UTC")).days if a_date else 0
                    dot_color = "#f59e0b" if i == 0 else "#ddd"
                    summary = act.get("summary", "")
                    # Truncate long text unless expanded
                    if not show_all_actions and len(summary) > 150:
                        summary = summary[:150] + "..."
                    timeline_html += (
                        f'<div style="position:relative; padding:4px 0 8px; font-size:12px;">'
                        f'<div style="position:absolute; left:-18px; top:6px; width:10px; height:10px; border-radius:50%; background:{dot_color}; border:2px solid white;"></div>'
                        f'<div style="color:#333;">{summary}</div>'
                        f'<div style="color:#999; font-size:11px;">{a_str} ({a_days}d ago)</div>'
                        f'</div>'
                    )
                timeline_html += '</div>'
                st.markdown(timeline_html, unsafe_allow_html=True)

                if len(actions_list) > 3:
                    label = f"Show all {len(actions_list)} actions" if not show_all_actions else "Show less"
                    if st.button(label, key=f"toggle_actions_{selected_sku}"):
                        st.session_state[f"show_all_actions_{selected_sku}"] = not show_all_actions
                        st.rerun()

                # Graph or monitoring message
                selected_item["_last14_str"] = last_14d_str
                selected_item["_lifetime_str"] = lifetime_str
                rolling_df = td.get("rolling_df", pd.DataFrame())
                has_data = not rolling_df.empty and rolling_df["overall_rate"].notna().sum() >= 7

                if has_data:
                    selected_item["td"] = td
                    _render_expanded_graph(selected_item)
                else:
                    st.markdown(
                        '<div style="padding:30px 20px; text-align:center; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; margin-top:8px;">'
                        '<div style="font-size:24px; margin-bottom:8px;">&#9203;</div>'
                        '<div style="font-size:14px; font-weight:600; color:#475569;">Monitoring</div>'
                        '<div style="font-size:13px; color:#888; margin-top:6px; line-height:1.6;">'
                        'Return rate trend will appear here once enough orders<br>have been processed. Typically 2-3 weeks after new stock arrives.'
                        '</div></div>',
                        unsafe_allow_html=True,
                    )

            else:
                st.markdown(
                    '<div style="padding:60px 20px; text-align:center; color:#aaa;">'
                    'Select a product from the list'
                    '</div>',
                    unsafe_allow_html=True,
                )

# =====================================================================
# TAB 3: PARKED
# =====================================================================
with tab_park:
    if not parked_data:
        st.info("No parked products.")
    else:
        st.caption(f"{len(parked_data)} products marked as 'no action possible'")
        for sku in parked_data:
            r = df_sku[df_sku["sku_prefix"] == sku]
            name = r.iloc[0]["product_name"] if not r.empty else sku
            img_url = r.iloc[0].get("image_url") if not r.empty else None
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 8, 2])
                with c1:
                    if has_img:
                        st.image(img_url, width=55)
                with c2:
                    st.markdown(f"**{name}**")
                    st.caption(sku)
                with c3:
                    if st.button("↩ Revert", key=f"rvn_{sku}", use_container_width=True):
                        revert_action(sku, _actor)
                        st.session_state.pop("computed", None)
                        st.rerun()


# =====================================================================
# SIDEBAR: AI CHAT
# =====================================================================

def _load_chat_context():
    ctx_path = Path(__file__).parent / "chat_context.md"
    if ctx_path.exists():
        return ctx_path.read_text()
    return ""


def _build_data_summary():
    """Build a concise text summary of current dashboard data for the LLM."""
    lines = ["## Current dashboard data\n"]

    if df_sku is not None and not df_sku.empty:
        total = len(df_sku)
        na_count = len(needs_attention) if needs_attention is not None else 0
        avg_rate = df_sku["return_rate"].mean()
        lines.append(f"Total products: {total}")
        lines.append(f"Products needing attention: {na_count}")
        lines.append(f"Average return rate: {avg_rate:.1%}\n")

        # Top 30 by returns
        top = df_sku.nlargest(30, "total_returned")
        lines.append("### Top 30 products by returns")
        for _, r in top.iterrows():
            hl = int(r.get("highlighted_sizes", 0))
            rating = r.get("product_avg_rating", 0)
            reviews = int(r.get("product_review_count", 0))
            pm = r.get("product_manager", "N/A") or "N/A"
            lines.append(
                f"- **{r.get('product_name', r['sku_prefix'])}** ({r['sku_prefix']}): "
                f"{r['return_rate']:.1%} return rate, {int(r['total_returned'])} returns, "
                f"{int(r['total_sold'])} sold, {hl} red sizes, "
                f"supplier: {r.get('supplier_name', 'N/A')}, PM: {pm}, "
                f"rating: {rating}/5 ({reviews} reviews), "
                f"category: {r.get('category_l3', 'N/A')}"
            )

        # Category summary
        lines.append("\n### Categories (top 10 by return rate)")
        cat = df_sku.groupby("category_l3").agg(
            sold=("total_sold", "sum"), returned=("total_returned", "sum"), skus=("sku_prefix", "nunique")
        ).reset_index()
        cat["rate"] = cat["returned"] / cat["sold"].replace(0, 1)
        for _, r in cat.nlargest(10, "rate").iterrows():
            lines.append(f"- {r['category_l3']}: {r['rate']:.1%} ({int(r['returned'])} returns, {int(r['skus'])} SKUs)")

        # Supplier summary
        lines.append("\n### Suppliers (top 10 by return rate)")
        sup = df_sku.groupby("supplier_name").agg(
            sold=("total_sold", "sum"), returned=("total_returned", "sum"), skus=("sku_prefix", "nunique")
        ).reset_index()
        sup["rate"] = sup["returned"] / sup["sold"].replace(0, 1)
        for _, r in sup.nlargest(10, "rate").iterrows():
            lines.append(f"- {r['supplier_name']}: {r['rate']:.1%} ({int(r['returned'])} returns, {int(r['skus'])} SKUs)")

    return "\n".join(lines)


def _find_product_context(question):
    """If the user mentions a specific SKU or product name, return its full data."""
    import re
    if df_sku is None or df_sku.empty:
        return ""

    nan = lambda v: 0 if pd.isna(v) else v

    # Extract SKU-like patterns — any alphanumeric token 6+ chars that isn't a common word
    sku_patterns = re.findall(r'\b[A-Z0-9][A-Z0-9\-]{5,}\b', question, re.IGNORECASE)

    # Find matches by SKU pattern
    matched_skus = set()
    all_skus = set(df_sku["sku_prefix"].tolist())
    for pat in sku_patterns:
        pat_upper = pat.upper()
        for sku in all_skus:
            if pat_upper in sku.upper() or sku.upper() in pat_upper:
                matched_skus.add(sku)

    # Also search by product name keywords (words > 4 chars)
    q_words = [w.lower() for w in question.split() if len(w) > 4 and not re.match(r'^[MW][A-Z0-9\-]{5,}$', w, re.IGNORECASE)]
    if q_words:
        name_matches = df_sku[df_sku["product_name"].astype(str).str.lower().apply(
            lambda n: any(w in n for w in q_words)
        )]
        matched_skus.update(name_matches["sku_prefix"].head(5).tolist())

    if not matched_skus:
        return ""

    lines = ["\n## Product details for mentioned products\n"]
    for sku in list(matched_skus)[:5]:
        r = df_sku[df_sku["sku_prefix"] == sku]
        if r.empty:
            continue
        r = r.iloc[0]
        lines.append(f"### {r.get('product_name', sku)} ({sku})")
        lines.append(f"Return rate: {r['return_rate']:.1%}, Sold: {int(r['total_sold'])}, Returned: {int(r['total_returned'])}")
        lines.append(f"Supplier: {r.get('supplier_name', 'N/A')}, PM: {r.get('product_manager', 'N/A')}, Category: {r.get('category_l3', 'N/A')}")
        lines.append(f"Rating: {r.get('product_avg_rating', 0)}/5 ({int(r.get('product_review_count', 0))} reviews)")

        # Size breakdown
        sizes = df_sku_size[df_sku_size["sku_prefix"] == sku].copy()
        if not sizes.empty:
            sizes["_s"] = sizes["size"].apply(size_sort_key)
            sizes = sizes.sort_values("_s")
            lines.append("Size breakdown:")
            for _, s in sizes.iterrows():
                rc = int(nan(s.get("reason_count", 0)))
                ft = int(nan(s.get("fit_true", 0))) + int(nan(s.get("fit_small", 0))) + int(nan(s.get("fit_large", 0)))
                red = "RED" if s.get("is_red", False) else ""
                lines.append(
                    f"  {s['size']}: sold={int(nan(s['sold']))}, returned={int(nan(s.get('returned', 0)))}, "
                    f"rate={nan(s['return_rate']):.1%}, stock={int(nan(s.get('parkpalet_stock', 0)))}, "
                    f"rating={nan(s.get('avg_rating', 0)):.1f} ({int(nan(s.get('review_count', 0)))} reviews), "
                    f"reasons(n={rc}): small={nan(s.get('pct_too_small', 0)):.0%} large={nan(s.get('pct_too_large', 0)):.0%} quality={nan(s.get('pct_quality', 0)):.0%}, "
                    f"fit(n={ft}): small={int(nan(s.get('fit_small', 0)))} true={int(nan(s.get('fit_true', 0)))} large={int(nan(s.get('fit_large', 0)))} "
                    f"{red}"
                )
        lines.append("")

    return "\n".join(lines)


def _get_chat_response(question, history):
    """Call Claude API with dashboard context + chat history."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "API key not configured. Add ANTHROPIC_API_KEY to .streamlit/secrets.toml."

    static_ctx = _load_chat_context()
    data_ctx = _build_data_summary()
    product_ctx = _find_product_context(question)

    system = f"""{static_ctx}

{data_ctx}
{product_ctx}

Answer concisely. Use the data above to give specific, actionable answers. If the user asks about a product not in the data, say so."""

    messages = [{"role": m["role"], "content": m["content"]} for m in history[-30:]]
    messages.append({"role": "user", "content": question})

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        return f"Error: {e}"


# Sidebar chat UI
with st.sidebar:
    st.markdown("### Ask about your data")
    st.caption("Ask questions about return rates, products, suppliers, or what actions to take.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("e.g. Which supplier has the worst returns?"):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = _get_chat_response(prompt, st.session_state["chat_history"])
            st.markdown(response)
        st.session_state["chat_history"].append({"role": "assistant", "content": response})

    if st.session_state["chat_history"]:
        if st.button("Clear chat", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()
