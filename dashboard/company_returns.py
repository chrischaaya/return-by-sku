"""
Company Returns page — 360-day return analytics powered by BigQuery.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.bigquery import get_filter_options, query_returns_data, get_capture_curves, get_capture_pct


def _fmt_pct(v):
    return f"{v:.1%}" if pd.notna(v) and v > 0 else "—"


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


def _build_breakdown_table(df, group_col, group_label, table_key, per_page=10):
    """Build a styled HTML breakdown table with pagination, sorted by sold desc."""
    if df.empty:
        st.caption("No data")
        return

    df = df.copy()
    df["return_rate"] = df["returned"] / df["sold"].replace(0, 1)
    df["pct_value_return"] = df["returned_amount"] / df["gmv"].replace(0, 1)
    df = df.sort_values("sold", ascending=False).reset_index(drop=True)

    # Grand total
    total_sold = df["sold"].sum()
    total_returned = df["returned"].sum()
    total_gmv = df["gmv"].sum()
    total_ret_amt = df["returned_amount"].sum()

    # Pagination
    total_rows = len(df)
    total_pages = max(1, -(-total_rows // per_page))
    pg_key = f"cr_pg_{table_key}"
    if pg_key not in st.session_state:
        st.session_state[pg_key] = 1
    if st.session_state[pg_key] > total_pages:
        st.session_state[pg_key] = 1
    page = st.session_state[pg_key]
    start = (page - 1) * per_page
    end = min(start + per_page, total_rows)
    page_df = df.iloc[start:end]

    cols = [group_label, "Returned", "Delivered", "Return Rate", "Returned Amt", "GMV", "% Value of Return"]

    html = '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
    html += '<tr style="background:#f59e0b; color:white; font-weight:600;">'
    for col in cols:
        html += f'<th style="padding:6px 10px; text-align:left;">{col}</th>'
    html += '</tr>'

    for _, row in page_df.iterrows():
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
    html += f'<td style="padding:5px 10px;">Grand total</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_num(total_returned)}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_num(total_sold)}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_pct(total_returned / max(total_sold, 1))}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_currency(total_ret_amt)}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_currency(total_gmv)}</td>'
    html += f'<td style="padding:5px 10px;">{_fmt_pct(total_ret_amt / max(total_gmv, 1))}</td>'
    html += '</tr></table>'

    st.markdown(html, unsafe_allow_html=True)

    # Pagination controls
    if total_pages > 1:
        pc1, pc2, pc3 = st.columns([1, 3, 1])
        with pc1:
            if st.button("←", key=f"{pg_key}_prev", disabled=page <= 1):
                st.session_state[pg_key] = page - 1
                st.rerun()
        with pc2:
            st.markdown(
                f'<div style="text-align:center; font-size:12px; color:#888; padding-top:6px;">'
                f'{start+1}–{end} of {total_rows} · Page {page}/{total_pages}</div>',
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("→", key=f"{pg_key}_next", disabled=page >= total_pages):
                st.session_state[pg_key] = page + 1
                st.rerun()


def render(actor: str):
    """Render the Company Returns tab."""

    # --- Filters ---
    options = get_filter_options()

    # Row 1: dates + granularity
    r1c1, r1c2, r1c3 = st.columns([0.7, 0.7, 0.8])
    with r1c1:
        start_date = st.date_input(
            "From",
            value=date.today() - timedelta(days=30),
            min_value=date(2024, 1, 1),
            max_value=date.today(),
            key="cr_start",
        )
    with r1c2:
        end_date = st.date_input(
            "To",
            value=date.today() - timedelta(days=7),
            min_value=date(2024, 1, 1),
            max_value=date.today(),
            key="cr_end",
        )
    with r1c3:
        granularity = st.selectbox("Granularity", ["Daily", "Weekly", "Monthly"], index=0, key="cr_gran")

    # Row 2: filters
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        sel_channels = st.multiselect("Channel", options["channels"], key="cr_ch")
    with r2c2:
        sel_suppliers = st.multiselect("Supplier", options["suppliers"], key="cr_sup")
    with r2c3:
        sel_categories = st.multiselect("Category", options["categories"], key="cr_cat")
    with r2c4:
        sku_input = st.text_input("SKU Prefix", placeholder="e.g. MBAJ1ZFU01", key="cr_sku")

    # Parse SKU input (comma-separated)
    sku_prefixes = tuple(s.strip().upper() for s in sku_input.split(",") if s.strip()) if sku_input else ()

    # --- Query BigQuery ---
    with st.spinner("Loading data from BigQuery..."):
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

    # Compute estimated overall rate using capture curves
    capture_curves = get_capture_curves()
    active_channels = list(sel_channels) if sel_channels else list(capture_curves.keys())
    today_ts = pd.Timestamp.now().normalize()

    df_daily["order_date"] = pd.to_datetime(df_daily["order_date"])
    df_daily["days_old"] = (today_ts - df_daily["order_date"]).dt.days
    df_daily["capture_pct"] = df_daily["days_old"].apply(
        lambda d: get_capture_pct(capture_curves, active_channels, d)
    )
    # Estimated returned = actual returned adjusted by capture curve
    df_daily["estimated_returned"] = (
        df_daily["returned"] / df_daily["capture_pct"].replace(0, 1)
    )
    total_estimated_returned = int(df_daily["estimated_returned"].sum())
    estimated_rate = total_estimated_returned / max(total_sold, 1)

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
        delta_str = ""
        delta_color = "#888"

    # Return rate card with vs previous period inline
    rate_str = _fmt_pct(total_rate)
    if delta_str:
        rate_html = f'{rate_str} <span style="font-size:14px; color:{delta_color}; margin-left:4px;">({delta_str})</span>'
    else:
        rate_html = rate_str

    # Estimated rate card
    est_rate_str = _fmt_pct(estimated_rate)

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value in [
        (k1, "Total Sold", _fmt_num(total_sold)),
        (k2, "Total Returned", _fmt_num(total_returned)),
    ]:
        with col:
            st.markdown(
                f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center;">'
                f'<div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>'
                f'<div style="font-size:28px; font-weight:700; margin-top:4px;">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with k3:
        st.markdown(
            f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center;">'
            f'<div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">Return Rate</div>'
            f'<div style="font-size:28px; font-weight:700; margin-top:4px;">{rate_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center;">'
            f'<div style="font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px;">Estimated Return Rate</div>'
            f'<div style="font-size:28px; font-weight:700; margin-top:4px; color:#f59e0b;">{est_rate_str}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    # --- Time series graph ---
    # order_date already converted to datetime and has capture_pct from KPI section

    if granularity == "Weekly":
        df_daily["period"] = df_daily["order_date"].dt.to_period("W").apply(lambda p: p.start_time)
        df_daily["period_end"] = df_daily["period"] + pd.Timedelta(days=6)
    elif granularity == "Monthly":
        df_daily["period"] = df_daily["order_date"].dt.to_period("M").apply(lambda p: p.start_time)
        df_daily["period_end"] = df_daily["period"] + pd.offsets.MonthEnd(0)
    else:
        df_daily["period"] = df_daily["order_date"]
        df_daily["period_end"] = df_daily["order_date"]

    df_grouped = df_daily.groupby("period").agg(
        sold=("sold", "sum"), returned=("returned", "sum"),
        estimated_returned=("estimated_returned", "sum"),
        gmv=("gmv", "sum"), returned_amount=("returned_amount", "sum"),
        period_end=("period_end", "max"),
    ).reset_index()
    df_grouped["return_rate"] = df_grouped["returned"] / df_grouped["sold"].replace(0, 1)
    df_grouped["estimated_rate"] = (df_grouped["estimated_returned"] / df_grouped["sold"].replace(0, 1)).clip(upper=1.0)
    df_grouped = df_grouped.sort_values("period").reset_index(drop=True)

    # Filter to selected range
    x_min = pd.Timestamp(start_date)
    x_max = pd.Timestamp(end_date)
    df_grouped = df_grouped[(df_grouped["period"] >= x_min - pd.Timedelta(days=7)) & (df_grouped["period"] <= x_max)]

    # Explicit x-axis labels so ticks always match data points
    if granularity == "Monthly":
        df_grouped["label"] = df_grouped["period"].dt.strftime("%y-M%m")
    elif granularity == "Weekly":
        df_grouped["label"] = df_grouped["period"].dt.strftime("%d %b")
    else:
        df_grouped["label"] = df_grouped["period"].dt.strftime("%d %b")

    # Capture pct using period end date
    df_grouped["days_old"] = (today_ts - df_grouped["period_end"]).dt.days.clip(lower=0)
    df_grouped["capture_pct"] = df_grouped["days_old"].apply(
        lambda d: get_capture_pct(capture_curves, active_channels, d)
    )

    reliable_mask = df_grouped["capture_pct"] >= 0.95

    fig = go.Figure()

    # Solid line: actual return rate
    fig.add_trace(go.Scatter(
        x=df_grouped["label"],
        y=df_grouped["return_rate"],
        mode="lines+markers+text",
        name="Actual",
        text=[f"{v:.1%}" for v in df_grouped["return_rate"]],
        textposition="top center",
        textfont=dict(size=10, color="#2563eb"),
        line=dict(color="#2563eb", width=2.5),
        marker=dict(size=6, color="#2563eb"),
        hovertemplate="%{x}<br>Actual: %{y:.1%}<br>Sold: %{customdata[0]:,}<br>Returned: %{customdata[1]:,}<br>Captured: %{customdata[2]:.0%}<extra></extra>",
        customdata=list(zip(
            df_grouped["sold"].astype(int),
            df_grouped["returned"].astype(int),
            df_grouped["capture_pct"],
        )),
    ))

    # Dotted line: estimated return rate
    # Only where: capture 50-95% AND estimate diverges > 1pp from actual
    est_eligible = (~reliable_mask) & (df_grouped["capture_pct"] >= 0.50)
    diverged = (df_grouped["estimated_rate"] - df_grouped["return_rate"]).abs() > 0.01
    est_show = est_eligible & diverged

    if est_show.any():
        est_df = df_grouped[est_show].copy()
        # Bridge from last reliable point for continuity
        first_est_idx = est_df.index[0]
        if first_est_idx > 0 and (first_est_idx - 1) in df_grouped.index:
            est_df = pd.concat([df_grouped.loc[[first_est_idx - 1]], est_df])

        fig.add_trace(go.Scatter(
            x=est_df["label"],
            y=est_df["estimated_rate"],
            mode="lines+markers",
            name="Estimated",
            line=dict(color="#f59e0b", width=2, dash="dot"),
            marker=dict(size=5, color="#f59e0b"),
            hovertemplate="%{x}<br>Estimated: %{y:.1%}<br>Captured: %{customdata:.0%}<extra></extra>",
            customdata=est_df["capture_pct"],
        ))

    # Y-axis scaling
    all_rates = df_grouped["return_rate"].tolist()
    if est_show.any():
        all_rates += df_grouped.loc[est_show, "estimated_rate"].tolist()
    y_max = max(max(all_rates) + 0.05, 0.10) if all_rates else 0.5

    fig.update_layout(
        title="Historic Return Rate",
        yaxis=dict(tickformat=".0%", title="Return Rate", gridcolor="#f0f0f0", range=[0, y_max]),
        xaxis=dict(title="", gridcolor="#f0f0f0", type="category"),
        height=420, margin=dict(t=40, b=40, l=50, r=20),
        plot_bgcolor="white", hovermode="x unified",
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Breakdown tables ---
    st.markdown("### Supplier Return Breakdown")
    _build_breakdown_table(data["by_supplier"], "supplier", "Supplier", "supplier")

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("### Category Return Breakdown")
        _build_breakdown_table(data["by_category"], "category", "Category", "category")

    with col_right:
        st.markdown("### Channel Return Breakdown")
        _build_breakdown_table(data["by_channel"], "channel", "Channel", "channel")
