"""
Return Investigation Tool — main Streamlit entry point.
Redesigned for non-technical ops users: clarity over completeness.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

# --- Size ordering ---
SIZE_ORDER = [
    "XXS", "XS", "S", "S/M", "M", "M/L", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36",
    "37", "38", "39", "40", "42", "44", "46", "48", "50",
    "ONE SIZE", "STD",
]


def size_sort_key(size):
    try:
        return SIZE_ORDER.index(str(size).upper())
    except ValueError:
        return 999


def issue_label(pct_small, pct_large, pct_quality, pct_other, has_reasons):
    """Convert reason percentages into a plain-English issue label."""
    if not has_reasons:
        return "Not enough data"
    sizing = pct_small + pct_large
    if sizing > 0.1:
        rs = pct_small / max(pct_large, 0.01) if pct_small > 0 else 0
        rl = pct_large / max(pct_small, 0.01) if pct_large > 0 else 0
        if rs >= 3 or (pct_small > 0 and pct_large == 0):
            label = "Runs small"
        elif rl >= 3 or (pct_large > 0 and pct_small == 0):
            label = "Runs large"
        elif rs >= 2:
            label = "Likely runs small"
        elif rl >= 2:
            label = "Likely runs large"
        else:
            label = "Mixed sizing"
        if pct_quality >= 0.25:
            label += " + Quality issue"
        return label
    if pct_quality >= 0.25:
        return "Quality issue"
    return "Mixed feedback"


def severity_badge(n_sizes, return_rate, baseline):
    """Return severity level and color."""
    if n_sizes >= 3 or (baseline > 0 and return_rate > baseline * 2):
        return "🔴 High", "#ffcccc"
    return "🟡 Moderate", "#fff3cd"


# --- Custom CSS ---
st.markdown("""
<style>
    .problem-box { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #e74c3c; background: #fef2f2; }
    .action-box { padding: 12px 16px; border-radius: 8px; background: #f0f9ff; border-left: 4px solid #3b82f6; }
    .progress-card { padding: 12px 16px; border-radius: 8px; background: #fffbeb; border-left: 4px solid #f59e0b; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
h1, h2, h3 = st.columns([5, 1, 1])
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

# --- Load / refresh data ---
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

# --- Compute P75 flagging (once, cached in session) ---
if "computed" not in st.session_state:
    df_sku = data["df_sku"].copy()
    df_sku_size = data["df_sku_size"].copy()

    if df_sku_size is not None and not df_sku_size.empty:
        baseline_pool = df_sku_size[df_sku_size["sold"] >= 20].copy()
        size_p75 = baseline_pool.groupby("category_l3")["return_rate"].quantile(config.BASELINE_PERCENTILE).rename("size_p75")
        df_sku_size = df_sku_size.merge(size_p75, on="category_l3", how="left")
        global_p75 = baseline_pool["return_rate"].quantile(config.BASELINE_PERCENTILE) if not baseline_pool.empty else 0
        df_sku_size["size_p75"] = df_sku_size["size_p75"].fillna(global_p75)
        df_sku_size["is_flagged"] = (df_sku_size["return_rate"] > df_sku_size["size_p75"]) & (df_sku_size["sold"] >= config.MIN_RECENT_SALES_PER_SIZE)

        df_recent_size = data.get("df_recent_size")
        if df_recent_size is not None and not df_recent_size.empty:
            df_sku_size = df_sku_size.merge(df_recent_size[["sku_prefix", "size", "recent_sold"]], on=["sku_prefix", "size"], how="left")
            df_sku_size["recent_sold"] = df_sku_size["recent_sold"].fillna(0).astype(int)
            df_sku_size["qualifies_size"] = df_sku_size["recent_sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        else:
            df_sku_size["recent_sold"] = 0
            df_sku_size["qualifies_size"] = False

        df_sku_size["is_problematic"] = df_sku_size["qualifies_size"] & df_sku_size["is_flagged"]
        df_sku_size["is_flagged_rising"] = (df_sku_size["return_rate"] > df_sku_size["size_p75"]) & (df_sku_size["sold"] >= config.RISING_STAR_MIN_SALES_PER_SIZE)
        df_sku_size["qualifies_rising"] = df_sku_size.get("recent_sold", 0) >= config.RISING_STAR_MIN_SALES_PER_SIZE
        df_sku_size["is_problematic_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_flagged_rising"]

        for col_name, prob_col in [("problematic_sizes", "is_problematic"), ("problematic_sizes_rising", "is_problematic_rising")]:
            counts = df_sku_size[df_sku_size[prob_col]].groupby("sku_prefix")["size"].count().rename(col_name)
            df_sku = df_sku.drop(columns=[col_name], errors="ignore")
            df_sku = df_sku.merge(counts, on="sku_prefix", how="left")
            df_sku[col_name] = df_sku[col_name].fillna(0).astype(int)

    if "parkpalet_stock" not in df_sku_size.columns:
        from engine.pipelines import get_parkpalet_stock
        stock_raw = get_parkpalet_stock()
        if stock_raw:
            df_sku_size = df_sku_size.merge(pd.DataFrame(stock_raw), on=["sku_prefix", "size"], how="left")
            df_sku_size["parkpalet_stock"] = df_sku_size["parkpalet_stock"].fillna(0).astype(int)
        else:
            df_sku_size["parkpalet_stock"] = 0

    check_transitions(df_sku_size)
    excluded = get_excluded_skus()

    rising_stars = df_sku[(df_sku["problematic_sizes_rising"] > 0) & (df_sku["is_rising_star"] == True) & (~df_sku["sku_prefix"].isin(excluded))].copy()
    bestsellers = df_sku[(df_sku["problematic_sizes"] > 0) & (~df_sku["sku_prefix"].isin(rising_stars["sku_prefix"])) & (~df_sku["sku_prefix"].isin(excluded))].copy()

    # Combine for "Needs Attention"
    needs_attention = pd.concat([bestsellers, rising_stars]).drop_duplicates(subset="sku_prefix")

    st.session_state["computed"] = {
        "df_sku": df_sku, "df_sku_size": df_sku_size,
        "bestsellers": bestsellers, "rising_stars": rising_stars,
        "needs_attention": needs_attention,
    }

comp = st.session_state["computed"]
df_sku = comp["df_sku"]
df_sku_size = comp["df_sku_size"]
needs_attention = comp["needs_attention"]
rising_stars = comp["rising_stars"]
bestsellers = comp["bestsellers"]

waiting_data = get_skus_by_status("waiting_for_fix")
fixed_data = get_skus_by_status("fixed")
parked_data = get_skus_by_status("no_action")

# --- Tabs ---
tab_attention, tab_progress, tab_results = st.tabs([
    f"Needs Attention ({len(needs_attention)})",
    f"In Progress ({len(waiting_data)})",
    f"Results ({len(fixed_data)})",
])


# =====================================================================
# HELPERS
# =====================================================================

def get_sku_problem_summary(sku_prefix, is_rising=False):
    """Get a plain-English problem description for a SKU."""
    prob_col = "is_problematic_rising" if is_rising else "is_problematic"
    min_reasons = config.RISING_STAR_MIN_SALES_PER_SIZE if is_rising else config.MIN_RECENT_SALES_PER_SIZE
    sizes = df_sku_size[df_sku_size["sku_prefix"] == sku_prefix]
    if sizes.empty:
        return ""

    all_data = sizes.apply(lambda s: {
        "size": s["size"], "is_flagged": s.get(prob_col, False),
        "pct_small": s.get("pct_too_small", 0) if s.get("reason_count", 0) >= min_reasons else 0,
        "pct_large": s.get("pct_too_large", 0) if s.get("reason_count", 0) >= min_reasons else 0,
        "pct_quality": s.get("pct_quality", 0) if s.get("reason_count", 0) >= min_reasons else 0,
        "stock": s.get("parkpalet_stock", 0),
    }, axis=1).tolist()
    return sku_summary(all_data)


def render_size_table(sku_prefix, is_rising=False, show_details=False):
    """Render size table — simplified or detailed."""
    prob_col = "is_problematic_rising" if is_rising else "is_problematic"
    min_reasons = config.RISING_STAR_MIN_SALES_PER_SIZE if is_rising else config.MIN_RECENT_SALES_PER_SIZE

    sku_sizes = df_sku_size[df_sku_size["sku_prefix"] == sku_prefix].copy()
    if sku_sizes.empty:
        return

    sku_sizes["_sort"] = sku_sizes["size"].apply(size_sort_key)
    sku_sizes = sku_sizes.sort_values("_sort")

    p75 = sku_sizes["size_p75"].iloc[0] if "size_p75" in sku_sizes.columns else 0
    if "reason_count" not in sku_sizes.columns:
        sku_sizes["reason_count"] = 0
    if "parkpalet_stock" not in sku_sizes.columns:
        sku_sizes["parkpalet_stock"] = 0

    # Compute issue labels and actions
    sku_sizes["has_reasons"] = sku_sizes["reason_count"] >= min_reasons
    sku_sizes["issue"] = sku_sizes.apply(
        lambda s: issue_label(s.get("pct_too_small", 0), s.get("pct_too_large", 0), s.get("pct_quality", 0), s.get("pct_other", 0), s["has_reasons"]),
        axis=1,
    )
    sku_sizes["action_text"] = sku_sizes.apply(
        lambda s: size_action(s["return_rate"], p75, s.get("pct_too_small", 0), s.get("pct_too_large", 0), s.get("pct_quality", 0), s.get("pct_other", 0), s.get(prob_col, False), s.get("parkpalet_stock", 0), s.get("sold", 0), s.get("reason_count", 0), min_reasons),
        axis=1,
    )

    is_prob = sku_sizes[prob_col].values if prob_col in sku_sizes.columns else [False] * len(sku_sizes)

    # Total row data
    total_sold = sku_sizes["sold"].sum()
    total_returned = sku_sizes.get("returned", pd.Series([0])).sum()
    total_rate = total_returned / total_sold if total_sold > 0 else 0
    total_stock = sku_sizes["parkpalet_stock"].sum()
    total_rc = sku_sizes["reason_count"].sum()
    has_total_reasons = total_rc >= min_reasons
    if has_total_reasons and total_rc > 0:
        rc = sku_sizes["reason_count"]
        ts = (sku_sizes["pct_too_small"] * rc).sum() / total_rc
        tl = (sku_sizes["pct_too_large"] * rc).sum() / total_rc
        tq = (sku_sizes["pct_quality"] * rc).sum() / total_rc
        to = (sku_sizes["pct_other"] * rc).sum() / total_rc
    else:
        ts = tl = tq = to = 0

    total_issue = issue_label(ts, tl, tq, to, has_total_reasons)
    all_data = sku_sizes.apply(lambda s: {"size": s["size"], "is_flagged": s.get(prob_col, False), "pct_small": s.get("pct_too_small", 0) if s["has_reasons"] else 0, "pct_large": s.get("pct_too_large", 0) if s["has_reasons"] else 0, "pct_quality": s.get("pct_quality", 0) if s["has_reasons"] else 0, "stock": s.get("parkpalet_stock", 0)}, axis=1).tolist()
    total_action = sku_summary(all_data)
    if not total_action and not has_total_reasons:
        total_action = "High return rate. Not enough data to diagnose."

    # Build HTML table
    if show_details:
        cols = ["Size", "Sold", "Returns", "Return Rate", "Issue", "% Small", "% Large", "% Quality", "% Other", "Stock", "Action"]
    else:
        cols = ["Size", "Sold", "Returns", "Return Rate", "Issue", "Stock", "Action"]

    html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
    html += '<tr style="background:#f8f8f8; font-weight:600; border-bottom:2px solid #ddd;">'
    for c in cols:
        html += f'<th style="padding:6px 8px; text-align:left;">{c}</th>'
    html += '</tr>'

    def fmt_pct(val, has_r):
        return f"{val:.0%}" if has_r and val > 0 else "—"

    rows_data = []
    for i, (_, s) in enumerate(sku_sizes.iterrows()):
        rows_data.append({
            "Size": s["size"], "Sold": int(s["sold"]),
            "Returns": int(s.get("returned", 0)),
            "Return Rate": f"{s['return_rate']:.1%}",
            "Issue": s["issue"],
            "% Small": fmt_pct(s.get("pct_too_small", 0), s["has_reasons"]),
            "% Large": fmt_pct(s.get("pct_too_large", 0), s["has_reasons"]),
            "% Quality": fmt_pct(s.get("pct_quality", 0), s["has_reasons"]),
            "% Other": fmt_pct(s.get("pct_other", 0), s["has_reasons"]),
            "Stock": int(s.get("parkpalet_stock", 0)),
            "Action": s["action_text"],
            "_prob": is_prob[i] if i < len(is_prob) else False,
        })

    # Total row
    rows_data.append({
        "Size": "TOTAL", "Sold": int(total_sold), "Returns": int(total_returned),
        "Return Rate": f"{total_rate:.1%}", "Issue": total_issue,
        "% Small": fmt_pct(ts, has_total_reasons), "% Large": fmt_pct(tl, has_total_reasons),
        "% Quality": fmt_pct(tq, has_total_reasons), "% Other": fmt_pct(to, has_total_reasons),
        "Stock": int(total_stock), "Action": total_action, "_prob": False,
    })

    for i, rd in enumerate(rows_data):
        is_total = rd["Size"] == "TOTAL"
        is_problem = rd["_prob"]

        if is_total:
            bg = "background:#f0f0f0; font-weight:600;"
        elif is_problem:
            bg = "background:#ffcccc;"
        else:
            bg = ""

        html += f'<tr style="{bg} border-bottom:1px solid #eee;">'
        for c in cols:
            val = rd.get(c, "")
            style = "padding:5px 8px; vertical-align:top;"
            if c == "Action":
                style += " white-space:pre-wrap; min-width:180px; font-size:12px;"
            html += f'<td style="{style}">{val}</td>'
        html += '</tr>'

    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)


# =====================================================================
# TAB 1: NEEDS ATTENTION
# =====================================================================
with tab_attention:
    # Toggle: All / New Products
    view_col, filter_col1, filter_col2, filter_col3 = st.columns([1.5, 1.5, 1.5, 1.5])
    with view_col:
        show_new = st.toggle("New products only", value=False)
    with filter_col1:
        search = st.text_input("Search", placeholder="Product name or SKU", key="att_search")
    with filter_col2:
        cats = sorted(needs_attention["category_l3"].dropna().unique().tolist())
        sel_cat = st.selectbox("Category", ["All"] + cats, key="att_cat")
    with filter_col3:
        sups = sorted(needs_attention["supplier_name"].dropna().unique().tolist())
        sel_sup = st.selectbox("Supplier", ["All"] + sups, key="att_sup")

    if show_new:
        display = rising_stars.sort_values("recent_sold", ascending=False)
    else:
        display = needs_attention.sort_values("recent_sold", ascending=False)

    # Apply filters
    if search:
        q = search.lower()
        display = display[display["sku_prefix"].str.lower().str.contains(q, na=False) | display["product_name"].astype(str).str.lower().str.contains(q, na=False)]
    if sel_cat != "All":
        display = display[display["category_l3"] == sel_cat]
    if sel_sup != "All":
        display = display[display["supplier_name"] == sel_sup]

    st.caption(f"{len(display)} products need attention")

    if display.empty:
        st.info("No products match your filters.")
    else:
        for _, row in display.iterrows():
            sku = row["sku_prefix"]
            name = row.get("product_name", sku) or sku
            img_url = row.get("image_url")
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
            is_rising = sku in rising_stars["sku_prefix"].values
            n_prob = int(row.get("problematic_sizes_rising" if is_rising else "problematic_sizes", 0))
            baseline = row.get("category_baseline", 0)
            sev_text, sev_color = severity_badge(n_prob, row.get("return_rate", 0), baseline)

            # --- Card ---
            col_img, col_main, col_sev = st.columns([1, 8, 2])
            with col_img:
                if has_img:
                    st.image(img_url, width=55)
            with col_main:
                line1 = f"**{name}**"
                if is_rising:
                    line1 += " &nbsp; `NEW`"
                st.markdown(line1, unsafe_allow_html=True)
                st.caption(f"{sku} · {row.get('supplier_name', 'N/A')} · {row.get('category_l3', '')}")
            with col_sev:
                st.markdown(f"<div style='text-align:right; font-size:14px;'>{sev_text}<br><span style='font-size:12px; color:#666;'>{n_prob} size{'s' if n_prob != 1 else ''} affected</span></div>", unsafe_allow_html=True)

            with st.expander("Details", expanded=False):
                # CTAs at the top
                c1, c2, c3 = st.columns([1, 1, 4])
                with c1:
                    if st.button("✓ Action taken", key=f"act_{sku}", use_container_width=True):
                        st.session_state[f"modal_{sku}"] = True
                with c2:
                    if st.button("✗ No action possible", key=f"noact_{sku}", use_container_width=True):
                        save_no_action(sku)
                        st.session_state.pop("computed", None)
                        st.rerun()

                # Action modal
                if st.session_state.get(f"modal_{sku}"):
                    st.markdown("---")
                    summary_text = st.text_area("What action was taken?", key=f"sum_{sku}", placeholder="e.g. Revised size chart with supplier")
                    if st.button("Submit", key=f"sub_{sku}"):
                        if summary_text.strip():
                            prob_col = "is_problematic_rising" if is_rising else "is_problematic"
                            snap_stock, snap_rate, flagged = {}, {}, []
                            for _, s in df_sku_size[df_sku_size["sku_prefix"] == sku].iterrows():
                                snap_stock[s["size"]] = int(s.get("parkpalet_stock", 0))
                                snap_rate[s["size"]] = float(s["return_rate"])
                                if s.get(prob_col, False):
                                    flagged.append(s["size"])
                            save_action(sku, summary_text.strip(), snap_stock, snap_rate, float(row.get("return_rate", 0)), flagged)
                            st.session_state.pop(f"modal_{sku}", None)
                            st.session_state.pop("computed", None)
                            st.rerun()

                # Problem summary
                problem = get_sku_problem_summary(sku, is_rising)
                rate_str = f"{row.get('return_rate', 0):.1%}"
                baseline_str = f"{baseline:.1%}"
                st.markdown(f'<div class="problem-box">Return rate: <b>{rate_str}</b> (category norm: {baseline_str}){" — " + problem if problem else ""}</div>', unsafe_allow_html=True)

                # Image + table
                if has_img:
                    ic, tc = st.columns([1, 4])
                else:
                    ic, tc = None, st.container()

                if ic:
                    with ic:
                        st.image(img_url, width=200)

                with tc:
                    show_details = st.checkbox("Show detailed breakdown", key=f"det_{sku}", value=False)
                    render_size_table(sku, is_rising=is_rising, show_details=show_details)

            st.markdown("")  # spacing


# =====================================================================
# TAB 2: IN PROGRESS
# =====================================================================
with tab_progress:
    if not waiting_data:
        st.info("No products in progress. Take action on products in 'Needs Attention' to track them here.")
    else:
        for sku, action in waiting_data.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku
            img_url = sku_row.iloc[0].get("image_url") if not sku_row.empty else None
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")

            created = action.get("createdOn")
            date_str = created.strftime("%d %b %Y") if created else "Unknown"
            days_ago = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(created, tz="UTC")).days if created else 0

            col_img, col_main = st.columns([1, 11])
            with col_img:
                if has_img:
                    st.image(img_url, width=55)
            with col_main:
                st.markdown(f"**{name}**")
                st.caption(f"{sku}")
                st.markdown(f'<div class="progress-card"><b>Action:</b> {action.get("actionSummary", "N/A")}<br><b>Date:</b> {date_str} ({days_ago} days ago)</div>', unsafe_allow_html=True)

                if st.button("↩ Undo action", key=f"rvw_{sku}"):
                    revert_waiting(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()

            st.markdown("")


# =====================================================================
# TAB 3: RESULTS
# =====================================================================
with tab_results:
    if not fixed_data:
        st.info("No results yet. Products will appear here once old stock is sold and new batch has enough sales.")
    else:
        for sku, action in fixed_data.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku
            img_url = sku_row.iloc[0].get("image_url") if not sku_row.empty else None
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")

            old_rates = action.get("returnRateAtAction", {})
            new_rates = action.get("newBatchReturnRate", {})
            new_sales = action.get("newBatchSales", {})
            flagged = action.get("flaggedSizes", [])

            # Determine overall result
            improvements = [s for s in flagged if s in new_rates and new_rates[s] < old_rates.get(s, 0) - 0.02]
            if len(improvements) == len([s for s in flagged if s in new_rates]):
                result_badge = "✅ Improved"
            elif len(improvements) > 0:
                result_badge = "🟡 Partial"
            else:
                result_badge = "🔴 Not improved"

            col_img, col_main, col_result = st.columns([1, 8, 2])
            with col_img:
                if has_img:
                    st.image(img_url, width=55)
            with col_main:
                st.markdown(f"**{name}**")
                st.caption(f"{sku} · Action: {action.get('actionSummary', 'N/A')}")
            with col_result:
                st.markdown(f"<div style='text-align:right; font-size:16px;'>{result_badge}</div>", unsafe_allow_html=True)

            with st.expander("See comparison", expanded=False):
                html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
                html += '<tr style="background:#f8f8f8; font-weight:600; border-bottom:2px solid #ddd;">'
                for c in ["Size", "Before", "After", "Change", "New Sales"]:
                    html += f'<th style="padding:6px 10px; text-align:left;">{c}</th>'
                html += '</tr>'

                for size in sorted(flagged, key=size_sort_key):
                    old = old_rates.get(size, 0)
                    if size in new_rates:
                        new = new_rates[size]
                        delta = new - old
                        bg = "background:#ccffcc;" if delta < -0.02 else ("background:#ffcccc;" if delta > 0.02 else "")
                        change = f"{delta:+.1%}"
                        after = f"{new:.1%}"
                    else:
                        bg = ""
                        change = "—"
                        after = "Pending"

                    html += f'<tr style="{bg} border-bottom:1px solid #eee;">'
                    html += f'<td style="padding:5px 10px;">{size}</td>'
                    html += f'<td style="padding:5px 10px;">{old:.1%}</td>'
                    html += f'<td style="padding:5px 10px;">{after}</td>'
                    html += f'<td style="padding:5px 10px;">{change}</td>'
                    html += f'<td style="padding:5px 10px;">{new_sales.get(size, 0)}</td>'
                    html += '</tr>'

                html += '</table>'
                st.markdown(html, unsafe_allow_html=True)

                st.markdown("")
                if st.button("✓ Dismiss — issue resolved", key=f"dis_{sku}", use_container_width=False):
                    dismiss_sku(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()

            st.markdown("")

# --- Parked (small section at bottom) ---
if parked_data:
    with st.expander(f"Parked — no action possible ({len(parked_data)} products)", expanded=False):
        for sku in parked_data:
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{sku}** — {name}")
            with c2:
                if st.button("Revert", key=f"rvn_{sku}"):
                    revert_no_action(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()
