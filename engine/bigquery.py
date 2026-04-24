"""
BigQuery connection and queries for the Company Returns page.
Reads from returns_analytics dataset (refreshed daily at 09:00).
"""

from datetime import date, timedelta

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
    Returns dict with daily_data, by_supplier, by_category, by_channel, kpis.
    """
    client = _get_client()

    # Build WHERE clauses from filters
    where_orders = ["o.order_date BETWEEN @start_date AND @end_date"]
    where_returns = ["r.order_date BETWEEN @start_date AND @end_date"]
    params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]

    if channels:
        where_orders.append("o.sales_channel IN UNNEST(@channels)")
        where_returns.append("r.sales_channel IN UNNEST(@channels)")
        params.append(bigquery.ArrayQueryParameter("channels", "STRING", list(channels)))

    if suppliers:
        where_orders.append("p.supplier_name IN UNNEST(@suppliers)")
        where_returns.append("rp.supplier_name IN UNNEST(@suppliers)")
        params.append(bigquery.ArrayQueryParameter("suppliers", "STRING", list(suppliers)))

    if categories:
        where_orders.append("p.category_l2 IN UNNEST(@categories)")
        where_returns.append("rp.category_l2 IN UNNEST(@categories)")
        params.append(bigquery.ArrayQueryParameter("categories", "STRING", list(categories)))

    if sku_prefixes:
        sku_clauses_o = " OR ".join(["o.sku_prefix LIKE @sku_" + str(i) for i in range(len(sku_prefixes))])
        sku_clauses_r = " OR ".join(["r.sku_prefix LIKE @sku_" + str(i) for i in range(len(sku_prefixes))])
        where_orders.append(f"({sku_clauses_o})")
        where_returns.append(f"({sku_clauses_r})")
        for i, sku in enumerate(sku_prefixes):
            params.append(bigquery.ScalarQueryParameter(f"sku_{i}", "STRING", f"{sku}%"))

    where_o = " AND ".join(where_orders)
    where_r = " AND ".join(where_returns)

    # Join condition for product dimension
    product_join_o = "LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix" if (suppliers or categories) else ""
    product_join_r = "LEFT JOIN `returns_analytics.products` rp ON r.sku_prefix = rp.sku_prefix" if (suppliers or categories) else ""

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    # 1. Daily time series
    q_daily = f"""
    SELECT
      o.order_date,
      SUM(o.sold) AS sold,
      SUM(o.gmv) AS gmv,
      COALESCE(SUM(r.returned), 0) AS returned,
      COALESCE(SUM(r.returned_amount), 0) AS returned_amount
    FROM (
      SELECT order_date, sku_prefix, size, sales_channel, SUM(sold) AS sold, SUM(gmv) AS gmv
      FROM `returns_analytics.daily_orders` o
      {product_join_o}
      WHERE {where_o}
      GROUP BY 1, 2, 3, 4
    ) o
    LEFT JOIN (
      SELECT order_date, sku_prefix, size, sales_channel, SUM(returned) AS returned, SUM(returned_amount) AS returned_amount
      FROM `returns_analytics.daily_returns` r
      {product_join_r}
      WHERE {where_r}
      GROUP BY 1, 2, 3, 4
    ) r ON o.order_date = r.order_date AND o.sku_prefix = r.sku_prefix AND o.size = r.size AND o.sales_channel = r.sales_channel
    GROUP BY o.order_date
    ORDER BY o.order_date
    """
    df_daily = client.query(q_daily, job_config=job_config).to_dataframe()

    # 2. By supplier
    q_supplier = f"""
    SELECT
      COALESCE(p.supplier_name, 'Unknown') AS supplier,
      SUM(o.sold) AS sold,
      SUM(o.gmv) AS gmv,
      COALESCE(SUM(r.returned), 0) AS returned,
      COALESCE(SUM(r.returned_amount), 0) AS returned_amount
    FROM (
      SELECT sku_prefix, SUM(sold) AS sold, SUM(gmv) AS gmv
      FROM `returns_analytics.daily_orders` o
      {"LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix" if (suppliers or categories) else ""}
      WHERE {where_o}
      GROUP BY 1
    ) o
    LEFT JOIN (
      SELECT sku_prefix, SUM(returned) AS returned, SUM(returned_amount) AS returned_amount
      FROM `returns_analytics.daily_returns` r
      {"LEFT JOIN `returns_analytics.products` rp ON r.sku_prefix = rp.sku_prefix" if (suppliers or categories) else ""}
      WHERE {where_r}
      GROUP BY 1
    ) r ON o.sku_prefix = r.sku_prefix
    LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix
    GROUP BY 1
    ORDER BY returned DESC
    """
    df_supplier = client.query(q_supplier, job_config=job_config).to_dataframe()

    # 3. By category
    q_category = f"""
    SELECT
      COALESCE(p.category_l2, 'Unknown') AS category,
      SUM(o.sold) AS sold,
      SUM(o.gmv) AS gmv,
      COALESCE(SUM(r.returned), 0) AS returned,
      COALESCE(SUM(r.returned_amount), 0) AS returned_amount
    FROM (
      SELECT sku_prefix, SUM(sold) AS sold, SUM(gmv) AS gmv
      FROM `returns_analytics.daily_orders` o
      {"LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix" if (suppliers or categories) else ""}
      WHERE {where_o}
      GROUP BY 1
    ) o
    LEFT JOIN (
      SELECT sku_prefix, SUM(returned) AS returned, SUM(returned_amount) AS returned_amount
      FROM `returns_analytics.daily_returns` r
      {"LEFT JOIN `returns_analytics.products` rp ON r.sku_prefix = rp.sku_prefix" if (suppliers or categories) else ""}
      WHERE {where_r}
      GROUP BY 1
    ) r ON o.sku_prefix = r.sku_prefix
    LEFT JOIN `returns_analytics.products` p ON o.sku_prefix = p.sku_prefix
    GROUP BY 1
    ORDER BY returned DESC
    """
    df_category = client.query(q_category, job_config=job_config).to_dataframe()

    # 4. By channel
    q_channel = f"""
    SELECT
      o.sales_channel AS channel,
      SUM(o.sold) AS sold,
      SUM(o.gmv) AS gmv,
      COALESCE(SUM(r.returned), 0) AS returned,
      COALESCE(SUM(r.returned_amount), 0) AS returned_amount
    FROM (
      SELECT order_date, sku_prefix, size, sales_channel, SUM(sold) AS sold, SUM(gmv) AS gmv
      FROM `returns_analytics.daily_orders` o
      {product_join_o}
      WHERE {where_o}
      GROUP BY 1, 2, 3, 4
    ) o
    LEFT JOIN (
      SELECT order_date, sku_prefix, size, sales_channel, SUM(returned) AS returned, SUM(returned_amount) AS returned_amount
      FROM `returns_analytics.daily_returns` r
      {product_join_r}
      WHERE {where_r}
      GROUP BY 1, 2, 3, 4
    ) r ON o.order_date = r.order_date AND o.sku_prefix = r.sku_prefix AND o.size = r.size AND o.sales_channel = r.sales_channel
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
