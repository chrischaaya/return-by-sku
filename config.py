"""
Central configuration for the Return Rate Dashboard.
All thresholds, connection details, and business rules in one place.
"""

# --- MongoDB Connection ---
import streamlit as st

MONGO_URI = st.secrets["MONGO_URI"]
MONGO_DB = "hiccup-app"

# --- Collections ---
COLL_RETURNS = "CustomerReturns"
COLL_ORDERS = "Orders"
COLL_PRODUCTS = "Products"
COLL_RETURN_REASONS = "ReturnReasons"
COLL_CATEGORIES = "Categories"
COLL_SALES_CHANNELS = "SalesChannels"

# --- Data Filters ---
# Only include items with these statuses from CustomerReturns.items
VALID_RETURN_ITEM_STATUSES = ["ACCEPTED", "PENDING", "REJECTED"]

# Only analyze products owned by Lykia (merchantKey = "hiccup")
MERCHANT_KEY = "hiccup"

# Channels to exclude from all analysis
EXCLUDED_CHANNELS = ["aboutYou", "vogaCloset"]

# Order statuses that count as "sold"
VALID_ORDER_STATUSES = ["DISPATCHED", "DELIVERED", "PROCESSING"]

# Days of recent orders to exclude (delivery lag — customers can't return yet)
# Trendyol and Hepsiburada deliver faster
FAST_DELIVERY_CHANNELS = ["trendyol", "hepsiburada"]
FAST_DELIVERY_LAG_DAYS = 7
SLOW_DELIVERY_LAG_DAYS = 14

# Rising stars: SKUs first seen in orders within this many days
RISING_STAR_MAX_AGE_DAYS = 45

# --- Time Window ---
DEFAULT_LOOKBACK_DAYS = 90

# --- Volume Thresholds ---
# Minimum units sold per size for size-level flagging
MIN_SIZE_VOLUME = 20

# Top N SKUs by recent sales for recovering/trend analysis
TOP_SKU_FOR_TRENDS = 300

# --- Anomaly Detection ---
# Category baseline percentile — SKUs above this are flagged
# P75 = only the worst 25% in each category
BASELINE_PERCENTILE = 0.75

# Size concentration index: if the worst size's return rate is this many times
# the SKU average, it's a sizing problem
SIZE_CONCENTRATION_THRESHOLD = 1.5

# If a single return reason accounts for more than this share, it's actionable
REASON_CONCENTRATION_THRESHOLD = 0.40

# --- Dashboard ---
# Min sales per size in last 30 days for a SKU to qualify
MIN_RECENT_SALES_PER_SIZE = 10

# For trend/evolution: compare current period vs this many days prior
TREND_COMPARISON_DAYS = 30

# --- Channels with Return Reason Data ---
# Full: reliable reason codes on most returns
# Partial: some returns have reasons, many don't
# None: no usable reason data
CHANNELS_WITH_FULL_REASONS = [
    "trendyol", "fashiondays", "fashiondaysBG",
    "hepsiburada", "emag", "trendyolRO",
]
CHANNELS_WITH_PARTIAL_REASONS = ["hiccup"]
CHANNELS_WITHOUT_REASONS = [
    "namshi", "debenhams", "tiktokShop",
    "amazonUS", "amazonUK", "allegro",
    "emagBG", "emagHU",
]

# --- Return Reason Codes (from ReturnReasons collection) ---
SIZING_REASONS = ["TOO_LARGE", "TOO_SMALL"]
QUALITY_REASONS = ["DEFECTIVE_PRODUCT", "EXPECTATION_MISMATCH"]
LISTING_REASONS = []  # folded into QUALITY
LOGISTICS_REASONS = ["NOT_DELIVERED", "DELIVERY_ISSUE", "WRONG_PRODUCT"]
NEUTRAL_REASONS = ["NO_LONGER_WANTED", "SURPLUS_PRODUCT", "OTHER"]
