"""
BigQuery connection and queries for the Company Returns page.
Reads from returns_analytics dataset (refreshed daily at 09:00).
"""

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# Per-channel max return window + 14d buffer.
# Capture curves are capped at this — anything after is noise, not real pending returns.
CHANNEL_MAX_RETURN_DAYS = {
    "trendyol": 22, "trendyolRO": 22, "hepsiburada": 22,
    "namshi": 21, "hiccup": 21,
    "debenhams": 35,
    "fashiondays": 37, "fashiondaysBG": 37, "emag": 37, "tiktokShop": 37,
    "aboutYou": 107,
}
DEFAULT_MAX_RETURN_DAYS = 37

_client = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        creds = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        _client = bigquery.Client(credentials=creds, project=st.secrets["GCP_PROJECT"])
    return _client


@st.cache_data(ttl=3600)
def get_filter_options() -> dict:
    """Fetch distinct values for all filter dropdowns."""
    client = _get_client()

    channels = [r.sales_channel for r in client.query(
        "SELECT DISTINCT sales_channel FROM `returns_analytics.daily_orders` WHERE sales_channel IS NOT NULL ORDER BY sales_channel"
    ).result()]

    # Suppliers: merchants first, then others, both alphabetical
    all_suppliers = [r.supplier_name for r in client.query(
        "SELECT DISTINCT supplier_name FROM `returns_analytics.products` WHERE supplier_name IS NOT NULL ORDER BY supplier_name"
    ).result()]
    merchants = sorted([s for s in all_suppliers if "merchant" in s.lower()])
    non_merchants = sorted([s for s in all_suppliers if "merchant" not in s.lower()])
    suppliers = merchants + non_merchants

    categories = [r.category_l3 for r in client.query(
        "SELECT DISTINCT category_l3 FROM `returns_analytics.products` WHERE category_l3 IS NOT NULL ORDER BY category_l3"
    ).result()]

    # Category → subcategory pairs (flat list for cache compatibility)
    cat_sub_pairs = [
        (r.category_l3, r.category_l4)
        for r in client.query(
            "SELECT DISTINCT category_l3, category_l4 FROM `returns_analytics.products` WHERE category_l4 IS NOT NULL ORDER BY category_l3, category_l4"
        ).result()
    ]

    return {
        "channels": channels,
        "suppliers": suppliers,
        "categories": categories,
        "cat_sub_pairs": cat_sub_pairs,
    }


@st.cache_data(ttl=86400)
def get_capture_curves() -> dict:
    """
    Compute return capture curves: per-channel AND a volume-weighted 'all' curve.
    - Recent 90-day window (orders 30-120 days ago) for current behavior
    - Outliers excluded (returns filed after policy + 7d buffer)
    - No post-hoc capping needed since outliers are filtered at query time
    """
    client = _get_client()

    # Build per-channel max days filter as SQL CASE
    channel_cases = " ".join(
        f"WHEN '{ch}' THEN {days}" for ch, days in CHANNEL_MAX_RETURN_DAYS.items()
    )
    max_days_sql = f"CASE o.sales_channel {channel_cases} ELSE {DEFAULT_MAX_RETURN_DAYS} END"

    # Per-channel curves: recent 90d, outliers excluded
    q = f"""
    WITH return_delays AS (
      SELECT
        o.sales_channel,
        DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) as days_to_return
      FROM `mongo_db.returns` r
      JOIN `mongo_db.orders` o ON r.order_id = o.order_id
      WHERE r.status != 'CANCELLED'
        AND DATE(o.creation_date) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 240 DAY)
                                      AND DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY)
        AND DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) >= 0
        AND DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) <= {max_days_sql}
    ),
    channel_totals AS (
      SELECT sales_channel, COUNT(*) as total_returns
      FROM return_delays
      GROUP BY 1
    )
    SELECT
      d.sales_channel,
      d.days_to_return as day,
      SUM(COUNT(*)) OVER (PARTITION BY d.sales_channel ORDER BY d.days_to_return) as cumulative,
      t.total_returns
    FROM return_delays d
    JOIN channel_totals t ON d.sales_channel = t.sales_channel
    GROUP BY d.sales_channel, d.days_to_return, t.total_returns
    ORDER BY d.sales_channel, d.days_to_return
    """
    rows = list(client.query(q).result())

    curves = {}
    for row in rows:
        ch = row.sales_channel
        if ch not in curves:
            curves[ch] = {}
        curves[ch][row.day] = row.cumulative / row.total_returns if row.total_returns > 0 else 1.0

    # Blended "all" curve: recent 90d, outliers excluded per channel
    q_all = f"""
    WITH return_delays AS (
      SELECT
        DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) as days_to_return
      FROM `mongo_db.returns` r
      JOIN `mongo_db.orders` o ON r.order_id = o.order_id
      WHERE r.status != 'CANCELLED'
        AND DATE(o.creation_date) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 240 DAY)
                                      AND DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY)
        AND DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) >= 0
        AND DATE_DIFF(DATE(r.creation_date), DATE(o.creation_date), DAY) <= {max_days_sql}
    ),
    total AS (SELECT COUNT(*) as t FROM return_delays)
    SELECT
      days_to_return as day,
      SUM(COUNT(*)) OVER (ORDER BY days_to_return) as cumulative,
      MAX(t.t) as total_returns
    FROM return_delays
    CROSS JOIN total t
    GROUP BY days_to_return, t.t
    ORDER BY days_to_return
    """
    all_rows = list(client.query(q_all).result())
    curves["_all"] = {}
    for row in all_rows:
        curves["_all"][row.day] = row.cumulative / row.total_returns if row.total_returns > 0 else 1.0

    return curves


