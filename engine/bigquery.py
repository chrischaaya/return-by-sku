"""
BigQuery connection and queries for the Company Returns page.
Reads from returns_analytics dataset (refreshed daily at 09:00).
"""

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

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

    suppliers = [r.supplier_name for r in client.query(
        "SELECT DISTINCT supplier_name FROM `returns_analytics.products` WHERE supplier_name IS NOT NULL ORDER BY supplier_name"
    ).result()]

    categories = [r.category_l2 for r in client.query(
        "SELECT DISTINCT category_l2 FROM `returns_analytics.products` WHERE category_l2 IS NOT NULL ORDER BY category_l2"
    ).result()]

    return {"channels": channels, "suppliers": suppliers, "categories": categories}


@st.cache_data(ttl=3600)
def query_returns_data(
    start_date: str,
    end_date: str,
    channels: tuple = (),
    suppliers: tuple = (),
    categories: tuple = (),
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
        filters.append("p.category_l2 IN UNNEST(@categories)")
        params.append(bigquery.ArrayQueryParameter("categories", "STRING", list(categories)))

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
        p.category_l2
      FROM `returns_analytics.daily_orders` o
      LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix
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
      LEFT JOIN `returns_analytics.products` rp ON r.sku_prefix = rp.sku_prefix
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
      COALESCE(fo.category_l2, 'Unknown') AS category,
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
