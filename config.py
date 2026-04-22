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

# What gets flagged
BASELINE_PERCENTILE = _s["baseline_percentile"]
MIN_RECENT_SALES_PER_SIZE = _s["min_recent_sales_per_size"]
RISING_STAR_MIN_SALES_PER_SIZE = _s["new_product_min_sales_per_size"]
RISING_STAR_MAX_AGE_DAYS = _s["new_product_max_age_days"]
MIN_SIZE_VOLUME = _s.get("min_reasons_bestsellers", 20)
MIN_SIZE_VOLUME_RISING = _s.get("min_reasons_new_products", 10)

# Flagging trigger
TRIGGER_MULTIPLIER = _s.get("trigger_multiplier", 1.3)

# Confidence thresholds
HIGH_CONFIDENCE_RATIO = _s.get("high_confidence_ratio", 3.0)
MID_CONFIDENCE_RATIO = _s.get("mid_confidence_ratio", 2.0)
QUALITY_HIGH_THRESHOLD = _s.get("quality_high_threshold", 0.40)
QUALITY_MID_THRESHOLD = _s.get("quality_mid_threshold", 0.25)

# Relabel conditions
RELABEL_MIN_STOCK = _s.get("relabel_min_stock", 50)
RELABEL_MIN_RETURN_RATE = _s.get("relabel_min_return_rate", 0.60)
RELABEL_MIN_SALES = _s.get("relabel_min_sales", 100)

# Data filters
FAST_DELIVERY_LAG_DAYS = _s["fast_delivery_lag_days"]
SLOW_DELIVERY_LAG_DAYS = _s["slow_delivery_lag_days"]
EXCLUDED_CHANNELS = _s["excluded_channels"]


def reload_settings():
    """Reload settings from MongoDB and update module-level variables."""
    global BASELINE_PERCENTILE, MIN_RECENT_SALES_PER_SIZE, RISING_STAR_MIN_SALES_PER_SIZE, TRIGGER_MULTIPLIER
    global RISING_STAR_MAX_AGE_DAYS, FAST_DELIVERY_LAG_DAYS, SLOW_DELIVERY_LAG_DAYS
    global MIN_SIZE_VOLUME, MIN_SIZE_VOLUME_RISING, EXCLUDED_CHANNELS
    global HIGH_CONFIDENCE_RATIO, MID_CONFIDENCE_RATIO
    global QUALITY_HIGH_THRESHOLD, QUALITY_MID_THRESHOLD
    global RELABEL_MIN_STOCK, RELABEL_MIN_RETURN_RATE, RELABEL_MIN_SALES
    s = _load()
    BASELINE_PERCENTILE = s["baseline_percentile"]
    MIN_RECENT_SALES_PER_SIZE = s["min_recent_sales_per_size"]
    RISING_STAR_MIN_SALES_PER_SIZE = s["new_product_min_sales_per_size"]
    RISING_STAR_MAX_AGE_DAYS = s["new_product_max_age_days"]
    MIN_SIZE_VOLUME = s.get("min_reasons_bestsellers", 20)
    MIN_SIZE_VOLUME_RISING = s.get("min_reasons_new_products", 10)
    TRIGGER_MULTIPLIER = s.get("trigger_multiplier", 1.3)
    HIGH_CONFIDENCE_RATIO = s.get("high_confidence_ratio", 3.0)
    MID_CONFIDENCE_RATIO = s.get("mid_confidence_ratio", 2.0)
    QUALITY_HIGH_THRESHOLD = s.get("quality_high_threshold", 0.40)
    QUALITY_MID_THRESHOLD = s.get("quality_mid_threshold", 0.25)
    RELABEL_MIN_STOCK = s.get("relabel_min_stock", 50)
    RELABEL_MIN_RETURN_RATE = s.get("relabel_min_return_rate", 0.60)
    RELABEL_MIN_SALES = s.get("relabel_min_sales", 100)
    FAST_DELIVERY_LAG_DAYS = s["fast_delivery_lag_days"]
    SLOW_DELIVERY_LAG_DAYS = s["slow_delivery_lag_days"]
    EXCLUDED_CHANNELS = s["excluded_channels"]
