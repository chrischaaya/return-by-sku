"""
Return Investigation Tool — main Streamlit entry point.
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
    check_transitions, seed_test_scenarios,
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


# --- Header ---
h1, h2, h3 = st.columns([4, 1, 1])
with h1:
    st.title("Return Investigation Tool")
    st.caption(f"Data: {get_cache_age()}")
with h2:
    should_update = st.button("Update Data", use_container_width=True)
with h3:
    if st.button("Load Test Data", use_container_width=True):
        seed_test_scenarios()
        st.session_state.pop("computed", None)
        st.toast("Test scenarios loaded!")

# --- Load / refresh data ---
if should_update:
    # Full refresh: recompute from source collections and save to cache
    with st.spinner("Recomputing data from MongoDB... (this may take ~30s)"):
        st.session_state["data"] = load_data()
        save_cache(st.session_state["data"])
        st.session_state.pop("computed", None)
    st.toast("Data updated and cached!")
elif "data" not in st.session_state:
    # First load: try cache first, fall back to full computation
    cached = load_cache()
    if cached and cached.get("updatedOn"):
        st.session_state["data"] = cached
        st.toast(f"Loaded from cache ({get_cache_age()})")
    else:
        with st.spinner("First load — computing from MongoDB... (this may take ~30s)"):
            st.session_state["data"] = load_data()
            save_cache(st.session_state["data"])
            st.session_state.pop("computed", None)
        st.toast("Data computed and cached!")

data = st.session_state.get("data")

if data is None:
    st.info("Click 'Update Data' to load the dashboard.")
    st.stop()

# --- Compute P75 flagging (once, cached) ---
if "computed" not in st.session_state:
    df_sku = data["df_sku"].copy()
    df_sku_size = data["df_sku_size"].copy()

    if df_sku_size is not None and not df_sku_size.empty:
        baseline_pool = df_sku_size[df_sku_size["sold"] >= 20].copy()
        size_p75 = baseline_pool.groupby("category_l3")["return_rate"].quantile(config.BASELINE_PERCENTILE).rename("size_p75")
        df_sku_size = df_sku_size.merge(size_p75, on="category_l3", how="left")
        global_p75 = baseline_pool["return_rate"].quantile(config.BASELINE_PERCENTILE) if not baseline_pool.empty else 0
        df_sku_size["size_p75"] = df_sku_size["size_p75"].fillna(global_p75)
        df_sku_size["is_flagged"] = (
            (df_sku_size["return_rate"] > df_sku_size["size_p75"])
            & (df_sku_size["sold"] >= config.MIN_RECENT_SALES_PER_SIZE)
        )

        df_recent_size = data.get("df_recent_size")
        if df_recent_size is not None and not df_recent_size.empty:
            df_sku_size = df_sku_size.merge(
                df_recent_size[["sku_prefix", "size", "recent_sold"]],
                on=["sku_prefix", "size"], how="left",
            )
            df_sku_size["recent_sold"] = df_sku_size["recent_sold"].fillna(0).astype(int)
            df_sku_size["qualifies_size"] = df_sku_size["recent_sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        else:
            df_sku_size["recent_sold"] = 0
            df_sku_size["qualifies_size"] = False

        df_sku_size["is_problematic"] = df_sku_size["qualifies_size"] & df_sku_size["is_flagged"]

        # Rising stars lower threshold
        df_sku_size["is_flagged_rising"] = (
            (df_sku_size["return_rate"] > df_sku_size["size_p75"])
            & (df_sku_size["sold"] >= config.RISING_STAR_MIN_SALES_PER_SIZE)
        )
        df_sku_size["qualifies_rising"] = df_sku_size.get("recent_sold", 0) >= config.RISING_STAR_MIN_SALES_PER_SIZE
        df_sku_size["is_problematic_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_flagged_rising"]

        for col_name, prob_col in [("problematic_sizes", "is_problematic"), ("problematic_sizes_rising", "is_problematic_rising")]:
            counts = df_sku_size[df_sku_size[prob_col]].groupby("sku_prefix")["size"].count().rename(col_name)
            df_sku = df_sku.drop(columns=[col_name], errors="ignore")
            df_sku = df_sku.merge(counts, on="sku_prefix", how="left")
            df_sku[col_name] = df_sku[col_name].fillna(0).astype(int)

    # Ensure parkpalet_stock
    if "parkpalet_stock" not in df_sku_size.columns:
        from engine.pipelines import get_parkpalet_stock
        stock_raw = get_parkpalet_stock()
        if stock_raw:
            df_stock = pd.DataFrame(stock_raw)
            df_sku_size = df_sku_size.merge(df_stock, on=["sku_prefix", "size"], how="left")
            df_sku_size["parkpalet_stock"] = df_sku_size["parkpalet_stock"].fillna(0).astype(int)
        else:
            df_sku_size["parkpalet_stock"] = 0

    # Check transitions
    check_transitions(df_sku_size)

    # Exclude actioned SKUs
    excluded = get_excluded_skus()

    rising_stars = df_sku[
        (df_sku["problematic_sizes_rising"] > 0)
        & (df_sku["is_rising_star"] == True)
        & (~df_sku["sku_prefix"].isin(excluded))
    ].copy()
    bestsellers = df_sku[
        (df_sku["problematic_sizes"] > 0)
        & (~df_sku["sku_prefix"].isin(rising_stars["sku_prefix"]))
        & (~df_sku["sku_prefix"].isin(excluded))
    ].copy()

    st.session_state["computed"] = {
        "df_sku": df_sku,
        "df_sku_size": df_sku_size,
        "bestsellers": bestsellers,
        "rising_stars": rising_stars,
    }

computed = st.session_state["computed"]
df_sku = computed["df_sku"]
df_sku_size = computed["df_sku_size"]
bestsellers = computed["bestsellers"]
rising_stars = computed["rising_stars"]

# Counts
waiting_skus = get_skus_by_status("waiting_for_fix")
fixed_skus = get_skus_by_status("fixed")
no_action_skus = get_skus_by_status("no_action")

# --- Tabs ---
tab_best, tab_rising, tab_waiting, tab_fixed, tab_noaction = st.tabs([
    f"Bestsellers ({len(bestsellers)})",
    f"Rising Stars ({len(rising_stars)})",
    f"Waiting for Fix ({len(waiting_skus)})",
    f"Fixed ({len(fixed_skus)})",
    f"No Action ({len(no_action_skus)})",
])


# =====================================================================
# SHARED: Render size table for a SKU
# =====================================================================
def render_size_table(sku_prefix, is_rising=False):
    """Render the size breakdown table for a SKU."""
    problematic_col = "is_problematic_rising" if is_rising else "is_problematic"
    min_reasons = config.RISING_STAR_MIN_SALES_PER_SIZE if is_rising else config.MIN_RECENT_SALES_PER_SIZE

    sku_sizes = df_sku_size[df_sku_size["sku_prefix"] == sku_prefix].copy()
    if sku_sizes.empty:
        return

    sku_sizes["_sort"] = sku_sizes["size"].apply(size_sort_key)
    sku_sizes = sku_sizes.sort_values("_sort")

    p75_val = sku_sizes["size_p75"].iloc[0] if "size_p75" in sku_sizes.columns else 0

    if "reason_count" not in sku_sizes.columns:
        sku_sizes["reason_count"] = 0
    if "parkpalet_stock" not in sku_sizes.columns:
        sku_sizes["parkpalet_stock"] = 0

    sku_sizes["action"] = sku_sizes.apply(
        lambda s: size_action(
            s["return_rate"], p75_val,
            s.get("pct_too_small", 0), s.get("pct_too_large", 0),
            s.get("pct_quality", 0), s.get("pct_other", 0),
            s.get(problematic_col, False),
            s.get("parkpalet_stock", 0), s.get("sold", 0),
            s.get("reason_count", 0), min_reasons,
        ),
        axis=1,
    )

    sku_sizes["has_enough_reasons"] = sku_sizes["reason_count"] >= min_reasons
    is_prob = sku_sizes[problematic_col].values if problematic_col in sku_sizes.columns else sku_sizes["is_problematic"].values

    size_display = sku_sizes[[
        "size", "sold", "return_rate",
        "pct_too_small", "pct_too_large", "pct_quality", "pct_other",
        "parkpalet_stock", "action", "has_enough_reasons"
    ]].copy()

    # Compute total row
    total_sold = sku_sizes["sold"].sum()
    total_returned = sku_sizes.get("returned", pd.Series([0])).sum()
    total_rate = total_returned / total_sold if total_sold > 0 else 0
    total_stock = sku_sizes["parkpalet_stock"].sum()
    total_reason_count = sku_sizes["reason_count"].sum()
    has_enough_total = total_reason_count >= min_reasons

    # Compute total reason pcts from raw counts
    if has_enough_total and total_reason_count > 0:
        # Weight by each size's reason count
        rc = sku_sizes["reason_count"]
        total_rc = rc.sum()
        if total_rc > 0:
            t_small = (sku_sizes["pct_too_small"] * rc).sum() / total_rc
            t_large = (sku_sizes["pct_too_large"] * rc).sum() / total_rc
            t_quality = (sku_sizes["pct_quality"] * rc).sum() / total_rc
            t_other = (sku_sizes["pct_other"] * rc).sum() / total_rc
        else:
            t_small = t_large = t_quality = t_other = 0
    else:
        t_small = t_large = t_quality = t_other = 0

    # Generate total-level action (SKU summary)
    _prob_col = problematic_col if problematic_col in sku_sizes.columns else "is_problematic"
    all_size_data = sku_sizes.apply(
        lambda s: {
            "size": s["size"],
            "is_flagged": s.get(_prob_col, False),
            "pct_small": s.get("pct_too_small", 0) if s.get("reason_count", 0) >= min_reasons else 0,
            "pct_large": s.get("pct_too_large", 0) if s.get("reason_count", 0) >= min_reasons else 0,
            "pct_quality": s.get("pct_quality", 0) if s.get("reason_count", 0) >= min_reasons else 0,
            "stock": s.get("parkpalet_stock", 0),
        },
        axis=1,
    ).tolist()
    total_action = sku_summary(all_size_data)
    if not total_action and not has_enough_total:
        total_action = "High return rate. Not enough return reason data to diagnose."

    # Format size rows
    size_display["return_rate"] = size_display["return_rate"].apply(lambda x: f"{x:.1%}")
    for col in ["pct_too_small", "pct_too_large", "pct_quality", "pct_other"]:
        size_display[col] = size_display.apply(
            lambda r: f"{r[col]:.0%}" if r["has_enough_reasons"] and r[col] > 0 else "—", axis=1
        )
    size_display = size_display.drop(columns=["has_enough_reasons"])
    size_display.columns = [
        "Size", "Eligible Sales", "Return Rate",
        "% Too Small", "% Too Large", "% Quality", "% Other",
        "Stock", "Action"
    ]

    # Append total row
    total_row = pd.DataFrame([{
        "Size": "TOTAL",
        "Eligible Sales": total_sold,
        "Return Rate": f"{total_rate:.1%}",
        "% Too Small": f"{t_small:.0%}" if has_enough_total and t_small > 0 else "—",
        "% Too Large": f"{t_large:.0%}" if has_enough_total and t_large > 0 else "—",
        "% Quality": f"{t_quality:.0%}" if has_enough_total and t_quality > 0 else "—",
        "% Other": f"{t_other:.0%}" if has_enough_total and t_other > 0 else "—",
        "Stock": total_stock,
        "Action": total_action,
    }])
    size_display = pd.concat([size_display, total_row], ignore_index=True)

    # Mark problematic rows + bold total row
    is_prob_extended = list(is_prob) + [False]

    def highlight_rows(row_df):
        idx = list(size_display.index).index(row_df.name)
        if idx == len(size_display) - 1:  # Total row
            return ["font-weight: bold; background-color: #f0f0f0"] * len(row_df)
        if idx < len(is_prob_extended) and is_prob_extended[idx]:
            return ["background-color: #ffcccc"] * len(row_df)
        return [""] * len(row_df)

    # Build HTML table with wrapping action column
    html = '<table style="width:100%; border-collapse:collapse; font-size:14px;">'
    html += '<tr style="background:#f8f8f8; font-weight:bold; border-bottom:2px solid #ddd;">'
    for col in size_display.columns:
        html += f'<th style="padding:6px 8px; text-align:left;">{col}</th>'
    html += '</tr>'

    for i, (_, row_data) in enumerate(size_display.iterrows()):
        is_total = i == len(size_display) - 1
        is_problem = i < len(is_prob_extended) and is_prob_extended[i]

        if is_total:
            bg = "background:#f0f0f0; font-weight:bold;"
        elif is_problem:
            bg = "background:#ffcccc;"
        else:
            bg = ""

        html += f'<tr style="{bg} border-bottom:1px solid #eee;">'
        for col in size_display.columns:
            val = row_data[col]
            style = "padding:6px 8px; vertical-align:top;"
            if col == "Action":
                style += " white-space:pre-wrap; min-width:200px;"
            html += f'<td style="{style}">{val}</td>'
        html += '</tr>'

    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)


def render_sku_list(display, is_rising=False, cta_mode="action"):
    """
    Render a list of SKUs.
    cta_mode: "action" (bestsellers/rising), "revert_waiting", "revert_noaction", "dismiss", None
    """
    if display.empty:
        st.info("No SKUs in this view.")
        return

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        search = st.text_input("Search", value="", placeholder="SKU or product name", key=f"search_{cta_mode}_{is_rising}")
    with f2:
        categories = sorted(display["category_l3"].dropna().unique().tolist()) if "category_l3" in display.columns else []
        selected_cat = st.selectbox("Category", ["All"] + categories, key=f"cat_{cta_mode}_{is_rising}")
    with f3:
        suppliers = sorted(display["supplier_name"].dropna().unique().tolist()) if "supplier_name" in display.columns else []
        selected_supplier = st.selectbox("Supplier", ["All"] + suppliers, key=f"sup_{cta_mode}_{is_rising}")

    if search:
        q = search.lower()
        display = display[
            display["sku_prefix"].str.lower().str.contains(q, na=False)
            | display["product_name"].astype(str).str.lower().str.contains(q, na=False)
        ]
    if selected_cat != "All":
        display = display[display["category_l3"] == selected_cat]
    if selected_supplier != "All":
        display = display[display["supplier_name"] == selected_supplier]

    if display.empty:
        st.info("No SKUs match filters.")
        return

    for _, row in display.iterrows():
        sku = row["sku_prefix"]
        name = row.get("product_name", sku)
        if name and len(str(name)) > 60:
            name = str(name)[:60] + "..."

        img_url = row.get("image_url")
        has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
        n_problems = int(row.get("problematic_sizes_rising" if is_rising else "problematic_sizes", 0))

        col_img, col_info = st.columns([1, 11])
        with col_img:
            if has_img:
                st.image(img_url, width=60)
        with col_info:
            label = (
                f"**{sku}** — {name} — "
                f"Last 30d: {row['recent_sold']:,} sold — "
                f"**{n_problems} problematic size{'s' if n_problems != 1 else ''}**"
            )
            if is_rising and pd.notna(row.get("first_order")):
                first_order = pd.to_datetime(row["first_order"])
                label += f" — First sale: {first_order.strftime('%d %b %Y')}"

            with st.expander(label, expanded=False):
                # Image + table
                if has_img:
                    img_col, table_col = st.columns([1, 4])
                else:
                    img_col = None
                    table_col = st.container()

                if img_col is not None:
                    with img_col:
                        st.image(img_url, width=200)

                with table_col:
                    # Show action info for waiting_for_fix
                    if cta_mode == "revert_waiting":
                        from engine.actions import get_action
                        action_data = get_action(sku)
                        if action_data:
                            st.markdown(f"**Action taken:** {action_data.get('actionSummary', 'N/A')}")
                            st.markdown(f"**Date:** {action_data['createdOn'].strftime('%d %b %Y %H:%M')}")
                            st.markdown("---")

                    render_size_table(sku, is_rising=is_rising)

                # CTAs
                if cta_mode == "action":
                    b1, b2, _ = st.columns([1, 1, 4])
                    with b1:
                        if st.button("Action taken", key=f"act_{sku}"):
                            st.session_state[f"modal_{sku}"] = True
                    with b2:
                        if st.button("No action possible", key=f"noact_{sku}"):
                            save_no_action(sku)
                            st.session_state.pop("computed", None)
                            st.rerun()

                    if st.session_state.get(f"modal_{sku}"):
                        summary_text = st.text_area(
                            "What action was taken?", key=f"summary_{sku}",
                            placeholder="e.g. Adjusted size chart, contacted supplier",
                        )
                        if st.button("Submit", key=f"submit_{sku}"):
                            if summary_text.strip():
                                problematic_col = "is_problematic_rising" if is_rising else "is_problematic"
                                stock_snap, rate_snap, flagged = {}, {}, []
                                ss = df_sku_size[df_sku_size["sku_prefix"] == sku]
                                for _, s in ss.iterrows():
                                    stock_snap[s["size"]] = int(s.get("parkpalet_stock", 0))
                                    rate_snap[s["size"]] = float(s["return_rate"])
                                    if s.get(problematic_col, False):
                                        flagged.append(s["size"])
                                save_action(sku, summary_text.strip(), stock_snap, rate_snap,
                                           float(row.get("return_rate", 0)), flagged)
                                st.session_state.pop(f"modal_{sku}", None)
                                st.session_state.pop("computed", None)
                                st.rerun()

                elif cta_mode == "revert_waiting":
                    if st.button("Revert action", key=f"revert_w_{sku}"):
                        revert_waiting(sku)
                        st.session_state.pop("computed", None)
                        st.rerun()

                elif cta_mode == "revert_noaction":
                    if st.button("Revert", key=f"revert_n_{sku}"):
                        revert_no_action(sku)
                        st.session_state.pop("computed", None)
                        st.rerun()


# =====================================================================
# TAB 1: Bestsellers
# =====================================================================
with tab_best:
    st.caption(
        f"Criteria: ≥{config.MIN_RECENT_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(bestsellers)} SKUs."
    )
    render_sku_list(bestsellers.sort_values("recent_sold", ascending=False), is_rising=False, cta_mode="action")

# =====================================================================
# TAB 2: Rising Stars
# =====================================================================
with tab_rising:
    st.caption(
        f"Criteria: launched in last {config.RISING_STAR_MAX_AGE_DAYS} days + "
        f"≥{config.RISING_STAR_MIN_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(rising_stars)} SKUs."
    )
    render_sku_list(rising_stars.sort_values("recent_sold", ascending=False), is_rising=True, cta_mode="action")

# =====================================================================
# TAB 3: Waiting for Fix
# =====================================================================
with tab_waiting:
    st.caption("Action taken — waiting for old stock to sell through and new batch to arrive.")
    waiting_data = get_skus_by_status("waiting_for_fix")
    if not waiting_data:
        st.info("No SKUs waiting for fix.")
    else:
        waiting_skus_list = list(waiting_data.keys())
        waiting_display = df_sku[df_sku["sku_prefix"].isin(waiting_skus_list)].copy()
        if waiting_display.empty:
            st.info("No matching SKU data found.")
        else:
            render_sku_list(waiting_display.sort_values("recent_sold", ascending=False), cta_mode="revert_waiting")

# =====================================================================
# TAB 4: Fixed
# =====================================================================
with tab_fixed:
    st.caption("New batch has enough sales to evaluate. Compare before vs after.")
    fixed_data = get_skus_by_status("fixed")
    if not fixed_data:
        st.info("No SKUs in fixed state yet.")
    else:
        for sku, action_data in fixed_data.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku
            img_url = sku_row.iloc[0].get("image_url") if not sku_row.empty else None
            has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")

            col_img, col_info = st.columns([1, 11])
            with col_img:
                if has_img:
                    st.image(img_url, width=60)
            with col_info:
                with st.expander(f"**{sku}** — {name}", expanded=False):
                    st.markdown(f"**Action:** {action_data.get('actionSummary', 'N/A')}")
                    st.markdown(f"**Action date:** {action_data['createdOn'].strftime('%d %b %Y')}")
                    if action_data.get("fixedOn"):
                        st.markdown(f"**Evaluated on:** {action_data['fixedOn'].strftime('%d %b %Y')}")

                    old_rates = action_data.get("returnRateAtAction", {})
                    new_rates = action_data.get("newBatchReturnRate", {})
                    new_sales = action_data.get("newBatchSales", {})
                    flagged = action_data.get("flaggedSizes", [])

                    comparison = []
                    for size in sorted(flagged, key=size_sort_key):
                        old_rate = old_rates.get(size, 0)
                        if size in new_rates:
                            new_rate = new_rates[size]
                            delta = new_rate - old_rate
                            improved = "Yes" if delta < -0.02 else ("No" if delta > 0.02 else "Stable")
                            comparison.append({
                                "Size": size,
                                "Old Return Rate": f"{old_rate:.1%}",
                                "New Return Rate": f"{new_rate:.1%}",
                                "Change": f"{delta:+.1%}",
                                "New Sales": new_sales.get(size, 0),
                                "Improved": improved,
                            })
                        else:
                            comparison.append({
                                "Size": size,
                                "Old Return Rate": f"{old_rate:.1%}",
                                "New Return Rate": "Not enough data",
                                "Change": "—",
                                "New Sales": new_sales.get(size, 0),
                                "Improved": "Pending",
                            })

                    if comparison:
                        comp_df = pd.DataFrame(comparison)

                        def color_improved(row_df):
                            colors = [""] * len(row_df)
                            imp = row_df.get("Improved", "")
                            if imp == "Yes":
                                colors = ["background-color: #ccffcc"] * len(row_df)
                            elif imp == "No":
                                colors = ["background-color: #ffcccc"] * len(row_df)
                            return colors

                        st.dataframe(comp_df.style.apply(color_improved, axis=1), use_container_width=True, hide_index=True)

                    if st.button("Dismiss", key=f"dismiss_{sku}"):
                        dismiss_sku(sku)
                        st.session_state.pop("computed", None)
                        st.rerun()

# =====================================================================
# TAB 5: No Action
# =====================================================================
with tab_noaction:
    st.caption("SKUs marked as 'no action possible'. Click Revert to put back in main views.")
    no_action_data = get_skus_by_status("no_action")
    if not no_action_data:
        st.info("No SKUs in this list.")
    else:
        no_action_list = list(no_action_data.keys())
        no_action_display = df_sku[df_sku["sku_prefix"].isin(no_action_list)].copy()
        if no_action_display.empty:
            st.info("No matching SKU data found.")
        else:
            render_sku_list(no_action_display, cta_mode="revert_noaction")
