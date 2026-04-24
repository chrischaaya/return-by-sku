"""
Company Returns page — 360-day return analytics powered by BigQuery.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.bigquery import get_filter_options, query_returns_data


def _fmt_pct(v):
    return f"{v:.1%}" if pd.notna(v) else "—"


def _fmt_num(v):
    if pd.isna(v) or v == 0:
        return "—"
    if v >= 1_000_000:
        return f"{v/1_000_000:,.1f}M"
    if v >= 1_000:
        return f"{v:,.0f}"
    return f"{v:.0f}"


def _fmt_currency(v):
    if pd.isna(v) or v == 0:
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:,.1f}M"
    if v >= 1_000:
        return f"${v:,.0f}"
    return f"${v:.0f}"


def _build_breakdown_table(df, group_col, group_label):
    """Build a styled HTML breakdown table (supplier/category/channel)."""
    if df.empty:
        return ""

    df = df.copy()
    df["return_rate"] = df["returned"] / df["sold"].replace(0, 1)
    df["pct_value_return"] = df["returned_amount"] / df["gmv"].replace(0, 1)
    df = df.sort_values("return_rate", ascending=False)

    # Grand total
    total = {
        group_col: "Grand total",
        "returned": df["returned"].sum(),
        "sold": df["sold"].sum(),
        "return_rate": df["returned"].sum() / max(df["sold"].sum(), 1),
        "returned_amount": df["returned_amount"].sum(),
        "gmv": df["gmv"].sum(),
        "pct_value_return": df["returned_amount"].sum() / max(df["gmv"].sum(), 1),
    }

    cols = [group_label, "Returned", "Delivered", "Return Rate", "Returned Amt", "GMV", "% Value of Return"]

    html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
    html += '<tr style="background:#f59e0b; color:white; font-weight:600;">'
    for col in cols:
        html += f'<th style="padding:6px 10px; text-align:left;">{col}</th>'
    html += '</tr>'

    for _, row in df.iterrows():
        html += '<tr style="border-bottom:1px solid #eee;">'
        html += f'<td style="padding:5px 10px;">{row[group_col]}</td>'
        html += f'<td style="padding:5px 10px;">{_fmt_num(row["returned"])}</td>'
        html += f'<td style="padding:5px 10px;">{_fmt_num(row["sold"])}</td>'
        html += f'<td style="padding:5px 10px; font-weight:600;">{_fmt_pct(row["return_rate"])}</td>'
        html += f'<td style="padding:5px 10px;">{_fmt_currency(row["returned_amount"])}</td>'
        html += f'<td style="padding:5px 10px;">{_fmt_currency(row["gmv"])}</td>'
        html += f'<td style="padding:5px 10px;">{_fmt_pct(row["pct_value_return"])}</td>'
        html += '</tr>'

    # Grand total row
    html += '<tr style="background:#f0f0f0; font-weight:600; border-top:2px solid #ddd;">'
    html += f'<td style="padding:5px 10px;">{total[group_col]}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_num(total["returned"])}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_num(total["sold"])}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_pct(total["return_rate"])}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_currency(total["returned_amount"])}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_currency(total["gmv"])}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_pct(total["pct_value_return"])}</td>'
    html += '</tr></table>'

    return html


def render(actor: str):
    """Render the Company Returns tab."""

    # --- Filters ---
    options = get_filter_options()

    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.2, 1, 1, 1, 1, 1])
    with fc1:
        date_range = st.date_input(
            "Date range",
            value=(date.today() - timedelta(days=90), date.today() - timedelta(days=7)),
            min_value=date(2024, 1, 1),
            max_value=date.today(),
        )
    with fc2:
        granularity = st.selectbox("Granularity", ["Weekly", "Daily", "Monthly"], index=0)
    with fc3:
        sel_channels = st.multiselect("Channel", options["channels"])
    with fc4:
        sel_suppliers = st.multiselect("Supplier", options["suppliers"])
    with fc5:
        sel_categories = st.multiselect("Category", options["categories"])
    with fc6:
        sku_input = st.text_input("SKU Prefix", placeholder="e.g. MBAJ1ZFU01")

    # Parse date range
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date.today() - timedelta(days=90)
        end_date = date.today() - timedelta(days=7)

    # Parse SKU input (comma-separated)
    sku_prefixes = tuple(s.strip().upper() for s in sku_input.split(",") if s.strip()) if sku_input else ()

    # --- Query BigQuery ---
    data = query_returns_data(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        channels=tuple(sel_channels),
        suppliers=tuple(sel_suppliers),
        categories=tuple(sel_categories),
        sku_prefixes=sku_prefixes,
    )

    df_daily = data["daily"]

    if df_daily.empty:
        st.info("No data for the selected filters.")
        return

    # --- KPI cards ---
    total_sold = int(df_daily["sold"].sum())
    total_returned = int(df_daily["returned"].sum())
    total_rate = total_returned / max(total_sold, 1)
    total_gmv = df_daily["gmv"].sum()
    total_ret_amt = df_daily["returned_amount"].sum()

    # Previous period comparison
    period_days = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)
    prev_data = query_returns_data(
        start_date=prev_start.isoformat(),
        end_date=prev_end.isoformat(),
        channels=tuple(sel_channels),
        suppliers=tuple(sel_suppliers),
        categories=tuple(sel_categories),
        sku_prefixes=sku_prefixes,
    )
    prev_sold = int(prev_data["daily"]["sold"].sum()) if not prev_data["daily"].empty else 0
    prev_returned = int(prev_data["daily"]["returned"].sum()) if not prev_data["daily"].empty else 0
    prev_rate = prev_returned / max(prev_sold, 1) if prev_sold > 0 else None

    if prev_rate is not None:
        delta_pp = (total_rate - prev_rate) * 100
        delta_str = f"{delta_pp:+.1f}pp"
        delta_color = "#ef4444" if delta_pp > 0 else "#22c55e" if delta_pp < 0 else "#888"
    else:
        delta_str = "—"
        delta_color = "#888"

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value in [
        (k1, "Total Sold", _fmt_num(total_sold)),
        (k2, "Total Returned", _fmt_num(total_returned)),
        (k3, "Return Rate", _fmt_pct(total_rate)),
    ]:
        with col:
            st.markdown(
                f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center;">'
                f'<div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>'
                f'<div style="font-size:28px; font-weight:700; margin-top:4px;">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with k4:
        st.markdown(
            f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center;">'
            f'<div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">vs Previous Period</div>'
            f'<div style="font-size:28px; font-weight:700; margin-top:4px; color:{delta_color};">{delta_str}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    # --- Time series graph ---
    df_daily["order_date"] = pd.to_datetime(df_daily["order_date"])

    if granularity == "Weekly":
        df_daily["period"] = df_daily["order_date"].dt.to_period("W").apply(lambda p: p.start_time)
    elif granularity == "Monthly":
        df_daily["period"] = df_daily["order_date"].dt.to_period("M").apply(lambda p: p.start_time)
    else:
        df_daily["period"] = df_daily["order_date"]

    df_grouped = df_daily.groupby("period").agg(
        sold=("sold", "sum"), returned=("returned", "sum"),
        gmv=("gmv", "sum"), returned_amount=("returned_amount", "sum"),
    ).reset_index()
    df_grouped["return_rate"] = df_grouped["returned"] / df_grouped["sold"].replace(0, 1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped["period"],
        y=df_grouped["return_rate"],
        mode="lines+markers+text",
        text=[f"{v:.1%}" for v in df_grouped["return_rate"]],
        textposition="top center",
        textfont=dict(size=10, color="#2563eb"),
        line=dict(color="#2563eb", width=2.5),
        marker=dict(size=6, color="#2563eb"),
        hovertemplate="%{x|%d %b %Y}<br>Return Rate: %{y:.1%}<br>Sold: %{customdata[0]:,}<br>Returned: %{customdata[1]:,}<extra></extra>",
        customdata=list(zip(df_grouped["sold"].astype(int), df_grouped["returned"].astype(int))),
    ))

    # Format x-axis labels based on granularity
    if granularity == "Monthly":
        tickformat = "%y-M%m"
    elif granularity == "Weekly":
        tickformat = "%d %b"
    else:
        tickformat = "%d %b"

    y_max = max(df_grouped["return_rate"].max() + 0.05, 0.10) if not df_grouped.empty else 0.5
    fig.update_layout(
        title="Historic Return Rate",
        yaxis=dict(tickformat=".0%", title="Return Rate", gridcolor="#f0f0f0", range=[0, y_max]),
        xaxis=dict(title="", gridcolor="#f0f0f0", tickformat=tickformat),
        height=420, margin=dict(t=40, b=40, l=50, r=20),
        plot_bgcolor="white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Breakdown tables ---
    st.markdown("### Supplier Return Breakdown")
    html_supplier = _build_breakdown_table(data["by_supplier"], "supplier", "Supplier")
    st.markdown(html_supplier, unsafe_allow_html=True)

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("### Category Return Breakdown")
        html_category = _build_breakdown_table(data["by_category"], "category", "Category")
        st.markdown(html_category, unsafe_allow_html=True)

    with col_right:
        st.markdown("### Channel Return Breakdown")
        html_channel = _build_breakdown_table(data["by_channel"], "channel", "Channel")
        st.markdown(html_channel, unsafe_allow_html=True)
