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


@st.cache_data(ttl=3600)
def get_tracking_summaries(cache_key: str, sku_action_pairs_json: str) -> dict:
    """
    Fast summary for the table: Before/After/Change/PO per SKU.
    Uses simple count queries (~0.5s total) instead of daily aggregations (~7s).
    Returns {sku_prefix: {last_14d, pre_po, change_pp, po_info, badge}}.
    """
    import json
    pairs = json.loads(sku_action_pairs_json)
    if not pairs:
        return {}

    now = datetime.now(timezone.utc)
    lag = config.SLOW_DELIVERY_LAG_DAYS

    sku_prefixes = [p[0] for p in pairs]
    sku_action_dates = {p[0]: datetime.fromisoformat(p[1]).replace(tzinfo=timezone.utc) for p in pairs}

    # "After" = last 14 days (same window for all SKUs) — 2 fast queries
    after_end = now - timedelta(days=lag)
    after_start = after_end - timedelta(days=14)
    after_sold = pipelines.get_orders_count_for_skus(sku_prefixes, after_start, after_end)
    after_returned = pipelines.get_returns_count_for_skus(sku_prefixes, after_start, after_end)

    # POs for all SKUs — 1 batch query
    po_pairs = [(sku, sku_action_dates[sku]) for sku in sku_prefixes]
    all_pos = pipelines.get_pos_for_skus(po_pairs)

    # "Before" = 30 days before first PO received per SKU — 2 queries per SKU
    results = {}
    for sku in sku_prefixes:
        a_sold = after_sold.get(sku, 0)
        a_ret = after_returned.get(sku, 0)
        last_14d = min(a_ret / a_sold, 1.0) if a_sold > 0 else None

        pos = all_pos.get(sku, [])
        pre_po = None
        po_info = ""

        if pos:
            first_po = pos[0]
            received = first_po["received_on"]
            r_str = received.strftime("%d %b") if hasattr(received, "strftime") else str(received)[:10]
            units = sum(i.get("received", 0) for i in first_po.get("items", []))
            po_info = f"{r_str} ({units}u)"

            # Before window: 30 days ending at (received - lag)
            before_end = received - timedelta(days=lag)
            before_start = before_end - timedelta(days=30)
            b_sold = pipelines.get_orders_count_for_skus([sku], before_start, before_end).get(sku, 0)
            b_ret = pipelines.get_returns_count_for_skus([sku], before_start, received).get(sku, 0)
            pre_po = min(b_ret / b_sold, 1.0) if b_sold > 0 else None

        change_pp = None
        if pre_po is not None and last_14d is not None:
            change_pp = (last_14d - pre_po) * 100

        badge = "WAITING"
        if change_pp is not None:
            if change_pp <= -3:
                badge = "IMPROVING"
            elif change_pp >= 3:
                badge = "WORSENING"
            else:
                badge = "NO CHANGE"

        results[sku] = {
            "last_14d": last_14d, "pre_po": pre_po, "change_pp": change_pp,
            "po_info": po_info, "pos": pos, "badge": badge,
        }

    return results


