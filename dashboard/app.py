"""
Return Investigation Tool — main Streamlit entry point.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Return Investigation Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import config
from engine.analyzer import load_data
from engine.recommender import size_action, sku_summary
from engine.actions import (
    save_action, save_no_action, dismiss_sku, revert_no_action,
    revert_waiting, get_excluded_skus, get_skus_by_status,
    check_transitions, seed_test_scenarios, get_action,
)
from engine.cache import save_cache, load_cache, get_cache_age
from engine.settings import load_settings, save_settings, DEFAULTS

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
    if sizing > 0.1:
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
</style>""", unsafe_allow_html=True)

# --- Header ---
h1, h2, h3, h4 = st.columns([5, 1, 1, 0.5])
with h1:
    st.title("Return Investigation Tool")
    st.caption(f"Last updated: {get_cache_age()}")
with h2:
    should_update = st.button("Refresh Data", use_container_width=True)
with h3:
    if st.button("Load Test Data", use_container_width=True):
        seed_test_scenarios()
        st.session_state.pop("computed", None)
        st.toast("Test scenarios loaded!")
with h4:
    show_settings = st.button("⚙️", use_container_width=True)

# --- Settings panel ---
if show_settings:
    st.session_state["show_settings"] = not st.session_state.get("show_settings", False)

if st.session_state.get("show_settings"):
    with st.container(border=True):
        st.subheader("Settings")
        s = load_settings()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            s["baseline_percentile"] = st.slider(
                "Baseline percentile",
                0.50, 0.95, float(s["baseline_percentile"]), 0.05,
                help="Percentile of category return rates used as 'normal'. P75 = only worst 25% flagged.",
            )
            s["min_recent_sales_per_size"] = st.number_input(
                "Min sales/size (Bestsellers)", 1, 100, int(s["min_recent_sales_per_size"]),
                help="Minimum sales per size in last 30 days to qualify.",
            )
        with c2:
            s["rising_star_min_sales_per_size"] = st.number_input(
                "Min sales/size (Rising Stars)", 1, 50, int(s["rising_star_min_sales_per_size"]),
                help="Lower threshold for new products.",
            )
            s["rising_star_max_age_days"] = st.number_input(
                "New product window (days)", 7, 180, int(s["rising_star_max_age_days"]),
                help="Products first sold within this many days count as 'new'.",
            )
        with c3:
            s["fast_delivery_lag_days"] = st.number_input(
                "Grace period — fast channels (days)", 1, 30, int(s["fast_delivery_lag_days"]),
                help="Trendyol, Hepsiburada. Exclude recent orders that haven't been delivered yet.",
            )
            s["slow_delivery_lag_days"] = st.number_input(
                "Grace period — other channels (days)", 1, 30, int(s["slow_delivery_lag_days"]),
                help="All channels except Trendyol/Hepsiburada.",
            )
        with c4:
            s["min_size_volume"] = st.number_input(
                "Min sales for reason data", 1, 100, int(s["min_size_volume"]),
                help="Minimum all-time sales to show return reason breakdown.",
            )
            all_channels = [
                "trendyol", "trendyolRO", "fashiondays", "fashiondaysBG",
                "emag", "emagBG", "emagHU", "hepsiburada", "hiccup",
                "debenhams", "namshi", "tiktokShop", "amazonUS", "amazonUK",
                "allegro", "ananas", "shein", "noon", "walmart", "aboutYou", "vogaCloset",
            ]
            s["excluded_channels"] = st.multiselect(
                "Excluded channels",
                options=all_channels,
                default=s["excluded_channels"],
                help="Channels to exclude from all analysis.",
            )

        if st.button("Save & recalculate", type="primary", use_container_width=True):
            save_settings(s)
            config.reload_settings()
            # Force full recalculation
            with st.spinner("Recalculating with new settings..."):
                st.session_state["data"] = load_data()
                save_cache(st.session_state["data"])
                st.session_state.pop("computed", None)
            st.session_state["show_settings"] = False
            st.toast("Settings saved and data recalculated!")
            st.rerun()

