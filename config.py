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
from engine.settings import load_settings as _load

_s = _load()

FILTER_THRESHOLD = _s.get("filter_threshold", 0.0)
PROBLEMATIC_THRESHOLD = _s.get("problematic_threshold", 1.3)
MIN_RECENT_SALES_PER_SIZE = _s.get("min_recent_sales_per_size", 10)
RISING_STAR_MIN_SALES_PER_SIZE = _s.get("new_product_min_sales_per_size", 5)
RISING_STAR_MAX_AGE_DAYS = _s.get("new_product_max_age_days", 45)
FAST_DELIVERY_LAG_DAYS = _s.get("fast_delivery_lag_days", 7)
SLOW_DELIVERY_LAG_DAYS = _s.get("slow_delivery_lag_days", 14)
EXCLUDED_CHANNELS = _s.get("excluded_channels", ["aboutYou", "vogaCloset"])


def reload_settings():
    """Reload settings from MongoDB and update module-level variables."""
    global FILTER_THRESHOLD, PROBLEMATIC_THRESHOLD, MIN_RECENT_SALES_PER_SIZE
    global RISING_STAR_MIN_SALES_PER_SIZE, RISING_STAR_MAX_AGE_DAYS
    global FAST_DELIVERY_LAG_DAYS, SLOW_DELIVERY_LAG_DAYS, EXCLUDED_CHANNELS
    s = _load()
    FILTER_THRESHOLD = s.get("filter_threshold", 0.0)
    PROBLEMATIC_THRESHOLD = s.get("problematic_threshold", 1.3)
    MIN_RECENT_SALES_PER_SIZE = s["min_recent_sales_per_size"]
    RISING_STAR_MIN_SALES_PER_SIZE = s.get("new_product_min_sales_per_size", 5)
    RISING_STAR_MAX_AGE_DAYS = s.get("new_product_max_age_days", 45)
    FAST_DELIVERY_LAG_DAYS = s["fast_delivery_lag_days"]
    SLOW_DELIVERY_LAG_DAYS = s["slow_delivery_lag_days"]
    EXCLUDED_CHANNELS = s["excluded_channels"]
