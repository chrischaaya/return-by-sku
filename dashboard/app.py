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
    st.toast("Data loaded!")

data = st.session_state.get("data")

if data is None:
    st.info("Click 'Update Data' to load the dashboard.")
    st.stop()

# --- Compute P75 flagging (once, cached in session state) ---
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
                on=["sku_prefix", "size"],
                how="left",
            )
            df_sku_size["recent_sold"] = df_sku_size["recent_sold"].fillna(0).astype(int)
            df_sku_size["qualifies_size"] = df_sku_size["recent_sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        else:
            df_sku_size["recent_sold"] = 0
            df_sku_size["qualifies_size"] = False

        df_sku_size["is_problematic"] = df_sku_size["qualifies_size"] & df_sku_size["is_flagged"]

        problem_counts = (
            df_sku_size[df_sku_size["is_problematic"]]
            .groupby("sku_prefix")["size"]
            .count()
            .rename("problematic_sizes")
        )
        df_sku = df_sku.drop(columns=["problematic_sizes"], errors="ignore")
        df_sku = df_sku.merge(problem_counts, on="sku_prefix", how="left")
        df_sku["problematic_sizes"] = df_sku["problematic_sizes"].fillna(0).astype(int)

    # Ensure parkpalet_stock survived merges
    if "parkpalet_stock" not in df_sku_size.columns:
        from engine.pipelines import get_parkpalet_stock
        stock_raw = get_parkpalet_stock()
        if stock_raw:
            df_stock = pd.DataFrame(stock_raw)
            df_sku_size = df_sku_size.merge(df_stock, on=["sku_prefix", "size"], how="left")
            df_sku_size["parkpalet_stock"] = df_sku_size["parkpalet_stock"].fillna(0).astype(int)
        else:
            df_sku_size["parkpalet_stock"] = 0

    # Rising stars: use lower threshold (5 sales/size)
    df_sku_size["is_flagged_rising"] = (
        (df_sku_size["return_rate"] > df_sku_size["size_p75"])
        & (df_sku_size["sold"] >= config.RISING_STAR_MIN_SALES_PER_SIZE)
    )
    if "recent_sold" in df_sku_size.columns:
        df_sku_size["qualifies_rising"] = df_sku_size["recent_sold"] >= config.RISING_STAR_MIN_SALES_PER_SIZE
    else:
        df_sku_size["qualifies_rising"] = False
    df_sku_size["is_problematic_rising"] = df_sku_size["qualifies_rising"] & df_sku_size["is_flagged_rising"]

    rising_problem_counts = (
        df_sku_size[df_sku_size["is_problematic_rising"]]
        .groupby("sku_prefix")["size"]
        .count()
        .rename("problematic_sizes_rising")
    )
    df_sku = df_sku.drop(columns=["problematic_sizes_rising"], errors="ignore")
    df_sku = df_sku.merge(rising_problem_counts, on="sku_prefix", how="left")
    df_sku["problematic_sizes_rising"] = df_sku["problematic_sizes_rising"].fillna(0).astype(int)

    # Split: rising stars use lower threshold, bestsellers use standard
    rising_stars = df_sku[
        (df_sku["is_rising_star"] == True) & (df_sku["problematic_sizes_rising"] > 0)
    ].copy()
    bestsellers = df_sku[
        (df_sku["problematic_sizes"] > 0)
        & (~df_sku["sku_prefix"].isin(rising_stars["sku_prefix"]))
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

# --- View selector ---
view = st.radio(
    "View",
    [f"Bestsellers ({len(bestsellers)})", f"Rising Stars ({len(rising_stars)})"],
    horizontal=True,
)

# --- Filters ---
f1, f2, f3 = st.columns(3)
with f1:
    search = st.text_input("Search SKU or product name", value="", placeholder="e.g. MBAJ1ZFU01 or dress")
with f2:
    categories = sorted(df_sku["category_l3"].dropna().unique().tolist())
    selected_cat = st.selectbox("Category", ["All"] + categories)
with f3:
    suppliers = sorted(df_sku["supplier_name"].dropna().unique().tolist())
    selected_supplier = st.selectbox("Supplier", ["All"] + suppliers)

if "Bestsellers" in view:
    display = bestsellers.sort_values("recent_sold", ascending=False)
    st.caption(
        f"Criteria: ≥{config.MIN_RECENT_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(display)} SKUs."
    )
else:
    display = rising_stars.sort_values("recent_sold", ascending=False)
    st.caption(
        f"Criteria: launched in last {config.RISING_STAR_MAX_AGE_DAYS} days + ≥{config.RISING_STAR_MIN_SALES_PER_SIZE} sales/size in last 30 days + return rate above category P75. "
        f"Sorted by sales. {len(display)} SKUs."
    )

# --- Apply filters ---
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
    st.info("No SKUs match this view with current filters.")
else:
    for _, row in display.iterrows():
        name = row.get("product_name", row["sku_prefix"])
        if name and len(str(name)) > 60:
            name = str(name)[:60] + "..."

        img_url = row.get("image_url")
        has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
        is_rising = "Rising" in view
        n_problems = int(row.get("problematic_sizes_rising" if is_rising else "problematic_sizes", 0))
        problematic_col = "is_problematic_rising" if is_rising else "is_problematic"

        # --- Collapsed row ---
        col_img, col_info = st.columns([1, 11])
        with col_img:
            if has_img:
                st.image(img_url, width=60)
        with col_info:
            with st.expander(
                f"**{row['sku_prefix']}** — {name} — "
                f"Last 30d: {row['recent_sold']:,} sold — "
                f"**{n_problems} problematic size{'s' if n_problems != 1 else ''}**",
                expanded=False,
            ):
                # --- Expanded: image + size table ---
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

                            # Generate actions
                            sku_sizes["action"] = sku_sizes.apply(
                                lambda s: size_action(
                                    s["return_rate"], p75_val,
                                    s.get("pct_too_small", 0),
                                    s.get("pct_too_large", 0),
                                    s.get("pct_quality", 0),
                                    s.get("pct_other", 0),
                                    s.get(problematic_col, False),
                                    s.get("parkpalet_stock", 0),
                                ),
                                axis=1,
                            )

                            is_problematic = sku_sizes[problematic_col].values if problematic_col in sku_sizes.columns else sku_sizes["is_problematic"].values

                            if "parkpalet_stock" not in sku_sizes.columns:
                                sku_sizes["parkpalet_stock"] = 0

                            size_display = sku_sizes[[
                                "size", "sold", "return_rate",
                                "pct_too_small", "pct_too_large", "pct_quality", "pct_other",
                                "parkpalet_stock", "action"
                            ]].copy()

                            size_display["return_rate"] = size_display["return_rate"].apply(lambda x: f"{x:.1%}")
                            size_display["pct_too_small"] = size_display["pct_too_small"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_too_large"] = size_display["pct_too_large"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_quality"] = size_display["pct_quality"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_other"] = size_display["pct_other"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display.columns = [
                                "Size", "Sold", "Return Rate",
                                "% Too Small", "% Too Large", "% Quality", "% Other",
                                "Stock", "Action"
                            ]

                            def highlight_problems(row_df):
                                idx = list(size_display.index).index(row_df.name)
                                if idx < len(is_problematic) and is_problematic[idx]:
                                    return ["background-color: #ffcccc"] * len(row_df)
                                return [""] * len(row_df)

                            styled = size_display.style.apply(highlight_problems, axis=1)
                            st.dataframe(styled, use_container_width=True, hide_index=True)

                            # SKU-level summary if pattern is consistent
                            _prob_col = problematic_col if problematic_col in sku_sizes.columns else "is_problematic"
                            flagged_data = sku_sizes[sku_sizes[_prob_col] == True].apply(
                                lambda s: {
                                    "size": s["size"],
                                    "is_flagged": True,
                                    "pct_small": s.get("pct_too_small", 0),
                                    "pct_large": s.get("pct_too_large", 0),
                                    "pct_quality": s.get("pct_quality", 0),
                                    "stock": s.get("parkpalet_stock", 0),
                                },
                                axis=1,
                            ).tolist()

                            summary = sku_summary(flagged_data)
                            if summary:
                                st.markdown(f"**Summary:** {summary}")
