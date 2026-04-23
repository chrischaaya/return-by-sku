"""
Action tracking: rolling return rate computation, pre-PO baseline, status badges.
No FIFO assumptions — purely trend-based.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

import config
from engine import pipelines


@st.cache_data(ttl=300)
def get_tracking_data(sku_prefix: str, action_date_str: str) -> dict:
    """
    Compute all tracking data for a single SKU.
    action_date_str is ISO format string (cache-friendly).
    Returns dict with: rolling_df, pos, last_14d_rate, pre_po_rate, lifetime_rate, badge.
    """
    action_date = datetime.fromisoformat(action_date_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    # Fetch data: go back 180 days or to action_date - 30d, whichever is earlier
    graph_start = min(action_date - timedelta(days=30), now - timedelta(days=180))

    daily_orders = pipelines.get_daily_orders_for_sku(sku_prefix, graph_start, now)
    daily_returns = pipelines.get_daily_returns_for_sku(sku_prefix, graph_start, now)
    pos = pipelines.get_sku_pos(sku_prefix, action_date)

    # Build daily DataFrames
    df_ord = pd.DataFrame(daily_orders) if daily_orders else pd.DataFrame(columns=["date", "size", "sold"])
    df_ret = pd.DataFrame(daily_returns) if daily_returns else pd.DataFrame(columns=["date", "size", "returned"])

    if df_ord.empty:
        return _empty_result(pos)

    # Get all sizes
    all_sizes = sorted(set(df_ord["size"].unique()) | set(df_ret["size"].unique()) if not df_ret.empty else set(df_ord["size"].unique()))

    # Build complete date range
    date_range = pd.date_range(graph_start.date(), now.date(), freq="D")

    # Compute rolling 7-day return rate per size + overall
    rolling_rows = []
    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        w_start = (d - timedelta(days=7)).strftime("%Y-%m-%d")

        # Window sold/returned
        sold_window = df_ord[(df_ord["date"] > w_start) & (df_ord["date"] <= d_str)]
        ret_window = df_ret[(df_ret["date"] > w_start) & (df_ret["date"] <= d_str)] if not df_ret.empty else pd.DataFrame(columns=["date", "size", "returned"])

        total_sold = sold_window["sold"].sum()
        total_returned = ret_window["returned"].sum() if not ret_window.empty else 0

        row = {
            "date": d_str,
            "overall_rate": min(total_returned / total_sold, 1.0) if total_sold > 0 else None,
            "overall_sold": int(total_sold),
        }

        for size in all_sizes:
            s_sold = sold_window[sold_window["size"] == size]["sold"].sum()
            s_ret = ret_window[ret_window["size"] == size]["returned"].sum() if not ret_window.empty else 0
            row[f"rate_{size}"] = min(s_ret / s_sold, 1.0) if s_sold > 0 else None

        rolling_rows.append(row)

    rolling_df = pd.DataFrame(rolling_rows)
    rolling_df["date"] = pd.to_datetime(rolling_df["date"])

    # Last 14 days rate (simple, not rolling)
    lag_days = config.SLOW_DELIVERY_LAG_DAYS
    end_14d = now - timedelta(days=lag_days)
    start_14d = end_14d - timedelta(days=14)
    s14 = start_14d.strftime("%Y-%m-%d")
    e14 = end_14d.strftime("%Y-%m-%d")
    sold_14d = df_ord[(df_ord["date"] >= s14) & (df_ord["date"] <= e14)]["sold"].sum()
    ret_14d = df_ret[(df_ret["date"] >= s14) & (df_ret["date"] <= e14)]["returned"].sum() if not df_ret.empty else 0
    last_14d_rate = min(ret_14d / sold_14d, 1.0) if sold_14d > 0 else None

    # Pre-PO baseline (30 days before first PO received)
    pre_po_rate = _compute_pre_po_rate(df_ord, df_ret, pos)

    # Lifetime rate
    total_sold = df_ord["sold"].sum()
    total_ret = df_ret["returned"].sum() if not df_ret.empty else 0
    lifetime_rate = min(total_ret / total_sold, 1.0) if total_sold > 0 else 0

    # Badge
    badge = _compute_badge(last_14d_rate, pre_po_rate, pos)

    return {
        "rolling_df": rolling_df,
        "sizes": all_sizes,
        "pos": pos,
        "last_14d_rate": last_14d_rate,
        "pre_po_rate": pre_po_rate,
        "lifetime_rate": lifetime_rate,
        "badge": badge,
    }


def _compute_pre_po_rate(df_ord, df_ret, pos) -> Optional[float]:
    """Return rate for the 30 days before the first PO was received at warehouse."""
    if not pos:
        return None

    received_on = pos[0].get("received_on")
    if received_on is None:
        return None

    if isinstance(received_on, str):
        received_on = datetime.fromisoformat(received_on)

    orders_end = received_on - timedelta(days=14)
    orders_start = orders_end - timedelta(days=30)
    s = orders_start.strftime("%Y-%m-%d")
    e = orders_end.strftime("%Y-%m-%d")
    r_end = received_on.strftime("%Y-%m-%d")

    sold = df_ord[(df_ord["date"] >= s) & (df_ord["date"] <= e)]["sold"].sum()
    returned = df_ret[(df_ret["date"] >= s) & (df_ret["date"] <= r_end)]["returned"].sum() if not df_ret.empty else 0

    if sold == 0:
        return None
    return min(returned / sold, 1.0)


def _compute_badge(last_14d_rate, pre_po_rate, pos) -> str:
    """Compute status badge from metrics."""
    if not pos or pre_po_rate is None or last_14d_rate is None:
        return "WAITING"

    diff = last_14d_rate - pre_po_rate
    if diff <= -0.03:
        return "IMPROVING"
    elif diff >= 0.03:
        return "WORSENING"
    else:
        return "NO CHANGE"


def _empty_result(pos):
    return {
        "rolling_df": pd.DataFrame(),
        "sizes": [],
        "pos": pos,
        "last_14d_rate": None,
        "pre_po_rate": None,
        "lifetime_rate": 0,
        "badge": "WAITING",
    }