@st.cache_data(ttl=86400)
def get_channel_volumes() -> dict:
    """Get return volume per channel for weighting capture curves. Same recent window as curves."""
    client = _get_client()
    q = """
    SELECT o.sales_channel, COUNT(*) as returns
    FROM `mongo_db.returns` r
    JOIN `mongo_db.orders` o ON r.order_id = o.order_id
    WHERE r.status != 'CANCELLED'
      AND DATE(o.creation_date) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 240 DAY)
                                    AND DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY)
    GROUP BY 1
    """
    return {row.sales_channel: row.returns for row in client.query(q).result()}


@st.cache_data(ttl=86400)
def get_channel_benchmarks() -> dict:
    """
    Historical return rate benchmarks per channel.
    Returns {channel: {avg, p5, p95, min_weekly_sold}} from recent 90d mature data.
    Used for: forecast validation guardrails + historical rate fallback.
    """
    client = _get_client()
    q = """
    WITH weekly_rates AS (
      SELECT
        o.sales_channel,
        DATE_TRUNC(o.order_date, WEEK(MONDAY)) as week,
        SUM(o.sold) as sold,
        COALESCE(SUM(r.returned), 0) as returned
      FROM (
        SELECT order_date, sku_prefix, size, sales_channel, SUM(sold) as sold
        FROM `returns_analytics.daily_orders`
        WHERE order_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 240 DAY)
                              AND DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY)
        GROUP BY 1, 2, 3, 4
      ) o
      LEFT JOIN (
        SELECT order_date, sku_prefix, size, sales_channel, SUM(returned) as returned
        FROM `returns_analytics.daily_returns`
        WHERE order_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 240 DAY)
                              AND DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY)
        GROUP BY 1, 2, 3, 4
      ) r ON o.order_date = r.order_date AND o.sku_prefix = r.sku_prefix
         AND o.size = r.size AND o.sales_channel = r.sales_channel
      GROUP BY 1, 2
      HAVING sold >= 20
    )
    SELECT
      sales_channel,
      ROUND(AVG(returned / sold), 4) as avg_rate,
      ROUND(APPROX_QUANTILES(returned / sold, 100)[OFFSET(5)], 4) as p5,
      ROUND(APPROX_QUANTILES(returned / sold, 100)[OFFSET(95)], 4) as p95,
      MIN(sold) as min_weekly_sold
    FROM weekly_rates
    GROUP BY 1
    """
    return {
        row.sales_channel: {
            "avg": row.avg_rate,
            "p5": row.p5,
            "p95": row.p95,
            "min_weekly_sold": row.min_weekly_sold,
        }
        for row in client.query(q).result()
    }


def _lookup_curve(curve: dict, days_old: int) -> float:
    """Look up cumulative capture % from a curve dict."""
    if not curve:
        return 1.0
    matching = [d for d in curve.keys() if d <= days_old]
    return curve[max(matching)] if matching else 0.0


def get_capture_pct(curves: dict, channels: list, days_old: int) -> float:
    """
    Get the expected capture % for a given number of days since order.
    - 0 or all channels: use the pre-computed volume-weighted '_all' curve
    - 1 channel: use that channel's specific curve
    - 2+ channels: compute weighted average of those channels' curves by return volume
    """
    all_channels = [c for c in curves.keys() if c != "_all"]

    if not channels or set(channels) == set(all_channels):
        return _lookup_curve(curves.get("_all", {}), days_old)

    if len(channels) == 1 and channels[0] in curves:
        return _lookup_curve(curves[channels[0]], days_old)

    # Multiple specific channels: weighted average by return volume
    volumes = get_channel_volumes()
    total_vol = sum(volumes.get(ch, 0) for ch in channels)
    if total_vol == 0:
        return _lookup_curve(curves.get("_all", {}), days_old)

    weighted_pct = 0.0
    for ch in channels:
        vol = volumes.get(ch, 0)
        pct = _lookup_curve(curves.get(ch, {}), days_old)
        weighted_pct += pct * (vol / total_vol)

    return weighted_pct


