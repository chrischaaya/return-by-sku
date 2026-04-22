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
    get_excluded_skus, get_skus_by_status, check_transitions, get_action,
)

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
h1, h2 = st.columns([4, 1])
with h1:
    st.title("Return Investigation Tool")
with h2:
    should_update = st.button("Update Data", use_container_width=True)

# --- Load / refresh data ---
if should_update or "data" not in st.session_state:
    with st.spinner("Loading data from MongoDB..."):
        st.session_state["data"] = load_data()
        st.session_state.pop("computed", None)
    st.toast("Data loaded!")

data = st.session_state.get("data")

if data is None:
    st.info("Click 'Update Data' to load the dashboard.")
    st.stop()

# --- Compute P75 flagging (once, cached) ---
if "computed" not in st.session_state or should_update:
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

        # Problem counts
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

    # Check transitions for waiting_for_fix SKUs
    check_transitions(df_sku_size)

    # Exclude actioned SKUs from bestsellers/rising stars
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

# --- Counts for tabs ---
waiting_count = len(get_skus_by_status("waiting_for_fix"))
fixed_count = len(get_skus_by_status("fixed"))
no_action_count = len(get_skus_by_status("no_action"))

# --- Tabs ---
tab_best, tab_rising, tab_waiting, tab_fixed, tab_noaction = st.tabs([
    f"Bestsellers ({len(bestsellers)})",
    f"Rising Stars ({len(rising_stars)})",
    f"Waiting for Fix ({waiting_count})",
    f"Fixed ({fixed_count})",
    f"No Action ({no_action_count})",
])


# =====================================================================
# SHARED: Render SKU list with size table
# =====================================================================
def render_sku_list(display, is_rising=False, show_actions=True):
    """Render a list of SKUs with expandable size tables."""
    if display.empty:
        st.info("No SKUs in this view.")
        return

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        search = st.text_input("Search", value="", placeholder="SKU or product name", key=f"search_{is_rising}")
    with f2:
        categories = sorted(display["category_l3"].dropna().unique().tolist())
        selected_cat = st.selectbox("Category", ["All"] + categories, key=f"cat_{is_rising}")
    with f3:
        suppliers = sorted(display["supplier_name"].dropna().unique().tolist())
        selected_supplier = st.selectbox("Supplier", ["All"] + suppliers, key=f"sup_{is_rising}")

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

    problematic_col = "is_problematic_rising" if is_rising else "is_problematic"
    min_reasons = config.RISING_STAR_MIN_SALES_PER_SIZE if is_rising else config.MIN_RECENT_SALES_PER_SIZE

    for _, row in display.iterrows():
        name = row.get("product_name", row["sku_prefix"])
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
                f"**{row['sku_prefix']}** — {name} — "
                f"Last 30d: {row['recent_sold']:,} sold — "
                f"**{n_problems} problematic size{'s' if n_problems != 1 else ''}**"
            )
            if is_rising and pd.notna(row.get("first_order")):
                first_order = pd.to_datetime(row["first_order"])
                label += f" — First sale: {first_order.strftime('%d %b %Y')}"

            with st.expander(label, expanded=False):
                if df_sku_size is not None and not df_sku_size.empty:
                    sku_sizes = df_sku_size[df_sku_size["sku_prefix"] == row["sku_prefix"]].copy()

                    if has_img:
                        img_col, table_col = st.columns([1, 4])
                    else:
                        img_col = None
                        table_col = st.container()

                    if img_col is not None:
                        with img_col:
                            st.image(img_url, width=200)

                    with table_col:
                        if not sku_sizes.empty:
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

                            def highlight_problems(row_df):
                                idx = list(size_display.index).index(row_df.name)
                                if idx < len(is_prob) and is_prob[idx]:
                                    return ["background-color: #ffcccc"] * len(row_df)
                                return [""] * len(row_df)

                            styled = size_display.style.apply(highlight_problems, axis=1)
                            st.dataframe(styled, use_container_width=True, hide_index=True)

                            # SKU summary
                            _prob_col = problematic_col if problematic_col in sku_sizes.columns else "is_problematic"
                            all_size_data = sku_sizes.apply(
                                lambda s: {
                                    "size": s["size"],
                                    "is_flagged": s.get(_prob_col, False),
                                    "has_enough_reasons": s.get("reason_count", 0) >= min_reasons,
                                    "pct_small": s.get("pct_too_small", 0) if s.get("reason_count", 0) >= min_reasons else 0,
                                    "pct_large": s.get("pct_too_large", 0) if s.get("reason_count", 0) >= min_reasons else 0,
                                    "pct_quality": s.get("pct_quality", 0) if s.get("reason_count", 0) >= min_reasons else 0,
                                    "stock": s.get("parkpalet_stock", 0),
                                },
                                axis=1,
                            ).tolist()

                            summary = sku_summary(all_size_data)
                            if summary:
                                st.markdown(f"**Summary:** {summary}")

                # Action buttons
                if show_actions:
                    b1, b2, _ = st.columns([1, 1, 4])
                    with b1:
                        if st.button("Action taken", key=f"act_{row['sku_prefix']}"):
                            st.session_state[f"modal_{row['sku_prefix']}"] = True
                    with b2:
                        if st.button("No action possible", key=f"noact_{row['sku_prefix']}"):
                            save_no_action(row["sku_prefix"])
                            st.session_state.pop("computed", None)
                            st.rerun()

                    # Modal for action summary
                    if st.session_state.get(f"modal_{row['sku_prefix']}"):
                        summary_text = st.text_area(
                            "What action was taken?",
                            key=f"summary_{row['sku_prefix']}",
                            placeholder="e.g. Adjusted size chart, contacted supplier for measurement review",
                        )
                        if st.button("Submit", key=f"submit_{row['sku_prefix']}"):
                            if summary_text.strip():
                                stock_snap = {}
                                rate_snap = {}
                                flagged = []
                                if df_sku_size is not None:
                                    ss = df_sku_size[df_sku_size["sku_prefix"] == row["sku_prefix"]]
                                    for _, s in ss.iterrows():
                                        stock_snap[s["size"]] = int(s.get("parkpalet_stock", 0))
                                        rate_snap[s["size"]] = float(s["return_rate"])
                                        if s.get(problematic_col, False):
                                            flagged.append(s["size"])

                                save_action(
                                    row["sku_prefix"], summary_text.strip(),
                                    stock_snap, rate_snap,
                                    float(row.get("return_rate", 0)), flagged,
                                )
                                st.session_state.pop(f"modal_{row['sku_prefix']}", None)
                                st.session_state.pop("computed", None)
                                st.rerun()