@st.cache_data(ttl=3600)
def preload_tracking_batch(cache_key: str, sku_action_pairs_json: str) -> dict:
    """
    Batch-fetch daily orders and returns for all tracked SKUs in 2 queries.
    cache_key: stable key (changes only when data should refresh, e.g. hourly)
    sku_action_pairs_json: JSON string of [[sku_prefix, action_date_iso], ...]
    Returns dict of sku_prefix -> {df_ord, df_ret}.
    """
    import json
    pairs = json.loads(sku_action_pairs_json)
    if not pairs:
        return {}

    now = datetime.now(timezone.utc)
    sku_prefixes = [p[0] for p in pairs]
    earliest_action = min(datetime.fromisoformat(p[1]).replace(tzinfo=timezone.utc) for p in pairs)
    graph_start = earliest_action - timedelta(days=30)

    all_orders = pipelines.get_daily_orders_for_skus(sku_prefixes, graph_start, now)
    all_returns = pipelines.get_daily_returns_for_skus(sku_prefixes, graph_start, now)

    df_all_ord = pd.DataFrame(all_orders) if all_orders else pd.DataFrame(columns=["sku_prefix", "date", "size", "sold"])
    df_all_ret = pd.DataFrame(all_returns) if all_returns else pd.DataFrame(columns=["sku_prefix", "date", "size", "returned"])

    result = {}
    for sku in sku_prefixes:
        result[sku] = {
            "df_ord": df_all_ord[df_all_ord["sku_prefix"] == sku].drop(columns=["sku_prefix"]).reset_index(drop=True) if not df_all_ord.empty else pd.DataFrame(columns=["date", "size", "sold"]),
            "df_ret": df_all_ret[df_all_ret["sku_prefix"] == sku].drop(columns=["sku_prefix"]).reset_index(drop=True) if not df_all_ret.empty else pd.DataFrame(columns=["date", "size", "returned"]),
        }
    return result


@st.cache_data(ttl=300)
def get_tracking_data(sku_prefix: str, action_date_str: str, _preloaded: dict = None) -> dict:
    """
    Compute all tracking data for a single SKU.
    action_date_str is ISO format string (cache-friendly).
    _preloaded: optional pre-fetched {df_ord, df_ret} from batch load.
    Returns dict with: rolling_df, pos, last_14d_rate, pre_po_rate, lifetime_rate, badge.
    """
    action_date = datetime.fromisoformat(action_date_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    graph_start = action_date - timedelta(days=30)

    # Use preloaded data if available, otherwise fetch individually
    if _preloaded and sku_prefix in _preloaded:
        daily_orders = _preloaded[sku_prefix]["df_ord"].to_dict("records")
        daily_returns = _preloaded[sku_prefix]["df_ret"].to_dict("records")
    else:
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

    # Minimum sales in a 7-day window to show a data point (suppresses noise)
    MIN_WINDOW_SOLD = 5  # overall
    MIN_WINDOW_SOLD_SIZE = 5  # per size

    # Compute rolling 7-day return rate per size + overall
    rolling_rows = []
    size_total_sold = {s: 0 for s in all_sizes}

    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        w_start = (d - timedelta(days=7)).strftime("%Y-%m-%d")

        sold_window = df_ord[(df_ord["date"] > w_start) & (df_ord["date"] <= d_str)]
        ret_window = df_ret[(df_ret["date"] > w_start) & (df_ret["date"] <= d_str)] if not df_ret.empty else pd.DataFrame(columns=["date", "size", "returned"])

        total_sold = sold_window["sold"].sum()
        total_returned = ret_window["returned"].sum() if not ret_window.empty else 0

        row = {
            "date": d_str,
            "overall_rate": min(total_returned / total_sold, 1.0) if total_sold >= MIN_WINDOW_SOLD else None,
            "overall_sold": int(total_sold),
        }

        for size in all_sizes:
            s_sold = sold_window[sold_window["size"] == size]["sold"].sum()
            s_ret = ret_window[ret_window["size"] == size]["returned"].sum() if not ret_window.empty else 0
            size_total_sold[size] += s_sold
            row[f"rate_{size}"] = min(s_ret / s_sold, 1.0) if s_sold >= MIN_WINDOW_SOLD_SIZE else None

        rolling_rows.append(row)

    rolling_df = pd.DataFrame(rolling_rows)
    rolling_df["date"] = pd.to_datetime(rolling_df["date"])

    # Only keep sizes with meaningful total volume (top sizes covering 95% of sales)
    sorted_sizes = sorted(all_sizes, key=lambda s: size_total_sold[s], reverse=True)
    cumulative = 0
    total_all = sum(size_total_sold.values())
    visible_sizes = []
    for s in sorted_sizes:
        if size_total_sold[s] == 0:
            continue
        visible_sizes.append(s)
        cumulative += size_total_sold[s]
        if total_all > 0 and cumulative / total_all >= 0.95:
            break
    all_sizes = visible_sizes

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