# --- Action Tracking queries (per-SKU time series) ---

@st.cache_data(ttl=3600)
def get_tracking_daily_orders(sku_prefix: str, start_date: str, end_date: str) -> list:
    """Daily order counts per size for a single SKU. Replaces pipelines.get_daily_orders_for_sku()."""
    client = _get_client()
    q = """
    SELECT order_date as date, size, SUM(sold) as sold
    FROM `returns_analytics.daily_orders`
    WHERE sku_prefix = @sku AND order_date BETWEEN @start AND @end
    GROUP BY 1, 2
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sku", "STRING", sku_prefix),
        bigquery.ScalarQueryParameter("start", "DATE", start_date),
        bigquery.ScalarQueryParameter("end", "DATE", end_date),
    ])
    rows = client.query(q, job_config=job_config).result()
    return [{"date": str(r.date), "size": r.size, "sold": r.sold} for r in rows]


@st.cache_data(ttl=3600)
def get_tracking_daily_returns(sku_prefix: str, start_date: str, end_date: str) -> list:
    """Daily return counts per size for a single SKU, grouped by order date.
    Replaces pipelines.get_daily_returns_for_sku() — no $lookup needed."""
    client = _get_client()
    q = """
    SELECT order_date as date, size, SUM(returned) as returned
    FROM `returns_analytics.daily_returns`
    WHERE sku_prefix = @sku AND order_date BETWEEN @start AND @end
    GROUP BY 1, 2
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sku", "STRING", sku_prefix),
        bigquery.ScalarQueryParameter("start", "DATE", start_date),
        bigquery.ScalarQueryParameter("end", "DATE", end_date),
    ])
    rows = client.query(q, job_config=job_config).result()
    return [{"date": str(r.date), "size": r.size, "returned": r.returned} for r in rows]