# --- Load data ---
if should_update:
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
        bp = df_sku_size[df_sku_size["sold"] >= 20].copy()
        sp75 = bp.groupby("category_l3")["return_rate"].quantile(config.BASELINE_PERCENTILE).rename("size_p75")
        cat_avg = bp.groupby("category_l3")["return_rate"].mean().rename("category_avg")
        df_sku_size = df_sku_size.merge(sp75, on="category_l3", how="left")
        df_sku_size = df_sku_size.merge(cat_avg, on="category_l3", how="left")
        gp75 = bp["return_rate"].quantile(config.BASELINE_PERCENTILE) if not bp.empty else 0
        gavg = bp["return_rate"].mean() if not bp.empty else 0
        df_sku_size["size_p75"] = df_sku_size["size_p75"].fillna(gp75)
        df_sku_size["category_avg"] = df_sku_size["category_avg"].fillna(gavg)
        df_sku_size["is_flagged"] = (df_sku_size["return_rate"] > df_sku_size["size_p75"]) & (df_sku_size["sold"] >= config.MIN_RECENT_SALES_PER_SIZE)

        drs = data.get("df_recent_size")
        if drs is not None and not drs.empty:
            df_sku_size = df_sku_size.merge(drs[["sku_prefix", "size", "recent_sold"]], on=["sku_prefix", "size"], how="left")
            df_sku_size["recent_sold"] = df_sku_size["recent_sold"].fillna(0).astype(int)
            df_sku_size["qualifies_size"] = df_sku_size["recent_sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        else:
            df_sku_size["recent_sold"] = 0
            df_sku_size["qualifies_size"] = False

        df_sku_size["is_problematic"] = df_sku_size["qualifies_size"] & df_sku_size["is_flagged"]
        df_sku_size["is_flagged_rising"] = (df_sku_size["return_rate"] > df_sku_size["size_p75"]) & (df_sku_size["sold"] >= config.RISING_STAR_MIN_SALES_PER_SIZE)
        df_sku_size["qualifies_rising"] = df_sku_size.get("recent_sold", 0) >= config.RISING_STAR_MIN_SALES_PER_SIZE
        df_sku_size["is_problematic_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_flagged_rising"]

        for cn, pc in [("problematic_sizes", "is_problematic"), ("problematic_sizes_rising", "is_problematic_rising")]:
            cts = df_sku_size[df_sku_size[pc]].groupby("sku_prefix")["size"].count().rename(cn)
            df_sku = df_sku.drop(columns=[cn], errors="ignore")
            df_sku = df_sku.merge(cts, on="sku_prefix", how="left")
            df_sku[cn] = df_sku[cn].fillna(0).astype(int)

    # --- Compute priority score ---
    # priority = deviation_pct * sqrt(recent_sold) * (1 + 0.2 * n_problematic_sizes)
    if "deviation_pct" in df_sku.columns and "recent_sold" in df_sku.columns:
        df_sku["priority_score"] = (
            df_sku["deviation_pct"].clip(lower=0)
            * df_sku["recent_sold"].apply(lambda x: math.sqrt(max(x, 0)))
            * (1 + 0.2 * df_sku["problematic_sizes"])
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

    check_transitions(df_sku_size)
    excluded = get_excluded_skus()
    rs = df_sku[(df_sku["problematic_sizes_rising"] > 0) & (df_sku["is_rising_star"] == True) & (~df_sku["sku_prefix"].isin(excluded))].copy()
    bs = df_sku[(df_sku["problematic_sizes"] > 0) & (~df_sku["sku_prefix"].isin(rs["sku_prefix"])) & (~df_sku["sku_prefix"].isin(excluded))].copy()
    na = pd.concat([bs, rs]).drop_duplicates(subset="sku_prefix")

    st.session_state["computed"] = {"df_sku": df_sku, "df_sku_size": df_sku_size, "bestsellers": bs, "rising_stars": rs, "needs_attention": na}

c = st.session_state["computed"]
df_sku, df_sku_size = c["df_sku"], c["df_sku_size"]
needs_attention, rising_stars, bestsellers = c["needs_attention"], c["rising_stars"], c["bestsellers"]
waiting_data = get_skus_by_status("waiting_for_fix")
fixed_data = get_skus_by_status("fixed")
parked_data = get_skus_by_status("no_action")

# --- Tabs ---
tab_att, tab_prog, tab_res, tab_park = st.tabs([
    f"Needs Attention ({len(needs_attention)})",
    f"In Progress ({len(waiting_data)})",
    f"Results ({len(fixed_data)})",
    f"Parked ({len(parked_data)})",
])


# =====================================================================
# HELPERS
# =====================================================================
def render_size_table(sku_prefix, is_rising=False, show_details=False):
    pc = "is_problematic_rising" if is_rising else "is_problematic"
    mr = config.RISING_STAR_MIN_SALES_PER_SIZE if is_rising else config.MIN_RECENT_SALES_PER_SIZE
    ss = df_sku_size[df_sku_size["sku_prefix"] == sku_prefix].copy()
    if ss.empty:
        return
    ss["_s"] = ss["size"].apply(size_sort_key)
    ss = ss.sort_values("_s")
    p75 = ss["size_p75"].iloc[0] if "size_p75" in ss.columns else 0
    if "reason_count" not in ss.columns:
        ss["reason_count"] = 0
    if "parkpalet_stock" not in ss.columns:
        ss["parkpalet_stock"] = 0
    ss["hr"] = ss["reason_count"] >= mr
    ss["issue"] = ss.apply(lambda r: issue_label(r.get("pct_too_small", 0), r.get("pct_too_large", 0), r.get("pct_quality", 0), r.get("pct_other", 0), r["hr"], reason_count=r.get("reason_count", 0)), axis=1)
    ss["act"] = ss.apply(lambda r: size_action(r["return_rate"], p75, r.get("pct_too_small", 0), r.get("pct_too_large", 0), r.get("pct_quality", 0), r.get("pct_other", 0), r.get(pc, False), r.get("parkpalet_stock", 0), r.get("sold", 0), r.get("reason_count", 0), mr), axis=1)
    ip = ss[pc].values if pc in ss.columns else [False] * len(ss)

    ts = ss["sold"].sum()
    tr = ss.get("returned", pd.Series([0])).sum()
    trate = tr / ts if ts > 0 else 0
    tstock = ss["parkpalet_stock"].sum()
    trc = ss["reason_count"].sum()
    htr = trc >= mr
    if htr and trc > 0:
        rc = ss["reason_count"]
        t_s = (ss["pct_too_small"] * rc).sum() / trc
        t_l = (ss["pct_too_large"] * rc).sum() / trc
        t_q = (ss["pct_quality"] * rc).sum() / trc
        t_o = (ss["pct_other"] * rc).sum() / trc
    else:
        t_s = t_l = t_q = t_o = 0
    ti = issue_label(t_s, t_l, t_q, t_o, htr, reason_count=trc)
    ad = ss.apply(lambda r: {"size": r["size"], "is_flagged": r.get(pc, False), "pct_small": r.get("pct_too_small", 0) if r["hr"] else 0, "pct_large": r.get("pct_too_large", 0) if r["hr"] else 0, "pct_quality": r.get("pct_quality", 0) if r["hr"] else 0, "stock": r.get("parkpalet_stock", 0)}, axis=1).tolist()
    ta = sku_summary(ad) or ("High return rate. Not enough data to diagnose." if not htr else "")

    def fp(v, h):
        return f"{v:.0%}" if h and v > 0 else "—"

    if show_details:
        cols = ["Size", "Sold", "Returns", "Return Rate", "Issue", "% Small", "% Large", "% Quality", "% Other", "Stock", "Action"]
    else:
        cols = ["Size", "Sold", "Returns", "Return Rate", "Issue", "Stock", "Action"]

    rows = []
    for i, (_, r) in enumerate(ss.iterrows()):
        rows.append({"Size": r["size"], "Sold": int(r["sold"]), "Returns": int(r.get("returned", 0)), "Return Rate": f"{r['return_rate']:.1%}", "Issue": r["issue"], "% Small": fp(r.get("pct_too_small", 0), r["hr"]), "% Large": fp(r.get("pct_too_large", 0), r["hr"]), "% Quality": fp(r.get("pct_quality", 0), r["hr"]), "% Other": fp(r.get("pct_other", 0), r["hr"]), "Stock": int(r.get("parkpalet_stock", 0)), "Action": r["act"], "_p": ip[i] if i < len(ip) else False})
    rows.append({"Size": "TOTAL", "Sold": int(ts), "Returns": int(tr), "Return Rate": f"{trate:.1%}", "Issue": ti, "% Small": fp(t_s, htr), "% Large": fp(t_l, htr), "% Quality": fp(t_q, htr), "% Other": fp(t_o, htr), "Stock": int(tstock), "Action": ta, "_p": False})

    html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
    html += '<tr style="background:#f8f8f8; font-weight:600; border-bottom:2px solid #ddd;">'
    for col in cols:
        html += f'<th style="padding:5px 8px; text-align:left;">{col}</th>'
    html += '</tr>'
    for rd in rows:
        ist = rd["Size"] == "TOTAL"
        bg = "background:#f0f0f0; font-weight:600;" if ist else ("background:#ffcccc;" if rd["_p"] else "")
        html += f'<tr style="{bg} border-bottom:1px solid #eee;">'
        for col in cols:
            sty = "padding:4px 8px; vertical-align:top;"
            if col == "Action":
                sty += " white-space:pre-wrap; min-width:170px; font-size:12px;"
            html += f'<td style="{sty}">{rd.get(col, "")}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)


def render_product_card(row, is_rising=False, cta_mode="action"):
    """Render a single product as a self-contained card."""
    sku = row["sku_prefix"]
    name = row.get("product_name", sku) or sku
    img_url = row.get("image_url")
    has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
    n_prob = int(row.get("problematic_sizes_rising" if is_rising else "problematic_sizes", 0))
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
            st.caption(f"{sku} · {row.get('supplier_name', 'N/A')} · {row.get('category_l3', '')}")
            st.markdown(
                f'<div class="problem-box">'
                f'Return rate: <b>{rate:.1%}</b> · Category average: {cat_avg:.1%} · '
                f'<span class="sizes-affected">{n_prob} size{"s" if n_prob != 1 else ""} affected</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Expandable size table
        with st.expander("Size breakdown", expanded=False):
            if has_img:
                _, tc = st.columns([1, 5])
            else:
                tc = st.container()
            with tc:
                det = st.checkbox("Show detailed breakdown", key=f"det_{sku}_{cta_mode}", value=False)
                render_size_table(sku, is_rising=is_rising, show_details=det)

        # CTAs
        if cta_mode == "action":
            c1, c2, c3 = st.columns([1, 1, 4])
            with c1:
                if st.button("✓ Action taken", key=f"act_{sku}", use_container_width=True):
                    st.session_state[f"modal_{sku}"] = True
            with c2:
                if st.button("✗ No action possible", key=f"noact_{sku}", use_container_width=True):
                    save_no_action(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()
            if st.session_state.get(f"modal_{sku}"):
                st.markdown("---")
                txt = st.text_area("What action was taken?", key=f"sum_{sku}", placeholder="e.g. Revised size chart with supplier")
                if st.button("Submit", key=f"sub_{sku}"):
                    if txt.strip():
                        pc = "is_problematic_rising" if is_rising else "is_problematic"
                        sn, rn, fl = {}, {}, []
                        for _, s in df_sku_size[df_sku_size["sku_prefix"] == sku].iterrows():
                            sn[s["size"]] = int(s.get("parkpalet_stock", 0))
                            rn[s["size"]] = float(s["return_rate"])
                            if s.get(pc, False):
                                fl.append(s["size"])
                        save_action(sku, txt.strip(), sn, rn, float(rate), fl)
                        st.session_state.pop(f"modal_{sku}", None)
                        st.session_state.pop("computed", None)
                        st.rerun()

        elif cta_mode == "revert_waiting":
            ad = get_action(sku)
            if ad:
                created = ad.get("createdOn")
                days = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(created, tz="UTC")).days if created else 0
                st.markdown(f'<div class="progress-card"><b>Action:</b> {ad.get("actionSummary", "N/A")}<br><b>Date:</b> {created.strftime("%d %b %Y") if created else "?"} ({days} days ago)</div>', unsafe_allow_html=True)
            if st.button("↩ Undo action", key=f"rvw_{sku}", use_container_width=False):
                revert_waiting(sku)
                st.session_state.pop("computed", None)
                st.rerun()


# =====================================================================
# TAB 1: NEEDS ATTENTION
# =====================================================================
with tab_att:
    r1, r2, r3, r4, r5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2])
    with r1:
        show_new = st.toggle("New products only", value=False)
    with r2:
        sort_by = st.selectbox("Sort by", ["Priority (impact)", "Sales (highest)", "Severity (worst)", "Newest first"], key="att_sort")
    with r3:
        search = st.text_input("Search", placeholder="Product or SKU", key="att_search")
    with r4:
        cats = sorted(needs_attention["category_l3"].dropna().unique().tolist())
        sel_cat = st.selectbox("Category", ["All"] + cats, key="att_cat")
    with r5:
        sups = sorted(needs_attention["supplier_name"].dropna().unique().tolist())
        sel_sup = st.selectbox("Supplier", ["All"] + sups, key="att_sup")

    display = rising_stars.copy() if show_new else needs_attention.copy()
    if sort_by == "Priority (impact)":
        display = display.sort_values("priority_score", ascending=False)
    elif sort_by == "Sales (highest)":
        display = display.sort_values("recent_sold", ascending=False)
    elif sort_by == "Severity (worst)":
        display = display.sort_values("deviation", ascending=False)
    else:
        if "first_order" in display.columns:
            display = display.sort_values("first_order", ascending=False, na_position="last")
    if search:
        q = search.lower()
        display = display[display["sku_prefix"].str.lower().str.contains(q, na=False) | display["product_name"].astype(str).str.lower().str.contains(q, na=False)]
    if sel_cat != "All":
        display = display[display["category_l3"] == sel_cat]
    if sel_sup != "All":
        display = display[display["supplier_name"] == sel_sup]

    st.caption(f"{len(display)} products need attention")
    for _, row in display.iterrows():
        render_product_card(row, is_rising=row["sku_prefix"] in rising_stars["sku_prefix"].values, cta_mode="action")

# =====================================================================
# TAB 2: IN PROGRESS
# =====================================================================
with tab_prog:
    if not waiting_data:
        st.info("No products in progress.")
    else:
        for sku, action in waiting_data.items():
            r = df_sku[df_sku["sku_prefix"] == sku]
            if not r.empty:
                render_product_card(r.iloc[0], cta_mode="revert_waiting")
            else:
                st.markdown(f"**{sku}** — data not found")

# =====================================================================
# TAB 3: RESULTS
# =====================================================================
with tab_res:
    if not fixed_data:
        st.info("No results yet.")
    else:
        for sku, action in fixed_data.items():
            r = df_sku[df_sku["sku_prefix"] == sku]
            name = r.iloc[0]["product_name"] if not r.empty else sku
            img_url = r.iloc[0].get("image_url") if not r.empty else None
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
            old_rates = action.get("returnRateAtAction", {})
            new_rates = action.get("newBatchReturnRate", {})
            new_sales = action.get("newBatchSales", {})
            flagged = action.get("flaggedSizes", [])
            improvements = [s for s in flagged if s in new_rates and new_rates[s] < old_rates.get(s, 0) - 0.02]
            evaluated = [s for s in flagged if s in new_rates]
            if len(improvements) == len(evaluated) and evaluated:
                badge = "✅ Improved"
            elif improvements:
                badge = "🟡 Partial"
            else:
                badge = "🔴 Not improved"

            with st.container(border=True):
                if has_img:
                    ic, mc, bc = st.columns([1, 4, 1])
                else:
                    ic, mc, bc = None, st.columns([5, 1])[0], st.columns([5, 1])[1]
                if ic:
                    with ic:
                        st.image(img_url, width=80)
                with mc:
                    st.markdown(f"**{name}**")
                    st.caption(f"{sku} · Action: {action.get('actionSummary', 'N/A')}")
                with bc:
                    st.markdown(f"<div style='text-align:center; font-size:16px; padding-top:8px;'>{badge}</div>", unsafe_allow_html=True)

                with st.expander("See comparison"):
                    html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
                    html += '<tr style="background:#f8f8f8; font-weight:600; border-bottom:2px solid #ddd;">'
                    for col in ["Size", "Before", "After", "Change", "New Sales"]:
                        html += f'<th style="padding:6px 10px;">{col}</th>'
                    html += '</tr>'
                    for size in sorted(flagged, key=size_sort_key):
                        old = old_rates.get(size, 0)
                        if size in new_rates:
                            new = new_rates[size]
                            d = new - old
                            bg = "background:#ccffcc;" if d < -0.02 else ("background:#ffcccc;" if d > 0.02 else "")
                            html += f'<tr style="{bg} border-bottom:1px solid #eee;"><td style="padding:5px 10px;">{size}</td><td style="padding:5px 10px;">{old:.1%}</td><td style="padding:5px 10px;">{new:.1%}</td><td style="padding:5px 10px;">{d:+.1%}</td><td style="padding:5px 10px;">{new_sales.get(size, 0)}</td></tr>'
                        else:
                            html += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:5px 10px;">{size}</td><td style="padding:5px 10px;">{old:.1%}</td><td style="padding:5px 10px;">Pending</td><td style="padding:5px 10px;">—</td><td style="padding:5px 10px;">{new_sales.get(size, 0)}</td></tr>'
                    html += '</table>'
                    st.markdown(html, unsafe_allow_html=True)

                if st.button("✓ Dismiss — resolved", key=f"dis_{sku}"):
                    dismiss_sku(sku)
                    st.session_state.pop("computed", None)
                    st.toast(f"Dismissed: {name}")

# =====================================================================
# TAB 4: PARKED
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
                        revert_no_action(sku)
                        st.session_state.pop("computed", None)
                        st.rerun()
