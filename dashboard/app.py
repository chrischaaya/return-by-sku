"""
Return Rate Dashboard — main Streamlit entry point.
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
from engine.ai_recommender import generate_all_recommendations

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


def size_action(return_rate, p75, pct_small, pct_large, pct_quality, pct_other, is_flagged):
    """
    Two separate axes:
    1. Sizing: compare too small vs too large. If one is 3x+ the other, it's clear direction.
    2. Quality/other: evaluated independently from sizing.
    """
    if not is_flagged:
        return ""

    issues = []

    # --- Sizing axis ---
    sizing_total = pct_small + pct_large
    if sizing_total > 0.1:
        if pct_small > 0 and (pct_large == 0 or pct_small / max(pct_large, 0.01) >= 3):
            issues.append(f"Runs small ({pct_small:.0%}). Size up or add 'order one size up'.")
        elif pct_large > 0 and (pct_small == 0 or pct_large / max(pct_small, 0.01) >= 3):
            issues.append(f"Runs large ({pct_large:.0%}). Size down or add 'order one size down'.")
        elif pct_small >= 0.15 and pct_large >= 0.15:
            issues.append(f"Inconsistent sizing ({pct_small:.0%} small, {pct_large:.0%} large). Review size chart.")

    # --- Quality/other axis (independent) ---
    if pct_quality >= 0.25:
        issues.append(f"Quality/expectation issue ({pct_quality:.0%}). Review photos, description, fabric.")
    if pct_other >= 0.40 and sizing_total < 0.2:
        issues.append(f"High 'other' returns ({pct_other:.0%}). Check customer reviews.")

    if issues:
        return " | ".join(issues)
    return f"Above P75 ({p75:.0%}). Investigate."


# --- Header ---
h1, h2, h3 = st.columns([4, 1, 1])
with h1:
    st.title("Return Investigation Tool")
with h2:
    lang = st.radio("", ["🇬🇧 EN", "🇹🇷 TR"], horizontal=True, label_visibility="collapsed")
with h3:
    should_update = st.button("Update Data", use_container_width=True)

if "TR" in lang:
    st.caption("💡 To translate: right-click anywhere on the page → 'Translate to Turkish' (Chrome/Edge)")

# --- Load / refresh data ---
if should_update or "data" not in st.session_state:
    with st.spinner("Loading data from MongoDB..."):
        st.session_state["data"] = load_data()
        st.session_state["ai_recs_ready"] = False  # flag to regenerate AI recs
    st.toast("Data loaded!")

data = st.session_state.get("data")

if data is None:
    st.info("Click 'Update Data' to load the dashboard.")
    st.stop()

df_sku = data["df_sku"]
df_sku_size = data["df_sku_size"]

# --- Compute size-level P75 and flag problematic sizes ---
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

# --- Generate AI recommendations (only after Update Data, cached otherwise) ---
if not st.session_state.get("ai_recs_ready", True):
    with st.spinner("Generating AI recommendations..."):
        ai_recs = generate_all_recommendations(df_sku, df_sku_size)
        st.session_state["ai_recs"] = ai_recs
        st.session_state["ai_recs_ready"] = True

# --- Split into bestsellers vs rising stars (mutually exclusive) ---
all_flagged = df_sku[df_sku["problematic_sizes"] > 0].copy()
rising_stars = all_flagged[all_flagged["is_rising_star"] == True]
bestsellers = all_flagged[~all_flagged["sku_prefix"].isin(rising_stars["sku_prefix"])]

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
        f"SKUs with at least one size with ≥{config.MIN_RECENT_SALES_PER_SIZE} sales in last 30 days "
        f"and return rate above category P75. Excludes products launched in last {config.RISING_STAR_MAX_AGE_DAYS} days. "
        f"{len(display)} SKUs."
    )
else:
    display = rising_stars.sort_values("recent_sold", ascending=False)
    st.caption(
        f"Products launched in last {config.RISING_STAR_MAX_AGE_DAYS} days with at least one size "
        f"with ≥{config.MIN_RECENT_SALES_PER_SIZE} sales in last 30 days and return rate above category P75. "
        f"{len(display)} SKUs."
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
        n_problems = int(row.get("problematic_sizes", 0))

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

                            sku_sizes["action"] = sku_sizes.apply(
                                lambda s: size_action(
                                    s["return_rate"], p75_val,
                                    s.get("pct_too_small", 0),
                                    s.get("pct_too_large", 0),
                                    s.get("pct_quality", 0),
                                    s.get("pct_other", 0),
                                    s.get("is_problematic", False),
                                ),
                                axis=1,
                            )

                            size_display = sku_sizes[[
                                "size", "sold", "return_rate",
                                "pct_too_small", "pct_too_large", "pct_quality", "pct_other", "action"
                            ]].copy()

                            is_problematic = sku_sizes["is_problematic"].values

                            size_display["return_rate"] = size_display["return_rate"].apply(lambda x: f"{x:.1%}")
                            size_display["pct_too_small"] = size_display["pct_too_small"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_too_large"] = size_display["pct_too_large"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_quality"] = size_display["pct_quality"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display["pct_other"] = size_display["pct_other"].apply(lambda x: f"{x:.0%}" if x > 0 else "—")
                            size_display.columns = [
                                "Size", "Sold", "Return Rate",
                                "% Too Small", "% Too Large", "% Quality", "% Other", "Action"
                            ]

                            def highlight_problems(row_df):
                                idx = list(size_display.index).index(row_df.name)
                                if idx < len(is_problematic) and is_problematic[idx]:
                                    return ["background-color: #ffcccc"] * len(row_df)
                                return [""] * len(row_df)

                            styled = size_display.style.apply(highlight_problems, axis=1)
                            st.dataframe(styled, use_container_width=True, hide_index=True)

                        # AI recommendation
                        ai_recs = st.session_state.get("ai_recs", {})
                        rec = ai_recs.get(row["sku_prefix"], "")
                        if rec:
                            st.markdown(f"**Recommendation:** {rec}")