@st.cache_data(ttl=3600)
def get_tracking_counts(sku_prefixes: tuple, start_date: str, end_date: str) -> dict:
    """Total sold and returned per SKU in a date range.
    Replaces pipelines.get_orders_count_for_skus() + get_returns_count_for_skus()."""
    if not sku_prefixes:
        return {}
    client = _get_client()
    q = """
    SELECT
      o.sku_prefix,
      SUM(o.sold) as sold,
      COALESCE(SUM(r.returned), 0) as returned
    FROM (
      SELECT sku_prefix, SUM(sold) as sold
      FROM `returns_analytics.daily_orders`
      WHERE sku_prefix IN UNNEST(@skus) AND order_date BETWEEN @start AND @end
      GROUP BY 1
    ) o
    LEFT JOIN (
      SELECT sku_prefix, SUM(returned) as returned
      FROM `returns_analytics.daily_returns`
      WHERE sku_prefix IN UNNEST(@skus) AND order_date BETWEEN @start AND @end
      GROUP BY 1
    ) r ON o.sku_prefix = r.sku_prefix
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("skus", "STRING", list(sku_prefixes)),
        bigquery.ScalarQueryParameter("start", "DATE", start_date),
        bigquery.ScalarQueryParameter("end", "DATE", end_date),
    ])
    return {r.sku_prefix: {"sold": r.sold, "returned": r.returned}
            for r in client.query(q, job_config=job_config).result()}


@st.cache_data(ttl=3600)
def query_returns_data(
    start_date: str,
    end_date: str,
    channels: tuple = (),
    suppliers: tuple = (),
    categories: tuple = (),
    subcategories: tuple = (),
    sku_prefixes: tuple = (),
) -> dict:
    """
    Main query: fetch aggregated data for the Company Returns page.
    Returns dict with daily_data, by_supplier, by_category, by_channel.
    """
    client = _get_client()

    # Build filter clauses
    filters = ["o.order_date BETWEEN @start_date AND @end_date"]
    params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]

    if channels:
        filters.append("o.sales_channel IN UNNEST(@channels)")
        params.append(bigquery.ArrayQueryParameter("channels", "STRING", list(channels)))

    if suppliers:
        filters.append("p.supplier_name IN UNNEST(@suppliers)")
        params.append(bigquery.ArrayQueryParameter("suppliers", "STRING", list(suppliers)))

    if categories:
        filters.append("p.category_l3 IN UNNEST(@categories)")
        params.append(bigquery.ArrayQueryParameter("categories", "STRING", list(categories)))

    if subcategories:
        filters.append("p.category_l4 IN UNNEST(@subcategories)")
        params.append(bigquery.ArrayQueryParameter("subcategories", "STRING", list(subcategories)))

    if sku_prefixes:
        sku_conditions = []
        for i, sku in enumerate(sku_prefixes):
            param_name = f"sku_{i}"
            sku_conditions.append(f"o.sku_prefix LIKE @{param_name}")
            params.append(bigquery.ScalarQueryParameter(param_name, "STRING", f"{sku}%"))
        filters.append(f"({' OR '.join(sku_conditions)})")

    where_clause = " AND ".join(filters)
    job_config = bigquery.QueryJobConfig(query_parameters=params)

    # Base CTE: filtered orders joined with products and returns
    base_cte = f"""
    WITH filtered_orders AS (
      SELECT
        o.order_date,
        o.sku_prefix,
        o.size,
        o.sales_channel,
        o.sold,
        o.gmv,
        p.supplier_name,
        p.category_l3,
        p.category_l4
      FROM `returns_analytics.daily_orders` o
      LEFT JOIN `returns_analytics.products` p ON LEFT(o.sku_prefix, 8) = p.family_sku
      WHERE {where_clause}
    ),
    filtered_returns AS (
      SELECT
        r.order_date,
        r.sku_prefix,
        r.size,
        r.sales_channel,
        r.returned,
        r.returned_amount
      FROM `returns_analytics.daily_returns` r
      LEFT JOIN `returns_analytics.products` rp ON LEFT(r.sku_prefix, 8) = rp.family_sku
      LEFT JOIN `returns_analytics.daily_orders` o ON r.order_date = o.order_date
        AND r.sku_prefix = o.sku_prefix AND r.size = o.size AND r.sales_channel = o.sales_channel
      WHERE {where_clause.replace('o.', 'r.').replace('p.', 'rp.')}
    )
    """

    # 1. Daily time series
    q_daily = base_cte + """
    SELECT
      fo.order_date,
      SUM(fo.sold) AS sold,
      SUM(fo.gmv) AS gmv,
      COALESCE(SUM(fr.returned), 0) AS returned,
      COALESCE(SUM(fr.returned_amount), 0) AS returned_amount
    FROM filtered_orders fo
    LEFT JOIN filtered_returns fr
      ON fo.order_date = fr.order_date AND fo.sku_prefix = fr.sku_prefix
      AND fo.size = fr.size AND fo.sales_channel = fr.sales_channel
    GROUP BY fo.order_date
    ORDER BY fo.order_date
    """
    df_daily = client.query(q_daily, job_config=job_config).to_dataframe()

    # 2. By supplier
    q_supplier = base_cte + """
    SELECT
      COALESCE(fo.supplier_name, 'Unknown') AS supplier,
      SUM(fo.sold) AS sold,
      SUM(fo.gmv) AS gmv,
      COALESCE(SUM(fr.returned), 0) AS returned,
      COALESCE(SUM(fr.returned_amount), 0) AS returned_amount
    FROM filtered_orders fo
    LEFT JOIN filtered_returns fr
      ON fo.order_date = fr.order_date AND fo.sku_prefix = fr.sku_prefix
      AND fo.size = fr.size AND fo.sales_channel = fr.sales_channel
    GROUP BY 1
    ORDER BY returned DESC
    """
    df_supplier = client.query(q_supplier, job_config=job_config).to_dataframe()

    # 3. By category
    q_category = base_cte + """
    SELECT
      COALESCE(fo.category_l3, 'Unknown') AS category,
      SUM(fo.sold) AS sold,
      SUM(fo.gmv) AS gmv,
      COALESCE(SUM(fr.returned), 0) AS returned,
      COALESCE(SUM(fr.returned_amount), 0) AS returned_amount
    FROM filtered_orders fo
    LEFT JOIN filtered_returns fr
      ON fo.order_date = fr.order_date AND fo.sku_prefix = fr.sku_prefix
      AND fo.size = fr.size AND fo.sales_channel = fr.sales_channel
    GROUP BY 1
    ORDER BY returned DESC
    """
    df_category = client.query(q_category, job_config=job_config).to_dataframe()

    # 4. By channel
    q_channel = base_cte + """
    SELECT
      fo.sales_channel AS channel,
      SUM(fo.sold) AS sold,
      SUM(fo.gmv) AS gmv,
      COALESCE(SUM(fr.returned), 0) AS returned,
      COALESCE(SUM(fr.returned_amount), 0) AS returned_amount
    FROM filtered_orders fo
    LEFT JOIN filtered_returns fr
      ON fo.order_date = fr.order_date AND fo.sku_prefix = fr.sku_prefix
      AND fo.size = fr.size AND fo.sales_channel = fr.sales_channel
    GROUP BY 1
    ORDER BY returned DESC
    """
    df_channel = client.query(q_channel, job_config=job_config).to_dataframe()

    return {
        "daily": df_daily,
        "by_supplier": df_supplier,
        "by_category": df_category,
        "by_channel": df_channel,
    }
