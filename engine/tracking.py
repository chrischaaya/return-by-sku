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
    from engine.bigquery import get_tracking_counts
    import json
    pairs = json.loads(sku_action_pairs_json)
    if not pairs:
        return {}

    now = datetime.now(timezone.utc)
    lag = config.SLOW_DELIVERY_LAG_DAYS

    sku_prefixes = [p[0] for p in pairs]
    sku_action_dates = {p[0]: datetime.fromisoformat(p[1]).replace(tzinfo=timezone.utc) for p in pairs}

    # "After" = last 14 days (same window for all SKUs) — from BigQuery
    after_end = now - timedelta(days=lag)
    after_start = after_end - timedelta(days=14)
    after_data = get_tracking_counts(
        tuple(sku_prefixes), after_start.strftime("%Y-%m-%d"), after_end.strftime("%Y-%m-%d")
    )

    # POs for all SKUs — stays on MongoDB (hiccup-ff operational data)
    po_pairs = [(sku, sku_action_dates[sku]) for sku in sku_prefixes]
    all_pos = pipelines.get_pos_for_skus(po_pairs)

    # "Before" = 30 days before first PO received per SKU — from BigQuery
    results = {}
    for sku in sku_prefixes:
        sku_after = after_data.get(sku, {})
        a_sold = sku_after.get("sold", 0)
        a_ret = sku_after.get("returned", 0)
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
            before_data = get_tracking_counts(
                (sku,), before_start.strftime("%Y-%m-%d"), before_end.strftime("%Y-%m-%d")
            )
            b_sold = before_data.get(sku, {}).get("sold", 0)
            b_ret = before_data.get(sku, {}).get("returned", 0)
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


@st.cache_data(ttl=3600)
def get_tracking_data(sku_prefix: str, action_date_str: str, days_back: int = 90, _excluded_channels: str = "", _preloaded: dict = None) -> dict:
    """
    Compute all tracking data for a single SKU.
    Vectorized rolling computation — no Python loops over dates.
    """
    from engine.bigquery import get_tracking_daily_orders, get_tracking_daily_returns

    action_date = datetime.fromisoformat(action_date_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    graph_start = now - timedelta(days=days_back)

    # Graph data from BigQuery (fast, no $lookup)
    daily_orders = get_tracking_daily_orders(sku_prefix, graph_start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    daily_returns = get_tracking_daily_returns(sku_prefix, graph_start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    # PO data stays on MongoDB (operational data from hiccup-ff)
    pos = pipelines.get_sku_pos(sku_prefix, action_date)

    df_ord = pd.DataFrame(daily_orders) if daily_orders else pd.DataFrame(columns=["date", "size", "sold"])
    df_ret = pd.DataFrame(daily_returns) if daily_returns else pd.DataFrame(columns=["date", "size", "returned"])

    if df_ord.empty:
        return _empty_result(pos)

    # Pivot to daily totals per size (one row per date, one column per size)
    df_ord["date"] = pd.to_datetime(df_ord["date"])
    df_ret["date"] = pd.to_datetime(df_ret["date"]) if not df_ret.empty else df_ret["date"]

    graph_end = now - timedelta(days=7)
    date_idx = pd.date_range(graph_start.date(), graph_end.date(), freq="D")

    # Daily totals
    ord_daily = df_ord.groupby("date")["sold"].sum().reindex(date_idx, fill_value=0)
    ret_daily = df_ret.groupby("date")["returned"].sum().reindex(date_idx, fill_value=0) if not df_ret.empty else pd.Series(0, index=date_idx)

    # Rolling 7-day return rate
    ord_roll = ord_daily.rolling(7, min_periods=7).sum()
    ret_roll = ret_daily.rolling(7, min_periods=7).sum()
    overall_rate = (ret_roll / ord_roll).where(ord_roll > 0).clip(upper=1.0)

    rolling_df = pd.DataFrame({"date": date_idx, "overall_rate": overall_rate.values, "overall_sold": ord_roll.values.astype(int)})

    # Per-size rolling 3-day rates
    all_sizes_set = set(df_ord["size"].unique())
    if not df_ret.empty:
        all_sizes_set |= set(df_ret["size"].unique())
    all_sizes = sorted(all_sizes_set)

    size_total_sold = {}
    for size in all_sizes:
        s_ord = df_ord[df_ord["size"] == size].groupby("date")["sold"].sum().reindex(date_idx, fill_value=0)
        s_ret = df_ret[df_ret["size"] == size].groupby("date")["returned"].sum().reindex(date_idx, fill_value=0) if not df_ret.empty else pd.Series(0, index=date_idx)
        s_ord_roll = s_ord.rolling(7, min_periods=7).sum()
        s_ret_roll = s_ret.rolling(7, min_periods=7).sum()
        rate = (s_ret_roll / s_ord_roll).where(s_ord_roll > 0).clip(upper=1.0)
        rolling_df[f"rate_{size}"] = rate.values
        size_total_sold[size] = int(s_ord.sum())

    # Only keep sizes covering 95% of sales
    sorted_sizes = sorted(all_sizes, key=lambda s: size_total_sold.get(s, 0), reverse=True)
    cumulative = 0
    total_all = sum(size_total_sold.values())
    visible_sizes = []
    for s in sorted_sizes:
        if size_total_sold.get(s, 0) == 0:
            continue
        visible_sizes.append(s)
        cumulative += size_total_sold[s]
        if total_all > 0 and cumulative / total_all >= 0.95:
            break

    # Sort sizes in standard order (smallest to largest)
    _SIZE_ORDER = [
        "XXS", "XS", "S", "S/M", "M", "M/L", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL",
        "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36",
        "37", "38", "39", "40", "42", "44", "46", "48", "50",
        "ONE SIZE", "STD",
    ]
    def _size_key(s):
        try:
            return _SIZE_ORDER.index(str(s).upper())
        except ValueError:
            return 999
    visible_sizes = sorted(visible_sizes, key=_size_key)

    # Last 14 days rate
    lag_days = config.SLOW_DELIVERY_LAG_DAYS
    e14 = (now - timedelta(days=lag_days)).strftime("%Y-%m-%d")
    s14 = (now - timedelta(days=lag_days + 14)).strftime("%Y-%m-%d")
    sold_14d = df_ord[(df_ord["date"] >= s14) & (df_ord["date"] <= e14)]["sold"].sum()
    ret_14d = df_ret[(df_ret["date"] >= s14) & (df_ret["date"] <= e14)]["returned"].sum() if not df_ret.empty else 0
    last_14d_rate = min(ret_14d / sold_14d, 1.0) if sold_14d > 0 else None

    pre_po_rate = _compute_pre_po_rate(df_ord, df_ret, pos)

    total_sold = df_ord["sold"].sum()
    total_ret = df_ret["returned"].sum() if not df_ret.empty else 0
    lifetime_rate = min(total_ret / total_sold, 1.0) if total_sold > 0 else 0

    badge = _compute_badge(last_14d_rate, pre_po_rate, pos)

    return {
        "rolling_df": rolling_df,
        "sizes": visible_sizes,
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
