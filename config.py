"""
Central configuration for the Return Rate Dashboard.
Static values that don't change + dynamic settings loaded from MongoDB.
"""

import streamlit as st

# --- MongoDB Connection ---
MONGO_URI = st.secrets["MONGO_URI"]
MONGO_DB = "hiccup-app"

# --- Collections ---
COLL_RETURNS = "CustomerReturns"
COLL_ORDERS = "Orders"
COLL_PRODUCTS = "Products"
COLL_RETURN_REASONS = "ReturnReasons"
COLL_CATEGORIES = "Categories"
COLL_SALES_CHANNELS = "SalesChannels"

# --- Static values (never change) ---
VALID_RETURN_ITEM_STATUSES = ["ACCEPTED", "PENDING", "REJECTED"]
MERCHANT_KEY = "hiccup"
VALID_ORDER_STATUSES = ["DISPATCHED", "DELIVERED", "PROCESSING"]
FAST_DELIVERY_CHANNELS = ["trendyol", "hepsiburada"]

SIZING_REASONS = ["TOO_LARGE", "TOO_SMALL"]
QUALITY_REASONS = ["DEFECTIVE_PRODUCT", "EXPECTATION_MISMATCH"]
LOGISTICS_REASONS = ["NOT_DELIVERED", "DELIVERY_ISSUE", "WRONG_PRODUCT"]
NEUTRAL_REASONS = ["NO_LONGER_WANTED", "SURPLUS_PRODUCT", "OTHER"]

# --- Dynamic settings (loaded from MongoDB, editable in UI) ---
# These are defaults — overridden by engine.settings.load_settings()
from engine.settings import load_settings as _load

_s = _load()
BASELINE_PERCENTILE = _s["baseline_percentile"]
MIN_RECENT_SALES_PER_SIZE = _s["min_recent_sales_per_size"]
RISING_STAR_MIN_SALES_PER_SIZE = _s["rising_star_min_sales_per_size"]
RISING_STAR_MAX_AGE_DAYS = _s["rising_star_max_age_days"]
FAST_DELIVERY_LAG_DAYS = _s["fast_delivery_lag_days"]
SLOW_DELIVERY_LAG_DAYS = _s["slow_delivery_lag_days"]
MIN_SIZE_VOLUME = _s["min_size_volume"]
EXCLUDED_CHANNELS = _s["excluded_channels"]


def reload_settings():
    """Reload settings from MongoDB and update module-level variables."""
    global BASELINE_PERCENTILE, MIN_RECENT_SALES_PER_SIZE, RISING_STAR_MIN_SALES_PER_SIZE
    global RISING_STAR_MAX_AGE_DAYS, FAST_DELIVERY_LAG_DAYS, SLOW_DELIVERY_LAG_DAYS
    global MIN_SIZE_VOLUME, EXCLUDED_CHANNELS
    s = _load()
    BASELINE_PERCENTILE = s["baseline_percentile"]
    MIN_RECENT_SALES_PER_SIZE = s["min_recent_sales_per_size"]
    RISING_STAR_MIN_SALES_PER_SIZE = s["rising_star_min_sales_per_size"]
    RISING_STAR_MAX_AGE_DAYS = s["rising_star_max_age_days"]
    FAST_DELIVERY_LAG_DAYS = s["fast_delivery_lag_days"]
    SLOW_DELIVERY_LAG_DAYS = s["slow_delivery_lag_days"]
    MIN_SIZE_VOLUME = s["min_size_volume"]
    EXCLUDED_CHANNELS = s["excluded_channels"]