# =====================================================================
# TAB 1: Bestsellers
# =====================================================================
with tab_best:
    display = bestsellers.sort_values("recent_sold", ascending=False)
    st.caption(
        f"Criteria: ≥{config.MIN_RECENT_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(display)} SKUs."
    )
    render_sku_list(display, is_rising=False)

# =====================================================================
# TAB 2: Rising Stars
# =====================================================================
with tab_rising:
    display = rising_stars.sort_values("recent_sold", ascending=False)
    st.caption(
        f"Criteria: launched in last {config.RISING_STAR_MAX_AGE_DAYS} days + "
        f"≥{config.RISING_STAR_MIN_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(display)} SKUs."
    )
    render_sku_list(display, is_rising=True)

# =====================================================================
# TAB 3: Waiting for Fix
# =====================================================================
with tab_waiting:
    st.caption("SKUs where action has been taken. Waiting for old stock to sell through and new batch to arrive.")

    waiting = get_skus_by_status("waiting_for_fix")
    if not waiting:
        st.info("No SKUs waiting for fix.")
    else:
        for sku, action_data in waiting.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku

            with st.expander(f"**{sku}** — {name} — Action: {action_data.get('actionSummary', 'N/A')}", expanded=False):
                st.markdown(f"**Action taken:** {action_data.get('actionSummary', 'N/A')}")
                st.markdown(f"**Date:** {action_data['createdOn'].strftime('%d %b %Y')}")
                st.markdown(f"**Return rate at action:** {action_data.get('overallRateAtAction', 0):.1%}")

                # Stock depletion progress
                stock_at = action_data.get("stockAtAction", {})
                depleted = action_data.get("oldStockDepletedOn", {})
                new_stock = action_data.get("newStockFirstSeenOn", {})

                if stock_at:
                    st.markdown("**Stock depletion progress:**")
                    progress_data = []
                    for size, initial in stock_at.items():
                        status = "Depleted" if size in depleted else "Selling"
                        if size in new_stock:
                            status = "New batch received"
                        progress_data.append({
                            "Size": size,
                            "Stock at action": initial,
                            "Status": status,
                        })
                    st.dataframe(pd.DataFrame(progress_data), use_container_width=True, hide_index=True)

# =====================================================================
# TAB 4: Fixed
# =====================================================================
with tab_fixed:
    st.caption("New batch has enough sales to evaluate. Compare before vs after.")

    fixed = get_skus_by_status("fixed")
    if not fixed:
        st.info("No SKUs in fixed state yet.")
    else:
        for sku, action_data in fixed.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku

            with st.expander(f"**{sku}** — {name}", expanded=False):
                st.markdown(f"**Action:** {action_data.get('actionSummary', 'N/A')}")
                st.markdown(f"**Fixed on:** {action_data.get('fixedOn', '').strftime('%d %b %Y') if action_data.get('fixedOn') else 'N/A'}")

                # Before / After comparison
                old_rates = action_data.get("returnRateAtAction", {})
                new_rates = action_data.get("newBatchReturnRate", {})
                new_sales = action_data.get("newBatchSales", {})
                flagged = action_data.get("flaggedSizes", [])

                comparison = []
                for size in flagged:
                    old_rate = old_rates.get(size, 0)
                    if size in new_rates:
                        new_rate = new_rates[size]
                        delta = new_rate - old_rate
                        comparison.append({
                            "Size": size,
                            "Old Return Rate": f"{old_rate:.1%}",
                            "New Return Rate": f"{new_rate:.1%}",
                            "Change": f"{delta:+.1%}",
                            "New Sales": new_sales.get(size, 0),
                        })
                    else:
                        comparison.append({
                            "Size": size,
                            "Old Return Rate": f"{old_rate:.1%}",
                            "New Return Rate": "Not enough data yet",
                            "Change": "—",
                            "New Sales": new_sales.get(size, 0),
                        })

                if comparison:
                    st.dataframe(pd.DataFrame(comparison), use_container_width=True, hide_index=True)

                if st.button("Dismiss", key=f"dismiss_{sku}"):
                    dismiss_sku(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()

# =====================================================================
# TAB 5: No Action
# =====================================================================
with tab_noaction:
    st.caption("SKUs marked as 'no action possible'. Click Revert to put back in main views.")

    no_actions = get_skus_by_status("no_action")
    if not no_actions:
        st.info("No SKUs in this list.")
    else:
        for sku, action_data in no_actions.items():
            sku_row = df_sku[df_sku["sku_prefix"] == sku]
            name = sku_row.iloc[0]["product_name"] if not sku_row.empty else sku

            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{sku}** — {name}")
            with col2:
                if st.button("Revert", key=f"revert_{sku}"):
                    revert_no_action(sku)
                    st.session_state.pop("computed", None)
                    st.rerun()
