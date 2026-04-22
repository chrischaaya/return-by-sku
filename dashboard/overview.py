"""
Returns Overview Dashboard — standalone app.
Replicates the Looker Studio return dashboard views using MongoDB data.

Run: streamlit run dashboard/overview.py --server.port 8502
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(page_title="Returns Overview", layout="wide", page_icon="📊")

import pandas as pd
import plotly.graph_objects as go

import config
from engine.analyzer import load_data
from engine import pipelines
from engine.cache import load_cache, save_cache, get_cache_age


# ── Data loading ────────────────────────────────────────────────────────

def _load_base_data():
    """Load or reuse the base analyzer data."""
    if "data" not in st.session_state:
        cached = load_cache()
        if cached and cached.get("updatedOn"):
            st.session_state["data"] = cached
        else:
            with st.spinner("Loading base data (~30s)..."):
                st.session_state["data"] = load_data()
                save_cache(st.session_state["data"])
    return st.session_state["data"]


def _load_overview_data(force=False):
    """Load monthly trend + revenue data."""
    if force or "overview" not in st.session_state:
        with st.spinner("Loading overview data..."):
            orders_m = pd.DataFrame(pipelines.get_monthly_orders_summary())
            returns_m = pd.DataFrame(pipelines.get_monthly_returns_summary())

            if not orders_m.empty and not returns_m.empty:
                monthly = orders_m.merge(returns_m, on="month", how="outer").fillna(0)
                monthly["sold"] = monthly["sold"].astype(int)
                monthly["returned"] = monthly["returned"].astype(int)
                monthly["return_rate"] = monthly["returned"] / monthly["sold"].replace(0, 1)
            else:
                monthly = pd.DataFrame(columns=["month", "sold", "returned", "return_rate"])

            rev_raw = pipelines.get_revenue_by_sku()
            df_rev = pd.DataFrame(rev_raw) if rev_raw else pd.DataFrame(
                columns=["sku_prefix", "revenue"]
            )

            st.session_state["overview"] = {"monthly": monthly, "df_rev": df_rev}

    return st.session_state["overview"]


# ── Table builders ──────────────────────────────────────────────────────

def _build_supplier_table(df_sku, df_rev):
    """Supplier return breakdown with monetary columns."""
    if df_sku.empty:
        return pd.DataFrame()

    sku_data = df_sku[["sku_prefix", "total_sold", "total_returned", "supplier_name"]].copy()
    sku_data = sku_data.merge(df_rev, on="sku_prefix", how="left")
    sku_data["revenue"] = sku_data["revenue"].fillna(0)
    sku_data["avg_price"] = sku_data["revenue"] / sku_data["total_sold"].replace(0, 1)
    sku_data["returned_amount"] = sku_data["avg_price"] * sku_data["total_returned"]

    supplier = (
        sku_data[sku_data["supplier_name"].notna()]
        .groupby("supplier_name")
        .agg(
            returned=("total_returned", "sum"),
            delivered=("total_sold", "sum"),
            returned_amount=("returned_amount", "sum"),
            gmv=("revenue", "sum"),
        )
        .reset_index()
    )
    supplier["return_ratio"] = supplier["returned"] / supplier["delivered"].replace(0, 1)
    supplier["pct_value"] = supplier["returned_amount"] / supplier["gmv"].replace(0, 1)
    supplier = supplier.sort_values("return_ratio", ascending=False).reset_index(drop=True)

    total = pd.DataFrame([{
        "supplier_name": "Grand total",
        "returned": supplier["returned"].sum(),
        "delivered": supplier["delivered"].sum(),
        "return_ratio": supplier["returned"].sum() / max(supplier["delivered"].sum(), 1),
        "returned_amount": supplier["returned_amount"].sum(),
        "gmv": supplier["gmv"].sum(),
        "pct_value": supplier["returned_amount"].sum() / max(supplier["gmv"].sum(), 1),
    }])
    return pd.concat([supplier, total], ignore_index=True)


def _build_category_table(df_sku, df_rev):
    """Category return breakdown with monetary columns."""
    if df_sku.empty:
        return pd.DataFrame()

    sku_data = df_sku[["sku_prefix", "total_sold", "total_returned", "category_l3"]].copy()
    sku_data = sku_data.merge(df_rev, on="sku_prefix", how="left")
    sku_data["revenue"] = sku_data["revenue"].fillna(0)
    sku_data["avg_price"] = sku_data["revenue"] / sku_data["total_sold"].replace(0, 1)
    sku_data["returned_amount"] = sku_data["avg_price"] * sku_data["total_returned"]

    cat = (
        sku_data[sku_data["category_l3"].notna()]
        .groupby("category_l3")
        .agg(
            returned=("total_returned", "sum"),
            delivered=("total_sold", "sum"),
            returned_amount=("returned_amount", "sum"),
            gmv=("revenue", "sum"),
        )
        .reset_index()
    )
    cat["return_ratio"] = cat["returned"] / cat["delivered"].replace(0, 1)
    cat["pct_value"] = cat["returned_amount"] / cat["gmv"].replace(0, 1)
    cat = cat.sort_values("return_ratio", ascending=False).reset_index(drop=True)
    return cat


# ── Formatting helpers ──────────────────────────────────────────────────

def _format_month(m):
    """Convert '2024-03' to '24-M03'."""
    parts = m.split("-")
    return f"{parts[0][2:]}-M{parts[1]}"


def _render_table_html(df, group_col, group_label):
    """Render a styled HTML table matching the Looker Studio look."""
    cols = [
        (group_label, group_col, "left", None),
        ("Returned Quantity", "returned", "right", lambda v: f"{int(v):,}"),
        ("Delivered Products", "delivered", "right", lambda v: f"{int(v):,}"),
        ("Return Ratio", "return_ratio", "right", lambda v: f"{v:.2%}"),
        ("Returned Amount", "returned_amount", "right", lambda v: f"{v:,.2f}"),
        ("GMV", "gmv", "right", lambda v: f"{v:,.2f}"),
        ("% Value of Return", "pct_value", "right", lambda v: f"{v:.2%}"),
    ]

    html = '<table style="width:100%; border-collapse:collapse; font-size:13px; font-family:sans-serif;">'

    # Header
    html += '<tr style="background:#d4a017; color:white; font-weight:600;">'
    for label, _, align, _ in cols:
        html += f'<th style="padding:8px 12px; text-align:{align}; white-space:nowrap;">{label}</th>'
    html += '</tr>'

    # Rows
    for i, (_, row) in enumerate(df.iterrows()):
        is_total = row[group_col] == "Grand total"
        bg = "background:#f5f0e0; font-weight:700;" if is_total else (
            "background:#fafafa;" if i % 2 == 0 else ""
        )
        html += f'<tr style="{bg} border-bottom:1px solid #e8e8e8;">'
        for label, col, align, fmt in cols:
            val = row.get(col, 0)
            text = fmt(val) if fmt and pd.notna(val) else str(val) if pd.notna(val) else ""
            style = f"padding:6px 12px; text-align:{align}; white-space:nowrap;"
            html += f'<td style="{style}">{text}</td>'
        html += '</tr>'

    html += '</table>'
    return html


# ═══════════════════════════════════════════════════════════════════════
# PAGE CONTENT
# ═══════════════════════════════════════════════════════════════════════

# Header
h1, h2 = st.columns([5, 1])
with h1:
    st.title("Returns Overview")
    st.caption(
        f"Last updated: {get_cache_age()} · "
        f"Hiccup products only · Excludes: {', '.join(config.EXCLUDED_CHANNELS)} · "
        f"Return statuses: {', '.join(config.VALID_RETURN_ITEM_STATUSES)}"
    )
with h2:
    if st.button("Refresh Data", use_container_width=True):
        pipelines.clear_cache()
        with st.spinner("Refreshing..."):
            st.session_state["data"] = load_data()
            save_cache(st.session_state["data"])
            _load_overview_data(force=True)
        st.toast("Data refreshed!")
        st.rerun()

# Load data
data = _load_base_data()
if data is None:
    st.warning("No data available. Click 'Refresh Data'.")
    st.stop()

overview = _load_overview_data()
monthly = overview["monthly"]
df_rev = overview["df_rev"]
df_sku = data["df_sku"].copy()

# ── Filters ─────────────────────────────────────────────────────────────

f1, f2, f3 = st.columns(3)
with f1:
    suppliers = sorted(df_sku["supplier_name"].dropna().unique().tolist())
    sel_supplier = st.selectbox("Supplier", ["All"] + suppliers)
with f2:
    categories = sorted(df_sku["category_l3"].dropna().unique().tolist())
    sel_category = st.selectbox("Category", ["All"] + categories)
with f3:
    min_delivered = st.number_input("Min delivered products", 0, 10000, 0, step=50,
                                     help="Filter out suppliers/categories below this threshold")

filtered = df_sku
if sel_supplier != "All":
    filtered = filtered[filtered["supplier_name"] == sel_supplier]
if sel_category != "All":
    filtered = filtered[filtered["category_l3"] == sel_category]

# ── Historic Return Ratio ───────────────────────────────────────────────

st.markdown("### Historic Return Ratio")

if not monthly.empty:
    display_monthly = monthly[monthly["sold"] > 0].copy()
    display_monthly["label"] = display_monthly["month"].apply(_format_month)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=display_monthly["label"],
        y=display_monthly["return_rate"],
        mode="lines+markers+text",
        text=display_monthly["return_rate"].apply(lambda x: f"{x:.1%}"),
        textposition="top center",
        textfont=dict(size=10, color="#1a73e8"),
        line=dict(color="#1a73e8", width=2.5),
        marker=dict(size=7, color="#1a73e8"),
        name="Return Ratio",
    ))
    fig.update_layout(
        yaxis=dict(tickformat=".0%", title="Return Ratio", gridcolor="#f0f0f0"),
        xaxis=dict(title="", tickangle=-45),
        height=420,
        margin=dict(t=30, b=60, l=60, r=20),
        showlegend=True,
        legend=dict(x=0, y=1.05, orientation="h"),
        plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics
    if len(display_monthly) >= 2:
        current = display_monthly.iloc[-1]
        previous = display_monthly.iloc[-2]
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Current Month", f"{current['return_rate']:.1%}",
                       f"{current['return_rate'] - previous['return_rate']:+.1%}")
        with m2:
            st.metric("Returned", f"{int(current['returned']):,}")
        with m3:
            st.metric("Delivered", f"{int(current['sold']):,}")
        with m4:
            avg_rate = display_monthly["return_rate"].mean()
            st.metric("Avg Return Rate", f"{avg_rate:.1%}")
else:
    st.info("No monthly data available.")

# ── Supplier Return Breakdown ───────────────────────────────────────────

st.markdown("### Supplier Return Breakdown")

supplier_table = _build_supplier_table(filtered, df_rev)
if not supplier_table.empty:
    if min_delivered > 0:
        supplier_table = supplier_table[
            (supplier_table["delivered"] >= min_delivered)
            | (supplier_table["supplier_name"] == "Grand total")
        ]
    st.markdown(_render_table_html(supplier_table, "supplier_name", "Supplier"),
                unsafe_allow_html=True)
    st.caption(f"{len(supplier_table) - 1} suppliers shown")
else:
    st.info("No supplier data available.")

# ── Category Return Breakdown ───────────────────────────────────────────

st.markdown("### Category Return Breakdown")

cat_table = _build_category_table(filtered, df_rev)
if not cat_table.empty:
    if min_delivered > 0:
        cat_table = cat_table[cat_table["delivered"] >= min_delivered]
    st.markdown(_render_table_html(cat_table, "category_l3", "Category"),
                unsafe_allow_html=True)
    st.caption(f"{len(cat_table)} categories shown")
else:
    st.info("No category data available.")
